from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

from mc_mod_i18n.ui_i18n import merged_catalog
from mc_mod_i18n.web import INDEX_HTML, normalize_models_url, parse_models_response, unique_filename


class WebUiContractTest(unittest.TestCase):
    def test_unique_filename_preserves_multiple_json_uploads(self) -> None:
        used: set[str] = set()
        self.assertEqual("en_us.json", unique_filename("en_us.json", used))
        self.assertEqual("en_us-2.json", unique_filename("en_us.json", used))
        self.assertEqual("en_us-3.json", unique_filename("folder/en_us.json", used))

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
        self.assertIn("Browser.close", script)
        self.assertIn("document.querySelectorAll('#settings-page .settings-section')", script)
        self.assertIn("Settings cards overlap", script)

    def test_sidebar_brand_uses_translation_workbench_name(self) -> None:
        self.assertIn('alt="翻译工作台"', INDEX_HTML)
        self.assertIn('data-i18n="app.brand.name">翻译工作台</strong>', INDEX_HTML)
        self.assertNotIn('alt="汉化工作台"', INDEX_HTML)

    def test_browser_favicon_and_sidebar_logo_use_current_branding(self) -> None:
        self.assertIn('<link rel="icon" href="/assets/logo/current-favicon">', INDEX_HTML)
        self.assertNotIn('<link rel="icon" href="/assets/logo/current.ico" type="image/x-icon">', INDEX_HTML)
        self.assertIn('<div class="mark"><img src="/assets/logo/current" alt="翻译工作台"', INDEX_HTML)
        self.assertNotIn('<link rel="icon" href="/assets/co1dsand_logo_cat.ico"', INDEX_HTML)

    def test_workspace_uses_progressive_disclosure_for_advanced_settings(self) -> None:
        self.assertIn("高级 API 设置", INDEX_HTML)
        self.assertIn("输出策略", INDEX_HTML)
        self.assertIn("data-advanced-panel", INDEX_HTML)
        self.assertIn("workflow-step", INDEX_HTML)
        self.assertIn('<div class="workflow-step"><strong data-i18n="workflow.input_step">选择输入</strong></div>', INDEX_HTML)
        self.assertIn('<div class="workflow-step"><strong data-i18n="workflow.preflight_step">运行预检并开始</strong></div>', INDEX_HTML)
        self.assertNotIn('<div class="workflow-step"><span>1</span>', INDEX_HTML)
        self.assertNotIn('<div class="workflow-step"><span>4</span>', INDEX_HTML)
        self.assertNotIn('<div class="workflow-step"><span>步骤 1</span>', INDEX_HTML)
        self.assertNotIn('<div class="workflow-step"><span>步骤 4</span>', INDEX_HTML)
        self.assertIn("可选增强项", INDEX_HTML)
        self.assertIn('class="workflow-rail"', INDEX_HTML)
        self.assertIn('class="workflow-step-item"', INDEX_HTML)
        self.assertIn('class="workflow-node"', INDEX_HTML)
        self.assertIn('class="workspace-option-group workflow-step-card"', INDEX_HTML)
        self.assertIn(".workflow-step-item::before", INDEX_HTML)
        self.assertIn("background: var(--line);", INDEX_HTML)
        self.assertIn("color: var(--accent);", INDEX_HTML)
        self.assertIn('<details class="inline-advanced-panel" data-advanced-panel>', INDEX_HTML)
        self.assertIn('class="inline-advanced-panel-body"', INDEX_HTML)
        self.assertIn(".inline-advanced-panel-body > .api-box", INDEX_HTML)
        self.assertIn("background: transparent;", INDEX_HTML)
        self.assertNotIn('<details class="form-card" data-advanced-panel>', INDEX_HTML)
        self.assertNotIn('data-advanced-panel open', INDEX_HTML)

    def test_header_has_single_navigation_system(self) -> None:
        self.assertNotIn('<div class="top-tabs">', INDEX_HTML)
        self.assertNotIn('class="top-search"', INDEX_HTML)
        self.assertIn("当前任务", INDEX_HTML)

    def test_side_nav_report_and_hardcoded_switch_result_views(self) -> None:
        self.assertIn("if (['language', 'report', 'hardcoded', 'api-log'].includes(view))", INDEX_HTML)
        self.assertIn("resultState.resultView = view;", INDEX_HTML)
        self.assertIn('data-view="report"', INDEX_HTML)
        self.assertIn('data-view="hardcoded"', INDEX_HTML)

    def test_new_running_job_cannot_repaint_previous_completed_result(self) -> None:
        self.assertIn("function clearCurrentResultForNewJob()", INDEX_HTML)
        self.assertIn("resultState.payload = null;", INDEX_HTML)
        self.assertIn("clearCurrentResultForNewJob();\n      startLoading();", INDEX_HTML)
        self.assertIn("function isCurrentResultPayload(payload = resultState.payload)", INDEX_HTML)
        self.assertIn("return Boolean(payload) && (!activeJobId || payload.job_id === activeJobId);", INDEX_HTML)
        self.assertIn("if (isCurrentResultPayload()) {\n        renderResultShell();", INDEX_HTML)
        self.assertIn("} else if (isCurrentResultPayload()) {\n        renderResultShell();", INDEX_HTML)

    def test_result_summary_uses_clickable_cards_with_details(self) -> None:
        self.assertIn('class="summary-card"', INDEX_HTML)
        self.assertIn('data-summary-card="${escapeHtml(card.key)}"', INDEX_HTML)
        self.assertIn('aria-haspopup="dialog"', INDEX_HTML)
        self.assertIn("bindResultSummaryCards", INDEX_HTML)
        self.assertIn('class="summary-popover"', INDEX_HTML)
        self.assertIn(".summary-popover[hidden]", INDEX_HTML)
        self.assertIn('role="dialog"', INDEX_HTML)
        self.assertIn('data-summary-close', INDEX_HTML)
        self.assertIn('data-summary-popover="${escapeHtml(card.key)}"', INDEX_HTML)
        self.assertIn("closeSummaryPopover();", INDEX_HTML)
        self.assertIn("bindSummaryOutsideClose", INDEX_HTML)
        self.assertIn("event.target.closest('[data-summary-card], [data-summary-popover]')", INDEX_HTML)
        self.assertIn("event.key === 'Escape'", INDEX_HTML)
        self.assertNotIn("positionSummaryPopover(key);\n        });\n      });", INDEX_HTML)
        self.assertNotIn('class="summary-modal-backdrop"', INDEX_HTML)
        self.assertNotIn('class="summary-modal"', INDEX_HTML)
        self.assertNotIn('class="summary-detail"', INDEX_HTML)
        self.assertIn("result.processed_jars", INDEX_HTML)
        self.assertIn("result.new_translation_entries", INDEX_HTML)
        self.assertIn("result.average_elapsed", INDEX_HTML)
        self.assertIn("result.report_generated", INDEX_HTML)
        self.assertIn("已处理 JAR", INDEX_HTML)
        self.assertIn("新增翻译条目", INDEX_HTML)
        self.assertIn("平均耗时", INDEX_HTML)
        self.assertIn("报告生成", INDEX_HTML)

    def test_result_priority_area_surfaces_download_failures_and_review(self) -> None:
        self.assertNotIn("${renderResultPriorityActions(payload)}", INDEX_HTML)
        self.assertIn('class="status error api-failure-notice"', INDEX_HTML)
        self.assertIn('class="api-failure-copy"', INDEX_HTML)
        self.assertIn("result.api_failure_title", INDEX_HTML)
        self.assertIn("result.api_failure_action", INDEX_HTML)
        self.assertIn('class="danger-button" id="retry-api-failures"', INDEX_HTML)
        self.assertNotIn("result.ready_to_download", INDEX_HTML)
        self.assertNotIn("renderResultPriorityActions", INDEX_HTML)
        self.assertNotIn("result.priority_failures_desc", INDEX_HTML)
        self.assertNotIn('data-priority-filter="issues"', INDEX_HTML)
        self.assertNotIn('data-priority-review="diff"', INDEX_HTML)
        self.assertIn("resultState.languageViewMode = hasIssueEntries(payload) ? 'diff' : 'table';", INDEX_HTML)

    def test_retry_failed_items_reuses_loading_progress_panel(self) -> None:
        self.assertIn("startLoading({", INDEX_HTML)
        self.assertIn("mode: 'retry'", INDEX_HTML)
        self.assertIn("retryActiveJobId", INDEX_HTML)
        self.assertIn("retry_job_id", INDEX_HTML)
        self.assertIn("startProgressPolling(retryPayload.retry_job_id", INDEX_HTML)
        self.assertIn("loading.mode.retry", INDEX_HTML)
        self.assertIn("loading.retry_item_progress", INDEX_HTML)

    def test_result_language_tabs_live_in_card_header(self) -> None:
        self.assertIn('<div class="view-head">\n                <div class="view-head-main">', INDEX_HTML)
        self.assertIn('<div class="tabs">\n                    <button type="button" data-result-tab="language"', INDEX_HTML)
        self.assertNotIn('<div class="view-body">\n                <div class="tabs">', INDEX_HTML)
        self.assertIn(".view-head .tabs", INDEX_HTML)
        self.assertIn(".view-head-side", INDEX_HTML)
        self.assertIn("function setResultView(view)", INDEX_HTML)
        self.assertIn("switchView(nextView);", INDEX_HTML)
        self.assertIn("event.stopPropagation();", INDEX_HTML)

    def test_language_controls_support_minecraft_locale_input(self) -> None:
        self.assertIn("minecraftLocales", INDEX_HTML)
        source = Path(__file__).resolve().parents[1] / "src" / "mc_mod_i18n" / "web.py"
        text = source.read_text(encoding="utf-8")
        self.assertIn("MINECRAFT_LOCALES_JSON", text)
        self.assertIn('const minecraftLocales = __MINECRAFT_LOCALES_JSON__;', text)
        self.assertNotIn('["zh_tw", "繁體中文"]', text)
        self.assertNotIn('["zh_hk", "繁體中文（香港）"]', text)
        self.assertIn("locale-control-input", INDEX_HTML)
        self.assertIn("data-locale-control-search", INDEX_HTML)
        self.assertIn("data-locale-apply", INDEX_HTML)
        self.assertIn("data-locale-options", INDEX_HTML)
        self.assertIn("localeMatchesOption", INDEX_HTML)
        self.assertIn("refreshLocaleMenuSearch", INDEX_HTML)
        self.assertIn("没有匹配的内置语言", INDEX_HTML)

    def test_ui_locale_settings_reuses_target_language_catalog(self) -> None:
        source = Path(__file__).resolve().parents[1] / "src" / "mc_mod_i18n" / "web.py"
        text = source.read_text(encoding="utf-8")
        self.assertIn("for option in list_ui_locales(root)", text)
        self.assertIn("minecraft_locale_display_names()", text)
        self.assertIn("from .ui_i18n import (", text)
        self.assertNotIn("def minecraft_locale_display_names()", text)

    def test_language_dropdowns_expose_searchable_listbox_state(self) -> None:
        self.assertIn('data-select-trigger="source_locale" role="combobox" tabindex="0" aria-haspopup="listbox" aria-expanded="false" aria-controls="source-locale-menu"', INDEX_HTML)
        self.assertIn('data-select-trigger="target_locale" role="combobox" tabindex="0" aria-haspopup="listbox" aria-expanded="false" aria-controls="target-locale-menu"', INDEX_HTML)
        self.assertIn('id="source-locale-menu" role="listbox"', INDEX_HTML)
        self.assertIn('id="target-locale-menu" role="listbox"', INDEX_HTML)
        self.assertIn('type="search" class="locale-control-input"', INDEX_HTML)
        self.assertNotIn('class="ghost-menu-input"', INDEX_HTML)

    def test_provider_list_is_limited_to_manual_and_compatible_api_options(self) -> None:
        self.assertIn('<option value="glossary" data-i18n="provider.glossary">离线术语表（有限）</option>', INDEX_HTML)
        self.assertIn('<option value="copy" data-i18n="provider.copy">复制原文</option>', INDEX_HTML)
        self.assertIn('<option value="deep-free" data-i18n="provider.deep-free">Deep Translator（免费试用）</option>', INDEX_HTML)
        self.assertIn('<option value="azure-translator" data-i18n="provider.azure-translator">Azure Translator</option>', INDEX_HTML)
        self.assertIn('<option value="openai-compatible" data-i18n="provider.openai-compatible">兼容 OpenAI</option>', INDEX_HTML)
        self.assertIn('<option value="anthropic-compatible" data-i18n="provider.anthropic-compatible">兼容 Anthropic</option>', INDEX_HTML)
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
        self.assertIn('name="ignore_translation_memory"', INDEX_HTML)
        self.assertIn("忽略缓存并重新翻译", INDEX_HTML)
        self.assertIn("忽略翻译记忆命中", INDEX_HTML)
        self.assertIn("progress-full", INDEX_HTML)
        self.assertIn('classList.toggle(\'indeterminate\'', INDEX_HTML)

    def test_settings_menu_exposes_cache_management(self) -> None:
        self.assertIn('id="settings-open"', INDEX_HTML)
        self.assertIn('id="settings-page"', INDEX_HTML)
        self.assertIn('data-main-view="settings"', INDEX_HTML)
        self.assertIn('class="settings-layout"', INDEX_HTML)
        self.assertIn('class="settings-nav"', INDEX_HTML)
        self.assertIn('class="settings-content"', INDEX_HTML)
        self.assertIn('data-settings-target="settings-cache-section"', INDEX_HTML)
        self.assertIn('data-settings-target="settings-presets-section"', INDEX_HTML)
        self.assertIn("function switchSettingsSection", INDEX_HTML)
        self.assertIn('id="settings-cache-section"', INDEX_HTML)
        self.assertIn('id="settings-locale-section"', INDEX_HTML)
        self.assertIn('class="active" data-settings-target="settings-system-section"', INDEX_HTML)
        self.assertIn('id="settings-cache-section" aria-labelledby="settings-cache-title" hidden', INDEX_HTML)
        self.assertIn('class="settings-footer"', INDEX_HTML)
        self.assertIn(".settings-layout", INDEX_HTML)
        self.assertIn(".settings-section-actions", INDEX_HTML)
        self.assertIn('id="settings-data-dir"', INDEX_HTML)
        self.assertIn('id="settings-default-cache-dir"', INDEX_HTML)
        self.assertIn('id="settings-default-ui-locale-dir"', INDEX_HTML)
        self.assertIn("data_dir", INDEX_HTML)
        self.assertIn("default_cache_dir", INDEX_HTML)
        self.assertIn("default_ui_locale_dir", INDEX_HTML)
        self.assertIn('id="settings-cache-dir"', INDEX_HTML)
        self.assertIn('id="settings-cache-clear"', INDEX_HTML)
        self.assertIn('id="settings-cache-default"', INDEX_HTML)
        self.assertIn('name="cache_dir" id="cache_dir"', INDEX_HTML)
        self.assertIn("CACHE_DIR_STORAGE_KEY", INDEX_HTML)
        self.assertIn("fetch('/api/cache/clear'", INDEX_HTML)

    def test_settings_menu_exposes_system_branding(self) -> None:
        self.assertIn('data-settings-target="settings-system-section"', INDEX_HTML)
        self.assertIn('id="settings-system-section"', INDEX_HTML)
        self.assertIn('data-i18n="settings.system_section">系统设置</span>', INDEX_HTML)
        self.assertIn('id="settings-branding-options"', INDEX_HTML)
        self.assertIn('data-brand-logo="cat"', INDEX_HTML)
        self.assertIn('data-brand-logo="grass"', INDEX_HTML)
        self.assertIn('data-brand-logo="sign"', INDEX_HTML)
        self.assertIn("猫猫头像", INDEX_HTML)
        self.assertIn("草方块", INDEX_HTML)
        self.assertIn("签名标识", INDEX_HTML)
        self.assertIn("function loadSystemSettings", INDEX_HTML)
        self.assertIn("function saveSystemSettings", INDEX_HTML)
        self.assertIn("function applyBrandingChoice", INDEX_HTML)
        self.assertIn("fetch('/api/system-settings'", INDEX_HTML)
        self.assertIn("/assets/logo/current", INDEX_HTML)
        self.assertIn("/assets/logo/current-favicon", INDEX_HTML)

    def test_branding_cards_use_stable_preview_and_copy_cells(self) -> None:
        self.assertIn('<span class="branding-preview"><img src="/assets/logo/cat.png" alt=""></span>', INDEX_HTML)
        self.assertIn('<span class="branding-preview"><img src="/assets/logo/grass.png" alt=""></span>', INDEX_HTML)
        self.assertIn('<span class="branding-preview"><img src="/assets/logo/sign.png" alt=""></span>', INDEX_HTML)
        self.assertIn('<span class="branding-copy">', INDEX_HTML)
        self.assertIn(".branding-preview {", INDEX_HTML)
        self.assertIn("place-items: center;", INDEX_HTML)
        self.assertIn(".branding-preview img {", INDEX_HTML)
        self.assertIn("max-width: 36px;", INDEX_HTML)
        self.assertIn("max-height: 36px;", INDEX_HTML)
        self.assertIn(".branding-copy {", INDEX_HTML)
        self.assertNotIn(".branding-option span {\n      display: block;", INDEX_HTML)

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
        self.assertIn('id="settings-preset-select-shell"', INDEX_HTML)
        self.assertIn('id="settings-preset-menu" role="listbox"', INDEX_HTML)
        self.assertIn('data-select-trigger="settings_preset"', INDEX_HTML)
        self.assertIn('data-preset-value="${escapeHtml(item.name)}"', INDEX_HTML)
        self.assertIn("bindSettingsPresetMenu", INDEX_HTML)
        self.assertIn("syncSettingsPresetDisplay", INDEX_HTML)
        self.assertIn("settings.preset_empty", INDEX_HTML)
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
        self.assertIn("grid-template-columns: 220px minmax(0, 1fr);", INDEX_HTML)
        self.assertIn(".settings-nav", INDEX_HTML)
        self.assertIn(".settings-content", INDEX_HTML)
        self.assertIn(".settings-section[hidden]", INDEX_HTML)
        self.assertIn("align-content: start;", INDEX_HTML)
        self.assertIn("min-width: 0;", INDEX_HTML)
        self.assertIn("height: fit-content;", INDEX_HTML)
        self.assertIn("@media (max-width: 1120px)", INDEX_HTML)

    def test_desktop_zoom_uses_compensated_viewport_height(self) -> None:
        self.assertIn("--app-vh: var(--desktop-vh, 100vh);", INDEX_HTML)
        self.assertIn("min-height: var(--app-vh);", INDEX_HTML)
        self.assertIn("height: var(--app-vh);", INDEX_HTML)
        self.assertIn("max-height: calc(var(--app-vh) - 104px);", INDEX_HTML)

    def test_task_history_view_is_exposed(self) -> None:
        self.assertIn('data-view="history"', INDEX_HTML)
        self.assertIn('id="history-panel"', INDEX_HTML)
        self.assertIn('id="history-status-filter-shell"', INDEX_HTML)
        self.assertIn('id="history-status-filter"', INDEX_HTML)
        self.assertIn('id="history-status-filter-menu"', INDEX_HTML)
        self.assertIn('id="history-kind-filter-shell"', INDEX_HTML)
        self.assertIn('id="history-kind-filter"', INDEX_HTML)
        self.assertIn('id="history-kind-filter-menu"', INDEX_HTML)
        self.assertIn('id="history-search"', INDEX_HTML)
        self.assertIn('id="history-stats"', INDEX_HTML)
        self.assertIn('id="history-detail"', INDEX_HTML)
        self.assertIn('class="history-workbench"', INDEX_HTML)
        self.assertIn('class="history-stage"', INDEX_HTML)
        self.assertIn('class="history-master"', INDEX_HTML)
        self.assertIn('class="history-detail"', INDEX_HTML)
        self.assertIn("bindSelectMenu(historyStatusFilterShell", INDEX_HTML)
        self.assertIn('data-select-trigger="history_status" role="combobox" tabindex="0" aria-haspopup="listbox"', INDEX_HTML)
        self.assertIn('data-select-trigger="history_kind" role="combobox" tabindex="0" aria-haspopup="listbox"', INDEX_HTML)
        self.assertIn('data-select-value="${escapeHtml(name)}" data-value="${escapeHtml(option.value)}" role="option"', INDEX_HTML)
        self.assertIn("loadJobHistory", INDEX_HTML)
        self.assertIn("renderJobHistory", INDEX_HTML)
        self.assertIn("renderJobHistoryDetail", INDEX_HTML)
        self.assertIn("renderHistoryStats", INDEX_HTML)
        self.assertIn("historyRecordHaystack", INDEX_HTML)
        self.assertIn("fetch('/api/jobs'", INDEX_HTML)
        self.assertIn("nav.history", INDEX_HTML)
        self.assertIn("download_status", INDEX_HTML)
        self.assertIn("history-download-missing", INDEX_HTML)
        self.assertIn("history.file_missing", INDEX_HTML)

    def test_history_artifacts_list_scrolls_inside_task_detail(self) -> None:
        self.assertIn(".history-detail-body {\n      min-height: 0;\n      display: flex;", INDEX_HTML)
        self.assertIn("flex-direction: column;", INDEX_HTML)
        self.assertIn("overflow-y: auto;", INDEX_HTML)
        self.assertIn(".history-detail-body > * {\n      flex: 0 0 auto;", INDEX_HTML)
        self.assertIn(".history-artifacts {\n      display: grid;\n      grid-template-rows: auto auto;", INDEX_HTML)
        self.assertNotIn(".history-artifacts {\n      display: grid;\n      grid-template-rows: auto auto;\n      overflow: hidden;", INDEX_HTML)
        self.assertIn(".history-artifacts-list {\n      min-height: 0;", INDEX_HTML)
        self.assertNotIn("max-height: clamp(220px, 34vh, 420px);", INDEX_HTML)
        self.assertIn("overflow: visible;", INDEX_HTML)
        self.assertIn("class=\"history-artifacts-list\"", INDEX_HTML)
        self.assertIn(".history-page {\n        height: auto;\n        max-height: none;\n        overflow: visible;", INDEX_HTML)
        self.assertIn(".history-detail-body {\n        overflow: visible;", INDEX_HTML)

    def test_docs_and_help_views_are_exposed(self) -> None:
        self.assertIn('data-view="docs"', INDEX_HTML)
        self.assertIn('data-view="help"', INDEX_HTML)
        self.assertIn('id="docs-panel"', INDEX_HTML)
        self.assertIn('id="help-panel"', INDEX_HTML)
        self.assertIn('id="docs-search"', INDEX_HTML)
        self.assertIn('id="docs-list"', INDEX_HTML)
        self.assertIn('id="docs-content"', INDEX_HTML)
        self.assertIn('id="docs-related"', INDEX_HTML)
        self.assertIn('id="docs-meta"', INDEX_HTML)
        self.assertIn('id="help-topics"', INDEX_HTML)
        self.assertIn('id="help-doc-preview"', INDEX_HTML)
        self.assertIn("loadDocsIndex", INDEX_HTML)
        self.assertIn("loadDocDetail", INDEX_HTML)
        self.assertIn("renderDocsList(docsSearch.value)", INDEX_HTML)
        self.assertIn("openDocView", INDEX_HTML)
        self.assertIn("renderHelpTopics", INDEX_HTML)
        self.assertIn("renderDocMeta(payload)", INDEX_HTML)
        self.assertIn("renderRelatedDocs(payload.related_topics)", INDEX_HTML)
        self.assertIn("const queryKey = docsLocaleQuery();", INDEX_HTML)
        self.assertIn("fetch(`/api/docs${queryKey}`)", INDEX_HTML)
        self.assertIn("fetch(`/api/docs/${encodeURIComponent(slug)}${docsLocaleQuery()}`)", INDEX_HTML)
        self.assertIn("data-doc-target", INDEX_HTML)

    def test_docs_and_help_shell_text_uses_ui_locale_messages(self) -> None:
        for snippet in (
            'data-i18n="docs.subtitle"',
            'data-i18n="docs.directory"',
            'data-i18n="docs.filter_hint"',
            'data-i18n="docs.search"',
            'data-i18n-placeholder="docs.search_placeholder"',
            'data-i18n="docs.select_prompt"',
            'data-i18n="docs.detail"',
            'data-i18n="docs.related_topics"',
            'data-i18n="help.subtitle"',
            'data-i18n="help.quick_check"',
            'data-i18n="help.quick_check_subtitle"',
        ):
            self.assertIn(snippet, INDEX_HTML)

    def test_ui_locale_switch_reloads_docs_and_help_content(self) -> None:
        self.assertIn("function docsLocaleQuery()", INDEX_HTML)
        self.assertIn("const params = new URLSearchParams();", INDEX_HTML)
        self.assertIn("params.set('ui_locale', uiLocale.value || 'zh_cn');", INDEX_HTML)
        self.assertIn("params.set('ui_locale_dir', dir);", INDEX_HTML)
        self.assertIn("function resetDocsLocaleCache()", INDEX_HTML)
        self.assertIn("docsIndex = [];", INDEX_HTML)
        self.assertIn("docsIndexCacheKey = '';", INDEX_HTML)
        self.assertIn("docDetailCache.clear();", INDEX_HTML)
        self.assertIn("renderDocsList(docsSearch.value);", INDEX_HTML)
        self.assertIn("renderHelpTopics();", INDEX_HTML)
        self.assertIn("function refreshDocsForCurrentLocale()", INDEX_HTML)
        self.assertIn("resetDocsLocaleCache();", INDEX_HTML)
        self.assertIn("refreshDocsForCurrentLocale();", INDEX_HTML)
        self.assertIn("const cacheKey = `${docsLocaleQuery()}:${String(slug || '').trim()}`;", INDEX_HTML)
        self.assertIn("renderHelpTopics();", INDEX_HTML)

    def test_docs_index_cache_is_scoped_to_current_locale_query(self) -> None:
        self.assertIn("let docsIndexCacheKey = '';", INDEX_HTML)
        self.assertIn("let docsIndexLoadToken = 0;", INDEX_HTML)
        self.assertIn("const queryKey = docsLocaleQuery();", INDEX_HTML)
        self.assertIn("if (docsIndex.length && docsIndexCacheKey === queryKey) {", INDEX_HTML)
        self.assertIn("const requestToken = ++docsIndexLoadToken;", INDEX_HTML)
        self.assertIn("if (requestToken !== docsIndexLoadToken || queryKey !== docsLocaleQuery()) {", INDEX_HTML)
        self.assertIn("docsIndexCacheKey = queryKey;", INDEX_HTML)

    def test_workspace_context_help_links_point_to_docs(self) -> None:
        self.assertIn('id="provider-doc-link"', INDEX_HTML)
        self.assertIn('id="preflight-doc-link"', INDEX_HTML)
        self.assertIn('id="output-doc-link"', INDEX_HTML)
        self.assertIn('id="memory-doc-link"', INDEX_HTML)
        self.assertIn("bindDocTriggers()", INDEX_HTML)
        self.assertIn("providerRiskBanner.innerHTML", INDEX_HTML)
        self.assertIn("preflightCallout.innerHTML", INDEX_HTML)

    def test_history_report_and_api_log_views_link_to_docs(self) -> None:
        self.assertIn('id="history-doc-link"', INDEX_HTML)
        self.assertIn('id="report-doc-link"', INDEX_HTML)
        self.assertIn('id="api-log-doc-link"', INDEX_HTML)
        self.assertIn('data-doc-target="history-and-report"', INDEX_HTML)
        self.assertIn("bindDocTriggers();", INDEX_HTML)

    def test_provider_test_status_can_render_help_action_for_failures(self) -> None:
        self.assertIn("provider-test-status.error.with-help", INDEX_HTML)
        self.assertIn("renderProviderTestStatus", INDEX_HTML)
        self.assertIn("providerTestHelpSlug", INDEX_HTML)
        self.assertIn("data-provider-test-help", INDEX_HTML)

    def test_docs_help_actions_use_high_contrast_card_and_button_styles(self) -> None:
        self.assertIn(".docs-link {\n      display: grid;", INDEX_HTML)
        self.assertIn("padding: 10px 14px;", INDEX_HTML)
        self.assertIn("border: 1px solid var(--card-border);", INDEX_HTML)
        self.assertIn("background: var(--field-bg);", INDEX_HTML)
        self.assertIn("transition: border-color var(--motion-fast) ease, background var(--motion-fast) ease, box-shadow var(--motion-fast) ease, transform var(--motion-fast) ease;", INDEX_HTML)
        self.assertIn(".docs-link:hover:not(:disabled) {\n      border-color: var(--field-border-hover);", INDEX_HTML)
        self.assertIn(".docs-link span {\n      color: var(--text);", INDEX_HTML)
        self.assertIn("opacity: .72;", INDEX_HTML)
        self.assertIn(".doc-jump-row .secondary,\n    .provider-test-status.error.with-help button {", INDEX_HTML)
        self.assertIn("background: var(--accent-soft);", INDEX_HTML)
        self.assertIn("color: var(--accent);", INDEX_HTML)
        self.assertIn("border: 1px solid var(--accent-soft-line);", INDEX_HTML)

    def test_docs_and_help_center_upgrade_use_theme_driven_workspace_layout(self) -> None:
        self.assertIn(".docs-page-shell {\n      display: grid;", INDEX_HTML)
        self.assertIn("background: linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, var(--surface)));", INDEX_HTML)
        self.assertIn(".docs-stage {\n      min-height: 0;", INDEX_HTML)
        self.assertIn("grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);", INDEX_HTML)
        self.assertIn(".docs-sidebar {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".docs-sidebar-body {\n      min-height: 0;", INDEX_HTML)
        self.assertIn("overflow-y: auto;", INDEX_HTML)
        self.assertIn(".docs-detail {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".docs-body {\n      display: grid;", INDEX_HTML)
        self.assertIn(".docs-related {\n      display: flex;", INDEX_HTML)
        self.assertIn(".docs-chip {\n      display: inline-flex;", INDEX_HTML)
        self.assertIn(".help-topic-grid {\n      display: grid;", INDEX_HTML)
        self.assertIn(".help-preview-card {\n      display: grid;", INDEX_HTML)
        self.assertIn(".help-topic-link {\n      position: relative;", INDEX_HTML)
        self.assertIn(".help-topic-link::after {", INDEX_HTML)

    def test_docs_center_reserves_theme_color_for_active_selection_feedback(self) -> None:
        self.assertIn("let activeHelpSlug = 'quick-start';", INDEX_HTML)
        self.assertIn("class=\"secondary docs-link help-topic-link ${item.slug === activeHelpSlug ? 'active' : ''}\"", INDEX_HTML)
        self.assertIn("activeHelpSlug = slug || 'quick-start';", INDEX_HTML)
        self.assertIn(".secondary.docs-link {\n      border-color: var(--card-border);\n      background: var(--panel);", INDEX_HTML)
        self.assertIn(".docs-link.active:hover:not(:disabled),\n    .secondary.docs-link.active:hover:not(:disabled) {\n      border-color: var(--accent);", INDEX_HTML)
        self.assertIn("transition: border-color 120ms ease-out, background-color 120ms ease-out, color 100ms ease-out;", INDEX_HTML)
        self.assertIn(".help-topic-link.active::after {\n      color: color-mix(in srgb, var(--button-text) 82%, transparent);", INDEX_HTML)
        self.assertIn("transform: translateX(1px);", INDEX_HTML)
        self.assertIn(".docs-link.active,\n    .secondary.docs-link.active {\n      border-color: var(--accent);", INDEX_HTML)
        self.assertIn(".docs-link.active strong {\n      color: var(--button-text);", INDEX_HTML)
        self.assertIn(".docs-link.active span {\n      color: color-mix(in srgb, var(--button-text) 90%, transparent);", INDEX_HTML)

    def test_docs_switching_reuses_loaded_index_and_caches_detail_payloads(self) -> None:
        self.assertIn("const docDetailCache = new Map();", INDEX_HTML)
        self.assertIn("if (docsIndex.length && docsIndexCacheKey === queryKey) {\n        renderDocsList(docsSearch.value);", INDEX_HTML)
        self.assertIn("let payload = cacheKey ? docDetailCache.get(cacheKey) : null;", INDEX_HTML)
        self.assertIn("docDetailCache.set(cacheKey, payload);", INDEX_HTML)

    def test_help_topics_stay_in_help_view_until_explicit_doc_open(self) -> None:
        self.assertIn("button.addEventListener('click', () => {\n          activeHelpSlug = button.dataset.helpDoc || 'quick-start';\n          renderHelpTopics();\n          renderHelpPreview(activeHelpSlug);", INDEX_HTML)
        self.assertNotIn("renderHelpTopics();\n          openDocView(button.dataset.helpDoc)", INDEX_HTML)
        self.assertIn("button.addEventListener('click', () => {\n          activeHelpSlug = button.dataset.helpRelated || activeHelpSlug;\n          renderHelpTopics();\n          renderHelpPreview(activeHelpSlug);", INDEX_HTML)
        self.assertIn("data-help-open", INDEX_HTML)
        self.assertIn("help.open_full_doc", INDEX_HTML)
        self.assertIn("docs.related_topics", INDEX_HTML)
        self.assertIn("help.topic_scenarios", INDEX_HTML)
        self.assertIn("help.quick_check", INDEX_HTML)
        self.assertIn("help.common_causes", INDEX_HTML)
        self.assertIn("help.next_steps", INDEX_HTML)

    def test_help_topic_directory_uses_localized_docs_index(self) -> None:
        self.assertIn("function preferredHelpTopicItems()", INDEX_HTML)
        self.assertIn("docsIndex.filter(item => preferredSlugs.includes(item.slug))", INDEX_HTML)
        self.assertIn("const items = preferredHelpTopicItems();", INDEX_HTML)
        self.assertNotIn("{ slug: 'quick-start', key: 'quick_start', title: '第一次使用'", INDEX_HTML)
        self.assertNotIn("summary: '先看快速开始，按最小流程跑通。'", INDEX_HTML)

    def test_progress_polling_ignores_stale_async_responses_after_completion(self) -> None:
        self.assertIn("let progressPollToken = 0;", INDEX_HTML)
        self.assertIn("const pollToken = ++progressPollToken;", INDEX_HTML)
        self.assertIn("if (pollToken !== progressPollToken || activeJobId !== jobId) {", INDEX_HTML)
        self.assertIn("progressTimer = window.setTimeout(poll, 900);", INDEX_HTML)
        self.assertNotIn("progressTimer = window.setInterval(poll, 900);", INDEX_HTML)

    def test_main_view_and_result_subview_use_separate_state_fields(self) -> None:
        self.assertIn("mainView: 'language',", INDEX_HTML)
        self.assertIn("resultView: 'language',", INDEX_HTML)
        self.assertIn("resultState.mainView = view;", INDEX_HTML)
        self.assertIn("shell.dataset.resultView === resultState.resultView", INDEX_HTML)
        self.assertIn("resultState.resultView = 'language';", INDEX_HTML)
        self.assertNotIn("resultState.activeView = view;", INDEX_HTML)

    def test_language_view_mode_has_dedicated_active_visual_state(self) -> None:
        self.assertIn(".language-view-mode button {\n      min-width: 72px;", INDEX_HTML)
        self.assertIn(".language-view-mode button.active {\n      border-color: var(--accent);", INDEX_HTML)
        self.assertIn(".language-view-mode button:not(.active):hover:not(:disabled) {", INDEX_HTML)
        self.assertIn("resultState.languageViewMode = button.dataset.languageView === 'diff' ? 'diff' : 'table';", INDEX_HTML)
        self.assertIn("renderResultShell();", INDEX_HTML)

    def test_deep_free_provider_is_library_backed_and_not_api_debug_log_driven(self) -> None:
        self.assertIn("Deep Translator（免费试用）", INDEX_HTML)
        self.assertIn("provider.value === 'deep-free'", INDEX_HTML)
        self.assertIn("provider.value === 'deep-free'", INDEX_HTML)
        self.assertIn("data-provider-field=\"api_base_url\"", INDEX_HTML)
        self.assertIn("data-provider-field=\"api_key\"", INDEX_HTML)
        self.assertIn("data-provider-field=\"api_region\"", INDEX_HTML)
        self.assertIn("data-provider-field=\"api_key_env\"", INDEX_HTML)
        self.assertIn("data-provider-field=\"api_debug_log\"", INDEX_HTML)
        self.assertIn("renderApiLogView()", INDEX_HTML)
        self.assertIn("当前翻译器通过 deep-translator 调用第三方免费引擎", INDEX_HTML)
        self.assertIn("GoogleTranslator", INDEX_HTML)
        self.assertIn("MyMemoryTranslator", INDEX_HTML)

    def test_pack_download_dialog_shows_theme_aware_manual_review_notice(self) -> None:
        self.assertIn(".pack-name-note {", INDEX_HTML)
        self.assertIn("background: var(--accent-soft);", INDEX_HTML)
        self.assertIn("border: 1px solid var(--accent-soft-line);", INDEX_HTML)
        self.assertIn("color: var(--accent);", INDEX_HTML)
        self.assertIn("animation: packDialogFadeIn var(--motion-base) ease;", INDEX_HTML)
        self.assertIn(".pack-name-card {\n      width: min(460px, 100%);", INDEX_HTML)
        self.assertIn("animation: packCardPopIn var(--motion-base) cubic-bezier(.22, 1, .36, 1);", INDEX_HTML)
        self.assertIn("任何翻译结果最好都由人工审核一遍哦", INDEX_HTML)
        self.assertIn("note.className = 'pack-name-note';", INDEX_HTML)

    def test_provider_panel_title_and_fields_change_with_deep_free(self) -> None:
        self.assertIn("providerTitle.textContent = provider.value === 'deep-free' ? ui('advanced.free_title', '免费翻译设置') : (provider.value === 'argos' ? ui('advanced.offline_title', '离线翻译设置') : ui('advanced.api_title', 'AI 接口配置'));", INDEX_HTML)
        self.assertIn("model_field: !['deep-free', 'argos', 'azure-translator', 'libretranslate'].includes(provider.value)", INDEX_HTML)
        self.assertIn("api_key: provider.value !== 'deep-free' && provider.value !== 'argos' && provider.value !== 'libretranslate'", INDEX_HTML)
        self.assertIn("api_base_url: !['deep-free', 'argos'].includes(provider.value)", INDEX_HTML)
        self.assertIn("api_debug_log: !['deep-free', 'argos', 'libretranslate'].includes(provider.value)", INDEX_HTML)
        self.assertIn("api_key_link: provider.value !== 'deep-free' && provider.value !== 'argos' && Boolean(preset?.keyUrl)", INDEX_HTML)
        self.assertIn("provider_test_row: provider.value !== 'deep-free' && provider.value !== 'argos'", INDEX_HTML)
        self.assertIn("apiBox.dataset.provider = provider.value || '';", INDEX_HTML)
        self.assertIn("providerHelp.hidden = false;", INDEX_HTML)
        self.assertIn(".api-box-head .provider-badge-wrap:focus-within .field-help,", INDEX_HTML)
        self.assertIn(".api-box-head .provider-badge[data-provider-help-active=\"true\"]:hover + .field-help,", INDEX_HTML)
        self.assertIn("providerBadge.setAttribute('data-provider-help-active', provider.value === 'deep-free' ? 'true' : 'false');", INDEX_HTML)
        self.assertIn(".api-box [data-provider-field][hidden] {\n      display: none !important;", INDEX_HTML)

    def test_provider_panel_help_popover_does_not_force_horizontal_scroll(self) -> None:
        self.assertIn(".config-panel,\n    .results-panel {\n      max-height: calc(var(--app-vh) - 104px);", INDEX_HTML)
        self.assertIn("overflow-y: auto;", INDEX_HTML)
        self.assertIn("overflow-x: hidden;", INDEX_HTML)
        self.assertIn(".provider-badge-wrap {\n      position: relative;", INDEX_HTML)
        self.assertIn("min-width: 0;", INDEX_HTML)
        self.assertIn(".api-box-head .provider-badge-wrap .field-help {\n      position: absolute;", INDEX_HTML)
        self.assertIn("width: min(420px, min(72vw, calc(100% - 12px)));", INDEX_HTML)
        self.assertNotIn(".api-box-head .provider-badge-wrap .field-help {\n      position: absolute;\n      left: 0;\n      top: calc(100% + 7px);\n      z-index: 16;\n      display: flex;\n      width: max-content;", INDEX_HTML)

    def test_loading_ai_copy_is_reserved_for_compatible_ai_providers(self) -> None:
        self.assertIn("const isAi = provider.value === 'openai-compatible' || provider.value === 'anthropic-compatible';", INDEX_HTML)
        self.assertNotIn("const isAi = Boolean(providerPresets[provider.value]);", INDEX_HTML)
        self.assertIn("translating: isAi ? ui('loading.stage.translating_ai', '正在分批调用 AI 翻译接口') : ui('loading.stage.translating', '正在生成语言文件')", INDEX_HTML)
        self.assertIn(": (isAi ? formatUi('loading.request_progress', '翻译请求 {progress}', { progress: progressText }) : ui('loading.running', '任务运行中')))));", INDEX_HTML)
        self.assertIn("const detail = isAi\n        ? formatUi('loading.detail_ai'", INDEX_HTML)
        self.assertIn(": formatUi('loading.detail', '翻译器：{provider}，{sourceLabel}：{sourceCount} 个。{cacheText}耗时 {elapsed}s。'", INDEX_HTML)

    def test_docs_sidebar_and_help_preview_are_tightened_toward_reference_density(self) -> None:
        self.assertIn(".docs-list.compact {\n      gap: 8px;", INDEX_HTML)
        self.assertIn(".docs-link {\n      display: grid;\n      align-content: center;\n      gap: 6px;", INDEX_HTML)
        self.assertIn("min-height: 72px;", INDEX_HTML)
        self.assertIn("padding: 14px 16px;", INDEX_HTML)
        self.assertIn(".docs-link strong {\n      font-size: 14px;", INDEX_HTML)
        self.assertIn(".docs-link span {\n      color: var(--text);\n      font-size: 12px;", INDEX_HTML)
        self.assertIn(".help-topic-list {\n      display: grid;\n      gap: 10px;", INDEX_HTML)
        self.assertIn(".help-preview-summary {\n      margin: 0;", INDEX_HTML)
        self.assertIn(".help-preview-checklist {\n      display: grid;", INDEX_HTML)
        self.assertIn(".help-preview-section {\n      display: grid;", INDEX_HTML)
        self.assertIn(".help-preview-actions.compact {\n      gap: 8px;", INDEX_HTML)
        self.assertIn(".help-preview-body.compact {\n      gap: 14px;", INDEX_HTML)
        self.assertIn("class=\"help-preview-body compact\"", INDEX_HTML)
        self.assertIn("class=\"help-preview-kicker\"", INDEX_HTML)
        self.assertIn("class=\"help-preview-summary\"", INDEX_HTML)
        self.assertIn("class=\"help-preview-actions compact\"", INDEX_HTML)
        self.assertIn("slice(0, 2)", INDEX_HTML)

    def test_docs_directory_matches_reference_structure_without_extra_meta_rows(self) -> None:
        self.assertIn(".docs-link {\n      display: grid;\n      align-content: center;\n      gap: 6px;", INDEX_HTML)
        self.assertIn("border-radius: 10px;", INDEX_HTML)
        self.assertIn(".docs-link strong {\n      width: 100%;\n      margin: 0;\n      overflow: hidden;", INDEX_HTML)
        self.assertIn(".docs-link span {\n      color: var(--text);\n      font-size: 12px;\n      line-height: 1.5;\n      opacity: .74;", INDEX_HTML)
        self.assertIn("white-space: nowrap;", INDEX_HTML)
        self.assertIn("text-overflow: ellipsis;", INDEX_HTML)
        self.assertIn(".help-topic-category {\n      display: inline-flex;\n      max-width: 100%;", INDEX_HTML)
        self.assertIn("overflow: hidden;", INDEX_HTML)
        self.assertNotIn("docs-link-meta", INDEX_HTML)

    def test_docs_reading_area_and_help_topic_category_hint_are_refined(self) -> None:
        self.assertIn(".docs-content {\n      display: grid;\n      gap: 14px;", INDEX_HTML)
        self.assertIn(".docs-content h1,\n    .docs-content h2,\n    .docs-content h3 {\n      margin: 0;\n      color: var(--text);", INDEX_HTML)
        self.assertIn("padding-bottom: 10px;", INDEX_HTML)
        self.assertIn("border-bottom: 1px solid color-mix(in srgb, var(--line) 82%, transparent);", INDEX_HTML)
        self.assertIn(".docs-content h2 {\n      font-size: 22px;", INDEX_HTML)
        self.assertIn(".docs-content h3 {\n      font-size: 17px;", INDEX_HTML)
        self.assertIn(".docs-content p,\n    .docs-content li {\n      color: color-mix(in srgb, var(--text) 94%, var(--muted));", INDEX_HTML)
        self.assertIn(".docs-content pre {\n      margin: 2px 0 4px;", INDEX_HTML)
        self.assertIn(".help-topic-category {\n      display: inline-flex;", INDEX_HTML)
        self.assertIn("class=\"help-topic-category\"", INDEX_HTML)
        self.assertIn("docCategoryLabel(findDocBySlug(item.slug)?.category || '')", INDEX_HTML)

    def test_history_dropdowns_can_escape_workbench_clipping(self) -> None:
        self.assertIn(".history-page {\n      overflow: hidden;", INDEX_HTML)
        self.assertIn(".history-toolbar {\n      display: grid;", INDEX_HTML)
        self.assertIn("overflow: visible;", INDEX_HTML)
        self.assertIn(".history-workbench {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".ghost-menu.is-floating", INDEX_HTML)
        self.assertIn("positionFloatingMenu", INDEX_HTML)
        self.assertIn("menu.style.position = 'fixed';", INDEX_HTML)
        self.assertIn("menu.style.left =", INDEX_HTML)
        self.assertIn("menu.style.top =", INDEX_HTML)
        self.assertIn("desktopZoomScale()", INDEX_HTML)
        self.assertIn("const cssZoom = desktopZoomScale();", INDEX_HTML)
        self.assertIn("rect.left / cssZoom", INDEX_HTML)
        self.assertIn("menu.style.maxHeight =", INDEX_HTML)
        self.assertIn("menu.style.removeProperty('position')", INDEX_HTML)
        self.assertIn("menu.style.removeProperty('max-height')", INDEX_HTML)
        self.assertNotIn("menu.style.setProperty('--dropdown-left'", INDEX_HTML)
        self.assertNotIn("menu.style.setProperty('--dropdown-max-height'", INDEX_HTML)
        self.assertIn("const openAbove = belowSpace < 180 && aboveSpace > belowSpace", INDEX_HTML)

    def test_floating_dropdowns_reposition_when_scroll_containers_move(self) -> None:
        self.assertIn("function syncFloatingMenus()", INDEX_HTML)
        self.assertIn("function scheduleFloatingMenuSync()", INDEX_HTML)
        self.assertIn("menu._floatingTrigger = anchor;", INDEX_HTML)
        self.assertIn("positionFloatingMenu(shell, menu, menu._floatingTrigger);", INDEX_HTML)
        self.assertIn("window.requestAnimationFrame(syncFloatingMenus)", INDEX_HTML)
        self.assertIn("window.addEventListener('scroll', scheduleFloatingMenuSync, true);", INDEX_HTML)
        self.assertIn("window.addEventListener('resize', scheduleFloatingMenuSync);", INDEX_HTML)
        self.assertIn("menu._floatingTrigger = null;", INDEX_HTML)

    def test_history_list_uses_master_detail_scroll_containers(self) -> None:
        self.assertIn(".history-stage {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".history-master,\n    .history-detail {\n      min-width: 0;", INDEX_HTML)
        self.assertIn(".history-list {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".history-detail-body {\n      min-height: 0;", INDEX_HTML)
        self.assertIn("display: flex;\n      flex-direction: column;", INDEX_HTML)
        self.assertIn("grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);", INDEX_HTML)
        self.assertIn("class=\"history-task-card ${isActive ? 'active' : ''}\"", INDEX_HTML)
        self.assertIn("class=\"history-artifacts\"", INDEX_HTML)
        self.assertIn('overflow-y: auto;', INDEX_HTML)

    def test_history_task_titles_render_primary_input_without_single_line_clamp(self) -> None:
        self.assertIn("record.primary_input", INDEX_HTML)
        self.assertIn("const title = record.primary_input || historyKindLabel(record.input_kind);", INDEX_HTML)
        self.assertIn("return providerName ? `${title} · ${providerName}` : title;", INDEX_HTML)
        self.assertIn(".history-task-title {\n      display: -webkit-box;", INDEX_HTML)
        self.assertIn("-webkit-line-clamp: 2;", INDEX_HTML)
        self.assertNotIn(".history-task-title,\n    .history-task-id,\n    .history-task-meta,", INDEX_HTML)

    def test_history_cards_keep_status_and_progress_text_fully_visible(self) -> None:
        self.assertIn(".history-status-chip {\n      display: inline-flex;", INDEX_HTML)
        self.assertIn("padding: 4px 9px;", INDEX_HTML)
        self.assertIn("line-height: 1.25;", INDEX_HTML)
        self.assertIn(".history-progress-text {\n      display: flex;", INDEX_HTML)
        self.assertIn("align-items: center;", INDEX_HTML)
        self.assertIn("line-height: 1.4;", INDEX_HTML)
        self.assertNotIn(".history-status-chip {\n      display: inline-flex;\n      align-items: center;\n      gap: 5px;\n      min-height: 24px;\n      padding: 0 9px;", INDEX_HTML)

    def test_history_active_card_uses_stronger_selection_motion(self) -> None:
        self.assertIn(".history-task-card {\n      width: 100%;", INDEX_HTML)
        self.assertIn("transition: background-color 140ms ease-out, border-color 140ms ease-out, color 120ms ease-out, transform 160ms ease-out, box-shadow 160ms ease-out;", INDEX_HTML)
        self.assertIn(".history-task-card.active {\n      border-left-color: var(--accent);", INDEX_HTML)
        self.assertIn("box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 22%, transparent);", INDEX_HTML)
        self.assertIn("transform: translateX(4px);", INDEX_HTML)

    def test_history_artifact_rows_use_left_aligned_three_column_layout(self) -> None:
        self.assertIn(".history-artifact-row {\n      display: grid;", INDEX_HTML)
        self.assertIn("grid-template-columns: 40px minmax(0, 1fr) auto;", INDEX_HTML)
        self.assertIn("align-items: center;", INDEX_HTML)
        self.assertIn(".history-artifact-copy {\n      min-width: 0;", INDEX_HTML)
        self.assertIn("justify-items: start;", INDEX_HTML)
        self.assertIn("text-align: left;", INDEX_HTML)

    def test_history_time_format_omits_utc_suffix_marker(self) -> None:
        self.assertIn("return new Date(text).toLocaleString('sv-SE', { hour12: false }).replace(',', '') + `.${String(date.getMilliseconds()).padStart(3, '0')}`;", INDEX_HTML)
        self.assertNotIn("return text.replace('T', ' ').replace(/\\+00:00$/, ' UTC').replace(/Z$/, '');", INDEX_HTML)

    def test_ghost_dropdowns_have_consistent_motion(self) -> None:
        self.assertIn("--dropdown-motion-offset", INDEX_HTML)
        self.assertIn("transition: opacity var(--motion-base) ease, visibility var(--motion-base) ease, transform var(--motion-base) ease", INDEX_HTML)
        self.assertIn(".ghost-select.open .ghost-menu", INDEX_HTML)
        self.assertIn("scheduleMenuHide", INDEX_HTML)
        self.assertIn("cancelMenuHide", INDEX_HTML)
        self.assertIn(".ghost-menu.is-closing", INDEX_HTML)
        self.assertIn(".ghost-select .chevron", INDEX_HTML)
        self.assertIn("@media (prefers-reduced-motion: reduce)", INDEX_HTML)

    def test_long_dropdown_labels_do_not_expand_workspace_cards(self) -> None:
        self.assertIn(".grid-2 > *,\n    .grid-3 > * {\n      min-width: 0;", INDEX_HTML)
        self.assertIn(".ghost-select,\n    .ghost-file {\n      position: relative;\n      display: grid;\n      gap: 6px;\n      min-width: 0;", INDEX_HTML)
        self.assertIn(".ghost-select .control,\n    .ghost-file .control {\n      display: flex;\n      align-items: center;\n      justify-content: space-between;\n      gap: 12px;\n      min-width: 0;", INDEX_HTML)
        self.assertIn("max-width: 100%;\n      box-sizing: border-box;\n      cursor: pointer;", INDEX_HTML)
        self.assertIn(".ghost-menu {\n      position: absolute;", INDEX_HTML)
        self.assertIn("min-width: 0;\n      max-width: 100%;\n      box-sizing: border-box;\n      max-height: 280px;", INDEX_HTML)
        self.assertIn("width: 100%;\n      min-width: 0;\n      max-width: 100%;\n      box-sizing: border-box;", INDEX_HTML)
        self.assertIn(".ghost-option strong,\n    .ghost-option span {\n      min-width: 0;\n      overflow: hidden;\n      text-overflow: ellipsis;", INDEX_HTML)

    def test_failed_retry_controls_and_status_trace_are_exposed(self) -> None:
        self.assertIn('id="retry-api-failures"', INDEX_HTML)
        self.assertIn("retryApiFailures", INDEX_HTML)
        self.assertIn("fetch(`/api/retry/${encodeURIComponent", INDEX_HTML)
        self.assertIn("retryStatusDetail", INDEX_HTML)
        self.assertIn("retry_previous_status", INDEX_HTML)
        self.assertIn("result.retry_status_detail", INDEX_HTML)

    def test_result_report_export_actions_are_removed_from_primary_actions(self) -> None:
        self.assertNotIn('id="export-report-json"', INDEX_HTML)
        self.assertNotIn('id="export-report-csv"', INDEX_HTML)
        self.assertNotIn('id="export-failed-json"', INDEX_HTML)
        self.assertIn("exportReportJson", INDEX_HTML)
        self.assertIn("exportReportCsv", INDEX_HTML)
        self.assertIn("exportFailedItemsJson", INDEX_HTML)
        self.assertIn("result.export_report_json", INDEX_HTML)
        self.assertIn("result.export_report_csv", INDEX_HTML)
        self.assertIn("result.export_failed_json", INDEX_HTML)

    def test_result_card_header_hosts_language_and_hardcoded_actions(self) -> None:
        self.assertIn("function renderResultHeadActions", INDEX_HTML)
        self.assertIn('class="view-head-actions"', INDEX_HTML)
        self.assertIn('id="export-language-edits"', INDEX_HTML)
        self.assertIn('id="import-hardcoded"', INDEX_HTML)
        self.assertIn('id="ai-translate-hardcoded"', INDEX_HTML)
        self.assertIn('id="export-hardcoded"', INDEX_HTML)
        self.assertIn("选择候选、AI 翻译或导出映射", INDEX_HTML)
        self.assertIn("可搜索并导出人工修改", INDEX_HTML)
        self.assertNotIn("result.hardcoded_workbench", INDEX_HTML)
        self.assertNotIn("硬编码映射工作台", INDEX_HTML)
        self.assertNotIn("hardcoded-head", INDEX_HTML)

    def test_output_preview_exposes_status_filter_diff_summary_and_json_metadata(self) -> None:
        self.assertIn('id="language-status-filter-shell"', INDEX_HTML)
        self.assertIn('id="language-status-filter-menu"', INDEX_HTML)
        self.assertIn('id="language-condition-filter-shell"', INDEX_HTML)
        self.assertIn('id="language-condition-filter-menu"', INDEX_HTML)
        self.assertIn('id="language-view-mode"', INDEX_HTML)
        self.assertIn("languageConditionFilter", INDEX_HTML)
        self.assertIn("languageViewMode", INDEX_HTML)
        self.assertIn("data-language-filter-kind", INDEX_HTML)
        self.assertIn("data-language-filter-value", INDEX_HTML)
        self.assertIn("data-language-view", INDEX_HTML)
        self.assertIn("data-language-row-issue", INDEX_HTML)
        self.assertIn("['failed', 'api_failed', 'incomplete', 'jar_failed'].includes(entry.status)", INDEX_HTML)
        self.assertIn("languageStatusFilter", INDEX_HTML)
        self.assertIn("renderLanguageStatusFilters", INDEX_HTML)
        self.assertIn("renderLanguageConditionFilters", INDEX_HTML)
        self.assertIn("bindLanguageFilterMenu", INDEX_HTML)
        self.assertIn('class="toolbar-filter-label">JAR:', INDEX_HTML)
        self.assertIn("result.translation_status_filter", INDEX_HTML)
        self.assertIn("result.text_status_filter", INDEX_HTML)
        self.assertIn("翻译状态", INDEX_HTML)
        self.assertIn("译文状态", INDEX_HTML)
        self.assertIn("renderLanguageDiffCards", INDEX_HTML)
        self.assertIn("language-diff-card", INDEX_HTML)
        self.assertNotIn('id="language-preview-summary"', INDEX_HTML)
        self.assertNotIn("renderLanguagePreviewSummary", INDEX_HTML)
        self.assertNotIn("result.preview_visible", INDEX_HTML)
        self.assertNotIn("result.preview_changed", INDEX_HTML)
        self.assertNotIn("result.preview_issues", INDEX_HTML)
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
            "action.close",
            "output.ignore_preflight_blockers",
            "preflight.ignored_blockers",
            "preflight.message_total",
            "preflight.blocking_count",
            "preflight.warning_count",
            "preflight.more_messages",
            "result.condition_filter",
            "result.translation_status_filter",
            "result.text_status_filter",
            "result.condition_issues",
            "result.issue_badge",
            "result.condition_changed",
            "result.condition_unchanged",
            "result.view_mode_table",
            "result.view_mode_diff",
            "result.api_failure_title",
            "result.api_failure_action",
            "result.processed_jars",
            "result.new_translation_entries",
            "result.average_elapsed",
            "result.report_generated",
            "status.json_locale_detected",
            "status.json_locale_conflict",
            "settings.memory_clear_scope",
            "settings.memory_clear_confirm",
            "settings.memory_scope_empty",
            "settings.preset_empty",
            "settings.preset_saved_config",
            "settings.system_section",
            "settings.data_dir",
            "settings.default_cache_dir",
            "settings.default_ui_locale_dir",
            "settings.brand_logo",
            "settings.brand_cat",
            "settings.brand_grass",
            "settings.brand_sign",
            "settings.brand_saved",
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
        source = Path(__file__).resolve().parents[1] / "src" / "mc_mod_i18n" / "web.py"
        text = source.read_text(encoding="utf-8")
        self.assertIn('INDEX_HTML = INDEX_HTML.replace("__SOURCE_LOCALE_OPTIONS_HTML__", _locale_options_html("en_us"))', text)
        self.assertNotIn('<option value="en_us" selected>en_us - English (US)</option>', text)
        self.assertIn("inferLocaleFromFtbquestsUploadPath", INDEX_HTML)
        self.assertIn("syncFtbquestsSourceLocaleFromInput", INDEX_HTML)
        self.assertIn("ftbquestsInput.addEventListener('change', handleFtbquestsInputChange)", INDEX_HTML)
        self.assertIn("ftbquestsDirectoryInput.addEventListener('change', handleFtbquestsInputChange)", INDEX_HTML)
        self.assertIn("const localePattern = /^[a-z]{2,3}_[a-z0-9]{2,8}$/", INDEX_HTML)

    def test_json_upload_infers_source_locale_without_conflicting_multiple_files(self) -> None:
        self.assertIn("inferLocaleFromJsonUploadPath", INDEX_HTML)
        self.assertIn("inferJsonSourceLocaleFromFiles", INDEX_HTML)
        self.assertIn("syncJsonSourceLocaleFromInput", INDEX_HTML)
        self.assertIn("jsonInput.addEventListener('change', handleJsonInputChange)", INDEX_HTML)
        self.assertIn("uniqueLocales.length === 1 && uniqueLocales.length === Array.from(files || []).length", INDEX_HTML)
        self.assertIn("status.json_locale_detected", INDEX_HTML)
        self.assertIn("status.json_locale_conflict", INDEX_HTML)

    def test_json_deep_free_uses_isolated_translator_and_unique_outputs(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "src" / "mc_mod_i18n" / "web.py").read_text(encoding="utf-8")
        self.assertIn('isolate_translator = args.provider == "deep-free"', source)
        self.assertIn("local_translator = create_translator(args) if isolate_translator else translator", source)
        self.assertIn("unique_output_name = unique_filename(output_name, output_names)", source)
        self.assertIn("entries = [replace(entry, file=unique_output_name) for entry in entries]", source)
        self.assertIn("same_locale = str(args.source_locale or \"\").strip().lower() == str(args.target_locale or \"\").strip().lower()", source)
        self.assertIn("source locale equals target locale", source)

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
        self.assertIn("ignorePreflightBlockersToggle.addEventListener('change'", INDEX_HTML)
        self.assertIn("preflight-list-collapsed", INDEX_HTML)
        self.assertIn("runPreflight", INDEX_HTML)
        self.assertIn("renderPreflight", INDEX_HTML)
        self.assertIn("fetch('/api/preflight'", INDEX_HTML)
        self.assertIn("preflight.blocked", INDEX_HTML)
        self.assertIn("preflight.summary", INDEX_HTML)

    def test_advanced_api_help_uses_focus_popover_motion(self) -> None:
        self.assertIn(".api-box label:focus-within .field-help", INDEX_HTML)
        self.assertIn("transform: translateY(-6px) scale(.98)", INDEX_HTML)
        self.assertIn("transition: opacity var(--motion-base) ease", INDEX_HTML)

    def test_api_debug_log_help_is_attached_to_checkbox_label(self) -> None:
        self.assertIn('<label class="checkline api-debug-log-line">', INDEX_HTML)
        self.assertIn('<span data-i18n="advanced.debug_log">记录 API 调试日志</span>', INDEX_HTML)
        self.assertIn('<span class="field-help" data-i18n="advanced.debug_log_help">会记录请求体、响应头和原始响应到本次任务目录；Authorization/API Key 会被隐藏。</span>', INDEX_HTML)
        self.assertNotIn('</label>\n          <div class="field-help" data-i18n="advanced.debug_log_help"', INDEX_HTML)

    def test_api_debug_log_help_can_escape_open_advanced_panel(self) -> None:
        self.assertIn(".inline-advanced-panel[open] {\n      position: relative;\n      z-index: 2;\n      overflow: visible;", INDEX_HTML)
        self.assertIn(".api-debug-log-line:hover,\n    .api-debug-log-line:focus-within {\n      z-index: 40;", INDEX_HTML)

    def test_settings_card_subtitles_use_hover_popover(self) -> None:
        self.assertIn(".settings-head > div:first-child:hover .card-head-copy,\n    .settings-head > div:first-child:focus-within .card-head-copy", INDEX_HTML)
        self.assertNotIn(".settings-head:hover .card-head-copy,\n    .settings-head:focus-within .card-head-copy", INDEX_HTML)
        self.assertIn("transform: translateY(-6px) scale(.98)", INDEX_HTML)
        self.assertIn('<span class="card-head-copy" role="tooltip" data-i18n="history.subtitle">找回最近任务的下载、报告和日志。</span>', INDEX_HTML)
        self.assertNotIn('<strong data-i18n="history.title">任务历史</strong>\n            <span data-i18n="history.subtitle">找回最近任务的下载、报告和日志。</span>', INDEX_HTML)

    def test_help_topic_buttons_allow_full_text(self) -> None:
        self.assertIn(".help-topic-link {\n      position: relative;\n      gap: 12px;\n      min-width: 0;\n      max-width: 100%;\n      min-height: 64px;", INDEX_HTML)
        self.assertIn("min-width: 0;\n      max-width: 100%;", INDEX_HTML)
        self.assertIn("white-space: normal;", INDEX_HTML)
        self.assertIn("overflow-wrap: break-word;", INDEX_HTML)
        self.assertIn("word-break: break-word;", INDEX_HTML)
        self.assertIn("overflow: hidden;", INDEX_HTML)
        self.assertNotIn("overflow-wrap: anywhere;\n      text-overflow: ellipsis;\n      overflow: visible;\n    }\n    .help-topic-link.active .help-topic-category", INDEX_HTML)
        self.assertNotIn("overflow: visible;\n    }\n    .help-topic-link.active .help-topic-category", INDEX_HTML)
        self.assertNotIn(".help-topic-category {\n      display: inline-flex;\n      max-width: 100%;\n      align-items: center;\n      gap: 6px;\n      min-height: 0;", INDEX_HTML)

    def test_results_report_and_history_keep_vertical_scroll_containers(self) -> None:
        self.assertIn(".results-panel {\n      display: grid;\n      grid-template-rows: auto minmax(0, 1fr);", INDEX_HTML)
        self.assertIn(".config-panel[hidden],\n    .results-panel[hidden] {\n      display: none;", INDEX_HTML)
        self.assertIn(".results {\n      min-height: 0;\n      padding: 20px;", INDEX_HTML)
        self.assertIn("overflow-y: auto;", INDEX_HTML)
        self.assertIn(".view-shell.active {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".view-frame {\n      min-height: 0;\n      display: grid;\n      grid-template-rows: auto minmax(0, 1fr);", INDEX_HTML)
        self.assertIn(".view-body {\n      min-height: 0;\n      overflow-y: auto;", INDEX_HTML)
        self.assertIn(".history-workbench {\n      min-height: 0;\n      height: 100%;", INDEX_HTML)
        self.assertIn(".history-list {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".history-detail-body {\n      min-height: 0;", INDEX_HTML)

    def test_settings_memory_and_cache_sections_keep_long_content_scrollable(self) -> None:
        self.assertIn(".settings-layout {\n      min-height: 0;", INDEX_HTML)
        self.assertIn("overflow: auto;", INDEX_HTML)
        self.assertIn(".settings-content {\n      min-width: 0;\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".settings-section {\n      min-width: 0;\n      min-height: 0;", INDEX_HTML)
        self.assertIn("max-height: 100%;", INDEX_HTML)
        self.assertIn("overflow-y: auto;", INDEX_HTML)
        self.assertIn(".memory-preview {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".memory-preview-card {\n      min-height: 0;", INDEX_HTML)
        self.assertIn(".memory-preview-list {\n      min-height: 0;\n      max-height: min(420px, calc(var(--app-vh) - 360px));", INDEX_HTML)
        self.assertIn("overscroll-behavior: contain;", INDEX_HTML)

    def test_system_settings_card_headers_use_consistent_type_size(self) -> None:
        self.assertIn(".settings-section-title {\n      display: flex;\n      align-items: center;\n      gap: 8px;\n      color: var(--text);\n      font-size: 14px;", INDEX_HTML)
        self.assertIn(".settings-current > span {\n      font-size: 12px;", INDEX_HTML)
        self.assertIn(".branding-option strong {\n      display: block;\n      min-width: 0;\n      overflow: hidden;\n      text-overflow: ellipsis;\n      color: inherit;\n      font-size: 13px;", INDEX_HTML)

    def test_high_visibility_frontend_text_uses_i18n(self) -> None:
        for expected in (
            'data-i18n="workflow.input_step"',
            'data-i18n="workflow.language_step"',
            'data-i18n="workflow.optional_step"',
            'data-i18n="workflow.preflight_step"',
            'data-i18n="advanced.apply_key"',
            'data-i18n="advanced.region_help"',
            'data-i18n="docs.open_provider"',
            'data-i18n="docs.open_output"',
            'data-i18n="docs.open_preflight"',
            'data-i18n="docs.open_history"',
            'data-i18n="docs.open_memory"',
            'data-i18n="history.detail"',
            'data-i18n="history.select_detail"',
            'data-i18n="settings.history_section"',
            'data-i18n="settings.history_note_body"',
            "ui('pack_dialog.review_title'",
            "ui('pack_dialog.review_body'",
            "ui('result.api_log_deep_free_empty'",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, INDEX_HTML)
        self.assertNotIn("noteTitle.textContent = '任何翻译结果最好都由人工审核一遍哦'", INDEX_HTML)
        self.assertNotIn("? '当前翻译器通过 deep-translator 调用第三方免费引擎", INDEX_HTML)

    def test_hardcoded_workbench_category_filter_uses_i18n_custom_dropdown(self) -> None:
        zh_messages = merged_catalog("zh_cn")
        en_messages = merged_catalog("en_us")

        self.assertIn("result.category_filter", zh_messages)
        self.assertIn("result.category_filter", en_messages)
        self.assertIn('id="hardcoded-category-filter-shell"', INDEX_HTML)
        self.assertIn('id="hardcoded-category-filter-menu" role="listbox"', INDEX_HTML)
        self.assertIn('data-hardcoded-category-value', INDEX_HTML)
        self.assertIn("bindHardcodedCategoryFilterMenu", INDEX_HTML)
        self.assertIn("ui('result.category_filter'", INDEX_HTML)
        self.assertNotIn('<label class="hardcoded-category-select"><span>${escapeHtml(ui(\'result.category\', \'分类\'))}</span>', INDEX_HTML)

    def test_dynamic_filter_and_provider_risk_text_is_language_switchable(self) -> None:
        zh_messages = merged_catalog("zh_cn")
        en_messages = merged_catalog("en_us")
        for key in (
            "provider.copy.risk_title",
            "provider.copy.risk_body",
            "provider.glossary.risk_title",
            "provider.glossary.risk_body",
            "provider.argos.risk_title",
            "provider.argos.risk_body",
            "provider.azure-translator.risk_title",
            "provider.azure-translator.risk_body",
            "provider.deep-free.risk_title",
            "provider.deep-free.risk_body",
            "provider.libretranslate.risk_title",
            "provider.libretranslate.risk_body",
            "provider.ai.risk_title",
            "provider.ai.risk_body",
            "provider.current.risk_title",
            "provider.current.risk_body",
            "settings.brand_cat_asset",
            "settings.brand_grass_asset",
            "settings.brand_sign_asset",
            "hardcoded.category.ponder",
            "hardcoded.category.ui_literal",
            "hardcoded.category.config_comment",
            "hardcoded.category.unknown_literal",
            "hardcoded.category.advancement_datagen",
            "hardcoded.category.unit_or_label",
            "hardcoded.risk.high",
            "hardcoded.risk.medium",
            "hardcoded.risk.low",
        ):
            with self.subTest(key=key):
                self.assertIn(key, zh_messages)
                self.assertIn(key, en_messages)

        self.assertIn("titleKey: 'provider.copy.risk_title'", INDEX_HTML)
        self.assertIn("ui(meta.titleKey", INDEX_HTML)
        self.assertNotIn("title: '复制原文'", INDEX_HTML)
        self.assertNotIn("title: '当前翻译器'", INDEX_HTML)
        self.assertIn("languageJarFilter: 'all'", INDEX_HTML)
        self.assertIn("data-select-value=\"all\"", INDEX_HTML)
        self.assertIn("hardcodedCategoryDisplay(entry.category", INDEX_HTML)
        self.assertIn("hardcodedRiskDisplay(entry.risk)", INDEX_HTML)
        self.assertNotIn("languageJarFilter: '全部'", INDEX_HTML)
        self.assertNotIn("resultState.languageJarFilter = '全部'", INDEX_HTML)

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
