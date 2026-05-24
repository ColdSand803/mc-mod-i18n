/* Theme picker module (Sprint H3).
   Loaded BEFORE the main inline <script>. Registers a bootstrap factory that
   the inline script invokes after defining its i18n / ghost-select helpers,
   so those deps can be injected without polluting the global namespace. */
(function () {
  window.AppThemeBootstrap = function (deps) {
    const { ui, formatUi, closeAllSelectMenus, openSelectMenu, scheduleMenuHide } = deps;

    const themePicker = document.getElementById('theme-picker');
    const themeToggle = document.getElementById('theme-toggle');
    const themeMenu = document.getElementById('theme-menu');
    const themeTriggerSwatches = document.querySelector('[data-theme-trigger-swatches]');
    const THEME_STORAGE_KEY = 'mc-mod-i18n-theme';

    const themeCatalog = [
      { id: 'auto', label: '跟随系统', group: '基础主题', icon: 'ri-computer-line', scheme: 'auto', colors: ['#2563eb', '#f8fafc', '#0f172a'] },
      { id: 'light', label: '默认浅色', group: '基础主题', icon: 'ri-sun-line', scheme: 'light', colors: ['#004ac6', '#f8f9ff', '#0b1c30'] },
      { id: 'dark', label: '默认深色', group: '基础主题', icon: 'ri-moon-clear-line', scheme: 'dark', colors: ['#60a5fa', '#020617', '#e5eefb'] },
      { id: 'forest', label: '森林安全', group: '专注主题', icon: 'ri-leaf-line', scheme: 'light', colors: ['#2f6b3f', '#f3f7f0', '#172313'] },
      { id: 'midnight', label: '午夜蓝', group: '专注主题', icon: 'ri-moon-foggy-line', scheme: 'dark', colors: ['#4f8cff', '#07111f', '#eaf2ff'] },
      { id: 'dongbei-rain', label: '东北雨', group: '趣味主题', icon: 'ri-cloudy-2-line', scheme: 'dark', colors: ['#c9162f', '#4d2f1f', '#fffaf0'] },
      { id: 'rainbow-rgb', label: '彩虹 RGB', group: '趣味主题', icon: 'ri-rainbow-line', scheme: 'dark', colors: ['#00d4ff', '#070711', '#f8fbff'] },
      { id: 'bleach-tybw', label: '死神:千年血战', group: '联名主题', icon: 'ri-sword-line', scheme: 'dark', colors: ['#e6397c', '#1a1a1d', '#fff7fb'] },
      { id: 'eva', label: 'EVA', group: '联名主题', icon: 'ri-robot-2-line', scheme: 'dark', colors: ['#b7ff2a', '#090812', '#f6ffe8'] },
      { id: 'p-site', label: 'P站', group: '联名主题', icon: 'ri-copyright-line', scheme: 'dark', colors: ['#ff9900', '#050505', '#f7f7f7'] },
      { id: 'starry-night', label: '梵高星空', group: '艺术主题', icon: 'ri-star-line', scheme: 'dark', colors: ['#f6c945', '#07142e', '#f8efcb'] },
      { id: 'monet', label: '莫奈', group: '艺术主题', icon: 'ri-palette-line', scheme: 'light', colors: ['#6b9f8a', '#eef4f2', '#243a3a'] },
      { id: 'qingming-scroll', label: '清明上河图', group: '艺术主题', icon: 'ri-landscape-line', scheme: 'light', colors: ['#2f6673', '#f3e8d2', '#2a241b'] },
      { id: 'cezanne', label: '塞尚', group: '艺术主题', icon: 'ri-brush-line', scheme: 'light', colors: ['#8f4f2f', '#efe6d8', '#2f241d'] },
      { id: 'sisley', label: '西斯莱', group: '艺术主题', icon: 'ri-brush-3-line', scheme: 'light', colors: ['#5f8fa8', '#eef4ef', '#24343a'] },
      { id: 'pissarro', label: '毕沙罗', group: '艺术主题', icon: 'ri-image-line', scheme: 'light', colors: ['#7f8f4e', '#f1eddf', '#2d2a1e'] },
      { id: 'morandi', label: '莫兰迪', group: '艺术主题', icon: 'ri-contrast-drop-line', scheme: 'light', colors: ['#8d8580', '#eeece8', '#2f2d2b'] },
      { id: 'gauguin', label: '高更', group: '艺术主题', icon: 'ri-paint-brush-line', scheme: 'light', colors: ['#b65f2a', '#f1e0c2', '#2c2117'] },
      { id: 'matisse', label: '马蒂斯', group: '艺术主题', icon: 'ri-shape-2-line', scheme: 'light', colors: ['#2468c9', '#f4efe5', '#18243a'] },
      { id: 'qi-baishi', label: '齐白石', group: '艺术主题', icon: 'ri-quill-pen-line', scheme: 'light', colors: ['#b7352d', '#f6f0e3', '#211f1b'] },
      { id: 'healing-sea-blue', label: '治愈海盐蓝', group: 'Stitch 配色', icon: 'ri-water-flash-line', scheme: 'light', colors: ['#0081ff', '#eef7ff', '#08204a'] },
      { id: 'mint-tea-green', label: '薄荷茶青', group: 'Stitch 配色', icon: 'ri-seedling-line', scheme: 'light', colors: ['#178b85', '#eefaf7', '#173a36'] },
      { id: 'neon-track', label: '荧光赛道绿', group: 'Stitch 配色', icon: 'ri-road-map-line', scheme: 'dark', colors: ['#00fd00', '#07180b', '#efffee'] },
      { id: 'cream-berry-purple', label: '奶油莓紫', group: 'Stitch 配色', icon: 'ri-cake-3-line', scheme: 'light', colors: ['#652c97', '#fff0f2', '#2d183a'] },
      { id: 'orange-slate', label: '橙灰机能', group: 'Stitch 配色', icon: 'ri-tools-line', scheme: 'dark', colors: ['#ff7400', '#172728', '#fff2e5'] },
      { id: 'seafoam-apricot', label: '海风杏桃', group: 'Stitch 配色', icon: 'ri-water-percent-line', scheme: 'light', colors: ['#01847f', '#effaf7', '#123936'] },
      { id: 'klein-gold', label: '克莱因金', group: 'Stitch 配色', icon: 'ri-vip-diamond-line', scheme: 'light', colors: ['#002fa7', '#ffcf14', '#061a4d'] },
      { id: 'honey-sunset', label: '蜜糖落日', group: 'Stitch 配色', icon: 'ri-sunset-line', scheme: 'light', colors: ['#ff6067', '#fff7d6', '#3b2b19'] },
      { id: 'crimson-ivory', label: '酒红象牙', group: 'Stitch 配色', icon: 'ri-goblet-line', scheme: 'light', colors: ['#990033', '#f4eee5', '#341019'] },
      { id: 'sakura-mist', label: '樱雾灰紫', group: 'Stitch 配色', icon: 'ri-blur-off-line', scheme: 'light', colors: ['#535369', '#ffe3ee', '#272333'] }
    ];
    const themeMeta = Object.fromEntries(themeCatalog.map(theme => [theme.id, theme]));
    const themeModes = themeCatalog.map(theme => theme.id);
    const systemThemeQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const themeGroupMessageKeys = {
      '基础主题': 'theme.group.basic',
      '专注主题': 'theme.group.focus',
      '趣味主题': 'theme.group.playful',
      '联名主题': 'theme.group.crossover',
      '艺术主题': 'theme.group.art',
      'Stitch 配色': 'theme.group.stitch'
    };

    function storedThemeMode() {
      try {
        const stored = localStorage.getItem(THEME_STORAGE_KEY) || document.documentElement.dataset.themeMode || 'auto';
        return themeMeta[stored] ? stored : 'auto';
      } catch (error) {
        const stored = document.documentElement.dataset.themeMode || 'auto';
        return themeMeta[stored] ? stored : 'auto';
      }
    }

    function resolveThemeMode(mode) {
      const requested = themeMeta[mode] ? mode : 'auto';
      if (requested === 'auto') {
        return systemThemeQuery.matches ? 'dark' : 'light';
      }
      return requested;
    }

    function themeColorScheme(themeId) {
      const meta = themeMeta[themeId] || themeMeta.light;
      return meta.scheme === 'dark' ? 'dark' : 'light';
    }

    function themeSwatchesHtml(colors, extraClass = '') {
      return `<span class="theme-swatches ${escapeHtml(extraClass)}" aria-hidden="true">
        ${(colors || []).map(color => `<span class="theme-swatch" style="background:${escapeHtml(color)}"></span>`).join('')}
      </span>`;
    }

    function themeMessageKey(theme) {
      return `theme.${String(theme?.id || '').replace(/[^a-z0-9_-]/gi, '_')}`;
    }

    function themeGroupMessageKey(theme) {
      return themeGroupMessageKeys[theme?.group] || `theme.group.${String(theme?.group || '').replace(/[^a-z0-9_-]/gi, '_')}`;
    }

    function themeLabel(theme) {
      return ui(themeMessageKey(theme), theme?.label || '');
    }

    function themeGroupLabel(theme) {
      return ui(themeGroupMessageKey(theme), theme?.group || '');
    }

    function themeModeText(theme) {
      if (!theme || theme.id === 'auto') {
        const resolvedMeta = themeMeta[resolveThemeMode('auto')] || themeMeta.light;
        return formatUi('theme.mode.auto_resolved', '当前解析为 {theme}', { theme: themeLabel(resolvedMeta) });
      }
      return theme.scheme === 'dark' ? ui('theme.mode.dark', '深色') : ui('theme.mode.light', '浅色');
    }

    function renderThemeMenu(activeMode) {
      if (!themeMenu) {
        return;
      }
      const groups = [];
      const groupMap = new Map();
      themeCatalog.forEach(theme => {
        const groupKey = themeGroupMessageKey(theme);
        if (!groupMap.has(groupKey)) {
          const group = { label: themeGroupLabel(theme), items: [] };
          groupMap.set(groupKey, group);
          groups.push(group);
        }
        groupMap.get(groupKey).items.push(theme);
      });
      themeMenu.innerHTML = groups.map(group => `
        <div class="theme-group" role="group" aria-label="${escapeHtml(group.label)}">
          <div class="theme-group-title">${escapeHtml(group.label)}</div>
          ${group.items.map(theme => {
            const active = activeMode === theme.id;
            const label = themeLabel(theme);
            const groupLabel = themeGroupLabel(theme);
            return `
              <button type="button" class="theme-option ${active ? 'active' : ''}" data-theme-value="${escapeHtml(theme.id)}" role="option" aria-selected="${active ? 'true' : 'false'}">
                <span class="theme-option-copy"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(groupLabel)} · ${escapeHtml(themeModeText(theme))}</span></span>
                ${themeSwatchesHtml(theme.colors || [])}
              </button>
            `;
          }).join('')}
        </div>
      `).join('');
    }

    function setThemeMenuOpen(open) {
      if (!themePicker || !themeMenu || !themeToggle) {
        return;
      }
      if (open) {
        closeAllSelectMenus();
        openSelectMenu(themePicker, themeMenu, themeToggle);
      } else {
        scheduleMenuHide(themePicker, themeMenu, themeToggle);
      }
    }

    function applyThemeMode(mode, persist = false) {
      const requested = themeMeta[mode] ? mode : 'auto';
      const resolved = resolveThemeMode(requested);
      const scheme = themeColorScheme(resolved);
      document.documentElement.dataset.themeMode = requested;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = scheme;
      if (persist) {
        try {
          localStorage.setItem(THEME_STORAGE_KEY, requested);
        } catch (error) {}
      }
      if (themeToggle) {
        const meta = themeMeta[requested] || themeMeta.auto;
        const resolvedMeta = themeMeta[resolved] || themeMeta.light;
        const icon = themeToggle.querySelector('[data-theme-icon]');
        const label = themeToggle.querySelector('[data-theme-label]');
        if (icon) {
          icon.className = meta.icon;
        }
        if (label) {
          label.textContent = themeLabel(meta);
        }
        if (themeTriggerSwatches) {
          const colors = requested === 'auto' ? resolvedMeta.colors : meta.colors;
          themeTriggerSwatches.innerHTML = (colors || []).map(color => `<span class="theme-swatch" style="background:${escapeHtml(color)}"></span>`).join('');
        }
        themeToggle.dataset.themeMode = requested;
        themeToggle.title = formatUi('theme.title', '主题：{theme}', { theme: themeLabel(meta) });
      }
      renderThemeMenu(requested);
    }

    function bindThemePicker() {
      renderThemeMenu(document.documentElement.dataset.themeMode || storedThemeMode());
      if (!themePicker || !themeToggle || !themeMenu) {
        return;
      }
      themeToggle.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        setThemeMenuOpen(!themePicker.classList.contains('open'));
      });
      themeMenu.addEventListener('click', event => {
        const option = event.target.closest('[data-theme-value]');
        if (!option) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        applyThemeMode(option.dataset.themeValue || 'auto', true);
        setThemeMenuOpen(false);
      });
      themeMenu.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
          event.preventDefault();
          setThemeMenuOpen(false);
          themeToggle.focus();
        }
      });
      document.addEventListener('click', event => {
        if (!themePicker.contains(event.target)) {
          setThemeMenuOpen(false);
        }
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
          setThemeMenuOpen(false);
        }
      });
    }

    applyThemeMode(storedThemeMode());
    const handleSystemThemeChange = () => {
      if ((document.documentElement.dataset.themeMode || 'auto') === 'auto') {
        applyThemeMode('auto');
      }
    };
    if (typeof systemThemeQuery.addEventListener === 'function') {
      systemThemeQuery.addEventListener('change', handleSystemThemeChange);
    } else if (typeof systemThemeQuery.addListener === 'function') {
      systemThemeQuery.addListener(handleSystemThemeChange);
    }
    bindThemePicker();

    window.AppTheme = {
      applyMode: applyThemeMode,
      renderMenu: renderThemeMenu,
      storedMode: storedThemeMode,
      setMenuOpen: setThemeMenuOpen,
      modes: themeModes,
      catalog: themeCatalog
    };
  };
})();
