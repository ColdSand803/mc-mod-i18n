from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from mc_mod_i18n.web import (
    glossary_conflicts,
    normalize_glossary_terms,
    read_user_glossary,
    saved_glossary_path_if_present,
    user_glossary_path,
    write_user_glossary,
)


class GlossaryManagementTest(unittest.TestCase):
    def test_user_glossary_roundtrip_normalizes_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_user_glossary(root, {" Copper ": " 铜 ", "": "ignored", "Empty": ""})

            self.assertEqual(user_glossary_path(root), path)
            self.assertEqual({"Copper": "铜"}, read_user_glossary(root))
            self.assertEqual(path, saved_glossary_path_if_present(root))

    def test_empty_or_missing_user_glossary_is_not_selected_for_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            self.assertIsNone(saved_glossary_path_if_present(root))
            write_user_glossary(root, {})
            self.assertIsNone(saved_glossary_path_if_present(root))

    def test_glossary_conflicts_report_builtin_overrides(self) -> None:
        conflicts = glossary_conflicts({"Advanced": "进阶", "Custom": "自定义"})

        self.assertEqual("高级", conflicts["Advanced"]["builtin"])
        self.assertEqual("进阶", conflicts["Advanced"]["user"])
        self.assertNotIn("Custom", conflicts)

    def test_normalize_rejects_non_object_glossary(self) -> None:
        with self.assertRaises(ValueError):
            normalize_glossary_terms(["Copper"])


if __name__ == "__main__":
    unittest.main()
