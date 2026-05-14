from __future__ import annotations

import argparse
import unittest

from mc_mod_i18n.cli import build_parser
from mc_mod_i18n.core import create_translator
from mc_mod_i18n.argos_adapter import (
    ArgosLocaleSupport,
    ArgosTranslator,
    argos_locale_support,
)
from mc_mod_i18n.translator import ProviderPreset, TranslationItem, get_provider_preset
from mc_mod_i18n.web import INDEX_HTML


class ArgosAdapterTest(unittest.TestCase):
    def test_common_locale_support_is_structured(self) -> None:
        support = argos_locale_support("en_us", "zh_cn")
        self.assertIsInstance(support.source, ArgosLocaleSupport)
        self.assertIsInstance(support.target, ArgosLocaleSupport)
        self.assertEqual("en", support.source.argos)
        self.assertEqual("zh", support.target.argos)

    def test_unknown_language_prefix_falls_back_to_copy(self) -> None:
        support = argos_locale_support("lol_us", "zh_cn")
        self.assertEqual("fallback-copy", support.source.status)
        self.assertIsNone(support.source.argos)

    def test_translate_batch_with_failures_uses_backend_translation(self) -> None:
        backend = FakeArgosBackend(
            installed_languages={"en", "zh"},
            translations={("en", "zh", "Start"): "开始", ("en", "zh", "Quit"): "退出"},
        )
        translator = ArgosTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            backend=backend,
        )
        items = [
            TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo"),
            TranslationItem(id="2", key="menu.quit", text="Quit", mod_id="demo"),
        ]

        translations, failures = translator.translate_batch_with_failures(items)

        self.assertEqual({"1": "开始", "2": "退出"}, translations)
        self.assertEqual({}, failures)
        self.assertEqual([("en", "zh", ["Start", "Quit"])], backend.calls)

    def test_translate_batch_with_failures_returns_source_when_package_missing(self) -> None:
        backend = FakeArgosBackend(installed_languages={"en"}, translations={})
        translator = ArgosTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            backend=backend,
        )
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("missing Argos language package", failures["1"])

    def test_translate_batch_with_failures_reports_missing_dependency(self) -> None:
        translator = ArgosTranslator(source_locale="en_us", target_locale="zh_cn", backend=MissingArgosBackend())
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("argostranslate dependency is not installed", failures["1"])

    def test_provider_preset_is_registered(self) -> None:
        preset = get_provider_preset("argos")
        self.assertIsInstance(preset, ProviderPreset)
        self.assertEqual("Argos Translate（离线）", preset.label)
        self.assertEqual("argos", preset.model)

    def test_cli_exposes_argos_provider_choice(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["translate", "input.jar", "--provider", "argos"])
        self.assertEqual("argos", args.provider)

    def test_create_translator_supports_argos(self) -> None:
        args = argparse.Namespace(
            provider="argos",
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

        self.assertEqual("ArgosTranslator", translator.__class__.__name__)

    def test_web_ui_exposes_argos_provider(self) -> None:
        self.assertIn('<option value="argos">Argos Translate（离线）</option>', INDEX_HTML)
        self.assertIn("'argos': {", INDEX_HTML)
        self.assertIn("本地离线翻译", INDEX_HTML)


class FakeArgosBackend:
    def __init__(self, installed_languages: set[str], translations: dict[tuple[str, str, str], str]) -> None:
        self.installed_languages = installed_languages
        self.translations = translations
        self.calls: list[tuple[str, str, list[str]]] = []

    def is_available(self) -> bool:
        return True

    def has_language(self, code: str) -> bool:
        return code in self.installed_languages

    def translate_batch(self, source_code: str, target_code: str, texts: list[str]) -> list[str]:
        self.calls.append((source_code, target_code, list(texts)))
        return [self.translations[(source_code, target_code, text)] for text in texts]


class MissingArgosBackend:
    def is_available(self) -> bool:
        return False

    def has_language(self, code: str) -> bool:
        return False

    def translate_batch(self, source_code: str, target_code: str, texts: list[str]) -> list[str]:
        raise RuntimeError("argostranslate dependency is not installed")


if __name__ == "__main__":
    unittest.main()
