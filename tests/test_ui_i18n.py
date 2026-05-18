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

    def test_docs_and_help_ui_messages_are_bilingual(self) -> None:
        required = (
            "docs.subtitle",
            "docs.directory",
            "docs.filter_hint",
            "docs.search",
            "docs.search_placeholder",
            "docs.select_prompt",
            "docs.detail",
            "docs.related_topics",
            "docs.empty",
            "docs.builtin",
            "docs.no_related",
            "docs.category.start",
            "docs.category.providers",
            "docs.category.workflow",
            "docs.category.operations",
            "docs.category.support",
            "docs.category.default",
            "docs.applies.workspace",
            "docs.applies.history",
            "docs.applies.report",
            "docs.applies.api_log",
            "docs.applies.settings",
            "docs.applies.hardcoded",
            "docs.applies.preflight",
            "docs.applies.output_policy",
            "docs.applies.translation_memory",
            "docs.applies.hardcoded_scan",
            "docs.applies.provider",
            "help.subtitle",
            "help.topic_scenarios",
            "help.quick_check",
            "help.quick_check_subtitle",
            "help.preview_empty",
            "help.common_causes",
            "help.next_steps",
            "help.open_full_doc",
            "help.no_recommendations",
            "help.default_summary",
            "help.default_cause",
            "help.default_next",
            "help.topic.quick_start.title",
            "help.topic.quick_start.summary",
            "help.issue.quick_start.summary",
            "help.issue.quick_start.cause_1",
            "help.issue.quick_start.next_1",
        )
        for key in required:
            with self.subTest(key=key):
                self.assertIn(key, BUILTIN_UI_LOCALES["zh_cn"]["messages"])
                self.assertIn(key, BUILTIN_UI_LOCALES["en_us"]["messages"])
                self.assertNotEqual(key, translate_ui(key, "zh_cn"))
                self.assertNotEqual(key, translate_ui(key, "en_us"))

    def test_high_visibility_web_ui_strings_are_bilingual(self) -> None:
        required = (
            "workflow.input_step",
            "workflow.language_step",
            "workflow.optional_step",
            "workflow.preflight_step",
            "advanced.apply_key",
            "advanced.region_help",
            "docs.open_provider",
            "docs.open_output",
            "docs.open_preflight",
            "docs.open_history",
            "docs.open_memory",
            "docs.open_report",
            "docs.open_api_log",
            "history.detail",
            "history.select_detail",
            "history.no_detail",
            "history.open_primary",
            "history.open_help",
            "history.progress",
            "history.error_message",
            "history.artifacts",
            "history.open_artifact",
            "history.stats.total",
            "history.stats.done",
            "history.stats.failed",
            "history.stats.generated",
            "settings.history_section",
            "settings.history_limit",
            "settings.history_limit_placeholder",
            "settings.history_current",
            "settings.history_delete_ids",
            "settings.history_delete_ids_placeholder",
            "settings.history_refresh",
            "settings.history_trim",
            "settings.history_delete",
            "settings.history_clear",
            "settings.history_note",
            "settings.history_note_body",
            "pack_dialog.review_title",
            "pack_dialog.review_body",
            "result.api_log_deep_free_empty",
        )
        for key in required:
            with self.subTest(key=key):
                self.assertIn(key, BUILTIN_UI_LOCALES["zh_cn"]["messages"])
                self.assertIn(key, BUILTIN_UI_LOCALES["en_us"]["messages"])
                self.assertNotEqual(key, translate_ui(key, "zh_cn"))
                self.assertNotEqual(key, translate_ui(key, "en_us"))

    def test_parse_ui_locale_package_supports_schema_and_flat_json(self) -> None:
        package = parse_ui_locale_package(
            {
                "schema_version": 1,
                "locale": "fr_fr",
                "name": "French",
                "native_name": "Français",
                "messages": {"app.title": "Titre"},
                "docs": [{"slug": "quick-start", "title": "Demarrage", "content": "# Demarrage"}],
            },
            "fr_fr.json",
        )
        self.assertEqual("fr_fr", package["locale"])
        self.assertEqual({"app.title": "Titre"}, package["messages"])
        self.assertEqual("quick-start", package["docs"][0]["slug"])

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

    def test_export_ui_locale_package_includes_help_docs_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = Path(__file__).resolve().parents[1] / "docs" / "help"
            exported = export_ui_locale_package("ja_jp", root, {"ja_jp": "日本語"}, docs_root)

            self.assertEqual("ja_jp", exported["locale"])
            self.assertEqual("日本語", exported["name"])
            self.assertIn("docs", exported)
            quick_start = next(item for item in exported["docs"] if item["slug"] == "quick-start")
            self.assertEqual("快速开始", quick_start["title"])
            self.assertIn("# 快速开始", quick_start["content"])

    def test_resolve_ui_locale_root_defaults_to_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = resolve_ui_locale_root(Path(tmp), "")
            self.assertEqual(Path(tmp, "extensions", "ui-locales").resolve(), root)

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
