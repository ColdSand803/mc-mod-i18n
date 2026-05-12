from __future__ import annotations

import unittest

from mc_mod_i18n.web import entry_id, merge_retry_result, successful_retry_updates


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


if __name__ == "__main__":
    unittest.main()
