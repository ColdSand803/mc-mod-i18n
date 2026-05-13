#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import process from 'node:process';

const baseUrl = process.argv[2] || 'http://127.0.0.1:8765';
const errors = [];

function fail(message) {
  throw new Error(message);
}

function recordBrowserError(prefix, value) {
  const text = String(value || '').trim();
  if (text) {
    errors.push(`${prefix}: ${text}`);
  }
}

async function expectVisible(page, selector, label) {
  const locator = page.locator(selector).first();
  await locator.waitFor({ state: 'visible', timeout: 5000 });
  return locator;
}

async function openMenu(page, triggerSelector, menuSelector, label) {
  const trigger = await expectVisible(page, triggerSelector, label);
  await trigger.click();
  await page.waitForFunction(
    ([triggerSelector, menuSelector]) => {
      const trigger = document.querySelector(triggerSelector);
      const menu = document.querySelector(menuSelector);
      return Boolean(
        trigger
          && menu
          && trigger.getAttribute('aria-expanded') === 'true'
          && !menu.hidden
      );
    },
    [triggerSelector, menuSelector],
    { timeout: 5000 },
  );
  await page.keyboard.press('Escape');
}

async function switchUiLanguage(page) {
  await openMenu(page, '[data-select-trigger="ui_locale"]', '#ui-locale-menu', '界面语言下拉框');
  const englishOption = page.locator('#ui-locale-menu [data-value="en_us"], #ui-locale-menu [data-ui-locale-value="en_us"]').first();
  if (await englishOption.count()) {
    await englishOption.click();
  } else {
    await page.selectOption('#ui_locale', 'en_us');
    await page.locator('#ui_locale').dispatchEvent('change');
  }
  await page.waitForFunction(() => document.querySelector('#ui_locale')?.value === 'en_us', null, { timeout: 5000 });
}

async function exposeModelSettings(page) {
  await page.selectOption('#provider', 'openai-compatible');
  await page.locator('#provider').dispatchEvent('change');
  await page.locator('[data-advanced-panel]').first().evaluate((details) => {
    details.open = true;
    details.querySelector('#api-box')?.removeAttribute('hidden');
  });
}

async function assertSettingsPage(page) {
  await expectVisible(page, '#settings-open', '设置入口');
  await page.locator('#settings-open').click();
  await page.locator('#settings-page').waitFor({ state: 'visible', timeout: 5000 });
  await expectVisible(page, '#settings-cache-clear', '清空缓存按钮');
  await expectVisible(page, '#settings-ui-locale-download', '语言包下载按钮');
  await assertNoSettingsOverlapPlaywright(page);
  await page.locator('[data-view="language"]').first().click();
  await exposeModelSettings(page);
  await expectVisible(page, '#provider-test', 'API 测试连接按钮');
}

async function assertNoSettingsOverlapPlaywright(page) {
  const result = await page.locator('#settings-page').evaluate((settingsPage) => {
    document.documentElement.style.zoom = '67%';
    const rects = Array.from(settingsPage.querySelectorAll('.settings-section')).map((node) => {
      const rect = node.getBoundingClientRect();
      return {
        id: node.id,
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
      };
    });
    const overlaps = findOverlaps(rects);
    document.documentElement.style.zoom = '';
    return { overlaps };

    function findOverlaps(items) {
      const hits = [];
      for (let i = 0; i < items.length; i += 1) {
        for (let j = i + 1; j < items.length; j += 1) {
          const a = items[i];
          const b = items[j];
          const separated = a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top;
          if (!separated) {
            hits.push([a.id, b.id]);
          }
        }
      }
      return hits;
    }
  });
  if (result.overlaps.length) {
    fail(`Settings cards overlap: ${JSON.stringify(result.overlaps)}`);
  }
}

async function launchPlaywrightSmoke(chromium) {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    page.on('pageerror', (error) => recordBrowserError('pageerror', error.stack || error.message));
    page.on('console', (message) => {
      if (message.type() === 'error') {
        recordBrowserError('console', message.text());
      }
    });

    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    await expectVisible(page, '[data-select-trigger="source_locale"]', '源语言下拉框');

    await openMenu(page, '[data-select-trigger="source_locale"]', '#source-locale-menu', '源语言下拉框');
    await openMenu(page, '[data-select-trigger="target_locale"]', '#target-locale-menu', '目标语言下拉框');
    await exposeModelSettings(page);
    await openMenu(page, '[data-model-trigger]', '#model-menu', '模型下拉框');
    await openMenu(page, '#theme-toggle', '#theme-menu', '主题下拉框');
    await switchUiLanguage(page);
    await assertSettingsPage(page);
  } finally {
    await browser.close();
  }
}

function findSystemBrowserExecutable() {
  const envPath = process.env.MC_MOD_I18N_BROWSER;
  const candidates = [
    envPath,
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ].filter(Boolean);
  return candidates.find((path) => existsSync(path)) || '';
}

