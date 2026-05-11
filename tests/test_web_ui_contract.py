from __future__ import annotations

import unittest

from mc_mod_i18n.web import INDEX_HTML


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
        self.assertIn("ghost-menu-input", INDEX_HTML)
        self.assertIn("data-locale-apply", INDEX_HTML)

    def test_cache_and_loading_controls_are_exposed(self) -> None:
        self.assertIn('name="ignore_cache"', INDEX_HTML)
        self.assertIn("忽略缓存并重新翻译", INDEX_HTML)
        self.assertIn("progress-full", INDEX_HTML)
        self.assertIn('classList.toggle(\'indeterminate\'', INDEX_HTML)

    def test_results_actions_include_workspace_before_pack_download(self) -> None:
        workspace_index = INDEX_HTML.index('<button type="button" data-view="language"><i class="ri-folder-open-line"></i><span>工作区</span></button>')
        download_index = INDEX_HTML.index('id="download-pack"')
        self.assertLess(workspace_index, download_index)


if __name__ == "__main__":
    unittest.main()
