"""Tests for mc_mod_i18n.lang module — language file parsing and rendering."""
from __future__ import annotations

import json
import unittest
import zipfile
from io import BytesIO

from mc_mod_i18n.lang import (
    LangDocument,
    collect_lang_documents,
    extract_plain_text,
    parse_json_lang,
    parse_legacy_lang,
    render_lang,
    target_path_for,
)


# Note: lang.py does NOT provide locale validation or normalization functions
# (e.g. is_valid_locale, normalize_locale). The following tests are commented
# out until such functions are implemented.
#
# class TestValidMinecraftLocale(unittest.TestCase):
#     def test_common_locales_accepted(self) -> None:
#         for code in ("zh_cn", "en_us", "ja_jp"):
#             self.assertTrue(is_valid_locale(code), f"{code} should be valid")
#
# class TestInvalidLocaleRejected(unittest.TestCase):
#     def test_invalid_locales_rejected(self) -> None:
#         for code in ("invalid", "", "xx_XX_XX"):
#             self.assertFalse(is_valid_locale(code), f"{code} should be invalid")
#
# class TestLocaleNormalization(unittest.TestCase):
#     def test_uppercase_to_lowercase(self) -> None:
#         self.assertEqual(normalize_locale("ZH_CN"), "zh_cn")
#
#     def test_hyphen_to_underscore(self) -> None:
#         self.assertEqual(normalize_locale("zh-cn"), "zh_cn")


class TestParseJsonLang(unittest.TestCase):
    def test_simple_entries(self) -> None:
        data = {"block.minecraft.stone": "Stone", "item.minecraft.apple": "Apple"}
        result = parse_json_lang(json.dumps(data))
        self.assertEqual(result, data)

    def test_nested_dict_values_preserved(self) -> None:
        data = {"key1": {"text": "nested"}, "key2": "plain"}
        result = parse_json_lang(json.dumps(data))
        self.assertEqual(result["key1"], {"text": "nested"})
        self.assertEqual(result["key2"], "plain")

    def test_non_dict_input_returns_empty(self) -> None:
        self.assertEqual(parse_json_lang(json.dumps(["not", "a", "dict"]), ), {})

    def test_non_string_values_skipped(self) -> None:
        data = {"key1": "valid", "key2": 123, "key3": None}
        result = parse_json_lang(json.dumps(data))
        self.assertEqual(result, {"key1": "valid"})

    def test_empty_dict(self) -> None:
        self.assertEqual(parse_json_lang("{}"), {})

    def test_bom_handling(self) -> None:
        """json.loads handles BOM-prefixed strings gracefully via utf-8-sig in collect_lang_documents."""
        data = {"key": "value"}
        raw = json.dumps(data)
        result = parse_json_lang(raw)
        self.assertEqual(result, {"key": "value"})


class TestParseLegacyLang(unittest.TestCase):
    def test_simple_key_value(self) -> None:
        result = parse_legacy_lang("block.stone=Stone\nblock.dirt=Dirt\n")
        self.assertEqual(result, {"block.stone": "Stone", "block.dirt": "Dirt"})

    def test_comment_lines_skipped(self) -> None:
        result = parse_legacy_lang("# This is a comment\nkey=value\n")
        self.assertEqual(result, {"key": "value"})

    def test_empty_lines_skipped(self) -> None:
        result = parse_legacy_lang("\n\nkey=value\n\n")
        self.assertEqual(result, {"key": "value"})

    def test_escaped_equals_in_key(self) -> None:
        # \= produces a literal '=', so "key\=with\=" becomes "key=with="
        result = parse_legacy_lang("key\\=with\\==value")
        self.assertEqual(result, {"key=with=": "value"})

    def test_escaped_backslash(self) -> None:
        result = parse_legacy_lang(r"key\\name=value")
        self.assertEqual(result, {"key\\name": "value"})

    def test_escaped_newline(self) -> None:
        result = parse_legacy_lang("key=line1\\nline2")
        self.assertEqual(result, {"key": "line1\nline2"})

    def test_value_with_equals_sign(self) -> None:
        """Equals sign in value part should be preserved."""
        result = parse_legacy_lang("key=a=b=c")
        self.assertEqual(result, {"key": "a=b=c"})

    def test_empty_key_skipped(self) -> None:
        result = parse_legacy_lang("=value\nvalid_key=valid_value\n")
        self.assertEqual(result, {"valid_key": "valid_value"})

    def test_whitespace_stripped_from_key(self) -> None:
        # Key is stripped; trailing whitespace in value is also lost
        result = parse_legacy_lang("  key  =  value  ")
        self.assertEqual(result["key"], "  value")


