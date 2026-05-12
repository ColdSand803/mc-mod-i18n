from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from mc_mod_i18n.ui_i18n import (
    BUILTIN_UI_LOCALES,
    base_message_keys,
    build_ui_locale_missing_template,
    check_ui_locale_package,
    export_ui_locale_package,
    list_ui_locales,
    parse_ui_locale_package,
    resolve_ui_locale_root,
    translate_ui,
    write_extension_package,
)


class UiI18nTest(unittest.TestCase):
    def test_builtin_ui_locales_are_complete(self) -> None:
        base_keys = base_message_keys()
        for code, entry in BUILTIN_UI_LOCALES.items():
            with self.subTest(code=code):
                self.assertEqual(set(), base_keys - set(entry["messages"]))

    def test_parse_ui_locale_package_supports_schema_and_flat_json(self) -> None:
        package = parse_ui_locale_package(
            {
                "schema_version": 1,
                "locale": "fr_fr",
                "name": "French",
                "native_name": "Français",
                "messages": {"app.title": "Titre"},
            },
            "fr_fr.json",
        )
        self.assertEqual("fr_fr", package["locale"])
        self.assertEqual({"app.title": "Titre"}, package["messages"])

        flat = parse_ui_locale_package({"app.title": "Titel"}, "de_de.json")
        self.assertEqual("de_de", flat["locale"])
        self.assertEqual({"app.title": "Titel"}, flat["messages"])

    def test_extension_language_pack_can_be_written_listed_and_exported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = write_extension_package(
                root,
                {
                    "locale": "fr_fr",
                    "name": "French",
                    "native_name": "Français",
                    "messages": {"app.brand.name": "Atelier"},
                },
            )
            self.assertEqual("fr_fr", result["locale"])
            self.assertTrue((root / "fr_fr.json").is_file())

            locales = {item.code: item for item in list_ui_locales(root)}
            self.assertIn("zh_cn", locales)
            self.assertIn("en_us", locales)
            self.assertIn("fr_fr", locales)
            self.assertFalse(locales["fr_fr"].builtin)

            exported = export_ui_locale_package("fr_fr", root)
            self.assertEqual("fr_fr", exported["locale"])
            self.assertEqual("Atelier", exported["messages"]["app.brand.name"])
            self.assertIn("nav.workspace", exported["messages"])

    def test_resolve_ui_locale_root_defaults_to_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = resolve_ui_locale_root(Path(tmp), "")
            self.assertEqual(Path(tmp, ".ui-locales").resolve(), root)

    def test_translate_ui_formats_and_falls_back(self) -> None:
        self.assertEqual("Upload a language JSON file", translate_ui("error.json_missing_input", "en_us"))
        self.assertEqual("缺少 Name: {bad}", translate_ui("result.missing_token", "zh_cn", label="Name", tokens="{bad}"))
        self.assertEqual("missing.key", translate_ui("missing.key", "en_us"))

    def test_ui_locale_checker_reports_missing_extra_and_placeholder_mismatches(self) -> None:
        package = parse_ui_locale_package(
            {
                "locale": "fr_fr",
                "messages": {
                    "app.brand.name": "Atelier",
                    "result.missing_token": "Il manque {label}",
                    "custom.extra": "Extra",
                },
            },
            "fr_fr.json",
        )

        check = check_ui_locale_package(package)

        self.assertGreater(check["missing_count"], 0)
        self.assertIn("nav.workspace", check["missing_keys"])
        self.assertEqual(["custom.extra"], check["extra_keys"])
        mismatch = next(item for item in check["placeholder_mismatches"] if item["key"] == "result.missing_token")
        self.assertEqual(["{label}", "{tokens}"], mismatch["expected"])
        self.assertEqual(["{label}"], mismatch["actual"])
        self.assertFalse(check["complete"])

    def test_ui_locale_missing_template_contains_only_missing_base_keys(self) -> None:
        package = parse_ui_locale_package({"locale": "fr_fr", "messages": {"app.brand.name": "Atelier"}}, "fr_fr.json")

        template = build_ui_locale_missing_template(package)

        self.assertEqual("fr_fr", template["locale"])
        self.assertIn("nav.workspace", template["messages"])
        self.assertNotIn("app.brand.name", template["messages"])


if __name__ == "__main__":
    unittest.main()
