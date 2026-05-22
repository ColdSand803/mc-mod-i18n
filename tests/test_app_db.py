from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mc_mod_i18n.app_db import SCHEMA_COMMENTS, app_db_path, connect_app_db


class AppDbTest(unittest.TestCase):
    def test_schema_comments_cover_all_declared_table_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = app_db_path(Path(tmp))
            with connect_app_db(db_path) as connection:
                tables = [
                    "schema_migrations",
                    "schema_comments",
                    "translation_memory",
                    "app_settings",
                    "job_history",
                    "job_input_files",
                    "glossary_terms",
                ]
                for table in tables:
                    with self.subTest(table=table):
                        columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]
                        rows = connection.execute(
                            """
                            SELECT column_name, comment
                            FROM schema_comments
                            WHERE table_name = ?
                            """,
                            (table,),
                        ).fetchall()
                        comments = {row["column_name"]: row["comment"] for row in rows}

                        self.assertEqual(set(columns), set(comments))
                        self.assertTrue(all(str(comment).strip() for comment in comments.values()))

    def test_schema_comments_constant_matches_database_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = app_db_path(Path(tmp))
            with connect_app_db(db_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM schema_comments").fetchone()[0]

        self.assertEqual(sum(len(columns) for columns in SCHEMA_COMMENTS.values()), count)


    def test_empty_database_first_startup_creates_all_tables(self) -> None:
        expected_tables = {
            "schema_migrations",
            "schema_comments",
            "translation_memory",
            "app_settings",
            "job_history",
            "job_input_files",
            "glossary_terms",
            "config_presets",
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = app_db_path(Path(tmp))
            with connect_app_db(db_path) as connection:
                tables = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                }
                self.assertEqual(expected_tables, tables)

                migrations_count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
                self.assertEqual(0, migrations_count)

                comments_count = connection.execute("SELECT COUNT(*) FROM schema_comments").fetchone()[0]
                self.assertGreater(comments_count, 0)

    def test_initialize_app_db_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = app_db_path(Path(tmp))
            with connect_app_db(db_path) as connection:
                connection.execute(
                    "INSERT INTO translation_memory(scope, source, target, updated_at) VALUES (?, ?, ?, ?)",
                    ("test-scope", "hello", "你好", "2026-01-01T00:00:00Z"),
                )
            with connect_app_db(db_path) as connection:
                row = connection.execute(
                    "SELECT source, target FROM translation_memory WHERE scope = ? AND source = ?",
                    ("test-scope", "hello"),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual("你好", row["target"])

    def test_connect_app_db_auto_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "a" / "b" / "c" / "mc-mod-i18n.sqlite3"
            with connect_app_db(db_path) as _connection:
                pass
            self.assertTrue(db_path.exists())

    def test_clear_job_history_removes_all_records(self) -> None:
        from mc_mod_i18n.job_history import append_job_history, clear_job_history, read_job_history

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(3):
                append_job_history(root, {"job_id": f"job-{i}", "status": "done"})
            result = clear_job_history(root)
            self.assertEqual({"ok": True, "before": 3, "after": 0, "removed": 3}, result)
            self.assertEqual([], read_job_history(root))

    def test_import_translation_memory_from_jsonl_upserts_rows(self) -> None:
        from mc_mod_i18n.app_db import import_translation_memory_from_jsonl

        with tempfile.TemporaryDirectory() as tmp:
            db_path = app_db_path(Path(tmp))
            jsonl_path = Path(tmp) / "test.jsonl"
            jsonl_path.write_text(
                '{"scope": "s1", "source": "hello", "target": "你好", "updated_at": "2026-01-01T00:00:00Z"}\n'
                '{"scope": "s1", "source": "world", "target": "世界", "updated_at": "2026-01-01T00:00:00Z"}\n',
                encoding="utf-8",
            )
            count = import_translation_memory_from_jsonl(db_path, jsonl_path)
            self.assertEqual(2, count)

            with connect_app_db(db_path) as connection:
                rows = connection.execute("SELECT source, target FROM translation_memory ORDER BY source").fetchall()
                self.assertEqual(2, len(rows))
                self.assertEqual("hello", rows[0]["source"])
                self.assertEqual("你好", rows[0]["target"])

    def test_import_translation_memory_from_jsonl_updates_on_conflict(self) -> None:
        from mc_mod_i18n.app_db import import_translation_memory_from_jsonl

        with tempfile.TemporaryDirectory() as tmp:
            db_path = app_db_path(Path(tmp))
            jsonl_path = Path(tmp) / "test.jsonl"
            jsonl_path.write_text(
                '{"scope": "s1", "source": "hello", "target": "你好", "updated_at": "2026-01-01T00:00:00Z"}\n',
                encoding="utf-8",
            )
            import_translation_memory_from_jsonl(db_path, jsonl_path)

            jsonl_path.write_text(
                '{"scope": "s1", "source": "hello", "target": "您好", "updated_at": "2026-02-01T00:00:00Z"}\n',
                encoding="utf-8",
            )
            count = import_translation_memory_from_jsonl(db_path, jsonl_path)
            self.assertEqual(1, count)

            with connect_app_db(db_path) as connection:
                row = connection.execute(
                    "SELECT target, updated_at FROM translation_memory WHERE scope = ? AND source = ?",
                    ("s1", "hello"),
                ).fetchone()
                self.assertEqual("您好", row["target"])
                self.assertEqual("2026-02-01T00:00:00Z", row["updated_at"])

    def test_import_translation_memory_from_jsonl_skips_invalid_lines(self) -> None:
        from mc_mod_i18n.app_db import import_translation_memory_from_jsonl

        with tempfile.TemporaryDirectory() as tmp:
            db_path = app_db_path(Path(tmp))
            jsonl_path = Path(tmp) / "test.jsonl"
            jsonl_path.write_text(
                '\n'
                'not json\n'
                '{"scope": "", "source": "hello", "target": "你好"}\n'
                '{"scope": "s1", "source": "", "target": "你好"}\n'
                '{"scope": "s1", "source": "ok", "target": "好的", "updated_at": "2026-01-01T00:00:00Z"}\n',
                encoding="utf-8",
            )
            count = import_translation_memory_from_jsonl(db_path, jsonl_path)
            self.assertEqual(1, count)

    def test_import_translation_memory_from_jsonl_raises_on_missing_file(self) -> None:
        from mc_mod_i18n.app_db import import_translation_memory_from_jsonl

        with tempfile.TemporaryDirectory() as tmp:
            db_path = app_db_path(Path(tmp))
            with self.assertRaises(ValueError):
                import_translation_memory_from_jsonl(db_path, Path(tmp) / "nonexistent.jsonl")


if __name__ == "__main__":
    unittest.main()