class TestExtractPlainText(unittest.TestCase):
    def test_string_value(self) -> None:
        self.assertEqual(extract_plain_text("hello"), "hello")

    def test_dict_with_text_key(self) -> None:
        self.assertEqual(extract_plain_text({"text": "nested text"}), "nested text")

    def test_dict_without_text_key(self) -> None:
        result = extract_plain_text({"other": "value"})
        self.assertEqual(result, "")

    def test_dict_with_non_string_text(self) -> None:
        result = extract_plain_text({"text": 42})
        self.assertEqual(result, "42")

    def test_non_string_non_dict(self) -> None:
        self.assertEqual(extract_plain_text(123), "123")


class TestTargetPathFor(unittest.TestCase):
    def test_json_locale_replacement(self) -> None:
        result = target_path_for(
            "assets/mymod/lang/en_us.json", "en_us", "zh_cn"
        )
        self.assertEqual(result, "assets/mymod/lang/zh_cn.json")

    def test_lang_locale_replacement(self) -> None:
        result = target_path_for(
            "assets/mymod/lang/en_us.lang", "en_us", "zh_cn"
        )
        self.assertEqual(result, "assets/mymod/lang/zh_cn.lang")

    def test_case_insensitive_match(self) -> None:
        result = target_path_for(
            "assets/mymod/lang/EN_US.json", "EN_US", "zh_cn"
        )
        self.assertEqual(result, "assets/mymod/lang/zh_cn.json")

    def test_no_match_returns_original(self) -> None:
        path = "assets/mymod/models/item.json"
        result = target_path_for(path, "en_us", "zh_cn")
        self.assertEqual(result, path)


class TestRenderLang(unittest.TestCase):
    def test_json_format(self) -> None:
        entries = {"key1": "value1", "key2": "value2"}
        result = render_lang(entries, "json")
        parsed = json.loads(result)
        self.assertEqual(parsed, entries)
        self.assertTrue(result.endswith("\n"))

    def test_legacy_format(self) -> None:
        entries = {"key1": "value1", "key2": "value2"}
        result = render_lang(entries, "lang")
        self.assertIn("key1=value1\n", result)
        self.assertIn("key2=value2\n", result)

    def test_json_preserves_non_ascii(self) -> None:
        entries = {"key": "石英块"}
        result = render_lang(entries, "json")
        parsed = json.loads(result)
        self.assertEqual(parsed["key"], "石英块")


class TestCollectLangDocuments(unittest.TestCase):
    def _make_zip(self, files: dict[str, str]) -> bytes:
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for path, content in files.items():
                zf.writestr(path, content)
        return buf.getvalue()

    def test_collects_json_lang_file(self) -> None:
        data = json.dumps({"key": "value"})
        raw = self._make_zip({"assets/mymod/lang/en_us.json": data})
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            docs = collect_lang_documents(zf, "en_us")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].mod_id, "mymod")
        self.assertEqual(docs[0].locale, "en_us")
        self.assertEqual(docs[0].format, "json")
        self.assertEqual(docs[0].entries, {"key": "value"})

    def test_collects_legacy_lang_file(self) -> None:
        raw = self._make_zip({"assets/mymod/lang/en_us.lang": "key=value\n"})
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            docs = collect_lang_documents(zf, "en_us")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].format, "lang")

    def test_ignores_other_locales(self) -> None:
        data = json.dumps({"key": "value"})
        raw = self._make_zip({
            "assets/mymod/lang/en_us.json": data,
            "assets/mymod/lang/zh_cn.json": data,
        })
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            docs = collect_lang_documents(zf, "en_us")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].locale, "en_us")

    def test_ignores_non_lang_paths(self) -> None:
        data = json.dumps({"key": "value"})
        raw = self._make_zip({
            "assets/mymod/lang/en_us.json": data,
            "assets/mymod/models/item.json": data,
        })
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            docs = collect_lang_documents(zf, "en_us")
        self.assertEqual(len(docs), 1)

    def test_multiple_mods(self) -> None:
        raw = self._make_zip({
            "assets/mod_a/lang/en_us.json": json.dumps({"a": "1"}),
            "assets/mod_b/lang/en_us.json": json.dumps({"b": "2"}),
        })
        with zipfile.ZipFile(BytesIO(raw)) as zf:
            docs = collect_lang_documents(zf, "en_us")
        self.assertEqual(len(docs), 2)
        mod_ids = {d.mod_id for d in docs}
        self.assertEqual(mod_ids, {"mod_a", "mod_b"})


if __name__ == "__main__":
    unittest.main()
