from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

from mc_mod_i18n.ui_i18n import merged_catalog
from mc_mod_i18n.web import INDEX_HTML, normalize_models_url, parse_models_response


class WebUiContractTest(unittest.TestCase):
    def test_browser_smoke_script_covers_core_ui_interactions(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "ui_smoke_test.mjs"
        self.assertTrue(script_path.is_file(), "scripts/ui_smoke_test.mjs should exist")
        script = script_path.read_text(encoding="utf-8")
        for selector in (
            "[data-select-trigger=\"source_locale\"]",
            "[data-select-trigger=\"target_locale\"]",
            "[data-model-trigger]",
            "#theme-toggle",
            "[data-select-trigger=\"ui_locale\"]",
            "#settings-open",
            "#settings-page",
            "#settings-cache-clear",
            "#settings-ui-locale-download",
            "#provider-test",
        ):
            self.assertIn(selector, script)
        self.assertIn("pageerror", script)
        self.assertIn("console", script)
        self.assertIn("aria-expanded", script)
        self.assertIn("launchSystemBrowserSmoke", script)
        self.assertIn("findSystemBrowserExecutable", script)
        self.assertIn("--remote-debugging-port=0", script)
        self.assertIn("Browser.getVersion", script)
        self.assertIn("document.querySelectorAll('#settings-page .settings-section')", script)
        self.assertIn("Settings cards overlap", script)

    def test_sidebar_brand_uses_translation_workbench_name(self) -> None:
        self.assertIn('alt="翻译工作台"', INDEX_HTML)
        self.assertIn('data-i18n="app.brand.name">翻译工作台</strong>', INDEX_HTML)
        self.assertNotIn('alt="汉化工作台"', INDEX_HTML)

    def test_workspace_uses_progressive_disclosure_for_advanced_settings(self) -> None:
        self.assertIn("高级 API 设置", INDEX_HTML)
        self.assertIn("输出策略", INDEX_HTML)
        self.assertIn("data-advanced-panel", INDEX_HTML)
        self.assertIn("workflow-step", INDEX_HTML)
        self.assertIn("步骤 1", INDEX_HTML)
        self.assertIn("步骤 4", INDEX_HTML)

    def test_header_has_single_navigation_system(self) -> None:
        self.assertNotIn('<div class="top-tabs">', INDEX_HTML)
        self.assertNotIn('class="top-search"', INDEX_HTML)
        self.assertIn("当前任务", INDEX_HTML)

    def test_result_summary_groups_outputs_quality_and_performance(self) -> None:
        self.assertIn("输出产物", INDEX_HTML)
        self.assertIn("质量概览", INDEX_HTML)
        self.assertIn("性能概览", INDEX_HTML)

    def test_language_controls_support_minecraft_locale_input(self) -> None:
        self.assertIn("minecraftLocales", INDEX_HTML)
        self.assertIn('["zh_tw", "繁體中文"]', INDEX_HTML)
        self.assertIn('["zh_hk", "繁體中文（香港）"]', INDEX_HTML)
        self.assertIn("locale-control-input", INDEX_HTML)
        self.assertIn("data-locale-control-search", INDEX_HTML)
        self.assertIn("data-locale-apply", INDEX_HTML)
        self.assertIn("data-locale-options", INDEX_HTML)
        self.assertIn("localeMatchesOption", INDEX_HTML)
        self.assertIn("refreshLocaleMenuSearch", INDEX_HTML)
        self.assertIn("没有匹配的内置语言", INDEX_HTML)

    def test_language_dropdowns_expose_searchable_listbox_state(self) -> None:
        self.assertIn('data-select-trigger="source_locale" role="combobox" tabindex="0" aria-haspopup="listbox" aria-expanded="false" aria-controls="source-locale-menu"', INDEX_HTML)
        self.assertIn('data-select-trigger="target_locale" role="combobox" tabindex="0" aria-haspopup="listbox" aria-expanded="false" aria-controls="target-locale-menu"', INDEX_HTML)
        self.assertIn('id="source-locale-menu" role="listbox"', INDEX_HTML)
        self.assertIn('id="target-locale-menu" role="listbox"', INDEX_HTML)
        self.assertIn('type="search" class="locale-control-input"', INDEX_HTML)
        self.assertNotIn('class="ghost-menu-input"', INDEX_HTML)

    def test_provider_list_is_limited_to_manual_and_compatible_api_options(self) -> None:
        self.assertIn('<option value="glossary">离线术语表（有限）</option>', INDEX_HTML)
        self.assertIn('<option value="copy">复制原文</option>', INDEX_HTML)
        self.assertIn('<option value="deep-free">Deep Translator（免费试用）</option>', INDEX_HTML)
        self.assertIn('<option value="openai-compatible">兼容 OpenAI</option>', INDEX_HTML)
        self.assertIn('<option value="anthropic-compatible">兼容 Anthropic</option>', INDEX_HTML)
        self.assertNotIn('<option value="deepseek">', INDEX_HTML)
        self.assertNotIn('<option value="gemini">', INDEX_HTML)

    def test_api_key_can_be_revealed_without_changing_form_contract(self) -> None:
        self.assertIn('name="api_key" id="api_key" type="password"', INDEX_HTML)
        self.assertIn('id="api-key-toggle"', INDEX_HTML)
        self.assertIn("syncApiKeyVisibility", INDEX_HTML)
        self.assertIn(".secret-input input::-ms-reveal", INDEX_HTML)

    def test_api_base_url_fetches_searchable_model_dropdown(self) -> None:
        self.assertIn('<span data-i18n="advanced.base_url">BaseURL</span>', INDEX_HTML)
        self.assertIn('name="api_url" id="api_base_url"', INDEX_HTML)
        self.assertIn('id="model-select"', INDEX_HTML)
        self.assertIn('id="model-refresh"', INDEX_HTML)
        self.assertIn("refreshModelList", INDEX_HTML)
        self.assertIn("fetch('/api/models'", INDEX_HTML)
        self.assertIn('class="model-control-input"', INDEX_HTML)
        self.assertIn('type="hidden" name="model" id="model"', INDEX_HTML)
        self.assertNotIn("<label>API URL", INDEX_HTML)

    def test_model_dropdown_stays_open_after_model_list_refresh(self) -> None:
        self.assertIn("function isMenuOpen(shell, menu)", INDEX_HTML)
        self.assertIn("if (isMenuOpen(modelSelectShell, modelMenu))", INDEX_HTML)
        self.assertIn("openSelectMenu(modelSelectShell, modelMenu, modelTrigger);", INDEX_HTML)
        self.assertIn("menu.style.position = 'fixed';", INDEX_HTML)
        self.assertIn("menu.style.left =", INDEX_HTML)
        self.assertIn("menu.style.top =", INDEX_HTML)
        self.assertIn("modelTrigger.addEventListener('click'", INDEX_HTML)
        self.assertIn("modelSearch.addEventListener('input'", INDEX_HTML)
        self.assertIn("document.addEventListener('click', (event) => {\n        if (!modelSelectShell.contains(event.target) && !modelMenu.contains(event.target))", INDEX_HTML)

    def test_advanced_api_settings_expose_provider_connection_test(self) -> None:
        self.assertIn('id="provider-test"', INDEX_HTML)
        self.assertIn('id="provider-test-status"', INDEX_HTML)
        self.assertIn('id="provider-risk-banner"', INDEX_HTML)
        self.assertIn("testProviderConnection", INDEX_HTML)
        self.assertIn("renderProviderRiskBanner", INDEX_HTML)
        self.assertIn("fetch('/api/test-provider'", INDEX_HTML)
        self.assertIn("advanced.test_provider", INDEX_HTML)
        self.assertIn("advanced.test_provider_success", INDEX_HTML)
        self.assertIn("advanced.test_provider_failed", INDEX_HTML)

    def test_pack_download_name_keeps_zip_suffix_fixed(self) -> None:
        self.assertIn("pack-name-input-wrap", INDEX_HTML)
        self.assertIn("pack-name-suffix", INDEX_HTML)
        self.assertIn("packNameStem", INDEX_HTML)
        self.assertIn("文件后缀固定为 .zip", INDEX_HTML)

    def test_cache_and_loading_controls_are_exposed(self) -> None:
        self.assertIn('name="ignore_cache"', INDEX_HTML)
        self.assertIn("忽略缓存并重新翻译", INDEX_HTML)
        self.assertIn("progress-full", INDEX_HTML)
        self.assertIn('classList.toggle(\'indeterminate\'', INDEX_HTML)

    def test_settings_menu_exposes_cache_management(self) -> None:
        self.assertIn('id="settings-open"', INDEX_HTML)
        self.assertIn('id="settings-page"', INDEX_HTML)
        self.assertIn('data-main-view="settings"', INDEX_HTML)
        self.assertIn('class="settings-layout"', INDEX_HTML)
        self.assertIn('id="settings-cache-section"', INDEX_HTML)
        self.assertIn('id="settings-locale-section"', INDEX_HTML)
        self.assertIn('class="settings-footer"', INDEX_HTML)
        self.assertIn(".settings-layout", INDEX_HTML)
        self.assertIn(".settings-section-actions", INDEX_HTML)
        self.assertIn('id="settings-cache-dir"', INDEX_HTML)
        self.assertIn('id="settings-cache-clear"', INDEX_HTML)
        self.assertIn('id="settings-cache-default"', INDEX_HTML)
        self.assertIn('name="cache_dir" id="cache_dir"', INDEX_HTML)
        self.assertIn("CACHE_DIR_STORAGE_KEY", INDEX_HTML)
        self.assertIn("fetch('/api/cache/clear'", INDEX_HTML)

    def test_settings_menu_exposes_glossary_management(self) -> None:
        self.assertIn('id="settings-glossary-section"', INDEX_HTML)
        self.assertIn('id="settings-glossary-editor"', INDEX_HTML)
        self.assertIn('id="settings-glossary-table"', INDEX_HTML)
        self.assertIn('id="settings-glossary-search"', INDEX_HTML)
        self.assertIn('id="settings-glossary-add-row"', INDEX_HTML)
        self.assertIn('id="settings-glossary-toggle-json"', INDEX_HTML)
        self.assertIn('id="settings-glossary-conflicts"', INDEX_HTML)
        self.assertIn('id="settings-glossary-save"', INDEX_HTML)
        self.assertIn('id="glossary-import-file"', INDEX_HTML)
        self.assertIn("loadGlossarySettings", INDEX_HTML)
        self.assertIn("saveGlossarySettings", INDEX_HTML)
        self.assertIn("renderGlossaryTable", INDEX_HTML)
        self.assertIn("collectGlossaryTermsFromTable", INDEX_HTML)
        self.assertIn("renderGlossaryConflicts", INDEX_HTML)
        self.assertIn("fetch('/api/glossary'", INDEX_HTML)
        self.assertIn("settings.glossary_section", INDEX_HTML)

    def test_settings_menu_exposes_config_presets_without_api_key_storage(self) -> None:
        self.assertIn('id="settings-presets-section"', INDEX_HTML)
        self.assertIn('id="settings-preset-name"', INDEX_HTML)
        self.assertIn('id="settings-preset-select"', INDEX_HTML)
        self.assertIn('id="settings-preset-save"', INDEX_HTML)
        self.assertIn('id="settings-preset-apply"', INDEX_HTML)
        self.assertIn('id="settings-preset-delete"', INDEX_HTML)
        self.assertIn("currentPresetConfig", INDEX_HTML)
        self.assertIn("data.delete('api_key')", INDEX_HTML)
        self.assertIn("fetch('/api/presets'", INDEX_HTML)
        self.assertIn("settings.presets_section", INDEX_HTML)

    def test_settings_menu_exposes_translation_memory_management(self) -> None:
        self.assertIn('id="settings-memory-section"', INDEX_HTML)
        self.assertIn('id="settings-memory-summary"', INDEX_HTML)
        self.assertIn('id="settings-memory-preview"', INDEX_HTML)
        self.assertIn('id="settings-memory-export"', INDEX_HTML)
        self.assertIn('id="settings-memory-compact"', INDEX_HTML)
        self.assertIn('id="settings-memory-clear-scope"', INDEX_HTML)
        self.assertIn('id="settings-memory-clear"', INDEX_HTML)
        self.assertIn("/api/translation-memory", INDEX_HTML)
        self.assertIn("loadTranslationMemorySettings", INDEX_HTML)
        self.assertIn("mutateTranslationMemory", INDEX_HTML)
        self.assertIn("renderTranslationMemoryPreview", INDEX_HTML)
        self.assertIn("currentTranslationMemoryScopePayload", INDEX_HTML)
        self.assertIn("settings.memory_section", INDEX_HTML)

    def test_settings_layout_uses_content_sized_rows_to_prevent_zoom_overlap(self) -> None:
        self.assertIn("grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr));", INDEX_HTML)
        self.assertIn("grid-auto-flow: row;", INDEX_HTML)
        self.assertIn("align-content: start;", INDEX_HTML)
        self.assertIn("min-width: 0;", INDEX_HTML)
        self.assertIn("height: fit-content;", INDEX_HTML)
        self.assertIn("@media (max-width: 1120px)", INDEX_HTML)

    def test_task_history_view_is_exposed(self) -> None:
        self.assertIn('data-view="history"', INDEX_HTML)
        self.assertIn('id="history-panel"', INDEX_HTML)
        self.assertIn('id="history-status-filter-shell"', INDEX_HTML)
        self.assertIn('id="history-status-filter"', INDEX_HTML)
        self.assertIn('id="history-status-filter-menu"', INDEX_HTML)
        self.assertIn('id="history-kind-filter-shell"', INDEX_HTML)
        self.assertIn('id="history-kind-filter"', INDEX_HTML)
        self.assertIn('id="history-kind-filter-menu"', INDEX_HTML)
        self.assertIn("bindSelectMenu(historyStatusFilterShell", INDEX_HTML)
        self.assertIn('data-select-trigger="history_status" role="combobox" tabindex="0" aria-haspopup="listbox"', INDEX_HTML)
        self.assertIn('data-select-trigger="history_kind" role="combobox" tabindex="0" aria-haspopup="listbox"', INDEX_HTML)
        self.assertIn('data-select-value="${escapeHtml(name)}" data-value="${escapeHtml(option.value)}" role="option"', INDEX_HTML)
        self.assertIn("loadJobHistory", INDEX_HTML)
        self.assertIn("renderJobHistory", INDEX_HTML)
        self.assertIn("fetch('/api/jobs'", INDEX_HTML)
        self.assertIn("nav.history", INDEX_HTML)
        self.assertIn("download_status", INDEX_HTML)
        self.assertIn("history-download-missing", INDEX_HTML)
        self.assertIn("history.file_missing", INDEX_HTML)

    def test_history_dropdowns_can_escape_card_clipping(self) -> None:
        self.assertIn(".history-page {\n      overflow: visible;", INDEX_HTML)
        self.assertIn(".history-card {\n      overflow: visible;", INDEX_HTML)
        self.assertIn(".history-card .settings-layout,\n    .history-card .settings-section {\n      overflow: visible;", INDEX_HTML)
        self.assertIn(".history-card .ghost-select.open {\n      z-index:", INDEX_HTML)
        self.assertIn(".ghost-menu.is-floating", INDEX_HTML)
        self.assertIn("positionFloatingMenu", INDEX_HTML)
        self.assertIn("menu.style.position = 'fixed';", INDEX_HTML)
        self.assertIn("menu.style.left =", INDEX_HTML)
        self.assertIn("menu.style.top =", INDEX_HTML)
        self.assertIn("menu.style.maxHeight =", INDEX_HTML)
        self.assertIn("menu.style.removeProperty('position')", INDEX_HTML)
        self.assertIn("menu.style.removeProperty('max-height')", INDEX_HTML)
        self.assertNotIn("menu.style.setProperty('--dropdown-left'", INDEX_HTML)
        self.assertNotIn("menu.style.setProperty('--dropdown-max-height'", INDEX_HTML)
        self.assertIn("const openAbove = belowSpace < 180 && aboveSpace > belowSpace", INDEX_HTML)

    def test_ghost_dropdowns_have_consistent_motion(self) -> None:
        self.assertIn("--dropdown-motion-offset", INDEX_HTML)
        self.assertIn("transition: opacity var(--motion-base) ease, visibility var(--motion-base) ease, transform var(--motion-base) ease", INDEX_HTML)
        self.assertIn(".ghost-select.open .ghost-menu", INDEX_HTML)
        self.assertIn("scheduleMenuHide", INDEX_HTML)
        self.assertIn("cancelMenuHide", INDEX_HTML)
        self.assertIn(".ghost-menu.is-closing", INDEX_HTML)
        self.assertIn(".ghost-select .chevron", INDEX_HTML)
        self.assertIn("@media (prefers-reduced-motion: reduce)", INDEX_HTML)

    def test_failed_retry_controls_and_status_trace_are_exposed(self) -> None:
        self.assertIn('id="retry-api-failures"', INDEX_HTML)
        self.assertIn("retryApiFailures", INDEX_HTML)
        self.assertIn("fetch(`/api/retry/${encodeURIComponent", INDEX_HTML)
        self.assertIn("retryStatusDetail", INDEX_HTML)
        self.assertIn("retry_previous_status", INDEX_HTML)
        self.assertIn("result.retry_status_detail", INDEX_HTML)

    def test_result_report_export_actions_are_exposed(self) -> None:
        self.assertIn('id="export-report-json"', INDEX_HTML)
        self.assertIn('id="export-report-csv"', INDEX_HTML)
        self.assertIn('id="export-failed-json"', INDEX_HTML)
        self.assertIn("exportReportJson", INDEX_HTML)
        self.assertIn("exportReportCsv", INDEX_HTML)
        self.assertIn("exportFailedItemsJson", INDEX_HTML)
        self.assertIn("result.export_report_json", INDEX_HTML)
        self.assertIn("result.export_report_csv", INDEX_HTML)
        self.assertIn("result.export_failed_json", INDEX_HTML)

    def test_hardcoded_workbench_explains_runtime_patch_requirement(self) -> None:
        self.assertIn("result.hardcoded_runtime_note", INDEX_HTML)
        self.assertIn("运行时补丁 Mod", INDEX_HTML)

    def test_output_preview_exposes_status_filter_diff_summary_and_json_metadata(self) -> None:
        self.assertIn('id="language-status-filter"', INDEX_HTML)
        self.assertIn('id="language-condition-filter"', INDEX_HTML)
        self.assertIn('id="language-view-mode"', INDEX_HTML)
        self.assertIn("languageConditionFilter", INDEX_HTML)
        self.assertIn("languageViewMode", INDEX_HTML)
        self.assertIn("data-language-condition", INDEX_HTML)
        self.assertIn("data-language-view", INDEX_HTML)
        self.assertIn("data-language-row-issue", INDEX_HTML)
        self.assertIn("['failed', 'api_failed', 'incomplete', 'jar_failed'].includes(entry.status)", INDEX_HTML)
        self.assertIn("data-language-status", INDEX_HTML)
        self.assertIn("languageStatusFilter", INDEX_HTML)
        self.assertIn("renderLanguageStatusFilters", INDEX_HTML)
        self.assertIn("renderLanguageConditionFilters", INDEX_HTML)
        self.assertIn("renderLanguageDiffCards", INDEX_HTML)
        self.assertIn("language-diff-card", INDEX_HTML)
        self.assertIn('id="language-preview-summary"', INDEX_HTML)
        self.assertIn("renderLanguagePreviewSummary", INDEX_HTML)
        self.assertIn("diff-badge", INDEX_HTML)
        self.assertIn("issue-badge", INDEX_HTML)
        self.assertIn("json_metadata_preview", INDEX_HTML)
        self.assertIn('id="json-metadata-preview"', INDEX_HTML)

    def test_output_policy_can_ignore_preflight_blockers(self) -> None:
        self.assertIn('name="ignore_preflight_blockers"', INDEX_HTML)
        self.assertIn("output.ignore_preflight_blockers", INDEX_HTML)
        self.assertIn("preflight.ignored_blockers", INDEX_HTML)
        self.assertIn("ignorePreflightBlockers", INDEX_HTML)

    def test_new_workspace_filters_have_builtin_i18n_messages(self) -> None:
        zh_messages = merged_catalog("zh_cn")
        en_messages = merged_catalog("en_us")
        for key in (
            "output.ignore_preflight_blockers",
            "preflight.ignored_blockers",
            "preflight.message_total",
            "preflight.blocking_count",
            "preflight.warning_count",
            "preflight.more_messages",
            "result.condition_filter",
            "result.condition_issues",
            "result.issue_badge",
            "result.condition_changed",
            "result.condition_unchanged",
            "result.view_mode_table",
            "result.view_mode_diff",
            "settings.memory_clear_scope",
            "settings.memory_clear_confirm",
            "settings.memory_scope_empty",
        ):
            self.assertIn(key, zh_messages)
            self.assertIn(key, en_messages)

    def test_result_performance_summary_exposes_translation_memory_hits(self) -> None:
        self.assertIn("payload.memory_hits", INDEX_HTML)
        self.assertIn("result.memory_hits", INDEX_HTML)
        self.assertIn("记忆命中", INDEX_HTML)

    def test_safevault_theme_dropdown_is_exposed_in_header(self) -> None:
        self.assertIn('id="theme-picker"', INDEX_HTML)
        self.assertIn('id="theme-toggle"', INDEX_HTML)
        self.assertIn('id="theme-menu"', INDEX_HTML)
        self.assertIn('data-theme-trigger-swatches', INDEX_HTML)
        self.assertIn('role="listbox"', INDEX_HTML)
        self.assertIn("renderThemeMenu", INDEX_HTML)
        self.assertIn("themeSwatchesHtml", INDEX_HTML)
        self.assertIn("theme-group-title", INDEX_HTML)
        self.assertIn("theme-option-copy", INDEX_HTML)
        self.assertNotIn('id="settings-theme"', INDEX_HTML)
        self.assertNotIn('id="settings-theme-preview"', INDEX_HTML)

    def test_safevault_theme_catalog_is_complete(self) -> None:
        self.assertIn("themeCatalog", INDEX_HTML)
        for theme_id in (
            "light",
            "dark",
            "forest",
            "midnight",
            "dongbei-rain",
            "rainbow-rgb",
            "bleach-tybw",
            "eva",
            "starry-night",
            "monet",
            "qingming-scroll",
            "cezanne",
            "sisley",
            "pissarro",
            "morandi",
            "gauguin",
            "matisse",
            "qi-baishi",
            "p-site",
            "healing-sea-blue",
            "mint-tea-green",
            "neon-track",
            "cream-berry-purple",
            "orange-slate",
            "seafoam-apricot",
            "klein-gold",
            "honey-sunset",
            "crimson-ivory",
            "sakura-mist",
        ):
            self.assertIn(f"id: '{theme_id}'", INDEX_HTML)
            if theme_id not in {"light", "dark"}:
                self.assertIn(f':root[data-theme="{theme_id}"]', INDEX_HTML)
        self.assertIn("--sv-accent", INDEX_HTML)
        self.assertIn("--button-text", INDEX_HTML)
        self.assertIn("themeColorScheme", INDEX_HTML)

    def test_language_jar_filter_renders_nested_jar_tree(self) -> None:
        self.assertIn("buildJarFilterTree", INDEX_HTML)
        self.assertIn("renderJarTreeOptions", INDEX_HTML)
        self.assertIn("jar-tree-option", INDEX_HTML)
        self.assertIn("jarFilterMatchesEntry", INDEX_HTML)
        self.assertIn("jar.startsWith(`${jarFilter}::`)", INDEX_HTML)
        self.assertIn("ri-corner-down-right-line", INDEX_HTML)

    def test_language_jar_filter_dropdown_uses_floating_menu_state(self) -> None:
        self.assertIn('id="language-jar-filter-menu" role="listbox"', INDEX_HTML)
        self.assertIn("function bindJarFilterMenu(shell)", INDEX_HTML)
        self.assertIn("if (isMenuOpen(shell, menu)) {\n          closeMenu();", INDEX_HTML)
        self.assertIn("if (!shell.contains(event.target) && !menu.contains(event.target))", INDEX_HTML)
        self.assertIn("menu.style.minWidth =", INDEX_HTML)

    def test_results_actions_include_workspace_before_pack_download(self) -> None:
        workspace_index = INDEX_HTML.index("<button type=\"button\" data-view=\"language\"><i class=\"ri-folder-open-line\"></i><span>${escapeHtml(ui('result.workspace', '工作区'))}</span></button>")
        download_index = INDEX_HTML.index('id="download-pack"')
        self.assertLess(workspace_index, download_index)

    def test_ftbquests_mode_is_exposed_without_reusing_resource_pack_download(self) -> None:
        self.assertIn('name="input_kind" id="input_kind"', INDEX_HTML)
        self.assertIn('data-input-kind="ftbquests"', INDEX_HTML)
        self.assertIn('name="ftbquests_files"', INDEX_HTML)
        self.assertIn('id="ftbquests-directory"', INDEX_HTML)
        self.assertIn("webkitdirectory", INDEX_HTML)
        self.assertIn("file.webkitRelativePath || file.name", INDEX_HTML)
        self.assertIn('id="download-ftbquests"', INDEX_HTML)
        self.assertIn("payload.kind === 'ftbquests'", INDEX_HTML)
        self.assertIn("下载任务书补丁", INDEX_HTML)

    def test_ftbquests_snbt_upload_infers_source_locale_in_ui(self) -> None:
        self.assertIn('name="source_locale" id="source_locale"', INDEX_HTML)
        self.assertIn('<option value="en_us" selected>en_us - English (US)</option>', INDEX_HTML)
        self.assertIn("inferLocaleFromFtbquestsUploadPath", INDEX_HTML)
        self.assertIn("syncFtbquestsSourceLocaleFromInput", INDEX_HTML)
        self.assertIn("ftbquestsInput.addEventListener('change', handleFtbquestsInputChange)", INDEX_HTML)
        self.assertIn("ftbquestsDirectoryInput.addEventListener('change', handleFtbquestsInputChange)", INDEX_HTML)
        self.assertIn("const localePattern = /^[a-z]{2,3}_[a-z0-9]{2,8}$/", INDEX_HTML)

    def test_ui_locale_switching_and_extension_pack_controls_are_exposed(self) -> None:
        self.assertIn('id="ui_locale"', INDEX_HTML)
        self.assertIn('name="ui_locale" id="ui_locale_field"', INDEX_HTML)
        self.assertNotIn('select name="ui_locale" id="ui_locale"', INDEX_HTML)
        self.assertIn("mc-mod-i18n-ui-locale", INDEX_HTML)
        self.assertIn("mc-mod-i18n-ui-locale-dir", INDEX_HTML)
        self.assertIn("urlUiLocaleSetting", INDEX_HTML)
        self.assertIn("browserUiLocaleSetting", INDEX_HTML)
        self.assertIn("preferredUiLocaleSetting", INDEX_HTML)
        self.assertIn("navigator.languages", INDEX_HTML)
        self.assertIn('id="settings-ui-locale-dir"', INDEX_HTML)
        self.assertIn('id="settings-ui-locale-default"', INDEX_HTML)
        self.assertIn('id="settings-ui-locale-download"', INDEX_HTML)
        self.assertIn('id="settings-ui-locale-import"', INDEX_HTML)
        self.assertIn("fetch(`/api/ui-locales", INDEX_HTML)
        self.assertIn("/api/ui-locales/import", INDEX_HTML)
        self.assertIn("/api/ui-locales/export/", INDEX_HTML)
        self.assertIn("/api/ui-locales/check", INDEX_HTML)
        self.assertIn("/api/ui-locales/missing-template/", INDEX_HTML)
        self.assertIn("/api/ui-locales/fill/", INDEX_HTML)
        self.assertIn('id="settings-ui-locale-check-summary"', INDEX_HTML)
        self.assertIn('id="settings-ui-locale-check"', INDEX_HTML)
        self.assertIn('id="settings-ui-locale-missing-template"', INDEX_HTML)
        self.assertIn('id="settings-ui-locale-fill-en"', INDEX_HTML)
        self.assertIn('id="settings-ui-locale-fill-zh"', INDEX_HTML)
        self.assertIn("downloadFilledUiLocale", INDEX_HTML)

    def test_ui_locale_switch_refreshes_dynamic_selects_and_settings_defaults(self) -> None:
        self.assertIn("function refreshSelectMenusForCurrentLocale()", INDEX_HTML)
        self.assertIn("refreshSelectMenusForCurrentLocale();", INDEX_HTML)
        self.assertIn("providerMenu.innerHTML = Array.from(provider.options).map", INDEX_HTML)
        self.assertIn("buildUiLocaleMenu();", INDEX_HTML)
        self.assertIn("function refreshSettingsDirectoryLabels()", INDEX_HTML)
        self.assertIn("refreshSettingsDirectoryLabels();", INDEX_HTML)

    def test_direct_json_language_file_mode_is_exposed(self) -> None:
        self.assertIn('data-input-kind="json"', INDEX_HTML)
        self.assertIn('name="json_files"', INDEX_HTML)
        self.assertIn('id="json-file-wrap"', INDEX_HTML)
        self.assertIn("inputKind.value === 'json'", INDEX_HTML)
        self.assertIn("data.append('json_files'", INDEX_HTML)
        self.assertIn("payload.kind === 'json'", INDEX_HTML)

    def test_preflight_summary_is_exposed_before_translation(self) -> None:
        self.assertIn('id="preflight-panel"', INDEX_HTML)
        self.assertIn('id="preflight-run"', INDEX_HTML)
        self.assertIn('id="preflight-message-summary"', INDEX_HTML)
        self.assertIn('id="preflight-callout"', INDEX_HTML)
        self.assertIn("PREVIEW_PREFLIGHT_MESSAGE_LIMIT", INDEX_HTML)
        self.assertIn("renderPreflightMessageSummary", INDEX_HTML)
        self.assertIn("syncSubmitStateFromPreflight", INDEX_HTML)
        self.assertIn("preflight-list-collapsed", INDEX_HTML)
        self.assertIn("runPreflight", INDEX_HTML)
        self.assertIn("renderPreflight", INDEX_HTML)
        self.assertIn("fetch('/api/preflight'", INDEX_HTML)
        self.assertIn("preflight.blocked", INDEX_HTML)
        self.assertIn("preflight.summary", INDEX_HTML)

    def test_results_prioritize_failures_and_risk_actions(self) -> None:
        self.assertIn('id="result-priority-actions"', INDEX_HTML)
        self.assertIn("renderResultPriorityActions", INDEX_HTML)
        self.assertIn("result.priority_failed", INDEX_HTML)
        self.assertIn("result.priority_risk", INDEX_HTML)

    def test_advanced_api_help_uses_focus_popover_motion(self) -> None:
        self.assertIn(".api-box label:focus-within .field-help", INDEX_HTML)
        self.assertIn("transform: translateY(-6px) scale(.98)", INDEX_HTML)
        self.assertIn("transition: opacity var(--motion-base) ease", INDEX_HTML)

    def test_api_debug_log_help_is_attached_to_checkbox_label(self) -> None:
        self.assertIn('<label class="checkline api-debug-log-line">', INDEX_HTML)
        self.assertIn('<span data-i18n="advanced.debug_log">记录 API 调试日志</span>', INDEX_HTML)
        self.assertIn('<span class="field-help" data-i18n="advanced.debug_log_help">会记录请求体、响应头和原始响应到本次任务目录；Authorization/API Key 会被隐藏。</span>', INDEX_HTML)
        self.assertNotIn('</label>\n          <div class="field-help" data-i18n="advanced.debug_log_help"', INDEX_HTML)

    def test_inline_scripts_are_syntax_valid_when_node_is_available(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        scripts = re.findall(r"<script>([\s\S]*?)</script>", INDEX_HTML)
        self.assertGreaterEqual(len(scripts), 2)
        with tempfile.TemporaryDirectory() as temp_dir:
            for index, script in enumerate(scripts):
                path = Path(temp_dir) / f"inline-{index}.js"
                path.write_text(script, encoding="utf-8")
                result = subprocess.run(
                    [node, "--check", str(path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(
                    0,
                    result.returncode,
                    msg=f"inline script {index} is not valid JavaScript:\n{result.stderr}",
                )

    def test_model_list_helpers_accept_base_url_and_provider_responses(self) -> None:
        self.assertEqual(
            "https://api.openai.com/v1/models",
            normalize_models_url("https://api.openai.com/v1", "openai-compatible"),
        )
        self.assertEqual(
            "https://api.anthropic.com/v1/models",
            normalize_models_url("https://api.anthropic.com/v1/messages", "anthropic-compatible"),
        )
        models = parse_models_response('{"data":[{"id":"gpt-4o-mini"},{"id":"claude-3-5-haiku-latest","display_name":"Claude Haiku"}]}')
        self.assertEqual(
            [
                {"id": "gpt-4o-mini", "label": "gpt-4o-mini"},
                {"id": "claude-3-5-haiku-latest", "label": "Claude Haiku"},
            ],
            models,
        )


if __name__ == "__main__":
    unittest.main()
