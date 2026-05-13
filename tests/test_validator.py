from __future__ import annotations

import unittest

from mc_mod_i18n.lang import LangDocument
from mc_mod_i18n.validator import pre_check_lang_documents, validate_translation


def lang_doc(entries: dict[str, str]) -> LangDocument:
    return LangDocument(
        path="assets/create/lang/en_us.json",
        mod_id="create",
        locale="en_us",
        format="json",
        entries=entries,
    )


class ValidatorTest(unittest.TestCase):
    def test_precheck_accepts_literal_percent_values(self) -> None:
        warnings = pre_check_lang_documents([
            lang_doc(
                {
                    "advancement.create.stressometer_maxed.desc": "Stress capacity reached 100%",
                    "create.gui.terrainzapper.pattern.chance25": "25%",
                    "create.gui.terrainzapper.pattern.chance50": "50 %",
                }
            )
        ])

        self.assertEqual([], [warning for warning in warnings if warning.category == "unusual_placeholder"])

    def test_precheck_still_reports_non_standard_percent_tokens(self) -> None:
        warnings = pre_check_lang_documents([
            lang_doc({"screen.example.value": "Progress: %q"})
        ])

        self.assertEqual(["unusual_placeholder"], [warning.category for warning in warnings])

    def test_precheck_accepts_intentional_blank_numbered_tooltip_lines(self) -> None:
        warnings = pre_check_lang_documents([
            lang_doc(
                {
                    "create.schematic.tool.flip.description.1": "Flip the Schematic",
                    "create.schematic.tool.flip.description.2": "",
                    "create.schematic.tool.flip.description.3": "",
                    "create.schematic.tool.flip.description.4": "Hold Ctrl to mirror on the other axis",
                }
            )
        ])

        self.assertEqual([], [warning for warning in warnings if warning.category == "empty_value"])

    def test_precheck_reports_plain_empty_values(self) -> None:
        warnings = pre_check_lang_documents([
            lang_doc({"item.example.empty": ""})
        ])

        self.assertEqual(["empty_value"], [warning.category for warning in warnings])

    def test_translation_validation_keeps_java_format_placeholders_strict(self) -> None:
        errors = validate_translation("Speed: %1$s %<s", "速度：%1$s")

        self.assertIn("missing printf placeholder: %<s", errors)


if __name__ == "__main__":
    unittest.main()
