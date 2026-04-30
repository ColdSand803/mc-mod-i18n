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
    entries: dict[str, str]


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


def parse_json_lang(raw: str) -> dict[str, str]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items() if isinstance(value, str)}


def parse_legacy_lang(raw: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            entries[key] = value.strip()
    return entries


def target_path_for(source_path: str, source_locale: str, target_locale: str) -> str:
    return re.sub(
        rf"/{re.escape(source_locale)}\.(json|lang)$",
        lambda match: f"/{target_locale}.{match.group(1)}",
        source_path,
        flags=re.IGNORECASE,
    )


def render_lang(entries: dict[str, str], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    return "".join(f"{key}={value}\n" for key, value in entries.items())
