from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mc_mod_i18n.web_state import (
    _escape_like_pattern,
    list_translation_memory_scopes,
    query_translation_memory,
    translation_memory_path,
)


def _seed_rows(cache_root, rows):
    list_translation_memory_scopes(cache_root)
    db_path = translation_memory_path(cache_root)
    connection = sqlite3.connect(db_path)
    try:
        connection.executemany(
            'INSERT INTO translation_memory(scope, source, target, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(scope, source) DO UPDATE SET target = excluded.target, updated_at = excluded.updated_at',
            rows,
        )
        connection.commit()
    finally:
        connection.close()



class ListTranslationMemoryScopesTest(unittest.TestCase):
    def test_empty_database_returns_empty_list(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            scopes = list_translation_memory_scopes(cache_root)
        self.assertEqual([], scopes)

    def test_scopes_sorted_by_count_descending_with_sample_and_latest(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            _seed_rows(
                cache_root,
                [
                    ("scope-a", "Start", "开始", "2026-05-20T10:00:00Z"),
                    ("scope-a", "Menu", "菜单", "2026-05-21T10:00:00Z"),
                    ("scope-a", "Tooltip", "提示", "2026-05-22T10:00:00Z"),
                    ("scope-b", "Hello", "你好", "2026-05-19T10:00:00Z"),
                ],
            )
            scopes = list_translation_memory_scopes(cache_root)

        self.assertEqual(2, len(scopes))
        self.assertEqual("scope-a", scopes[0]["scope"])
        self.assertEqual(3, scopes[0]["count"])
        self.assertEqual("Tooltip", scopes[0]["sample_source"])
        self.assertEqual("提示", scopes[0]["sample_target"])
        self.assertEqual("2026-05-22T10:00:00Z", scopes[0]["latest_updated_at"])
        self.assertEqual("scope-b", scopes[1]["scope"])
        self.assertEqual(1, scopes[1]["count"])
        self.assertEqual("Hello", scopes[1]["sample_source"])

    def test_sample_text_truncated_at_60_characters(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            _seed_rows(cache_root, [("scope-a", "S" * 100, "T" * 80, "2026-05-22T10:00:00Z")])
            scopes = list_translation_memory_scopes(cache_root)
        self.assertEqual("S" * 60 + "…", scopes[0]["sample_source"])
        self.assertEqual("T" * 60 + "…", scopes[0]["sample_target"])

    def test_sample_text_at_exactly_60_characters_is_not_truncated(self):
        boundary = "X" * 60
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            _seed_rows(cache_root, [("scope-a", boundary, boundary, "2026-05-22T10:00:00Z")])
            scopes = list_translation_memory_scopes(cache_root)
        self.assertEqual(boundary, scopes[0]["sample_source"])
        self.assertEqual(boundary, scopes[0]["sample_target"])



class QueryTranslationMemoryTest(unittest.TestCase):
    def test_empty_database_returns_zero_total(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            result = query_translation_memory(cache_root)
        self.assertEqual({"rows": [], "total": 0, "page": 1, "page_size": 50}, result)

    def test_pagination_and_sort_order(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            _seed_rows(
                cache_root,
                [
                    ("scope-a", "src-%02d" % i, "tgt-%02d" % i, "2026-05-%02dT00:00:00Z" % (i + 1))
                    for i in range(5)
                ],
            )
            page1 = query_translation_memory(cache_root, page=1, page_size=2)
            page2 = query_translation_memory(cache_root, page=2, page_size=2)
            page3 = query_translation_memory(cache_root, page=3, page_size=2)

        self.assertEqual(5, page1["total"])
        self.assertEqual(2, page1["page_size"])
        self.assertEqual(["src-04", "src-03"], [row["source"] for row in page1["rows"]])
        self.assertEqual(["src-02", "src-01"], [row["source"] for row in page2["rows"]])
        self.assertEqual(["src-00"], [row["source"] for row in page3["rows"]])
        self.assertEqual(3, page3["page"])

    def test_scope_filter_returns_only_matching_rows(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            _seed_rows(
                cache_root,
                [
                    ("scope-a", "Start", "开始", "2026-05-20T10:00:00Z"),
                    ("scope-b", "Start", "启动", "2026-05-21T10:00:00Z"),
                    ("scope-b", "Menu", "菜单", "2026-05-22T10:00:00Z"),
                ],
            )
            result_a = query_translation_memory(cache_root, scope="scope-a")
            result_b = query_translation_memory(cache_root, scope="scope-b")
            result_missing = query_translation_memory(cache_root, scope="scope-nope")

        self.assertEqual(1, result_a["total"])
        self.assertEqual("Start", result_a["rows"][0]["source"])
        self.assertEqual("scope-a", result_a["rows"][0]["scope"])
        self.assertEqual(2, result_b["total"])
        self.assertEqual(["Menu", "Start"], [row["source"] for row in result_b["rows"]])
        self.assertEqual(0, result_missing["total"])
        self.assertEqual([], result_missing["rows"])


    def test_q_filter_case_insensitive_matches_source_or_target(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            _seed_rows(
                cache_root,
                [
                    ("scope-a", "Start Menu", "开始菜单", "2026-05-20T10:00:00Z"),
                    ("scope-a", "Hello", "你好", "2026-05-21T10:00:00Z"),
                    ("scope-a", "TOOLTIP", "提示HELLO", "2026-05-22T10:00:00Z"),
                ],
            )
            result_menu = query_translation_memory(cache_root, q="menu")
            result_hello = query_translation_memory(cache_root, q="hello")
            result_zh = query_translation_memory(cache_root, q="菜单")
            result_none = query_translation_memory(cache_root, q="zzzzz")

        self.assertEqual(1, result_menu["total"])
        self.assertEqual("Start Menu", result_menu["rows"][0]["source"])
        self.assertEqual(2, result_hello["total"])
        self.assertEqual({"Hello", "TOOLTIP"}, {row["source"] for row in result_hello["rows"]})
        self.assertEqual(1, result_zh["total"])
        self.assertEqual(0, result_none["total"])

    def test_q_filter_escapes_like_wildcards(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            _seed_rows(
                cache_root,
                [
                    ("scope-a", "100% done", "100% 完成", "2026-05-20T10:00:00Z"),
                    ("scope-a", "abc done", "abc 完成", "2026-05-21T10:00:00Z"),
                    ("scope-a", "a_b sample", "a_b 样本", "2026-05-22T10:00:00Z"),
                    ("scope-a", "axb sample", "axb 样本", "2026-05-23T10:00:00Z"),
                ],
            )
            result_pct = query_translation_memory(cache_root, q="100%")
            result_underscore = query_translation_memory(cache_root, q="a_b")

        self.assertEqual(1, result_pct["total"])
        self.assertEqual("100% done", result_pct["rows"][0]["source"])
        self.assertEqual(1, result_underscore["total"])
        self.assertEqual("a_b sample", result_underscore["rows"][0]["source"])

    def test_page_and_page_size_bounds_clamped(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            _seed_rows(cache_root, [("scope-a", "Start", "开始", "2026-05-20T10:00:00Z")])
            zero_page = query_translation_memory(cache_root, page=0, page_size=10)
            negative_page = query_translation_memory(cache_root, page=-3, page_size=10)
            huge_page_size = query_translation_memory(cache_root, page=1, page_size=10000)
            zero_page_size = query_translation_memory(cache_root, page=1, page_size=0)
            garbage = query_translation_memory(cache_root, page="abc", page_size="xyz")

        self.assertEqual(1, zero_page["page"])
        self.assertEqual(1, negative_page["page"])
        self.assertEqual(200, huge_page_size["page_size"])
        self.assertEqual(1, zero_page_size["page_size"])
        self.assertEqual(1, garbage["page"])
        self.assertEqual(50, garbage["page_size"])



class EscapeLikePatternTest(unittest.TestCase):
    def test_special_characters_are_escaped(self):
        self.assertEqual("a~%b~_c\\d", _escape_like_pattern("a%b_c\\d"))

    def test_plain_text_unchanged(self):
        self.assertEqual("hello world", _escape_like_pattern("hello world"))


if __name__ == "__main__":
    unittest.main()
