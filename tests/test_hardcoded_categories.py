from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mc_mod_i18n.hardcoded import HardcodedEntry
from mc_mod_i18n.report import write_hardcoded_report
from mc_mod_i18n.web import INDEX_HTML


class HardcodedCategoryTest(unittest.TestCase):
    def test_report_filters_only_show_categories_present_in_entries(self) -> None:
        entries = [
            HardcodedEntry(
                jar="example.jar",
                class_path="com/example/client/Screen.class",
                text="Open Settings",
                category="ui_literal",
                risk="high",
                suggestion="确认是客户端显示文本后，加入补丁 Mod 映射表。",
            )
        ]

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "hardcoded-report.html"
            write_hardcoded_report(path, entries)
            html = path.read_text(encoding="utf-8")

        self.assertIn('data-category="ui_literal"', html)
        self.assertNotIn('data-category="ponder">', html)

    def test_report_filters_include_non_map_categories_when_scanned(self) -> None:
        entries = [
            HardcodedEntry(
                jar="example.jar",
                class_path="com/example/datagen/AdvancementProvider.class",
                text="Find a new crystal",
                category="advancement_datagen",
                risk="low",
                suggestion="多数应已进入 lang 文件；只在游戏中仍显示英文时处理。",
            )
        ]

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "hardcoded-report.html"
            write_hardcoded_report(path, entries)
            html = path.read_text(encoding="utf-8")

        self.assertIn('data-category="advancement_datagen">', html)

    def test_web_workbench_does_not_use_a_fixed_hardcoded_category_list(self) -> None:
        self.assertNotIn("['all', 'ponder', 'config_comment', 'ui_literal', 'unknown_literal']", INDEX_HTML)
        self.assertIn("hardcodedCategoryFilters", INDEX_HTML)


if __name__ == "__main__":
    unittest.main()
