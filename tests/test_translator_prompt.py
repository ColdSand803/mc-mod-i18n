from __future__ import annotations

import json
import unittest

from mc_mod_i18n.translator import OpenAICompatibleTranslator, TranslationItem


class CapturingTranslator(OpenAICompatibleTranslator):
    def __init__(self, target_locale: str) -> None:
        super().__init__(
            api_url="https://example.test/v1/chat/completions",
            api_key_env="TEST_API_KEY",
            api_key="test-key",
            model="test-model",
            target_locale=target_locale,
        )
        self.payload: dict[str, object] | None = None

    def _open_with_retries(self, request, items, start_time=0.0):
        self.payload = json.loads(request.data.decode("utf-8"))
        return 200, {}, json.dumps({
            "choices": [
                {
                    "message": {
                        "content": json.dumps([{"id": items[0].id, "text": "銅錠"}], ensure_ascii=False)
                    }
                }
            ]
        }, ensure_ascii=False)


class TranslatorPromptTest(unittest.TestCase):
    def test_prompt_uses_traditional_chinese_when_target_locale_is_zh_tw(self) -> None:
        translator = CapturingTranslator(target_locale="zh_tw")

        translator.translate_batch([TranslationItem("1", "item.example.copper", "Copper Ingot", "example")])

        assert translator.payload is not None
        system_prompt = translator.payload["messages"][0]["content"]
        self.assertIn("繁體中文", system_prompt)
        self.assertNotIn("翻译成简体中文", system_prompt)


if __name__ == "__main__":
    unittest.main()
