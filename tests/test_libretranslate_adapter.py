from __future__ import annotations

import argparse
import json
import unittest

from mc_mod_i18n.cli import build_parser
from mc_mod_i18n.core import create_translator
from mc_mod_i18n.libretranslate_adapter import (
    LibreTranslateLocaleSupport,
    LibreTranslateTranslator,
    libretranslate_locale_support,
    normalize_libretranslate_base_url,
)
from mc_mod_i18n.translator import ProviderPreset, TranslationItem, get_provider_preset
from mc_mod_i18n.web import INDEX_HTML


class LibreTranslateAdapterTest(unittest.TestCase):
    def test_normalize_libretranslate_base_url_accepts_root_and_endpoint(self) -> None:
        self.assertEqual("http://127.0.0.1:5000", normalize_libretranslate_base_url("http://127.0.0.1:5000"))
        self.assertEqual("http://127.0.0.1:5000", normalize_libretranslate_base_url("http://127.0.0.1:5000/translate"))

    def test_common_locale_support_is_structured(self) -> None:
        support = libretranslate_locale_support("en_us", "zh_cn")
        self.assertIsInstance(support.source, LibreTranslateLocaleSupport)
        self.assertIsInstance(support.target, LibreTranslateLocaleSupport)
        self.assertEqual("en", support.source.libre)
        self.assertEqual("zh", support.target.libre)

    def test_special_locale_support_uses_provider_specific_codes(self) -> None:
        support = libretranslate_locale_support("pt_br", "zh_tw")
        self.assertEqual("pb", support.source.libre)
        self.assertEqual("zt", support.target.libre)

    def test_unsupported_locale_falls_back_to_copy(self) -> None:
        support = libretranslate_locale_support("lol_us", "zh_cn")
        self.assertEqual("fallback-copy", support.source.status)
        self.assertIsNone(support.source.libre)

    def test_translate_batch_with_failures_posts_array_payload(self) -> None:
        captured: dict[str, object] = {}

        def fake_request(method: str, url: str, payload: dict[str, object], timeout: float) -> object:
            captured["method"] = method
            captured["url"] = url
            captured["payload"] = payload
            captured["timeout"] = timeout
            if url.endswith("/languages"):
                return [{"code": "en", "name": "English", "targets": ["zh"]}, {"code": "zh", "name": "Chinese", "targets": ["en"]}]
            return {"translatedText": ["你好", "退出"]}

        translator = LibreTranslateTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            api_url="http://127.0.0.1:5000",
            api_key="",
            request_timeout=7.0,
            request_func=fake_request,
        )
        items = [
            TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo"),
            TranslationItem(id="2", key="menu.quit", text="Quit", mod_id="demo"),
        ]

        translations, failures = translator.translate_batch_with_failures(items)

        self.assertEqual({"1": "你好", "2": "退出"}, translations)
        self.assertEqual({}, failures)
        self.assertEqual("POST", captured["method"])
        self.assertEqual("http://127.0.0.1:5000/translate", captured["url"])
        self.assertEqual(
            {
                "q": ["Start", "Quit"],
                "source": "en",
                "target": "zh",
                "format": "text",
            },
            captured["payload"],
        )
        self.assertEqual(7.0, captured["timeout"])

    def test_translate_batch_with_failures_appends_api_key_when_present(self) -> None:
        payloads: list[dict[str, object]] = []

        def fake_request(method: str, url: str, payload: dict[str, object], timeout: float) -> object:
            payloads.append(payload)
            if url.endswith("/languages"):
                return [{"code": "en", "name": "English", "targets": ["es"]}, {"code": "es", "name": "Spanish", "targets": ["en"]}]
            return {"translatedText": ["Hola"]}

        translator = LibreTranslateTranslator(
            source_locale="en_us",
            target_locale="es_es",
            api_url="http://127.0.0.1:5000",
            api_key="secret-key",
            request_timeout=5.0,
            request_func=fake_request,
        )
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Hola"}, translations)
        self.assertEqual({}, failures)
        self.assertEqual("secret-key", payloads[-1]["api_key"])

    def test_translate_batch_with_failures_returns_source_when_provider_language_missing(self) -> None:
        def fake_request(method: str, url: str, payload: dict[str, object], timeout: float) -> object:
            if url.endswith("/languages"):
                return [{"code": "en", "name": "English", "targets": ["es"]}, {"code": "es", "name": "Spanish", "targets": ["en"]}]
            raise AssertionError("translate endpoint should not be called")

        translator = LibreTranslateTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            api_url="http://127.0.0.1:5000",
            request_func=fake_request,
        )
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("unsupported target locale", failures["1"])

    def test_translate_batch_with_failures_returns_source_when_api_returns_error(self) -> None:
        def fake_request(method: str, url: str, payload: dict[str, object], timeout: float) -> object:
            if url.endswith("/languages"):
                return [{"code": "en", "name": "English", "targets": ["zh"]}, {"code": "zh", "name": "Chinese", "targets": ["en"]}]
            return {"error": "Slow down"}

        translator = LibreTranslateTranslator(
            source_locale="en_us",
            target_locale="zh_cn",
            api_url="http://127.0.0.1:5000",
            request_func=fake_request,
        )
        item = TranslationItem(id="1", key="menu.start", text="Start", mod_id="demo")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertEqual({"1": "Start"}, translations)
        self.assertIn("Slow down", failures["1"])

    def test_provider_preset_is_registered(self) -> None:
        preset = get_provider_preset("libretranslate")
        self.assertIsInstance(preset, ProviderPreset)
        self.assertEqual("LibreTranslate（自托管/托管）", preset.label)
        self.assertEqual("http://127.0.0.1:5000", preset.api_url)

    def test_cli_exposes_libretranslate_provider_choice(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["translate", "input.jar", "--provider", "libretranslate"])
        self.assertEqual("libretranslate", args.provider)

    def test_create_translator_supports_libretranslate(self) -> None:
        args = argparse.Namespace(
            provider="libretranslate",
            source_locale="en_us",
            target_locale="zh_cn",
            glossary=None,
            api_url="http://127.0.0.1:5000",
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

        self.assertEqual("LibreTranslateTranslator", translator.__class__.__name__)

    def test_web_ui_exposes_libretranslate_provider(self) -> None:
        self.assertIn('<option value="libretranslate">LibreTranslate（自托管/托管）</option>', INDEX_HTML)
        self.assertIn("'libretranslate': {", INDEX_HTML)
        self.assertIn("可连接自托管或托管实例", INDEX_HTML)


if __name__ == "__main__":
    unittest.main()
