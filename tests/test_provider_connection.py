from __future__ import annotations

from io import BytesIO
import json
import urllib.error
import unittest
from unittest.mock import patch

from mc_mod_i18n.web import test_provider_connection


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
            )

        self.assertFalse(result["ok"])
        self.assertEqual("model_not_found", result["error_type"])
        self.assertIn("模型列表中没有 gpt-4o-mini", result["message"])


if __name__ == "__main__":
    unittest.main()