async function launchSystemBrowserSmoke() {
  const executable = findSystemBrowserExecutable();
  if (!executable) {
    fail('Playwright is not installed and no system Chrome/Edge executable was found. Set MC_MOD_I18N_BROWSER to a browser executable.');
  }

  const userDataDir = mkdtempSync(join(tmpdir(), 'mc-mod-i18n-browser-'));
  const chrome = spawn(executable, [
    '--headless=new',
    '--disable-gpu',
    '--disable-software-rasterizer',
    '--disable-dev-shm-usage',
    '--disable-gpu-compositing',
    '--no-first-run',
    '--no-default-browser-check',
    '--remote-allow-origins=*',
    '--remote-debugging-port=0',
    `--user-data-dir=${userDataDir}`,
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'ignore'] });

  try {
    const debugInfo = await waitForDebugInfo(userDataDir, chrome);
    const browserClient = new CdpClient(debugInfo.browserUrl);
    await browserClient.connect();
    try {
      await browserClient.send('Browser.getVersion');
      const targetId = await waitForPageTarget(browserClient);
      const attached = await browserClient.send('Target.attachToTarget', { targetId, flatten: true });
      const sessionId = attached.sessionId;
      try {
        await evalExpression(browserClient, `window.location.href = ${JSON.stringify(baseUrl)}; true;`, sessionId);
        await waitForReadyState(browserClient, sessionId);
        await runSystemBrowserAssertions(browserClient, sessionId);
      } finally {
        if (sessionId) {
          try {
            await browserClient.send('Target.detachFromTarget', { sessionId });
          } catch {}
        }
      }
    } finally {
      browserClient.close();
    }
  } finally {
    chrome.kill();
    await waitForProcessExit(chrome, 5000);
    await removeDirWithRetry(userDataDir, 12, 250);
  }
}

async function waitForDebugInfo(userDataDir, chrome) {
  const path = join(userDataDir, 'DevToolsActivePort');
  const started = Date.now();
  while (Date.now() - started < 10000) {
    if (chrome.exitCode !== null) {
      fail(`System browser exited before DevTools became available: ${chrome.exitCode}`);
    }
    if (existsSync(path)) {
      const [port, wsPath] = readFileSync(path, 'utf-8').trim().split(/\r?\n/);
      if (port && wsPath) {
        return {
          port,
          browserUrl: `ws://127.0.0.1:${port}${wsPath}`,
        };
      }
    }
    await sleep(100);
  }
  fail('Timed out waiting for system browser DevTools endpoint.');
}

async function waitForPageTarget(client) {
  const started = Date.now();
  let lastError = null;
  while (Date.now() - started < 10000) {
    try {
      const payload = await client.send('Target.getTargets');
      const target = (payload.targetInfos || []).find((item) => item.type === 'page' && item.targetId);
      if (target?.targetId) {
        return target.targetId;
      }
      lastError = new Error('No debuggable browser page target was available.');
    } catch (error) {
      lastError = error;
    }
    await sleep(200);
  }
  throw lastError || new Error('Timed out waiting for a browser debug page target.');
}

async function waitForReadyState(client, sessionId = undefined) {
  const started = Date.now();
  while (Date.now() - started < 10000) {
    const state = await evalExpression(client, 'document.readyState', sessionId);
    if (state === 'interactive' || state === 'complete') {
      return;
    }
    await sleep(100);
  }
  fail('Timed out waiting for page readiness.');
}

async function runSystemBrowserAssertions(client, sessionId = undefined) {
  await expectSelector(client, '[data-select-trigger="source_locale"]', '源语言下拉框', sessionId);
  await clickSelector(client, '[data-select-trigger="source_locale"]', sessionId);
  await expectExpression(client, "document.querySelector('[data-select-trigger=\"source_locale\"]')?.getAttribute('aria-expanded') === 'true'", undefined, sessionId);
  await keypress(client, 'Escape', sessionId);
  await clickSelector(client, '[data-select-trigger="target_locale"]', sessionId);
  await expectExpression(client, "document.querySelector('[data-select-trigger=\"target_locale\"]')?.getAttribute('aria-expanded') === 'true'", undefined, sessionId);
  await keypress(client, 'Escape', sessionId);
  await evalExpression(client, "document.querySelector('#provider').value = 'openai-compatible'; document.querySelector('#provider').dispatchEvent(new Event('change', { bubbles: true }));", sessionId);
  await clickSelector(client, '[data-model-trigger]', sessionId);
  await expectExpression(client, "document.querySelector('[data-model-trigger]')?.getAttribute('aria-expanded') === 'true'", undefined, sessionId);
  await keypress(client, 'Escape', sessionId);
  await clickSelector(client, '#theme-toggle', sessionId);
  await expectExpression(client, "document.querySelector('#theme-toggle')?.getAttribute('aria-expanded') === 'true'", undefined, sessionId);
  await keypress(client, 'Escape', sessionId);
  await clickSelector(client, '#settings-open', sessionId);
  await expectSelector(client, '#settings-page:not([hidden])', '设置页面', sessionId);
  await expectSelector(client, '#settings-cache-clear', '清空缓存按钮', sessionId);
  await expectSelector(client, '#settings-ui-locale-download', '语言包下载按钮', sessionId);

  const overlap = await evalExpression(client, `(() => {
    document.documentElement.style.zoom = '67%';
    const rects = Array.from(document.querySelectorAll('#settings-page .settings-section')).map((node) => {
      const rect = node.getBoundingClientRect();
      return { id: node.id, left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom };
    });
    const overlaps = [];
    for (let i = 0; i < rects.length; i += 1) {
      for (let j = i + 1; j < rects.length; j += 1) {
        const a = rects[i];
        const b = rects[j];
        const separated = a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top;
        if (!separated) overlaps.push([a.id, b.id]);
      }
    }
    document.documentElement.style.zoom = '';
    return overlaps;
  })()`, sessionId);
  if (overlap.length) {
    fail(`Settings cards overlap: ${JSON.stringify(overlap)}`);
  }
}

