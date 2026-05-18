from __future__ import annotations

import argparse
import unittest

from mc_mod_i18n.cli import build_parser
from mc_mod_i18n.core import create_translator
from mc_mod_i18n.azure_translator_adapter import (
    AzureTranslatorLocaleSupport,
    AzureTranslatorTranslator,
    azure_translator_locale_support,
    normalize_azure_base_url,
)
from mc_mod_i18n.translator import ProviderPreset, TranslationItem, get_provider_preset
from mc_mod_i18n.web import INDEX_HTML


class AzureTranslatorAdapterTest(unittest.TestCase):
    def test_normalize_azure_base_url_accepts_root_and_translate_path(self) -> None:
        self.assertEqual("https://api.cognitive.microsofttranslator.com", normalize_azure_base_url("https://api.cognitive.microsofttranslator.com"))
        self.assertEqual("https://api.cognitive.microsofttranslator.com", normalize_azure_base_url("https://api.cognitive.microsofttranslator.com/translate"))

    def test_common_locale_support_is_structured(self) -> None:
        support = azure_translator_locale_support("en_us", "zh_cn")
        self.assertIsInstance(support.source, AzureTranslatorLocaleSupport)
        self.assertIsInstance(support.target, AzureTranslatorLocaleSupport)
        self.assertEqual("en", support.source.azure)
        self.assertEqual("zh-Hans", support.target.azure)

    def test_special_locale_support_uses_provider_specific_codes(self) -> None:
        support = azure_translator_locale_support("zh_hk", "pt_br")
        self.assertEqual("zh-Hant", support.source.azure)
        self.assertEqual("pt", support.target.azure)

    def test_unsupported_locale_falls_back_to_copy(self) -> None:
        support = azure_translator_locale_support("lol_us", "zh_cn")
        self.assertEqual("fallback-copy", support.source.status)
        self.assertIsNone(support.source.azure)

    def test_translate_batch_with_failures_posts_expected_payload(self) -> None:
        captured: dict[str, object] = {}

        def fake_request(method: str, url: str, headers: dict[str, str], payload: object, timeout: float) -> object:
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            captured["timeout"] = timeout
            return [
                {"translations": [{"text": "开始", "to": "zh-Hans"}]},
                {"translations": [{"text": "退出", "to": "zh-Hans"}]},
            ]

        translator = AzureTranslatorTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            api_url="https://api.cognitive.microsofttranslator.com",
            api_key="secret-key",
            api_region="global",
            request_timeout=8.0,
            request_func=fake_request,
        )
        items = [
            TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo"),
            TranslationItem(id="2", key="menu.quit", text="Quit", mod_id="demo"),
        ]

        translations, failures = translator.translate_batch_with_failures(items)

        self.assertEqual({"1": "开始", "2": "退出"}, translations)
        self.assertEqual({}, failures)
        self.assertEqual("POST", captured["method"])
        self.assertIn("/translate?api-version=3.0&from=en&to=zh-Hans", str(captured["url"]))
        self.assertEqual(
            [
                {"Text": "Start"},
                {"Text": "Quit"},
            ],
            captured["payload"],
        )
        headers = captured["headers"]
        self.assertEqual("secret-key", headers["Ocp-Apim-Subscription-Key"])
        self.assertEqual("global", headers["Ocp-Apim-Subscription-Region"])
        self.assertEqual(8.0, captured["timeout"])

    def test_translate_batch_with_failures_returns_source_when_api_key_missing(self) -> None:
        translator = AzureTranslatorTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            api_url="https://api.cognitive.microsofttranslator.com",
            api_key="",
            api_region="global",
        )
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("API key is required", failures["1"])

    def test_translate_batch_with_failures_returns_source_when_api_returns_error(self) -> None:
        def fake_request(method: str, url: str, headers: dict[str, str], payload: object, timeout: float) -> object:
            raise RuntimeError("403 Forbidden")

        translator = AzureTranslatorTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            api_url="https://api.cognitive.microsofttranslator.com",
            api_key="secret-key",
            api_region="global",
            request_func=fake_request,
        )
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("403 Forbidden", failures["1"])

    def test_provider_preset_is_registered(self) -> None:
        preset = get_provider_preset("azure-translator")
        self.assertIsInstance(preset, ProviderPreset)
        self.assertEqual("Azure Translator", preset.label)
        self.assertEqual("https://api.cognitive.microsofttranslator.com", preset.api_url)

    def test_cli_exposes_azure_translator_provider_choice(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["translate", "input.jar", "--provider", "azure-translator"])
        self.assertEqual("azure-translator", args.provider)

    def test_create_translator_supports_azure_translator(self) -> None:
        args = argparse.Namespace(
            provider="azure-translator",
            source_locale="en_us",
            target_locale="zh_cn",
            glossary=None,
            api_url="https://api.cognitive.microsofttranslator.com",
            api_key_env="AZURE_TRANSLATOR_KEY",
            api_key="",
            api_region="global",
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

        self.assertEqual("AzureTranslatorTranslator", translator.__class__.__name__)

    def test_web_ui_exposes_azure_translator_provider(self) -> None:
        self.assertIn('<option value="azure-translator" data-i18n="provider.azure-translator">Azure Translator</option>', INDEX_HTML)
        self.assertIn("'azure-translator': {", INDEX_HTML)
        self.assertIn("api_region", INDEX_HTML)
        self.assertIn("Azure 官方翻译服务", INDEX_HTML)


if __name__ == "__main__":
    unittest.main()
