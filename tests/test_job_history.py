from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mc_mod_i18n.web import append_job_history, build_job_history_record, read_job_history


class JobHistoryTest(unittest.TestCase):
    def test_build_record_summarizes_done_job_without_api_key(self) -> None:
        record = build_job_history_record(
            "abc123",
            {
                "status": "done",
                "created_at": "2026-05-13T10:00:00+08:00",
                "result": {
                    "kind": "json",
                    "provider": "openai-compatible",
                    "model": "gpt-4o-mini",
                    "processed_sources": 2,
                    "summary": {"translated": 3, "api_failed": 1},
                    "json_url": "/download/abc123/out/json-locales-zh_cn.zip",
                    "report_json_url": "/download/abc123/out/report.json",
                    "report_csv_url": "/download/abc123/out/report.csv",
                    "failed_items_url": "/download/abc123/out/failed-items.json",
                    "api_key": "sk-secret",
                },
            },
        )

        self.assertEqual("abc123", record["job_id"])
        self.assertEqual("json", record["input_kind"])
        self.assertEqual("done", record["status"])
        self.assertEqual(3, record["success_count"])
        self.assertEqual(1, record["failure_count"])
        self.assertEqual("/download/abc123/out/json-locales-zh_cn.zip", record["downloads"]["json"])
        self.assertEqual("/download/abc123/out/report.json", record["downloads"]["report_json"])
        self.assertEqual("/download/abc123/out/report.csv", record["downloads"]["report_csv"])
        self.assertEqual("/download/abc123/out/failed-items.json", record["downloads"]["failed_items"])
        self.assertEqual("out/report.json", record["download_files"]["report_json"])
        self.assertEqual("out/report.csv", record["download_files"]["report_csv"])
        self.assertNotIn("sk-secret", json.dumps(record, ensure_ascii=False))

    def test_history_roundtrip_keeps_newest_with_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(3):
                append_job_history(
                    root,
                    {"job_id": str(index), "status": "done", "created_at": f"2026-05-13T10:0{index}:00+08:00"},
                    limit=2,
                )

            records = read_job_history(root, limit=10)

        self.assertEqual(["2", "1"], [record["job_id"] for record in records])

    def test_read_history_marks_missing_download_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "abc123" / "out" / "report.json"
            existing.parent.mkdir(parents=True)
            existing.write_text("{}", encoding="utf-8")
            append_job_history(
                root,
                {
                    "job_id": "abc123",
                    "status": "done",
                    "created_at": "2026-05-13T10:00:00+08:00",
                    "downloads": {
                        "report_json": "/download/abc123/out/report.json",
                        "report_csv": "/download/abc123/out/report.csv",
                    },
                    "download_files": {
                        "report_json": "out/report.json",
                        "report_csv": "out/report.csv",
                    },
                },
            )

            record = read_job_history(root)[0]

        self.assertTrue(record["download_status"]["report_json"]["exists"])
        self.assertFalse(record["download_status"]["report_csv"]["exists"])


if __name__ == "__main__":
    unittest.main()
