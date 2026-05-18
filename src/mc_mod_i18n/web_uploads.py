from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .web_state import saved_glossary_path_if_present
from .web_utils import sanitize_filename


@dataclass(frozen=True)
class MultipartPart:
    name: str
    filename: str | None
    content_type: str
    data: bytes


def parse_multipart(content_type: str, body: bytes) -> list[MultipartPart]:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("请求不是 multipart/form-data")
    boundary = match.group("boundary").strip('"')
    delimiter = b"--" + boundary.encode("utf-8")
    parts: list[MultipartPart] = []

    for raw_part in body.split(delimiter):
        raw_part = raw_part.strip(b"\r\n")
        if not raw_part or raw_part == b"--":
            continue
        if raw_part.endswith(b"--"):
            raw_part = raw_part[:-2].rstrip(b"\r\n")
        if b"\r\n\r\n" not in raw_part:
            continue
        raw_headers, data = raw_part.split(b"\r\n\r\n", 1)
        headers = parse_part_headers(raw_headers)
        disposition = headers.get("content-disposition", "")
        params = parse_header_params(disposition)
        name = params.get("name")
        if not name:
            continue
        parts.append(
            MultipartPart(
                name=name,
                filename=params.get("filename"),
                content_type=headers.get("content-type", "application/octet-stream"),
                data=data,
            )
        )
    return parts


def parse_part_headers(raw_headers: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in raw_headers.decode("utf-8", errors="replace").split("\r\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def parse_header_params(value: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for piece in value.split(";"):
        piece = piece.strip()
        if "=" not in piece:
            continue
        key, raw_value = piece.split("=", 1)
        params[key.strip().lower()] = raw_value.strip().strip('"')
    return params


def collect_fields(parts: list[MultipartPart]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in parts:
        if part.filename is None:
            fields[part.name] = part.data.decode("utf-8", errors="replace")
    return fields


def glossary_upload_or_saved(parts: list[MultipartPart], upload_dir: Path, workdir: Path) -> Path | None:
    for part in parts:
        if part.name == "glossary" and part.filename and part.data:
            glossary_path = upload_dir / sanitize_filename(part.filename)
            glossary_path.write_bytes(part.data)
            return glossary_path
    return saved_glossary_path_if_present(workdir)
