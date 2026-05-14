from __future__ import annotations

from argparse import Namespace
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mc_mod_i18n.pack import (
    OutputLangDocument,
    load_checkpoint_config_hash,
    save_checkpoint,
)
from mc_mod_i18n.report import ReportEntry
from mc_mod_i18n.core import compute_translation_config_hash, report_has_uncacheable_failures


class CheckpointConfigHashTest(unittest.TestCase):
    def test_checkpoint_persists_translation_config_hash(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            save_checkpoint(
                out_dir,
                "example",
                [OutputLangDocument("assets/example/lang/zh_cn.json", "json", {"k": "铜"})],
                [ReportEntry("example.jar", "example", "assets/example/lang/zh_cn.json", "k", "Copper", "铜", "translated", "")],
                source_hash="source-1",
                config_hash="config-1",
            )

            self.assertEqual(load_checkpoint_config_hash(out_dir, "example"), "config-1")

    def test_translation_config_hash_changes_when_provider_changes(self) -> None:
        base = Namespace(
            source_locale="en_us",
            target_locale="zh_cn",
            provider="copy",
            model="gpt-4o-mini",
            api_url="https://api.openai.com/v1/chat/completions",
            overwrite_existing=False,
            skip_translated=False,
            ignore_translation_memory=False,
            pack_format="1.20.1",
            glossary=None,
        )
        changed = Namespace(**{**vars(base), "provider": "glossary"})

        self.assertNotEqual(
            compute_translation_config_hash(base),
            compute_translation_config_hash(changed),
        )

    def test_translation_config_hash_changes_when_ignore_translation_memory_changes(self) -> None:
        base = Namespace(
            source_locale="en_us",
            target_locale="zh_cn",
            provider="copy",
            model="gpt-4o-mini",
            api_url="https://api.openai.com/v1/chat/completions",
            overwrite_existing=False,
            skip_translated=False,
            ignore_translation_memory=False,
            pack_format="1.20.1",
            glossary=None,
        )
        changed = Namespace(**{**vars(base), "ignore_translation_memory": True})

        self.assertNotEqual(
            compute_translation_config_hash(base),
            compute_translation_config_hash(changed),
        )

    def test_failed_report_entries_are_not_cacheable(self) -> None:
        self.assertTrue(
            report_has_uncacheable_failures([
                ReportEntry("example.jar", "example", "assets/example/lang/zh_tw.json", "k", "Copper", "Copper", "api_failed", "missed")
            ])
        )
        self.assertFalse(
            report_has_uncacheable_failures([
                ReportEntry("example.jar", "example", "assets/example/lang/zh_tw.json", "k", "Copper", "銅錠", "translated", "")
            ])
        )


if __name__ == "__main__":
    unittest.main()
