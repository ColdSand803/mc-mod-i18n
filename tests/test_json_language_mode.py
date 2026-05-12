from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
import unittest

from mc_mod_i18n.translator import CopyTranslator
from mc_mod_i18n.web import json_target_filename, process_json_language_file


class JsonLanguageModeTest(unittest.TestCase):
    def test_flat_json_translation_preserves_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "en_us.json"
            path.write_text(json.dumps({"menu.start": "Start", "number": 3}), encoding="utf-8")
            args = argparse.Namespace(source_locale="en_us", target_locale="fr_fr")

            output_name, output, report, translated_count, failed_count, skipped_count = process_json_language_file(
                path,
                args,
                CopyTranslator(),
            )

            self.assertEqual("fr_fr.json", output_name)
            self.assertEqual({"menu.start", "number"}, set(output))
            self.assertEqual("Start", output["menu.start"])
            self.assertEqual(3, output["number"])
            self.assertEqual(1, translated_count)
            self.assertEqual(0, failed_count)
            self.assertEqual(1, skipped_count)
            self.assertTrue(any(entry.status == "skipped" and entry.key == "number" for entry in report))

    def test_ui_locale_schema_translation_preserves_metadata_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mc-mod-i18n-ui-en_us.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "locale": "en_us",
                        "name": "English",
                        "messages": {"app.title": "Title"},
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(source_locale="en_us", target_locale="ja_jp")

            output_name, output, _report, translated_count, failed_count, _skipped_count = process_json_language_file(
                path,
                args,
                CopyTranslator(),
            )

            self.assertEqual("mc-mod-i18n-ui-ja_jp.json", output_name)
            self.assertEqual("ja_jp", output["locale"])
            self.assertEqual("日本語", output["name"])
            self.assertEqual("日本語", output["native_name"])
            self.assertEqual("en_us", output["source_locale"])
            self.assertEqual({"app.title": "Title"}, output["messages"])
            self.assertEqual(1, translated_count)
            self.assertEqual(0, failed_count)

    def test_ui_locale_schema_uses_target_language_text_for_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mc-mod-i18n-ui-en_us.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "locale": "en_us",
                        "name": "English",
                        "native_name": "English",
                        "messages": {"app.title": "Title"},
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(source_locale="en_us", target_locale="ar_sa")

            _output_name, output, _report, _translated_count, _failed_count, _skipped_count = process_json_language_file(
                path,
                args,
                CopyTranslator(),
            )

            self.assertEqual("العربية", output["name"])
            self.assertEqual("العربية", output["native_name"])
            self.assertNotEqual("ar_sa", output["name"])
            self.assertNotEqual("ar_sa", output["native_name"])

    def test_json_target_filename_replaces_source_locale(self) -> None:
        self.assertEqual("fr_fr.json", json_target_filename("en_us.json", "en_us", "fr_fr", "flat"))
        self.assertEqual("foo.fr_fr.json", json_target_filename("foo.json", "en_us", "fr_fr", "flat"))


if __name__ == "__main__":
    unittest.main()
