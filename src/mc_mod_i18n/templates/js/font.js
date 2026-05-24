/* Font picker module (Sprint H?).
   Self-contained. Loads catalog from /api/fonts, persists selection
   in localStorage, dynamically injects @font-face, applies --font-sans
   and --font-mono custom properties to documentElement.
   Loaded AFTER ghost-select.js. */

(function () {
  'use strict';

  const STORAGE_KEY = 'mc-mod-i18n-font';
  const DEFAULT_SANS_FALLBACK = '"Fira Sans", Inter, "Segoe UI", "Microsoft YaHei", Arial, sans-serif';
  const DEFAULT_MONO_FALLBACK = '"Fira Code", ui-monospace, SFMono-Regular, Consolas, monospace';
  const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10MB

  let catalog = null; // 最新拉到的 catalog
  let state = { sans: 'default-sans', mono: 'default-mono' };

  // ---- helpers ----
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function escapeQuoted(s) {
    return String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  function formatSize(bytes) {
    const n = Number(bytes) || 0;
    if (n >= 1024 * 1024) {
      return (n / 1024 / 1024).toFixed(1) + ' MB';
    }
    if (n >= 1024) {
      return (n / 1024).toFixed(0) + ' KB';
    }
    return n + ' B';
  }

  // ---- storage ----
  function readStored() {
    const fallback = { sans: 'default-sans', mono: 'default-mono' };
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return fallback;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return fallback;
      const sans = typeof parsed.sans === 'string' && parsed.sans ? parsed.sans : 'default-sans';
      const mono = typeof parsed.mono === 'string' && parsed.mono ? parsed.mono : 'default-mono';
      return { sans, mono };
    } catch (err) {
      return fallback;
    }
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (err) {
      // localStorage 可能被禁用 / 配额满，静默忽略
    }
  }

  // ---- catalog ----
  async function fetchCatalog() {
    const res = await fetch('/api/fonts', { headers: { 'Accept': 'application/json' } });
    if (!res.ok) throw new Error('GET /api/fonts ' + res.status);
    const data = await res.json();
    if (!data || data.ok === false) throw new Error('catalog payload not ok');
    catalog = {
      default: data.default || {
        sans: { id: 'default-sans', label: '默认 Fira Sans', family: 'Fira Sans' },
        mono: { id: 'default-mono', label: '默认 Fira Code', family: 'Fira Code' },
      },
      builtin: Array.isArray(data.builtin) ? data.builtin : [],
      user: Array.isArray(data.user) ? data.user : [],
    };
    return catalog;
  }

  function findFont(id) {
    if (!catalog || !id) return null;
    if (id === 'default-sans') return catalog.default.sans;
    if (id === 'default-mono') return catalog.default.mono;
    for (const f of catalog.builtin) {
      if (f && f.id === id) return f;
    }
    for (const f of catalog.user) {
      if (f && f.id === id) return f;
    }
    return null;
  }

  // ---- font-face injection ----
  function styleEl() {
    let el = document.getElementById('dynamic-font-faces');
    if (!el) {
      el = document.createElement('style');
      el.id = 'dynamic-font-faces';
      document.head.appendChild(el);
    }
    return el;
  }

  function injectFontFaces() {
    if (!catalog) return;
    const lines = [];
    [...catalog.builtin, ...catalog.user].forEach(f => {
      if (!f || !f.family || !f.url) return;
      const family = escapeQuoted(f.family);
      const url = escapeQuoted(f.url);
      const format = (f.format || 'truetype').replace(/[^a-z0-9-]/gi, '');
      lines.push('@font-face { font-family: "' + family + '"; src: url("' + url + '") format("' + format + '"); font-display: swap; }');
    });
    styleEl().textContent = lines.join('\n');
  }

  // ---- apply ----
  function applySlot(slot, font) {
    const fallback = slot === 'sans' ? DEFAULT_SANS_FALLBACK : DEFAULT_MONO_FALLBACK;
    const root = document.documentElement;
    if (!font || (typeof font.id === 'string' && font.id.indexOf('default-') === 0)) {
      root.style.removeProperty('--font-' + slot);
      return;
    }
    const family = escapeQuoted(font.family || '');
    if (!family) {
      root.style.removeProperty('--font-' + slot);
      return;
    }
    root.style.setProperty('--font-' + slot, '"' + family + '", ' + fallback);
  }

  function applySelection() {
    applySlot('sans', findFont(state.sans));
    applySlot('mono', findFont(state.mono));
  }

  // ---- UI rendering ----
  function renderSlotMenu(slot) {
    const shell = document.querySelector('.ghost-select.font-slot-control[data-font-slot="' + slot + '"]');
    if (!shell) return;
    const menu = shell.querySelector('.ghost-menu');
    const trigger = shell.querySelector('[data-select-trigger]');
    const triggerLabel = shell.querySelector('[data-select-trigger] .value');
    const currentId = state[slot];
    const fallbackDefault = slot === 'sans'
      ? { id: 'default-sans', label: '默认 Fira Sans', family: 'Fira Sans' }
      : { id: 'default-mono', label: '默认 Fira Code', family: 'Fira Code' };
    const defaultFont = (catalog && catalog.default && catalog.default[slot]) || fallbackDefault;
    const currentFont = findFont(currentId) || defaultFont;
    if (triggerLabel) triggerLabel.textContent = currentFont.label || '';
    if (trigger) {
      trigger.title = currentFont.label || '';
    }

    if (!menu) return;
    const groups = [
      { key: 'default', label: '默认', items: [defaultFont] },
      { key: 'builtin', label: '内置', items: (catalog && catalog.builtin) || [] },
      { key: 'user', label: '自定义', items: (catalog && catalog.user) || [] },
    ].filter(g => g.items && g.items.length > 0);

    const fallbackStack = slot === 'sans' ? 'sans-serif' : 'monospace';
    menu.innerHTML = groups.map(g => {
      const title = '<div class="ghost-option-group-title">' + escapeHtml(g.label) + '</div>';
      const opts = g.items.map(f => {
        if (!f) return '';
        const isActive = f.id === currentId;
        const family = (f.family || '').replace(/'/g, "\\'");
        const sizeBadge = (f.size_bytes && f.size_bytes > 1024 * 1024)
          ? '<span class="font-option-size">' + escapeHtml(formatSize(f.size_bytes)) + ' ⚠</span>'
          : '';
        const fontStyle = family ? ' style="font-family: \'' + family + '\', ' + fallbackStack + '"' : '';
        return '<button type="button" class="ghost-option' + (isActive ? ' active' : '') + '" '
          + 'role="option" aria-selected="' + (isActive ? 'true' : 'false') + '" '
          + 'data-value="' + escapeHtml(f.id || '') + '" data-font-slot="' + slot + '"'
          + fontStyle + '>'
          + '<span class="font-option-label">' + escapeHtml(f.label || f.id || '') + '</span>'
          + sizeBadge
          + '</button>';
      }).join('');
      return title + opts;
    }).join('');
  }

  function renderUserList() {
    const list = document.getElementById('font-user-list');
    if (!list) return;
    const users = (catalog && catalog.user) || [];
    if (users.length === 0) {
      list.dataset.empty = 'true';
      list.innerHTML = '';
      return;
    }
    list.dataset.empty = 'false';
    list.innerHTML = users.map(f => {
      const meta = formatSize(f.size_bytes) + ' · ' + escapeHtml(String(f.format || '').toUpperCase());
      return '<div class="font-user-row">'
        + '<div class="font-user-info">'
        + '<strong>' + escapeHtml(f.label || f.id || '') + '</strong>'
        + '<span class="font-user-meta">' + meta + '</span>'
        + '</div>'
        + '<button type="button" class="danger-icon" data-font-delete="' + escapeHtml(f.id || '') + '" '
        + 'title="删除" aria-label="删除字体"><i class="ri-delete-bin-line"></i></button>'
        + '</div>';
    }).join('');
  }

  function renderAll() {
    renderSlotMenu('sans');
    renderSlotMenu('mono');
    renderUserList();
  }

  // ---- handlers ----
  async function handleUpload(file) {
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      window.alert('字体文件过大（' + formatSize(file.size) + '），上限 10 MB');
      return;
    }
    const fd = new FormData();
    fd.append('file', file, file.name);
    let res;
    try {
      res = await fetch('/api/fonts/upload', { method: 'POST', body: fd });
    } catch (err) {
      console.error('[font] upload failed', err);
      window.alert('上传失败：网络错误');
      return;
    }
    let data = null;
    try {
      data = await res.json();
    } catch (err) {
      data = null;
    }
    if (!res.ok || !data || data.ok === false) {
      const reason = (data && data.error) || ('HTTP ' + res.status);
      window.alert('上传失败：' + reason);
      return;
    }
    try {
      await fetchCatalog();
      injectFontFaces();
      renderAll();
      window.alert('字体上传成功');
    } catch (err) {
      console.error('[font] post-upload refresh failed', err);
    }
  }

  async function handleDelete(id) {
    if (!id) return;
    const font = findFont(id);
    const name = (font && font.label) || id;
    if (!window.confirm('确定删除字体「' + name + '」？')) return;
    let res;
    try {
      res = await fetch('/api/fonts/' + encodeURIComponent(id), { method: 'DELETE' });
    } catch (err) {
      console.error('[font] delete failed', err);
      window.alert('删除失败：网络错误');
      return;
    }
    let data = null;
    try {
      data = await res.json();
    } catch (err) {
      data = null;
    }
    if (!res.ok || !data || data.ok === false) {
      const reason = (data && data.error) || ('HTTP ' + res.status);
      window.alert('删除失败：' + reason);
      return;
    }
    // 如果当前在用，掉回默认
    let changed = false;
    if (state.sans === id) { state.sans = 'default-sans'; changed = true; }
    if (state.mono === id) { state.mono = 'default-mono'; changed = true; }
    if (changed) persist();
    try {
      await fetchCatalog();
      injectFontFaces();
      applySelection();
      renderAll();
    } catch (err) {
      console.error('[font] post-delete refresh failed', err);
    }
  }

  function handleResetAll() {
    state = { sans: 'default-sans', mono: 'default-mono' };
    persist();
    applySelection();
    renderAll();
  }

  function pickFont(slot, fontId) {
    if (slot !== 'sans' && slot !== 'mono') return;
    if (!fontId) return;
    state[slot] = fontId;
    persist();
    applySelection();
    renderSlotMenu(slot);
  }

  // ---- bind ----
  function bindUI() {
    document.querySelectorAll('.ghost-select.font-slot-control').forEach(shell => {
      const trigger = shell.querySelector('[data-select-trigger]');
      const menu = shell.querySelector('.ghost-menu');
      if (!trigger || !menu) return;

      trigger.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        const isOpen = shell.classList.contains('open');
        if (typeof window.closeAllSelectMenus === 'function') window.closeAllSelectMenus();
        if (!isOpen && typeof window.openSelectMenu === 'function') {
          window.openSelectMenu(shell, menu, trigger);
        }
      });

      menu.addEventListener('click', e => {
        const opt = e.target.closest('[data-value][data-font-slot]');
        if (!opt) return;
        e.preventDefault();
        e.stopPropagation();
        pickFont(opt.dataset.fontSlot, opt.dataset.value);
        if (typeof window.scheduleMenuHide === 'function') {
          window.scheduleMenuHide(shell, menu, trigger);
        }
      });
    });

    // outside click closes menus (handled by ghost-select global doc listeners
    // already, but we add ESC keyboard fallback here too)
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && typeof window.closeAllSelectMenus === 'function') {
        const anyFontMenuOpen = document.querySelector('.ghost-select.font-slot-control.open');
        if (anyFontMenuOpen) window.closeAllSelectMenus();
      }
    });

    // Upload
    const uploadInput = document.getElementById('font-upload-input');
    const uploadBtn = document.getElementById('font-upload-btn');
    if (uploadBtn && uploadInput) {
      uploadBtn.addEventListener('click', () => uploadInput.click());
      uploadInput.addEventListener('change', async () => {
        const file = uploadInput.files && uploadInput.files[0];
        if (file) {
          try {
            await handleUpload(file);
          } finally {
            uploadInput.value = '';
          }
        } else {
          uploadInput.value = '';
        }
      });
    }

    // Delete (event delegation)
    const userList = document.getElementById('font-user-list');
    if (userList) {
      userList.addEventListener('click', e => {
        const btn = e.target.closest('[data-font-delete]');
        if (btn) handleDelete(btn.dataset.fontDelete);
      });
    }

    // Reset
    const resetBtn = document.getElementById('font-reset-all');
    if (resetBtn) resetBtn.addEventListener('click', handleResetAll);
  }

  // ---- init ----
  async function init() {
    state = readStored();
    applySelection(); // 先用 fallback 应用一次
    try {
      await fetchCatalog();
      injectFontFaces();
      // 校验 state 里 id 还存在
      let mutated = false;
      if (!findFont(state.sans)) { state.sans = 'default-sans'; mutated = true; }
      if (!findFont(state.mono)) { state.mono = 'default-mono'; mutated = true; }
      if (mutated) persist();
      applySelection();
      renderAll();
      bindUI();
    } catch (err) {
      console.error('[font] init failed', err);
      // 即使 catalog 失败也尝试绑定 reset 按钮，方便用户兜底
      try { bindUI(); } catch (err2) { /* noop */ }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.AppFont = {
    applySelection: applySelection,
    refresh: async function () {
      await fetchCatalog();
      injectFontFaces();
      renderAll();
    },
    getState: function () { return { sans: state.sans, mono: state.mono }; },
  };
})();
