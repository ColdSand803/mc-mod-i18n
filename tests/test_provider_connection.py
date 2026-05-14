from __future__ import annotations

from io import BytesIO
import json
import urllib.error
import unittest
from unittest.mock import patch

from mc_mod_i18n.web import provider_test_help_slug, test_provider_connection


class FakeResponse:
    def __init__(self, body: str, status: int = 200) -> None:
        self.body = body.encode("utf-8")
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class ProviderConnectionTest(unittest.TestCase):
    def test_provider_test_help_slug_maps_common_failures(self) -> None:
        self.assertEqual("providers", provider_test_help_slug({"provider": "openai-compatible", "error_type": "auth"}))
        self.assertEqual("providers", provider_test_help_slug({"provider": "azure-translator", "error_type": "auth"}))
        self.assertEqual("faq", provider_test_help_slug({"provider": "deep-free", "error_type": "network"}))
        self.assertEqual("providers", provider_test_help_slug({"provider": "argos", "error_type": "missing_package"}))
        self.assertEqual("", provider_test_help_slug({"provider": "glossary", "ok": True}))

    def test_azure_translator_success_uses_provider_specific_smoke_test(self) -> None:
        with patch("mc_mod_i18n.web.azure_translator_smoke_test", return_value={"ok": True, "provider": "azure-translator", "model": "azure-translator", "latency_ms": 7, "message": "连接正常"}):
            result = test_provider_connection(
                provider="azure-translator",
                api_url="https://api.cognitive.microsofttranslator.com",
                api_key="secret-key",
                api_key_env="AZURE_TRANSLATOR_KEY",
                model="azure-translator",
                timeout=4,
                api_region="global",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("azure-translator", result["provider"])
        self.assertEqual("azure-translator", result["model"])

    def test_azure_translator_smoke_test_passes_base_url_key_and_region(self) -> None:
        captured: dict[str, object] = {}

        def fake_smoke_test(base_url: str, api_key: str, api_region: str, timeout: float) -> dict[str, object]:
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured["api_region"] = api_region
            captured["timeout"] = timeout
            return {"ok": False, "provider": "azure-translator", "model": "azure-translator", "latency_ms": 3, "message": "401 Unauthorized", "error_type": "auth"}

        with patch("mc_mod_i18n.web.azure_translator_smoke_test", fake_smoke_test):
            result = test_provider_connection(
                provider="azure-translator",
                api_url="https://api.cognitive.microsofttranslator.com/translate",
                api_key="secret-key",
                api_key_env="AZURE_TRANSLATOR_KEY",
                model="azure-translator",
                timeout=9,
                api_region="eastasia",
            )

        self.assertFalse(result["ok"])
        self.assertEqual("https://api.cognitive.microsofttranslator.com/translate", captured["base_url"])
        self.assertEqual("secret-key", captured["api_key"])
        self.assertEqual("eastasia", captured["api_region"])
        self.assertEqual(9, captured["timeout"])
        self.assertEqual("auth", result["error_type"])

    def test_argos_success_uses_provider_specific_smoke_test(self) -> None:
        with patch("mc_mod_i18n.web.argos_smoke_test", return_value={"ok": True, "provider": "argos", "model": "argos", "latency_ms": 6, "message": "连接正常"}):
            result = test_provider_connection(
                provider="argos",
                api_url="",
                api_key="",
                api_key_env="",
                model="argos",
                timeout=4,
                api_region="",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("argos", result["provider"])
        self.assertEqual("argos", result["model"])

    def test_argos_smoke_test_uses_timeout_only(self) -> None:
        captured: dict[str, object] = {}

        def fake_smoke_test(timeout: float) -> dict[str, object]:
            captured["timeout"] = timeout
            return {"ok": False, "provider": "argos", "model": "argos", "latency_ms": 2, "message": "argostranslate dependency is not installed", "error_type": "missing_dependency"}

        with patch("mc_mod_i18n.web.argos_smoke_test", fake_smoke_test):
            result = test_provider_connection(
                provider="argos",
                api_url="",
                api_key="ignored",
                api_key_env="IGNORED",
                model="argos",
                timeout=11,
                api_region="",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(11, captured["timeout"])
        self.assertEqual("missing_dependency", result["error_type"])

    def test_libretranslate_success_uses_provider_specific_smoke_test(self) -> None:
        with patch("mc_mod_i18n.web.libretranslate_smoke_test", return_value={"ok": True, "provider": "libretranslate", "model": "libretranslate", "latency_ms": 8, "message": "连接正常"}):
            result = test_provider_connection(
                provider="libretranslate",
                api_url="http://127.0.0.1:5000",
                api_key="",
                api_key_env="",
                model="libretranslate",
                timeout=4,
                api_region="",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("libretranslate", result["provider"])
        self.assertEqual("libretranslate", result["model"])

    def test_libretranslate_smoke_test_passes_base_url_and_key(self) -> None:
        captured: dict[str, object] = {}

        def fake_smoke_test(base_url: str, api_key: str, timeout: float) -> dict[str, object]:
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured["timeout"] = timeout
            return {"ok": False, "provider": "libretranslate", "model": "libretranslate", "latency_ms": 5, "message": "unauthorized", "error_type": "auth"}

        with patch("mc_mod_i18n.web.libretranslate_smoke_test", fake_smoke_test):
            result = test_provider_connection(
                provider="libretranslate",
                api_url="http://127.0.0.1:5000/translate",
                api_key="secret-key",
                api_key_env="",
                model="libretranslate",
                timeout=9,
                api_region="",
            )

        self.assertFalse(result["ok"])
        self.assertEqual("http://127.0.0.1:5000/translate", captured["base_url"])
        self.assertEqual("secret-key", captured["api_key"])
        self.assertEqual(9, captured["timeout"])
        self.assertEqual("auth", result["error_type"])

    def test_deep_free_success_does_not_require_api_key(self) -> None:
        with patch("mc_mod_i18n.web.deep_free_smoke_test", return_value={"ok": True, "provider": "deep-free", "model": "deep-free", "latency_ms": 12, "message": "连接正常"}):
            result = test_provider_connection(
                provider="deep-free",
                api_url="",
                api_key="",
                api_key_env="",
                model="deep-free",
                timeout=3,
                api_region="",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("deep-free", result["provider"])
        self.assertEqual("deep-free", result["model"])
        self.assertIn("连接正常", result["message"])

    def test_deep_free_uses_provider_specific_smoke_test(self) -> None:
        captured = {}

        def fake_smoke_test(timeout: float) -> dict[str, object]:
            captured["timeout"] = timeout
            return {"ok": False, "provider": "deep-free", "model": "deep-free", "latency_ms": 3, "message": "google: timeout", "error_type": "network"}

        with patch("mc_mod_i18n.web.deep_free_smoke_test", fake_smoke_test):
            result = test_provider_connection(
                provider="deep-free",
                api_url="",
                api_key="",
                api_key_env="",
                model="deep-free",
                timeout=7,
                api_region="",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(7, captured["timeout"])
        self.assertEqual("network", result["error_type"])
        self.assertIn("google: timeout", result["message"])

    def test_openai_compatible_success_uses_models_endpoint(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse('{"data":[{"id":"gpt-4o-mini"}]}')

        with patch("mc_mod_i18n.web.urllib.request.urlopen", fake_urlopen):
            result = test_provider_connection(
                provider="openai-compatible",
                api_url="https://example.test/v1/chat/completions",
                api_key="sk-secret",
                api_key_env="OPENAI_API_KEY",
                model="gpt-4o-mini",
                timeout=3,
                api_region="",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("openai-compatible", result["provider"])
        self.assertEqual("gpt-4o-mini", result["model"])
        self.assertGreaterEqual(result["latency_ms"], 0)
        self.assertIn("连接正常", result["message"])
        self.assertEqual("https://example.test/v1/models", captured["request"].full_url)
        self.assertEqual(3, captured["timeout"])
        self.assertNotIn("sk-secret", json.dumps(result, ensure_ascii=False))

    def test_http_401_is_classified_as_auth_without_leaking_key(self) -> None:
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                BytesIO(b'{"error":"bad key sk-secret"}'),
            )

        with patch("mc_mod_i18n.web.urllib.request.urlopen", fake_urlopen):
            result = test_provider_connection(
                provider="openai-compatible",
                api_url="https://example.test/v1",
                api_key="sk-secret",
                api_key_env="OPENAI_API_KEY",
                model="gpt-4o-mini",
                timeout=3,
                api_region="",
            )

        self.assertFalse(result["ok"])
        self.assertEqual("auth", result["error_type"])
        self.assertIn("认证失败", result["message"])
        self.assertNotIn("sk-secret", json.dumps(result, ensure_ascii=False))

    def test_missing_model_is_structured_when_models_endpoint_works(self) -> None:
        def fake_urlopen(request, timeout):
            return FakeResponse('{"data":[{"id":"other-model"}]}')

        with patch("mc_mod_i18n.web.urllib.request.urlopen", fake_urlopen):
            result = test_provider_connection(
                provider="openai-compatible",
                api_url="https://example.test/v1",
                api_key="sk-secret",
                api_key_env="OPENAI_API_KEY",
                model="gpt-4o-mini",
                timeout=3,
                api_region="",
            )

        self.assertFalse(result["ok"])
        self.assertEqual("model_not_found", result["error_type"])
        self.assertIn("模型列表中没有 gpt-4o-mini", result["message"])


if __name__ == "__main__":
    unittest.main()
