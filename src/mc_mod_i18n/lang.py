from __future__ import annotations

from dataclasses import dataclass
import json
import re
from zipfile import ZipFile


@dataclass(frozen=True)
class LangDocument:
    path: str
    mod_id: str
    locale: str
    format: str
    entries: dict[str, str | dict[str, object]]


def collect_lang_documents(zf: ZipFile, locale: str) -> list[LangDocument]:
    docs: list[LangDocument] = []
    pattern = re.compile(rf"^assets/([^/]+)/lang/{re.escape(locale)}\.(json|lang)$", re.IGNORECASE)

    for path in sorted(zf.namelist()):
        match = pattern.match(path)
        if not match:
            continue

        raw = zf.read(path).decode("utf-8-sig", errors="replace")
        fmt = match.group(2).lower()
        if fmt == "json":
            entries = parse_json_lang(raw)
        else:
            entries = parse_legacy_lang(raw)

        docs.append(
            LangDocument(
                path=path,
                mod_id=match.group(1),
                locale=locale,
                format=fmt,
                entries=entries,
            )
        )

    return docs


def parse_json_lang(raw: str) -> dict[str, str | dict[str, object]]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        return {}
    result: dict[str, str | dict[str, object]] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[str(key)] = value
        elif isinstance(value, dict):
            result[str(key)] = value
    return result


def extract_plain_text(value: str | dict[str, object]) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("text", "")
        if isinstance(text, str):
            return text
        return str(text)
    return str(value)


def parse_legacy_lang(raw: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key_parts: list[str] = []
        value_parts: list[str] = []
        current = key_parts
        i = 0
        while i < len(stripped):
            ch = stripped[i]
            if ch == "\\" and i + 1 < len(stripped):
                nxt = stripped[i + 1]
                if nxt == "=":
                    current.append("=")
                    i += 2
                    continue
                if nxt == "\\":
                    current.append("\\")
                    i += 2
                    continue
                if nxt == "n":
                    current.append("\n")
                    i += 2
                    continue
            elif ch == "=" and current is key_parts:
                current = value_parts
                i += 1
                continue
            current.append(ch)
            i += 1
        key = "".join(key_parts).strip()
        if not key:
            continue
        entries[key] = "".join(value_parts)
    return entries


def target_path_for(source_path: str, source_locale: str, target_locale: str) -> str:
    return re.sub(
        rf"/{re.escape(source_locale)}\.(json|lang)$",
        lambda match: f"/{target_locale}.{match.group(1)}",
        source_path,
        flags=re.IGNORECASE,
    )


def render_lang(entries: dict[str, str | dict[str, object]], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    return "".join(f"{key}={value}\n" for key, value in entries.items())
