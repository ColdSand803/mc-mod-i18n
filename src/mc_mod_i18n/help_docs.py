from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .ui_i18n import resolve_ui_locale


HELP_DOCS_DIRNAME = "docs/help"
HELP_DOCS_INDEX_FILENAME = "index.json"


def help_docs_dir(root: Path) -> Path:
    return root / HELP_DOCS_DIRNAME


def localized_help_docs_dir(root: Path, locale: str | None) -> Path:
    return help_docs_dir(root) / resolve_ui_locale(locale)


def _append_locale_help_doc_dirs(candidates: list[Path], base: Path, locale: str | None, *, include_base: bool = True) -> None:
    if locale:
        normalized = resolve_ui_locale(locale)
        candidates.append(base / normalized)
        language = normalized.split("_", 1)[0]
        if language and language != normalized:
            candidates.append(base / language)
    if include_base:
        candidates.append(base)


def _candidate_help_docs_dirs(root: Path, locale: str | None = None, extension_root: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    if extension_root is not None:
        _append_locale_help_doc_dirs(candidates, help_docs_dir(extension_root), locale, include_base=False)
    _append_locale_help_doc_dirs(candidates, help_docs_dir(root), locale)
    unique: list[Path] = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    return unique


def _select_help_docs_dir(root: Path, locale: str | None = None, extension_root: Path | None = None) -> Path:
    for docs_root in _candidate_help_docs_dirs(root, locale, extension_root):
        if (docs_root / HELP_DOCS_INDEX_FILENAME).is_file():
            return docs_root
    return help_docs_dir(root)


def _help_docs_index_path(root: Path, locale: str | None = None, extension_root: Path | None = None) -> Path:
    return _select_help_docs_dir(root, locale, extension_root) / HELP_DOCS_INDEX_FILENAME


def _read_help_docs_index_from_dir(docs_root: Path) -> list[dict[str, Any]]:
    path = docs_root / HELP_DOCS_INDEX_FILENAME
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    docs = payload.get("docs", [])
    if not isinstance(docs, list):
        raise ValueError("帮助文档索引格式无效")
    return [item for item in docs if isinstance(item, dict)]


def _read_help_docs_index(root: Path, locale: str | None = None, extension_root: Path | None = None) -> list[dict[str, Any]]:
    return _read_help_docs_index_from_dir(_select_help_docs_dir(root, locale, extension_root))


def list_help_docs(root: Path, locale: str | None = None, extension_root: Path | None = None) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for item in _read_help_docs_index(root, locale, extension_root):
        slug = normalize_help_doc_slug(str(item.get("slug", "") or ""))
        docs.append(
            {
                "slug": slug,
                "title": str(item.get("title", slug) or slug),
                "summary": str(item.get("summary", "") or ""),
                "category": str(item.get("category", "") or ""),
                "keywords": [str(keyword) for keyword in item.get("keywords", []) if str(keyword or "").strip()],
                "related_topics": [normalize_help_doc_slug(str(topic)) for topic in item.get("related_topics", []) if str(topic or "").strip()],
                "applies_to": [str(value) for value in item.get("applies_to", []) if str(value or "").strip()],
            }
        )
    return docs


def normalize_help_doc_slug(value: str) -> str:
    slug = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug):
        raise ValueError("文档 slug 无效")
    return slug


def read_help_doc(root: Path, slug: str, locale: str | None = None, extension_root: Path | None = None) -> dict[str, Any]:
    normalized_slug = normalize_help_doc_slug(slug)
    for docs_root in _candidate_help_docs_dirs(root, locale, extension_root):
        for item in _read_help_docs_index_from_dir(docs_root):
            item_slug = normalize_help_doc_slug(str(item.get("slug", "") or ""))
            if item_slug != normalized_slug:
                continue
            path = docs_root / f"{normalized_slug}.md"
            if not path.is_file():
                break
            normalized_item = {
                "slug": item_slug,
                "title": str(item.get("title", item_slug) or item_slug),
                "summary": str(item.get("summary", "") or ""),
                "category": str(item.get("category", "") or ""),
                "keywords": [str(keyword) for keyword in item.get("keywords", []) if str(keyword or "").strip()],
                "related_topics": [normalize_help_doc_slug(str(topic)) for topic in item.get("related_topics", []) if str(topic or "").strip()],
                "applies_to": [str(value) for value in item.get("applies_to", []) if str(value or "").strip()],
            }
            content = path.read_text(encoding="utf-8-sig")
            return {
                **normalized_item,
                "content": content,
                "html": render_help_doc_html(content),
            }
    raise ValueError("文档不存在")


