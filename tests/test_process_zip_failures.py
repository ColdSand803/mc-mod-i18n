from __future__ import annotations

from argparse import Namespace
from io import BytesIO
import unittest
from zipfile import ZipFile

from mc_mod_i18n.core import process_zip
from mc_mod_i18n.translator import TranslationItem


def make_zip() -> ZipFile:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zf:
        zf.writestr(
            "assets/example/lang/en_us.json",
            '{"item.example.copper": "Copper Ingot", "item.example.crystal": "Crystal"}',
        )
    buffer.seek(0)
    return ZipFile(buffer)


class PartialFailureTranslator:
    def translate_batch(self, items: list[TranslationItem]) -> dict[str, str]:
        raise AssertionError("process_zip should use translate_batch_with_failures when available")

    def translate_batch_with_failures(self, items: list[TranslationItem]) -> tuple[dict[str, str], dict[str, str]]:
        translations = {items[0].id: "铜锭"}
        failures = {items[1].id: "provider missed this entry"}
        return translations, failures


class PollutedResponseTranslator:
    def translate_batch_with_failures(self, items: list[TranslationItem]) -> tuple[dict[str, str], dict[str, str]]:
        return {
            items[0].id: "铜锭",
            items[1].id: "水晶\n公益 token2 通知群：1104138863",
        }, {}


class ProcessZipFailuresTest(unittest.TestCase):
    def test_failures_are_taken_from_current_translate_call(self) -> None:
        args = Namespace(
            source_locale="en_us",
            target_locale="zh_cn",
            skip_translated=False,
            overwrite_existing=False,
        )
        with make_zip() as zf:
            docs, report, _ = process_zip(zf, "example.jar", args, PartialFailureTranslator())

        statuses = {entry.key: entry.status for entry in report if entry.key}
        self.assertEqual(statuses["item.example.copper"], "translated")
        self.assertEqual(statuses["item.example.crystal"], "api_failed")
        self.assertEqual(docs[0].entries["item.example.copper"], "铜锭")
        self.assertEqual(docs[0].entries["item.example.crystal"], "Crystal")

    def test_polluted_translation_response_is_filtered_before_writing_output(self) -> None:
        args = Namespace(
            source_locale="en_us",
            target_locale="zh_cn",
            skip_translated=False,
            overwrite_existing=False,
        )
        with make_zip() as zf:
            docs, report, _ = process_zip(zf, "example.jar", args, PollutedResponseTranslator())

        statuses = {entry.key: entry.status for entry in report if entry.key}
        messages = {entry.key: entry.message for entry in report if entry.key}
        self.assertEqual(statuses["item.example.copper"], "translated")
        self.assertEqual(statuses["item.example.crystal"], "translated")
        self.assertEqual(docs[0].entries["item.example.copper"], "铜锭")
        self.assertEqual(docs[0].entries["item.example.crystal"], "水晶")
        self.assertIn("filtered suspicious provider response", messages["item.example.crystal"])
        self.assertIn("公益 token", messages["item.example.crystal"])


if __name__ == "__main__":
    unittest.main()
