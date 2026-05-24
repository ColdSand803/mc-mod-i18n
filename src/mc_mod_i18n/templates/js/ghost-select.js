/* Ghost-select menu machinery (Sprint H4).
   Extracted verbatim from the inline <script> in index.html.
   No IIFE wrapper — top-level function declarations become globals
   (window.openSelectMenu, etc.) so the existing ~50 callsites in the
   inline script keep working without rewiring. theme.js still receives
   these via its bootstrap deps object.

   Loaded BEFORE theme.js and the main inline <script>.
   Depends on: nothing (pure DOM helpers). */

function closeAllSelectMenus() {
  document.querySelectorAll('.ghost-select.open').forEach(shell => {
    const trigger = shell.querySelector('[data-select-trigger]');
    const modelTriggerNode = shell.querySelector('[data-model-trigger]');
    if (modelTriggerNode) {
      modelTriggerNode.setAttribute('aria-expanded', 'false');
    }
    const localeSearchInput = shell.querySelector('[data-locale-control-search]');
    if (localeSearchInput) {
      localeSearchInput.value = '';
    }
    const modelSearchInput = shell.querySelector('.model-control-input');
    if (modelSearchInput) {
      modelSearchInput.value = '';
    }
    const menu = shell.querySelector('.ghost-menu');
    if (menu) {
      scheduleMenuHide(shell, menu, trigger || modelTriggerNode);
    }
  });
}

function updateSelectMenuActive(menu, value) {
  if (!menu) {
    return;
  }
  menu.querySelectorAll('.ghost-option').forEach(item => {
    const isActive = item.dataset.value === value;
    item.classList.toggle('active', isActive);
    if (item.hasAttribute('role')) {
      item.setAttribute('aria-selected', isActive ? 'true' : 'false');
    }
  });
}

function cancelMenuHide(menu) {
  if (!menu) {
    return;
  }
  if (menu._hideTimer) {
    window.clearTimeout(menu._hideTimer);
    menu._hideTimer = 0;
  }
  menu.classList.remove('is-closing');
}

function isMenuOpen(shell, menu) {
  return Boolean(shell && menu && shell.classList.contains('open') && !menu.hidden && !menu.classList.contains('is-closing'));
}

let floatingMenuSyncFrame = 0;

function floatingMenuShellFor(menu) {
  if (!menu) {
    return null;
  }
  return menu.closest('.ghost-select.open, .theme-picker.open');
}

function syncFloatingMenus() {
  floatingMenuSyncFrame = 0;
  document.querySelectorAll('.ghost-menu.is-floating, .theme-menu.is-floating').forEach(menu => {
    const shell = floatingMenuShellFor(menu);
    if (!isMenuOpen(shell, menu)) {
      return;
    }
    positionFloatingMenu(shell, menu, menu._floatingTrigger);
  });
}

function scheduleFloatingMenuSync() {
  if (floatingMenuSyncFrame) {
    return;
  }
  floatingMenuSyncFrame = window.requestAnimationFrame(syncFloatingMenus);
}

function desktopZoomScale() {
  const raw = Number(document.documentElement.dataset.desktopZoom || '1');
  return Number.isFinite(raw) && raw > 0 ? raw : 1;
}

function scheduleMenuHide(shell, menu, trigger) {
  if (!shell || !menu) {
    return;
  }
  cancelMenuHide(menu);
  shell.classList.remove('open');
  menu.classList.add('is-closing');
  if (trigger) {
    trigger.setAttribute('aria-expanded', 'false');
  }
  menu._hideTimer = window.setTimeout(() => {
    menu.hidden = true;
    menu.classList.remove('is-closing');
    menu.classList.remove('is-floating');
    menu.style.removeProperty('position');
    menu.style.removeProperty('left');
    menu.style.removeProperty('top');
    menu.style.removeProperty('right');
    menu.style.removeProperty('width');
    menu.style.removeProperty('min-width');
    menu.style.removeProperty('max-width');
    menu.style.removeProperty('max-height');
    menu.style.removeProperty('z-index');
    menu._floatingTrigger = null;
    menu._hideTimer = 0;
  }, 180);
}

