from __future__ import annotations

import re
import unittest
from pathlib import Path

from mc_mod_i18n.ui_i18n import BUILTIN_UI_LOCALES


class I18nCoverageTest(unittest.TestCase):
    def test_all_html_i18n_keys_have_translations(self) -> None:
        """Ensure every data-i18n key in index.html has a translation in zh_cn and en_us."""
        html_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "mc_mod_i18n"
            / "templates"
            / "index.html"
        )
        if not html_path.exists():
            self.skipTest("index.html not found")

        html_content = html_path.read_text(encoding="utf-8")
        # Match data-i18n="...", data-i18n-title="...", data-i18n-placeholder="...", etc.
        keys = set(re.findall(r'data-i18n(?:-\w+)?="([^"]+)"', html_content))

        zh_keys = set(BUILTIN_UI_LOCALES.get("zh_cn", {}).get("messages", {}).keys())
        en_keys = set(BUILTIN_UI_LOCALES.get("en_us", {}).get("messages", {}).keys())

        missing_zh = keys - zh_keys
        missing_en = keys - en_keys

        self.assertEqual(set(), missing_zh, f"zh_cn missing keys: {sorted(missing_zh)}")
        self.assertEqual(set(), missing_en, f"en_us missing keys: {sorted(missing_en)}")


if __name__ == "__main__":
    unittest.main()
