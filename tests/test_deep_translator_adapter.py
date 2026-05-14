from __future__ import annotations

import argparse
import unittest

from mc_mod_i18n.cli import build_parser
from mc_mod_i18n.core import create_translator
from mc_mod_i18n.deep_translator_adapter import (
    DeepFreeLocaleSupport,
    DeepFreeTranslator,
    deep_free_locale_support,
)
from mc_mod_i18n.translator import ProviderPreset, TranslationItem, get_provider_preset
from mc_mod_i18n.web import INDEX_HTML


class DeepTranslatorAdapterTest(unittest.TestCase):
    def test_common_locales_map_to_stable_engine_codes(self) -> None:
        cases = {
            "en_us": ("en", "en-US"),
            "en_gb": ("en", "en-GB"),
            "en_ca": ("en", "en-CA"),
            "en_au": ("en", "en-AU"),
            "fr_fr": ("fr", "fr-FR"),
            "de_de": ("de", "de-DE"),
            "es_es": ("es", "es-ES"),
            "es_mx": ("es", "es-MX"),
            "pt_br": ("pt", "pt-BR"),
            "pt_pt": ("pt", "pt-PT"),
            "ja_jp": ("ja", "ja-JP"),
            "ko_kr": ("ko", "ko-KR"),
            "ru_ru": ("ru", "ru-RU"),
            "uk_ua": ("uk", "uk-UA"),
            "it_it": ("it", "it-IT"),
            "nl_nl": ("nl", "nl-NL"),
            "pl_pl": ("pl", "pl-PL"),
            "tr_tr": ("tr", "tr-TR"),
            "ar_sa": ("ar", "ar-SA"),
            "zh_cn": ("zh-CN", "zh-CN"),
            "zh_tw": ("zh-TW", "zh-TW"),
            "zh_hk": ("zh-TW", "zh-HK"),
            "he_il": ("iw", "he-IL"),
            "fil_ph": ("tl", "fil-PH"),
            "nn_no": ("no", "nn-NO"),
        }

        for locale, (google_code, mymemory_code) in cases.items():
            with self.subTest(locale=locale):
                support = deep_free_locale_support(locale, "zh_cn").source
                self.assertEqual(google_code, support.google)
                self.assertEqual(mymemory_code, support.mymemory)

    def test_known_locale_support_maps_mymemory_to_regional_code(self) -> None:
        support = deep_free_locale_support("en_us", "fr_fr")

        self.assertEqual("en", support.source.google)
        self.assertEqual("en-US", support.source.mymemory)
        self.assertEqual("fr", support.target.google)
        self.assertEqual("fr-FR", support.target.mymemory)

    def test_known_locale_support_is_structured(self) -> None:
        support = deep_free_locale_support("en_us", "zh_cn")
        self.assertIsInstance(support.source, DeepFreeLocaleSupport)
        self.assertIsInstance(support.target, DeepFreeLocaleSupport)
        self.assertEqual("en_us", support.source.minecraft_locale)
        self.assertEqual("zh_cn", support.target.minecraft_locale)
        self.assertEqual("supported", support.source.status)
        self.assertIn(support.target.status, {"supported", "fallback-copy"})

    def test_unsupported_target_locale_falls_back_to_copy(self) -> None:
        support = deep_free_locale_support("en_us", "lol_us")
        self.assertEqual("supported", support.source.status)
        self.assertEqual("fallback-copy", support.target.status)
        self.assertIn("unsupported", support.target.note)

    def test_unknown_language_prefix_does_not_claim_supported_mapping(self) -> None:
        support = deep_free_locale_support("gaa_gh", "zh_cn")

        self.assertEqual("fallback-copy", support.source.status)
        self.assertIsNone(support.source.google)
        self.assertIsNone(support.source.mymemory)
        self.assertIn("unsupported", support.source.note)

    def test_translate_batch_with_failures_uses_second_engine_after_first_failure(self) -> None:
        translator = DeepFreeTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            engine_order=["google", "mymemory"],
            engine_factories={
                "google": lambda source, target, timeout: FakeEngine(error=RuntimeError("google down")),
                "mymemory": lambda source, target, timeout: FakeEngine(prefix="mm"),
            },
        )
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "mm:Start"}, translations)
        self.assertEqual({}, failures)

    def test_translate_batch_with_failures_reuses_engine_instances_and_translate_batch(self) -> None:
        translator = DeepFreeTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            engine_order=["google", "mymemory"],
            engine_factories={
                "google": lambda source, target, timeout: FakeBatchEngine(prefix="g"),
            },
        )
        items = [
            TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo"),
            TranslationItem(id="2", key="menu.quit", text="Quit", mod_id="demo"),
        ]

        translations, failures = translator.translate_batch_with_failures(items)

        self.assertEqual({"1": "g:Start", "2": "g:Quit"}, translations)
        self.assertEqual({}, failures)
        self.assertEqual(1, translator._engine_build_count["google"])

    def test_translate_batch_with_failures_falls_back_when_batch_call_fails(self) -> None:
        translator = DeepFreeTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            engine_order=["google", "mymemory"],
            engine_factories={
                "google": lambda source, target, timeout: FakeBatchEngine(error=RuntimeError("google batch down")),
                "mymemory": lambda source, target, timeout: FakeBatchEngine(prefix="mm"),
            },
        )
        items = [
            TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo"),
            TranslationItem(id="2", key="menu.quit", text="Quit", mod_id="demo"),
        ]

        translations, failures = translator.translate_batch_with_failures(items)

        self.assertEqual({"1": "mm:Start", "2": "mm:Quit"}, translations)
        self.assertEqual({}, failures)

    def test_translate_batch_with_failures_returns_source_and_reason_when_all_engines_fail(self) -> None:
        translator = DeepFreeTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            engine_order=["google", "mymemory"],
            engine_factories={
                "google": lambda source, target, timeout: FakeEngine(error=RuntimeError("g timeout")),
                "mymemory": lambda source, target, timeout: FakeEngine(error=RuntimeError("mm 429")),
            },
        )
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("google", failures["1"])
        self.assertIn("mymemory", failures["1"])

    def test_translate_batch_with_failures_returns_source_when_locale_is_unsupported(self) -> None:
        translator = DeepFreeTranslator(source_locale="en_us", target_locale="lol_us")
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("unsupported", failures["1"])

    def test_translate_batch_with_failures_reports_missing_dependency(self) -> None:
        translator = DeepFreeTranslator(source_locale="en_us", target_locale="zh_cn")
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        original = DeepFreeTranslator._build_engine
        try:
            def _missing_dependency(self, engine_name: str, source_locale: str, target_locale: str):
                raise RuntimeError("deep-translator dependency is not installed")

            DeepFreeTranslator._build_engine = _missing_dependency
            translations, failures = translator.translate_batch_with_failures([item])
        finally:
            DeepFreeTranslator._build_engine = original

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("dependency is not installed", failures["1"])

    def test_provider_preset_is_registered(self) -> None:
        preset = get_provider_preset("deep-free")
        self.assertIsInstance(preset, ProviderPreset)
        self.assertEqual("Deep Translator（免费试用）", preset.label)
        self.assertEqual("deep-free", preset.model)
        self.assertEqual("", preset.api_key_env)

    def test_cli_exposes_deep_free_provider_choice(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["translate", "input.jar", "--provider", "deep-free"])
        self.assertEqual("deep-free", args.provider)

    def test_create_translator_supports_deep_free(self) -> None:
        args = argparse.Namespace(
            provider="deep-free",
            source_locale="en_us",
            target_locale="zh_cn",
            glossary=None,
            api_url="",
            api_key_env="",
            api_key="",
            model="",
            api_debug_log="",
            api_concurrency=1,
            api_retries=5,
            api_batch_size=20,
            api_timeout=10.0,
            overwrite_existing=False,
            skip_translated=False,
            pack_format="15",
            translation_memory_path="",
        )

        translator = create_translator(args)

        self.assertEqual("DeepFreeTranslator", translator.__class__.__name__)

    def test_web_ui_exposes_deep_free_provider(self) -> None:
        self.assertIn('<option value="deep-free">Deep Translator（免费试用）</option>', INDEX_HTML)
        self.assertIn("'deep-free': {", INDEX_HTML)
        self.assertIn("免费公共翻译源", INDEX_HTML)


class FakeEngine:
    def __init__(self, prefix: str = "", error: Exception | None = None) -> None:
        self.prefix = prefix
        self.error = error

    def translate(self, text: str) -> str:
        if self.error:
            raise self.error
        return f"{self.prefix}:{text}" if self.prefix else text


class FakeBatchEngine(FakeEngine):
    def translate_batch(self, texts: list[str]) -> list[str]:
        if self.error:
            raise self.error
        return [f"{self.prefix}:{text}" if self.prefix else text for text in texts]


if __name__ == "__main__":
    unittest.main()