def write_ui_locale_help_docs(extension_root: Path, package: dict[str, Any]) -> dict[str, Any]:
    docs = package.get("docs") or []
    if not isinstance(docs, list) or not docs:
        return {"docs_count": 0}
    locale = resolve_ui_locale(str(package.get("locale") or ""))
    docs_root = localized_help_docs_dir(extension_root, locale)
    docs_root.mkdir(parents=True, exist_ok=True)
    index_docs: list[dict[str, Any]] = []
    for item in docs:
        if not isinstance(item, dict):
            continue
        slug = normalize_help_doc_slug(str(item.get("slug") or ""))
        content = str(item.get("content") or item.get("markdown") or "")
        if not content.strip():
            continue
        (docs_root / f"{slug}.md").write_text(content, encoding="utf-8")
        index_docs.append(
            {
                "slug": slug,
                "title": str(item.get("title") or slug),
                "summary": str(item.get("summary") or ""),
                "category": str(item.get("category") or ""),
                "keywords": [str(keyword) for keyword in item.get("keywords", []) if str(keyword or "").strip()],
                "related_topics": [
                    normalize_help_doc_slug(str(topic))
                    for topic in item.get("related_topics", [])
                    if str(topic or "").strip()
                ],
                "applies_to": [str(target) for target in item.get("applies_to", []) if str(target or "").strip()],
            }
        )
    if not index_docs:
        return {"docs_count": 0}
    (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
        json.dumps({"docs": index_docs}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"docs_count": len(index_docs), "docs_path": str(docs_root)}


def render_help_doc_html(markdown_text: str) -> str:
    lines = str(markdown_text or "").splitlines()
    parts: list[str] = []
    in_list = False
    list_tag = "ul"
    in_code_block = False
    code_language = ""
    code_lines: list[str] = []
    paragraph: list[str] = []

    def render_inline_markdown(text: str) -> str:
        escaped = html.escape(text)
        escaped = re.sub(r"`([^`]+)`", lambda match: f"<code>{match.group(1)}</code>", escaped)
        escaped = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            lambda match: f'<a href="{html.escape(match.group(2), quote=True)}">{match.group(1)}</a>',
            escaped,
        )
        return escaped

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        text = " ".join(item.strip() for item in paragraph if item.strip())
        if text:
            parts.append(f"<p>{render_inline_markdown(text)}</p>")
        paragraph = []

    def close_list() -> None:
        nonlocal in_list, list_tag
        if in_list:
            parts.append(f"</{list_tag}>")
            in_list = False
            list_tag = "ul"

    def flush_code_block() -> None:
        nonlocal in_code_block, code_language, code_lines
        if not in_code_block:
            return
        class_attr = f' class="language-{html.escape(code_language, quote=True)}"' if code_language else ""
        parts.append(f"<pre><code{class_attr}>{html.escape(chr(10).join(code_lines))}</code></pre>")
        in_code_block = False
        code_language = ""
        code_lines = []

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code_block:
                flush_code_block()
            else:
                in_code_block = True
                code_language = stripped.removeprefix("```").strip()
                code_lines = []
            continue
        if in_code_block:
            code_lines.append(raw)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            close_list()
            parts.append(f"<h1>{html.escape(stripped[2:].strip())}</h1>")
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            close_list()
            parts.append(f"<h2>{html.escape(stripped[3:].strip())}</h2>")
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            close_list()
            parts.append(f"<h3>{html.escape(stripped[4:].strip())}</h3>")
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if in_list and list_tag != "ul":
                close_list()
            if not in_list:
                parts.append("<ul>")
                in_list = True
                list_tag = "ul"
            parts.append(f"<li>{render_inline_markdown(stripped[2:].strip())}</li>")
            continue
        numbered_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if numbered_match:
            flush_paragraph()
            if in_list and list_tag != "ol":
                close_list()
            if not in_list:
                parts.append("<ol>")
                in_list = True
                list_tag = "ol"
            parts.append(f"<li>{render_inline_markdown(numbered_match.group(2).strip())}</li>")
            continue
        paragraph.append(stripped)

    flush_paragraph()
    close_list()
    flush_code_block()
    return "".join(parts)


def ui_locale_doc_translation_entries(root: dict[str, Any]) -> dict[str, str]:
    docs = root.get("docs")
    if not isinstance(docs, list):
        return {}
    entries: dict[str, str] = {}
    for item in docs:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip().lower()
        if not slug:
            continue
        for field in ("title", "summary", "content"):
            value = item.get(field)
            if isinstance(value, str):
                entries[f"docs.{slug}.{field}"] = value
    return entries


def set_ui_locale_doc_translation(root: dict[str, Any], key: str, value: str) -> None:
    match = re.fullmatch(r"docs\.([a-z0-9][a-z0-9._-]*)\.(title|summary|content)", key)
    if not match:
        return
    slug, field = match.groups()
    docs = root.get("docs")
    if not isinstance(docs, list):
        return
    for item in docs:
        if isinstance(item, dict) and str(item.get("slug") or "").strip().lower() == slug:
            item[field] = value
            return
