from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from mc_mod_i18n.web import preflight_inputs


class PreflightTest(unittest.TestCase):
    def test_jar_preflight_reports_source_and_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jar_path = Path(tmp) / "example.jar"
            with ZipFile(jar_path, "w") as zf:
                zf.writestr("assets/demo/lang/en_us.json", json.dumps({"item.demo": "Demo"}))
                zf.writestr("assets/demo/lang/zh_cn.json", json.dumps({"item.demo": "演示"}))

            result = preflight_inputs("jar", [jar_path], "en_us", "zh_cn")

        self.assertTrue(result["ok"])
        self.assertEqual("jar", result["kind"])
        self.assertEqual(1, result["summary"]["source_files"])
        self.assertEqual(1, result["summary"]["existing_target_files"])
        self.assertEqual("assets/demo/lang/zh_cn.json", result["items"][0]["target_path"])
        self.assertEqual("info", result["messages"][0]["level"])

    def test_json_preflight_reports_schema_and_output_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "en_us.json"
            path.write_text(json.dumps({"menu.start": "Start"}), encoding="utf-8")

            result = preflight_inputs("json", [path], "en_us", "fr_fr")

        self.assertTrue(result["ok"])
        self.assertEqual("json", result["kind"])
        self.assertEqual("flat", result["items"][0]["schema"])
        self.assertEqual("fr_fr.json", result["items"][0]["output_name"])
        self.assertEqual(1, result["summary"]["source_files"])

    def test_invalid_json_preflight_blocks_translation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "en_us.json"
            path.write_text("{bad", encoding="utf-8")

            result = preflight_inputs("json", [path], "en_us", "zh_cn")

        self.assertFalse(result["ok"])
        self.assertEqual("blocking", result["messages"][0]["level"])
        self.assertIn("不是有效 JSON", result["messages"][0]["message"])


if __name__ == "__main__":
    unittest.main()
