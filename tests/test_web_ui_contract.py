from __future__ import annotations

import unittest

from mc_mod_i18n.web import INDEX_HTML, normalize_models_url, parse_models_response


class WebUiContractTest(unittest.TestCase):
    def test_workspace_uses_progressive_disclosure_for_advanced_settings(self) -> None:
        self.assertIn("高级 API 设置", INDEX_HTML)
        self.assertIn("输出策略", INDEX_HTML)
        self.assertIn("data-advanced-panel", INDEX_HTML)

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
        self.assertIn('<option value="openai-compatible">兼容 OpenAI</option>', INDEX_HTML)
        self.assertIn('<option value="anthropic-compatible">兼容 Anthropic</option>', INDEX_HTML)
        self.assertNotIn('<option value="deepseek">', INDEX_HTML)
        self.assertNotIn('<option value="gemini">', INDEX_HTML)

    def test_api_key_can_be_revealed_without_changing_form_contract(self) -> None:
        self.assertIn('name="api_key" id="api_key" type="password"', INDEX_HTML)
        self.assertIn('id="api-key-toggle"', INDEX_HTML)
        self.assertIn("syncApiKeyVisibility", INDEX_HTML)

    def test_api_base_url_fetches_searchable_model_dropdown(self) -> None:
        self.assertIn("<label>BaseURL", INDEX_HTML)
        self.assertIn('name="api_url" id="api_base_url"', INDEX_HTML)
        self.assertIn('id="model-select"', INDEX_HTML)
        self.assertIn('id="model-refresh"', INDEX_HTML)
        self.assertIn("refreshModelList", INDEX_HTML)
        self.assertIn("fetch('/api/models'", INDEX_HTML)
        self.assertIn('class="model-control-input"', INDEX_HTML)
        self.assertIn('type="hidden" name="model" id="model"', INDEX_HTML)
        self.assertNotIn("<label>API URL", INDEX_HTML)

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
        self.assertIn('id="settings-dialog"', INDEX_HTML)
        self.assertIn('id="settings-cache-dir"', INDEX_HTML)
        self.assertIn('id="settings-cache-clear"', INDEX_HTML)
        self.assertIn('id="settings-cache-default"', INDEX_HTML)
        self.assertIn('name="cache_dir" id="cache_dir"', INDEX_HTML)
        self.assertIn("CACHE_DIR_STORAGE_KEY", INDEX_HTML)
        self.assertIn("fetch('/api/cache/clear'", INDEX_HTML)

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

    def test_results_actions_include_workspace_before_pack_download(self) -> None:
        workspace_index = INDEX_HTML.index('<button type="button" data-view="language"><i class="ri-folder-open-line"></i><span>工作区</span></button>')
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
