from __future__ import annotations

import unittest

from mc_mod_i18n.response_guard import inspect_provider_response, sanitize_provider_response


class ResponseGuardTest(unittest.TestCase):
    def test_blocks_public_token_group_notice_in_any_response_text(self) -> None:
        result = inspect_provider_response("公益 token2 通知群：1104138863")

        self.assertTrue(result.blocked)
        self.assertIn("public-token-notice", result.message)
        self.assertIn("notification-group", result.message)
        self.assertIn("1104138863", result.message)

    def test_allows_normal_code_or_translation_text(self) -> None:
        result = inspect_provider_response("def add(a, b):\n    return a + b\n")

        self.assertFalse(result.blocked)
        self.assertEqual("", result.message)

    def test_supports_project_specific_extra_keywords(self) -> None:
        result = inspect_provider_response("please join mirror relay", extra_keywords=["mirror relay"])

        self.assertTrue(result.blocked)
        self.assertIn("custom-keyword-1", result.message)

    def test_sanitizes_polluted_tail_and_keeps_clean_content(self) -> None:
        result = sanitize_provider_response("铜锭\n公益 token2 通知群：1104138863")

        self.assertTrue(result.changed)
        self.assertEqual("铜锭", result.text)
        self.assertIn("filtered suspicious provider response", result.message)

    def test_sanitizes_to_empty_when_response_only_contains_pollution(self) -> None:
        result = sanitize_provider_response("公益 token2 通知群：1104138863")

        self.assertTrue(result.changed)
        self.assertEqual("", result.text)


if __name__ == "__main__":
    unittest.main()
