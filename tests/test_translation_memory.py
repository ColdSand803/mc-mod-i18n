from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import tempfile
import unittest

from mc_mod_i18n.core import TranslationMemory, TranslationMemoryTranslator, compute_translation_config_hash
from mc_mod_i18n.translator import TranslationItem


class CountingTranslator:
    def __init__(self) -> None:
        self.calls = 0

    def translate_batch_with_failures(self, items: list[TranslationItem]):
        self.calls += 1
        return {item.id: f"{item.text}-zh" for item in items}, {}


def args(**overrides):
    values = {
        "source_locale": "en_us",
        "target_locale": "zh_cn",
        "provider": "openai-compatible",
        "model": "gpt-4o-mini",
        "api_url": "https://api.openai.com/v1",
        "glossary": None,
        "overwrite_existing": False,
        "skip_translated": False,
        "pack_format": 15,
    }
    values.update(overrides)
    return Namespace(**values)


class TranslationMemoryTest(unittest.TestCase):
    def test_memory_translator_reuses_previous_translation_without_inner_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.jsonl"
            scope = compute_translation_config_hash(args())
            first_inner = CountingTranslator()
            first = TranslationMemoryTranslator(first_inner, TranslationMemory(memory_path, scope))
            item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="example")

            translations, failed = first.translate_batch_with_failures([item])

            self.assertEqual({"1": "Start-zh"}, translations)
            self.assertEqual({}, failed)
            self.assertEqual(1, first_inner.calls)

            second_inner = CountingTranslator()
            second = TranslationMemoryTranslator(second_inner, TranslationMemory(memory_path, scope))
            translations, failed = second.translate_batch_with_failures([TranslationItem(id="2", key="menu.start", text="Start", mod_id="example")])

            self.assertEqual({"2": "Start-zh"}, translations)
            self.assertEqual({}, failed)
            self.assertEqual(0, second_inner.calls)
            self.assertEqual(1, second.memory_hits)

    def test_memory_scope_separates_target_locale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.jsonl"
            zh_scope = compute_translation_config_hash(args(target_locale="zh_cn"))
            ja_scope = compute_translation_config_hash(args(target_locale="ja_jp"))
            TranslationMemory(memory_path, zh_scope).put_many({"Start": "开始"})

            self.assertEqual("开始", TranslationMemory(memory_path, zh_scope).get("Start"))
            self.assertIsNone(TranslationMemory(memory_path, ja_scope).get("Start"))

    def test_memory_supports_sqlite_path_with_unique_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.sqlite3"
            scope = compute_translation_config_hash(args())

            memory = TranslationMemory(memory_path, scope)
            memory.put_many({"Start": "开始"})
            memory.put_many({"Start": "启动", "Menu": "菜单"})

            reloaded = TranslationMemory(memory_path, scope)

            self.assertEqual("启动", reloaded.get("Start"))
            self.assertEqual("菜单", reloaded.get("Menu"))

    def test_memory_scope_changes_when_ignore_translation_memory_changes(self) -> None:
        self.assertNotEqual(
            compute_translation_config_hash(args(ignore_translation_memory=False)),
            compute_translation_config_hash(args(ignore_translation_memory=True)),
        )


if __name__ == "__main__":
    unittest.main()
