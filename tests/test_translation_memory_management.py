from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from mc_mod_i18n.web import (
    INDEX_HTML,
    clear_translation_memory,
    compact_translation_memory,
    resolve_cache_root,
    translation_memory_path,
    translation_memory_stats,
)
from mc_mod_i18n.web_state import legacy_translation_memory_jsonl_path


class TranslationMemoryManagementTest(unittest.TestCase):
    def test_default_cache_root_uses_unified_workdir_cache_folder(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)

            cache_root = resolve_cache_root(workdir, "")

        self.assertEqual((workdir / "cache").resolve(), cache_root)

    def test_stats_clear_and_compact_translation_memory(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            path = legacy_translation_memory_jsonl_path(cache_root)
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"scope": "a", "source": "Start", "target": "开始"}, ensure_ascii=False),
                        json.dumps({"scope": "a", "source": "Start", "target": "启动"}, ensure_ascii=False),
                        json.dumps({"scope": "b", "source": "Start", "target": "开始"}, ensure_ascii=False),
                        "{bad",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            stats = translation_memory_stats(cache_root)
            removed = compact_translation_memory(cache_root)
            compacted_stats = translation_memory_stats(cache_root)
            cleared = clear_translation_memory(cache_root)

        self.assertEqual(2, stats["entries"])
        self.assertEqual(0, removed)
        self.assertEqual(2, compacted_stats["entries"])
        self.assertEqual(2, cleared)
        self.assertTrue(str(compacted_stats["path"]).endswith(".sqlite3"))

    def test_stats_and_clear_can_target_current_scope_preview(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            path = legacy_translation_memory_jsonl_path(cache_root)
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"scope": "a", "source": "Start", "target": "开始"}, ensure_ascii=False),
                        json.dumps({"scope": "a", "source": "Menu", "target": "菜单"}, ensure_ascii=False),
                        json.dumps({"scope": "b", "source": "Start", "target": "开始"}, ensure_ascii=False),
                        json.dumps({"scope": "a", "source": "Tooltip", "target": "提示"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            stats = translation_memory_stats(cache_root, scope="a", limit=2)
            removed = clear_translation_memory(cache_root, scope="a")
            remaining = translation_memory_stats(cache_root, limit=5)

        self.assertEqual(4, stats["entries"])
        self.assertEqual(3, stats["scope_entries"])
        self.assertEqual(["Tooltip", "Menu"], [row["source"] for row in stats["scope_rows"]])
        self.assertEqual(3, removed)
        self.assertEqual(1, remaining["entries"])
        self.assertEqual(["Start"], [row["source"] for row in remaining["recent_rows"]])

    def test_translation_memory_path_uses_sqlite_database(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)

            path = translation_memory_path(cache_root)

        self.assertEqual(cache_root / "mc-mod-i18n.sqlite3", path)

    def test_legacy_jsonl_is_imported_once_into_sqlite_memory(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            legacy_path = legacy_translation_memory_jsonl_path(cache_root)
            legacy_path.write_text(
                "\n".join(
                    [
                        json.dumps({"scope": "a", "source": "Start", "target": "开始"}, ensure_ascii=False),
                        json.dumps({"scope": "a", "source": "Start", "target": "启动"}, ensure_ascii=False),
                        json.dumps({"scope": "b", "source": "Menu", "target": "菜单"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            first = translation_memory_stats(cache_root, scope="a", limit=5)
            second = translation_memory_stats(cache_root, scope="a", limit=5)

        self.assertEqual(2, first["entries"])
        self.assertEqual(1, first["scope_entries"])
        self.assertEqual(["Start"], [row["source"] for row in first["scope_rows"]])
        self.assertEqual("启动", first["scope_rows"][0]["target"])
        self.assertEqual(first["entries"], second["entries"])

    def test_sqlite_memory_uses_unique_scope_source_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            db_path = translation_memory_path(cache_root)
            stats_before = translation_memory_stats(cache_root)
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    """
                    INSERT INTO translation_memory(scope, source, target, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(scope, source) DO UPDATE SET
                      target = excluded.target,
                      updated_at = excluded.updated_at
                    """,
                    ("a", "Start", "启动", "2026-05-21T00:00:00Z"),
                )
                connection.commit()
            finally:
                connection.close()
            stats_after = translation_memory_stats(cache_root, scope="a")

        self.assertEqual(0, stats_before["entries"])
        self.assertEqual(1, stats_after["entries"])
        self.assertEqual("启动", stats_after["scope_rows"][0]["target"])

    def test_memory_preview_card_exposes_inline_edit_and_delete_controls(self) -> None:
        self.assertIn('data-role="target-view"', INDEX_HTML)
        self.assertIn('data-role="target-input"', INDEX_HTML)
        self.assertIn('data-action="edit"', INDEX_HTML)
        self.assertIn('data-action="save"', INDEX_HTML)
        self.assertIn('data-action="cancel"', INDEX_HTML)
        self.assertIn('data-action="delete"', INDEX_HTML)
        self.assertIn("updateTranslationMemoryEntry", INDEX_HTML)
        self.assertIn("deleteTranslationMemoryEntry", INDEX_HTML)
        self.assertIn("/api/translation-memory/update", INDEX_HTML)
        self.assertIn("/api/translation-memory/delete", INDEX_HTML)
        self.assertIn("handleMemoryPreviewClick", INDEX_HTML)


if __name__ == "__main__":
    unittest.main()