function positionFloatingMenu(shell, menu, trigger) {
  if (!shell || !menu) {
    return;
  }
  const anchor = trigger || shell.querySelector('[data-select-trigger]') || shell.querySelector('[data-model-trigger]') || shell;
  const rect = anchor.getBoundingClientRect();
  const cssZoom = desktopZoomScale();
  const gutter = 12;
  const viewportWidth = (window.innerWidth || document.documentElement.clientWidth || 1024) / cssZoom;
  const viewportHeight = (window.innerHeight || document.documentElement.clientHeight || 768) / cssZoom;
  const anchorLeft = rect.left / cssZoom;
  const anchorRight = rect.right / cssZoom;
  const anchorTop = rect.top / cssZoom;
  const anchorBottom = rect.bottom / cssZoom;
  const anchorWidth = rect.width / cssZoom;
  const prevWidth = menu.style.width;
  const prevMinWidth = menu.style.minWidth;
  const prevMaxWidth = menu.style.maxWidth;
  menu.style.width = 'max-content';
  menu.style.minWidth = '0';
  menu.style.maxWidth = `${Math.max(120, viewportWidth - gutter * 2)}px`;
  const naturalWidth = Math.ceil(menu.getBoundingClientRect().width / cssZoom);
  menu.style.width = prevWidth;
  menu.style.minWidth = prevMinWidth;
  menu.style.maxWidth = prevMaxWidth;
  const contentWidth = Math.max(anchorWidth, naturalWidth);
  const width = Math.min(contentWidth, viewportWidth - gutter * 2);
  const leftAlignLeft = anchorLeft;
  const rightAlignLeft = anchorRight - width;
  const rightSpilloverIfLeftAlign = (leftAlignLeft + width) - (viewportWidth - gutter);
  let left;
  if (rightSpilloverIfLeftAlign <= 0) {
    left = leftAlignLeft;
  } else if (rightAlignLeft >= gutter) {
    left = rightAlignLeft;
  } else {
    left = Math.max(gutter, viewportWidth - width - gutter);
  }
  left = Math.max(gutter, Math.min(left, viewportWidth - width - gutter));
  const belowTop = anchorBottom + 6;
  const aboveSpace = Math.max(0, anchorTop - gutter - 6);
  const belowSpace = Math.max(0, viewportHeight - belowTop - gutter);
  const openAbove = belowSpace < 180 && aboveSpace > belowSpace;
  const maxHeight = Math.max(96, Math.min(320, openAbove ? aboveSpace : belowSpace));
  const top = openAbove
    ? Math.max(gutter, anchorTop - 6 - maxHeight)
    : Math.max(gutter, Math.min(belowTop, viewportHeight - 64));
  menu._floatingTrigger = anchor;
  menu.classList.add('is-floating');
  menu.style.position = 'fixed';
  menu.style.left = `${Math.round(left)}px`;
  menu.style.top = `${Math.round(top)}px`;
  menu.style.right = 'auto';
  menu.style.width = `${Math.round(width)}px`;
  menu.style.minWidth = `${Math.round(width)}px`;
  menu.style.maxWidth = 'calc(100vw - 24px)';
  menu.style.maxHeight = `${Math.round(maxHeight)}px`;
  menu.style.zIndex = '180';
}

function openSelectMenu(shell, menu, trigger) {
  if (!shell || !menu) {
    return;
  }
  cancelMenuHide(menu);
  menu.hidden = false;
  positionFloatingMenu(shell, menu, trigger);
  void menu.offsetHeight;
  shell.classList.add('open');
  if (trigger) {
    trigger.setAttribute('aria-expanded', 'true');
  }
}

window.addEventListener('scroll', scheduleFloatingMenuSync, true);
window.addEventListener('resize', scheduleFloatingMenuSync);