async function expectSelector(client, selector, label, sessionId = undefined) {
  await expectExpression(client, `Boolean(document.querySelector(${JSON.stringify(selector)}))`, `${label} not found`, sessionId);
}

async function clickSelector(client, selector, sessionId = undefined) {
  await expectSelector(client, selector, selector, sessionId);
  await evalExpression(client, `document.querySelector(${JSON.stringify(selector)}).click()`, sessionId);
}

async function keypress(client, key, sessionId = undefined) {
  await evalExpression(
    client,
    `(() => {
      const down = new KeyboardEvent('keydown', { key: ${JSON.stringify(key)}, bubbles: true });
      const up = new KeyboardEvent('keyup', { key: ${JSON.stringify(key)}, bubbles: true });
      document.dispatchEvent(down);
      document.dispatchEvent(up);
      return true;
    })()`,
    sessionId,
  );
}

async function expectExpression(client, expression, message = `Expression failed: ${expression}`, sessionId = undefined) {
  const started = Date.now();
  while (Date.now() - started < 5000) {
    if (await evalExpression(client, expression, sessionId)) {
      return;
    }
    await sleep(100);
  }
  fail(message);
}

async function evalExpression(client, expression, sessionId = undefined) {
  const response = await client.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  }, sessionId);
  if (response.exceptionDetails) {
    fail(response.exceptionDetails.text || 'Browser evaluation failed');
  }
  return response.result?.value;
}

class CdpClient {
  constructor(url) {
    this.url = url;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    this.socket = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true });
      this.socket.addEventListener('error', () => reject(new Error(`Could not connect to browser DevTools at ${this.url}`)), { once: true });
    });
    this.socket.addEventListener('message', async (event) => {
      const text = await readWebSocketMessage(event.data);
      const payload = JSON.parse(text);
      if (!payload.id) {
        return;
      }
      const pending = this.pending.get(payload.id);
      if (!pending) {
        return;
      }
      this.pending.delete(payload.id);
      if (payload.error) {
        pending.reject(new Error(payload.error.message || JSON.stringify(payload.error)));
      } else {
        pending.resolve(payload.result || {});
      }
    });
  }

  send(method, params = {}, sessionId = undefined) {
    const id = this.nextId;
    this.nextId += 1;
    const payload = { id, method, params };
    if (sessionId) {
      payload.sessionId = sessionId;
    }
    this.socket.send(JSON.stringify(payload));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP command timed out: ${method}`));
        }
      }, 10000);
    });
  }

  close() {
    if (this.socket) {
      this.socket.close();
    }
  }
}

async function readWebSocketMessage(data) {
  if (typeof data === 'string') {
    return data;
  }
  if (data instanceof ArrayBuffer) {
    return Buffer.from(data).toString('utf-8');
  }
  if (ArrayBuffer.isView(data)) {
    return Buffer.from(data.buffer, data.byteOffset, data.byteLength).toString('utf-8');
  }
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    return Buffer.from(await data.arrayBuffer()).toString('utf-8');
  }
  return Buffer.from(await data.arrayBuffer()).toString('utf-8');
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForProcessExit(child, timeoutMs) {
  if (child.exitCode !== null) {
    return;
  }
  await new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs);
    child.once('exit', () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

async function removeDirWithRetry(path, attempts = 8, delayMs = 200) {
  let lastError = null;
  for (let index = 0; index < attempts; index += 1) {
    try {
      rmSync(path, { recursive: true, force: true });
      return;
    } catch (error) {
      lastError = error;
      await sleep(delayMs);
    }
  }
  if (lastError) {
    throw lastError;
  }
}

let usedPlaywright = false;
try {
  const { chromium } = await import('playwright');
  await launchPlaywrightSmoke(chromium);
  usedPlaywright = true;
} catch (error) {
  if (error?.code !== 'ERR_MODULE_NOT_FOUND' && !String(error?.message || '').includes('Cannot find package')) {
    throw error;
  }
  await launchSystemBrowserSmoke();
}

if (errors.length) {
  fail(`Browser errors were reported:\n${errors.join('\n')}`);
}

console.log(`UI smoke test passed (${usedPlaywright ? 'Playwright' : 'system browser'}): ${baseUrl}`);
