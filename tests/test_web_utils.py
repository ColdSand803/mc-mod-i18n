"""Tests for mc_mod_i18n.web_utils helper functions."""
from __future__ import annotations

import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mc_mod_i18n.web_utils import (
    sanitize_filename,
    sanitize_job_id,
    sanitize_relative_upload_path,
    safe_run_path,
    unique_filename,
    utc_timestamp,
)


class TestUtcTimestamp(unittest.TestCase):
    def test_utc_timestamp_format(self) -> None:
        """utc_timestamp() must return ISO 8601 with T separator and UTC indicator."""
        result = utc_timestamp()
        # Must contain 'T' separator between date and time
        self.assertIn("T", result)
        # Must end with 'Z' or '+00:00' (both are valid UTC indicators)
        self.assertTrue(
            result.endswith("Z") or result.endswith("+00:00"),
            f"Expected UTC indicator, got: {result}",
        )
        # Must be parseable as ISO format
        if result.endswith("Z"):
            parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(result)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_utc_timestamp_seconds_precision(self) -> None:
        """utc_timestamp() uses timespec='seconds', so no fractional digits."""
        result = utc_timestamp()
        # After the seconds digits there should be the UTC indicator, not a dot
        time_part = result.split("T", 1)[1]
        # The time part should end with Z or +00:00, no sub-second precision
        self.assertNotIn(".", time_part.rstrip("Z").rstrip("+00:00"))


# Note: escape_html is NOT implemented in web_utils.py.
# The following tests are commented out until the function is added.
#
# class TestEscapeHtml(unittest.TestCase):
#     def test_escape_html_basic(self) -> None:
#         result = escape_html("<script>alert('xss')</script>")
#         self.assertNotIn("<script>", result)
#         self.assertIn("&lt;", result)
#         self.assertIn("&gt;", result)
#
#     def test_escape_html_normal_text(self) -> None:
#         self.assertEqual(escape_html("normal text"), "normal text")
#
#     def test_escape_html_none_and_empty(self) -> None:
#         self.assertEqual(escape_html(None), "")
#         self.assertEqual(escape_html(""), "")


class TestSanitizeFilename(unittest.TestCase):
    def test_strips_path_components(self) -> None:
        """Path separators and directory traversal are removed."""
        result = sanitize_filename("../../etc/passwd")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)
        self.assertNotIn("..", result)

    def test_replaces_special_characters(self) -> None:
        """Characters outside [A-Za-z0-9._ -] are replaced with underscores."""
        result = sanitize_filename("file@name#$.jar")
        self.assertNotIn("@", result)
        self.assertNotIn("#", result)
        self.assertNotIn("$", result)

    def test_preserves_allowed_characters(self) -> None:
        """Letters, digits, dots, spaces, hyphens, and underscores are kept."""
        result = sanitize_filename("my_mod-1.0.json")
        self.assertEqual(result, "my_mod-1.0.json")

    def test_empty_after_sanitize_returns_default(self) -> None:
        """If the entire filename is stripped away, return 'upload.bin'."""
        # "@@@" becomes "_" after regex replacement, which is not empty
        # To get truly empty, use characters that become empty after strip(" .")
        result = sanitize_filename("...")
        self.assertEqual(result, "upload.bin")

    def test_strips_leading_trailing_dots_and_spaces(self) -> None:
        result = sanitize_filename("  ..hidden..  ")
        # After regex replacement, leading/trailing dots and spaces are stripped
        self.assertFalse(result.startswith("."))
        self.assertFalse(result.endswith("."))

    def test_backslash_path_separator(self) -> None:
        result = sanitize_filename("C:\\Users\\test\\file.txt")
        self.assertNotIn("\\", result)
        self.assertEqual(result, "file.txt")


class TestUniqueFilename(unittest.TestCase):
    def test_first_occurrence_unchanged(self) -> None:
        used: set[str] = set()
        self.assertEqual(unique_filename("test.json", used), "test.json")

    def test_second_occurrence_gets_suffix(self) -> None:
        used: set[str] = set()
        unique_filename("test.json", used)
        self.assertEqual(unique_filename("test.json", used), "test-2.json")

    def test_third_occurrence(self) -> None:
        used: set[str] = set()
        unique_filename("test.json", used)
        unique_filename("test.json", used)
        self.assertEqual(unique_filename("test.json", used), "test-3.json")

    def test_directory_component_stripped(self) -> None:
        used: set[str] = set()
        result = unique_filename("folder/sub/test.json", used)
        self.assertEqual(result, "test.json")


class TestSanitizeJobId(unittest.TestCase):
    def test_hex_preserved(self) -> None:
        self.assertEqual(sanitize_job_id("abcdef1234567890"), "abcdef1234567890")

    def test_non_hex_removed(self) -> None:
        result = sanitize_job_id("abc-def_123")
        self.assertEqual(result, "abcdef123")

    def test_truncated_to_32(self) -> None:
        long_id = "a" * 64
        result = sanitize_job_id(long_id)
        self.assertEqual(len(result), 32)

    def test_empty_input(self) -> None:
        self.assertEqual(sanitize_job_id(""), "")


class TestSanitizeRelativeUploadPath(unittest.TestCase):
    def test_normal_path_preserved(self) -> None:
        result = sanitize_relative_upload_path("assets/mod/lang/zh_cn.json")
        self.assertEqual(result, "assets/mod/lang/zh_cn.json")

    def test_directory_traversal_removed(self) -> None:
        result = sanitize_relative_upload_path("../../etc/passwd")
        self.assertNotIn("..", result)

    def test_backslash_normalized(self) -> None:
        result = sanitize_relative_upload_path("assets\\mod\\lang\\zh_cn.json")
        self.assertIn("/", result)
        self.assertNotIn("\\", result)

    def test_empty_returns_default(self) -> None:
        self.assertEqual(sanitize_relative_upload_path(""), "upload.snbt")

    def test_colon_stripped(self) -> None:
        """Drive letter prefix like 'C:' should be stripped."""
        result = sanitize_relative_upload_path("C:\\test\\file.txt")
        self.assertNotIn(":", result)


class TestSafeRunPath(unittest.TestCase):
    def test_valid_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            (workdir / "sub").mkdir()
            (workdir / "sub" / "file.txt").write_text("hello")
            result = safe_run_path(workdir, "sub/file.txt")
            self.assertEqual(result, (workdir / "sub" / "file.txt").resolve())

    def test_directory_traversal_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            with self.assertRaises(ValueError, msg="invalid path"):
                safe_run_path(workdir, "../../etc/passwd")

    def test_backslash_traversal_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            with self.assertRaises(ValueError, msg="invalid path"):
                safe_run_path(workdir, "..\\..\\etc\\passwd")

    def test_url_encoded_traversal_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            with self.assertRaises(ValueError, msg="invalid path"):
                safe_run_path(workdir, "%2e%2e/%2e%2e/etc/passwd")


if __name__ == "__main__":
    unittest.main()
