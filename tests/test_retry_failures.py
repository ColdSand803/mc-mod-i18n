from __future__ import annotations

import unittest
import tempfile
import json
from pathlib import Path
from zipfile import ZipFile

from mc_mod_i18n.ftbquests import (
    FTBQuestsOutputFile,
    FTBQuestsResult,
    collect_string_leaves,
    parse_snbt,
)
from mc_mod_i18n.report import ReportEntry
from mc_mod_i18n.web import (
    entry_id,
    merge_retry_result,
    successful_retry_updates,
    update_ftbquests_retry_outputs,
    update_json_retry_outputs,
)


def report_entry(key: str, source: str, target: str = "") -> dict[str, str]:
    return {
        "jar": "example.jar",
        "file": "assets/example/lang/zh_cn.json",
        "key": key,
        "source": source,
        "target": target or source,
        "status": "api_failed",
        "message": "provider failed",
        "mod_id": "example",
    }


class RetryFailuresTest(unittest.TestCase):
    def test_merge_retry_result_updates_successes_and_keeps_remaining_failures(self) -> None:
        success = report_entry("item.example.copper", "Copper Ingot")
        failed = report_entry("item.example.crystal", "Crystal")
        result = {
            "entries": [success, failed],
            "summary": {"translated": 1, "api_failed": 2, "skipped": 0},
            "api_failure_count": 2,
            "api_failed_entries": [dict(success), dict(failed)],
        }
        translations = {entry_id(success): "铜锭"}
        failed_map = {entry_id(failed): "provider still failed"}

        updated, still_failed, remaining = merge_retry_result(
            result,
            [success, failed],
            translations,
            failed_map,
        )

        self.assertEqual(1, updated)
        self.assertEqual(1, still_failed)
        self.assertEqual("translated", success["status"])
        self.assertEqual("铜锭", success["target"])
        self.assertEqual("api_failed", success["retry_previous_status"])
        self.assertEqual("provider failed", success["retry_previous_message"])
        self.assertEqual("api_failed", failed["status"])
        self.assertEqual("provider still failed", failed["message"])
        self.assertEqual("api_failed", failed["retry_previous_status"])
        self.assertEqual({"translated": 2, "api_failed": 1, "skipped": 0}, result["summary"])
        self.assertEqual(1, result["api_failure_count"])
        self.assertEqual([failed["key"]], [entry["key"] for entry in remaining])
        self.assertEqual([failed["key"]], [entry["key"] for entry in result["api_failed_entries"]])

    def test_merge_retry_result_rejects_placeholder_validation_failures(self) -> None:
        entry = report_entry("screen.example.value", "Value: %s")
        result = {
            "entries": [entry],
            "summary": {"translated": 0, "api_failed": 1},
            "api_failure_count": 1,
            "api_failed_entries": [dict(entry)],
        }

        updated, still_failed, remaining = merge_retry_result(
            result,
            [entry],
            {entry_id(entry): "数值"},
            {},
        )

        self.assertEqual(0, updated)
        self.assertEqual(1, still_failed)
        self.assertEqual("api_failed", entry["status"])
        self.assertIn("%s", entry["message"])
        self.assertEqual([entry["key"]], [item["key"] for item in remaining])

    def test_successful_retry_updates_only_returns_valid_translated_entries(self) -> None:
        valid = report_entry("item.example.copper", "Copper Ingot")
        failed = report_entry("item.example.crystal", "Crystal")
        invalid = report_entry("screen.example.value", "Value: %s")
        missing_key = dict(report_entry("", "Nameless"))

        updates = successful_retry_updates(
            [valid, failed, invalid, missing_key],
            {
                entry_id(valid): "铜锭",
                entry_id(invalid): "数值",
                entry_id(missing_key): "无名",
            },
            {entry_id(failed): "provider still failed"},
        )

        self.assertEqual(
            {"assets/example/lang/zh_cn.json": {"item.example.copper": "铜锭"}},
            updates,
        )

    def test_json_retry_updates_single_file_and_zip_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            single = out_dir / "zh_cn.json"
            single.write_text(json.dumps({"item.example.copper": "Copper"}), encoding="utf-8")
            zipped = out_dir / "json-locales-zh_cn.zip"
            with ZipFile(zipped, "w") as zf:
                zf.writestr("zh_cn.json", json.dumps({"item.example.copper": "Copper"}))
                zf.writestr("extra.json", json.dumps({"item.example.tin": "Tin"}))

            updated = update_json_retry_outputs(
                out_dir,
                [
                    {
                        "file": "zh_cn.json",
                        "key": "item.example.copper",
                        "target": "铜",
                    }
                ],
            )

            self.assertEqual(2, updated)
            self.assertEqual("铜", json.loads(single.read_text(encoding="utf-8"))["item.example.copper"])
            with ZipFile(zipped) as zf:
                self.assertEqual("铜", json.loads(zf.read("zh_cn.json").decode("utf-8"))["item.example.copper"])
                self.assertEqual("Tin", json.loads(zf.read("extra.json").decode("utf-8"))["item.example.tin"])

    def test_ftbquests_retry_updates_directory_patch_and_result_outputs(self) -> None:
        result = FTBQuestsResult(
            source_label="pack.zip",
            mode="lang",
            source_locale="en_us",
            target_locale="zh_cn",
            source_hash="",
            output_files=[
                FTBQuestsOutputFile(
                    path="config/ftbquests/quests/lang/zh_cn.snbt",
                    content='{ "quest.title": "Start" }',
                )
            ],
            report_entries=[
                ReportEntry(
                    "pack.zip",
                    "ftbquests",
                    "lang/zh_cn.snbt",
                    "quest.title",
                    "Start",
                    "开始",
                    "translated",
                    "",
                )
            ],
            legacy_files=[],
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            target = out_dir / "ftbquests" / "config" / "ftbquests" / "quests" / "lang" / "zh_cn.snbt"
            target.parent.mkdir(parents=True)
            target.write_text('{ "quest.title": "Start" }', encoding="utf-8")
            patch = out_dir / "ftbquests-zh_cn-patch.zip"
            with ZipFile(patch, "w") as zf:
                zf.writestr("config/ftbquests/quests/lang/zh_cn.snbt", '{ "quest.title": "Start" }')

            updated = update_ftbquests_retry_outputs(
                out_dir,
                result,
                [
                    {
                        "file": "lang/zh_cn.snbt",
                        "key": "quest.title",
                        "target": "开始",
                    }
                ],
            )

            self.assertEqual(2, updated)
            self.assertEqual(
                "开始",
                {leaf.key: leaf.text for leaf in collect_string_leaves(parse_snbt(target.read_text(encoding="utf-8")))}["quest.title"],
            )
            self.assertIn("开始", result.output_files[0].content)
            with ZipFile(patch) as zf:
                self.assertIn("开始", zf.read("config/ftbquests/quests/lang/zh_cn.snbt").decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
