from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from mc_mod_i18n.core import TranslationMemoryTranslator, compute_translation_config_hash
from mc_mod_i18n.translator import GlossaryTranslator, TranslationItem


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


class TestComputeTranslationConfigHash(unittest.TestCase):
    def test_compute_translation_config_hash_is_stable(self):
        a = args()
        hash1 = compute_translation_config_hash(a)
        hash2 = compute_translation_config_hash(a)
        self.assertEqual(hash1, hash2)

    def test_hash_changes_when_params_change(self):
        hash_a = compute_translation_config_hash(args())
        hash_b = compute_translation_config_hash(args(target_locale="ja_jp"))
        self.assertNotEqual(hash_a, hash_b)


class TestTranslationMemoryTranslator(unittest.TestCase):
    def test_memory_translator_skips_already_translated_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.db"
            scope = compute_translation_config_hash(args())
            from mc_mod_i18n.core import TranslationMemory
            memory = TranslationMemory(memory_path, scope)
            inner = CountingTranslator()
            translator = TranslationMemoryTranslator(inner, memory)
            items = [
                TranslationItem(id="1", key="a", text="Hello", mod_id="m"),
                TranslationItem(id="2", key="b", text="World", mod_id="m"),
            ]
            translator.translate_batch_with_failures(items)
            self.assertEqual(1, inner.calls)

            inner2 = CountingTranslator()
            translator2 = TranslationMemoryTranslator(inner2, memory)
            translator2.translate_batch_with_failures(items)
            self.assertEqual(0, inner2.calls)
            self.assertEqual(2, translator2.memory_hits)

    def test_memory_translator_mixed_hit_and_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.db"
            scope = compute_translation_config_hash(args())
            from mc_mod_i18n.core import TranslationMemory
            memory = TranslationMemory(memory_path, scope)
            inner = CountingTranslator()
            translator = TranslationMemoryTranslator(inner, memory)
            item_a = TranslationItem(id="1", key="a", text="Hello", mod_id="m")
            translator.translate_batch_with_failures([item_a])
            self.assertEqual(1, inner.calls)

            inner2 = CountingTranslator()
            translator2 = TranslationMemoryTranslator(inner2, memory)
            item_b = TranslationItem(id="2", key="b", text="World", mod_id="m")
            translator2.translate_batch_with_failures([item_a, item_b])
            self.assertEqual(1, inner2.calls)
            self.assertEqual(1, translator2.memory_hits)


class TestGlossaryTranslatorWordReplacement(unittest.TestCase):
    def test_glossary_translator_word_replacement(self):
        translator = GlossaryTranslator({"Copper": "铜", "Iron": "铁"})
        items = [TranslationItem(id="1", key="a", text="Copper and Iron", mod_id="m")]
        result = translator.translate_batch(items)
        self.assertEqual("铜 and 铁", result["1"])


if __name__ == "__main__":
    unittest.main()
