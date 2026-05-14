from __future__ import annotations

import os
import unittest

from mc_mod_i18n.deep_translator_adapter import DeepFreeTranslator
from mc_mod_i18n.translator import TranslationItem


@unittest.skipUnless(os.environ.get("MC_MOD_I18N_LIVE_TRANSLATION_TESTS") == "1", "live translation tests are disabled")
class DeepTranslatorLiveTest(unittest.TestCase):
    def test_deep_free_returns_translation_or_readable_failure(self) -> None:
        translator = DeepFreeTranslator(source_locale="en_us", target_locale="zh_cn")
        item = TranslationItem(id="1", key="probe", text="Hello world", mod_id="live")

        translations, failures = translator.translate_batch_with_failures([item])

        self.assertIn("1", translations)
        result = translations["1"]
        if result == "Hello world":
            self.assertIn("1", failures)
            self.assertTrue(failures["1"].strip())
        else:
            self.assertTrue(result.strip())


if __name__ == "__main__":
    unittest.main()
