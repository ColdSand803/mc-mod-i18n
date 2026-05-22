"""Tests for mc_mod_i18n.web_uploads module — multipart parsing and upload handling."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mc_mod_i18n.web_uploads import (
    MultipartPart,
    collect_fields,
    glossary_upload_or_saved,
    parse_header_params,
    parse_multipart,
    parse_part_headers,
)


class TestParsePartHeaders(unittest.TestCase):
    def test_single_header(self) -> None:
        raw = b"Content-Disposition: form-data; name=\"file\""
        result = parse_part_headers(raw)
        self.assertEqual(result["content-disposition"], "form-data; name=\"file\"")

    def test_multiple_headers(self) -> None:
        raw = b"Content-Disposition: form-data; name=\"file\"\r\nContent-Type: application/json"
        result = parse_part_headers(raw)
        self.assertEqual(result["content-disposition"], "form-data; name=\"file\"")
        self.assertEqual(result["content-type"], "application/json")

    def test_keys_are_lowercase(self) -> None:
        raw = b"Content-Type: text/plain"
        result = parse_part_headers(raw)
        self.assertIn("content-type", result)

    def test_empty_input(self) -> None:
        self.assertEqual(parse_part_headers(b""), {})


class TestParseHeaderParams(unittest.TestCase):
    def test_single_param(self) -> None:
        result = parse_header_params("form-data; name=\"file\"")
        self.assertEqual(result["name"], "file")

    def test_multiple_params(self) -> None:
        result = parse_header_params("form-data; name=\"glossary\"; filename=\"terms.json\"")
        self.assertEqual(result["name"], "glossary")
        self.assertEqual(result["filename"], "terms.json")

    def test_unquoted_values(self) -> None:
        result = parse_header_params("form-data; name=test")
        self.assertEqual(result["name"], "test")

    def test_empty_string(self) -> None:
        self.assertEqual(parse_header_params(""), {})


class TestParseMultipart(unittest.TestCase):
    def _build_body(self, parts: list[dict[str, str | bytes]]) -> tuple[str, bytes]:
        """Build a multipart body from part specs.

        Each spec dict has 'name', optional 'filename', optional 'content_type',
        and 'data' (str or bytes).
        """
        boundary = "----testboundary"
        lines: list[bytes] = []
        for part in parts:
            lines.append(b"--" + boundary.encode())
            name = part["name"]
            filename = part.get("filename")
            if filename:
                disp = f'form-data; name="{name}"; filename="{filename}"'
            else:
                disp = f'form-data; name="{name}"'
            lines.append(f"Content-Disposition: {disp}".encode())
            ct = part.get("content_type", "application/octet-stream")
            lines.append(f"Content-Type: {ct}".encode())
            lines.append(b"")
            data = part["data"]
            if isinstance(data, str):
                data = data.encode("utf-8")
            lines.append(data)
        lines.append(b"--" + boundary.encode() + b"--")
        lines.append(b"")
        body = b"\r\n".join(lines)
        content_type = f"multipart/form-data; boundary={boundary}"
        return content_type, body

    def test_parse_single_text_field(self) -> None:
        ct, body = self._build_body([{"name": "field1", "data": "value1"}])
        parts = parse_multipart(ct, body)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].name, "field1")
        self.assertEqual(parts[0].data, b"value1")
        self.assertIsNone(parts[0].filename)

    def test_parse_file_part(self) -> None:
        ct, body = self._build_body([
            {"name": "glossary", "filename": "terms.json", "data": '{"a":"b"}'},
        ])
        parts = parse_multipart(ct, body)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].name, "glossary")
        self.assertEqual(parts[0].filename, "terms.json")
        self.assertEqual(parts[0].data, b'{"a":"b"}')

    def test_parse_multiple_parts(self) -> None:
        ct, body = self._build_body([
            {"name": "field1", "data": "hello"},
            {"name": "glossary", "filename": "g.json", "data": "{}"},
        ])
        parts = parse_multipart(ct, body)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0].name, "field1")
        self.assertEqual(parts[1].name, "glossary")

    def test_invalid_boundary_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_multipart("text/plain", b"irrelevant")


class TestCollectFields(unittest.TestCase):
    def test_text_parts_collected(self) -> None:
        parts = [
            MultipartPart(name="a", filename=None, content_type="text/plain", data=b"1"),
            MultipartPart(name="b", filename=None, content_type="text/plain", data=b"2"),
        ]
        result = collect_fields(parts)
        self.assertEqual(result, {"a": "1", "b": "2"})

    def test_file_parts_excluded(self) -> None:
        parts = [
            MultipartPart(name="glossary", filename="g.json", content_type="application/json", data=b"{}"),
            MultipartPart(name="field", filename=None, content_type="text/plain", data=b"val"),
        ]
        result = collect_fields(parts)
        self.assertEqual(result, {"field": "val"})

    def test_empty_list(self) -> None:
        self.assertEqual(collect_fields([]), {})


class TestGlossaryUploadOrSaved(unittest.TestCase):
    def test_prefers_upload_over_saved(self) -> None:
        """When an upload part with name='glossary' exists, it should be used."""
        upload_dir = Path(tempfile.mkdtemp())
        workdir = Path(tempfile.mkdtemp())
        parts = [
            MultipartPart(
                name="glossary",
                filename="my_terms.json",
                content_type="application/json",
                data=b'{"hello":"world"}',
            ),
        ]
        result = glossary_upload_or_saved(parts, upload_dir, workdir)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.exists())
        self.assertEqual(result.read_bytes(), b'{"hello":"world"}')
        # The file should be inside upload_dir
        self.assertIn(str(upload_dir), str(result))

    def test_falls_back_to_saved_when_no_upload(self) -> None:
        """When no glossary upload part exists, fall back to saved glossary."""
        upload_dir = Path(tempfile.mkdtemp())
        workdir = Path(tempfile.mkdtemp())
        parts: list[MultipartPart] = []
        expected_path = workdir / "glossaries" / "user-glossary.json"
        with patch(
            "mc_mod_i18n.web_uploads.saved_glossary_path_if_present",
            return_value=expected_path,
        ) as mock_saved:
            result = glossary_upload_or_saved(parts, upload_dir, workdir)
            mock_saved.assert_called_once_with(workdir)
            self.assertEqual(result, expected_path)

    def test_falls_back_returns_none_when_no_saved(self) -> None:
        """When no upload and no saved glossary, returns None."""
        upload_dir = Path(tempfile.mkdtemp())
        workdir = Path(tempfile.mkdtemp())
        parts: list[MultipartPart] = []
        with patch(
            "mc_mod_i18n.web_uploads.saved_glossary_path_if_present",
            return_value=None,
        ):
            result = glossary_upload_or_saved(parts, upload_dir, workdir)
            self.assertIsNone(result)

    def test_upload_part_without_filename_skipped(self) -> None:
        """A part named 'glossary' but without filename is not a file upload."""
        upload_dir = Path(tempfile.mkdtemp())
        workdir = Path(tempfile.mkdtemp())
        parts = [
            MultipartPart(
                name="glossary",
                filename=None,
                content_type="text/plain",
                data=b"not a file",
            ),
        ]
        with patch(
            "mc_mod_i18n.web_uploads.saved_glossary_path_if_present",
            return_value=None,
        ):
            result = glossary_upload_or_saved(parts, upload_dir, workdir)
            self.assertIsNone(result)

    def test_upload_part_with_empty_data_skipped(self) -> None:
        """A part named 'glossary' with filename but empty data is skipped."""
        upload_dir = Path(tempfile.mkdtemp())
        workdir = Path(tempfile.mkdtemp())
        parts = [
            MultipartPart(
                name="glossary",
                filename="empty.json",
                content_type="application/json",
                data=b"",
            ),
        ]
        with patch(
            "mc_mod_i18n.web_uploads.saved_glossary_path_if_present",
            return_value=None,
        ):
            result = glossary_upload_or_saved(parts, upload_dir, workdir)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
