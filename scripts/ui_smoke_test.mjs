#!/usr/bin/env node
import process from 'node:process';

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch (error) {
  console.error('Playwright is required. Install it with: npm install --save-dev playwright');
  process.exit(1);
}

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
  await page.locator('[data-view="language"]').first().click();
  await exposeModelSettings(page);
  await expectVisible(page, '#provider-test', 'API 测试连接按钮');
}

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

  if (errors.length) {
    fail(`Browser errors were reported:\n${errors.join('\n')}`);
  }

  console.log(`UI smoke test passed: ${baseUrl}`);
} finally {
  await browser.close();
}
