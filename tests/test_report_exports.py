from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mc_mod_i18n.report import ReportEntry
from mc_mod_i18n.web import write_report_exports


class ReportExportsTest(unittest.TestCase):
    def test_write_report_exports_creates_json_csv_and_failed_items(self) -> None:
        entries = [
            ReportEntry("example.jar", "example", "assets/example/lang/zh_cn.json", "item.example.copper", "Copper", "铜", "translated", ""),
            ReportEntry("example.jar", "example", "assets/example/lang/zh_cn.json", "item.example.crystal", "Crystal", "Crystal", "api_failed", "timeout"),
        ]
        with TemporaryDirectory() as tmp:
            paths = write_report_exports(
                Path(tmp),
                entries,
                {"translated": 1, "api_failed": 1},
                {"job_id": "abc123", "provider": "copy"},
            )

            report_payload = json.loads(paths["report_json"].read_text(encoding="utf-8"))
            failed_payload = json.loads(paths["failed_json"].read_text(encoding="utf-8"))
            csv_text = paths["report_csv"].read_text(encoding="utf-8-sig")

        self.assertEqual("abc123", report_payload["job_id"])
        self.assertEqual(2, len(report_payload["entries"]))
        self.assertEqual(["item.example.crystal"], [entry["key"] for entry in failed_payload["entries"]])
        self.assertIn("jar,mod_id,file,key,source,target,status,message", csv_text)
        self.assertIn("item.example.copper", csv_text)


if __name__ == "__main__":
    unittest.main()
