from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .core import translate_batch_with_failures
from .help_docs import set_ui_locale_doc_translation, ui_locale_doc_translation_entries
from .report import ReportEntry
from .translator import LOCALE_DISPLAY_NAMES, TranslationItem
from .ui_i18n import minecraft_locale_display_names, parse_ui_locale_package
from .validator import validate_translation
from .web_utils import sanitize_filename


UI_LOCALE_NAME_MAP: dict[str, str] = {**LOCALE_DISPLAY_NAMES, **minecraft_locale_display_names()}


def json_target_filename(source_name: str, source_locale: str, target_locale: str, schema: str) -> str:
    name = sanitize_filename(source_name)
    stem = Path(name).stem
    source = str(source_locale or "en_us").lower()
    target = str(target_locale or "zh_cn").lower()
    if schema == "ui_locale":
        return f"mc-mod-i18n-ui-{target}.json"
    pattern = re.compile(re.escape(source), flags=re.IGNORECASE)
    if pattern.search(stem):
        stem = pattern.sub(target, stem, count=1)
    elif re.fullmatch(r"[a-z]{2,3}_[a-z0-9]{2,8}", stem.lower()):
        stem = target
    else:
        stem = f"{stem}.{target}"
    return f"{stem}.json"


def ui_locale_name_pair(locale: str) -> tuple[str, str]:
    normalized = str(locale or "").strip().lower().replace("-", "_")
    display = UI_LOCALE_NAME_MAP.get(normalized) or normalized or "Custom"
    return display, display


def parse_json_translation_payload(data: Any, filename: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError("语言 JSON 必须是对象")
    if isinstance(data.get("messages"), dict):
        package = parse_ui_locale_package(data, filename)
        root = {
            key: value
            for key, value in data.items()
            if key != "messages"
        }
        root.update(
            {
                "schema_version": package["schema_version"],
                "locale": package["locale"],
                "name": package["name"],
                "native_name": package["native_name"],
                "source_locale": package["source_locale"],
                "source_version": package["source_version"],
                "messages": dict(package["messages"]),
            }
        )
        return "ui_locale", root, root["messages"]
    return "flat", dict(data), data


def json_output_metadata_preview(filename: str, data: dict[str, Any]) -> dict[str, str] | None:
    if not isinstance(data.get("messages"), dict):
        return None
    return {
        "file": filename,
        "schema": "UI 语言包 JSON",
        "locale": str(data.get("locale", "")),
        "name": str(data.get("name", "")),
        "native_name": str(data.get("native_name", "")),
        "source_locale": str(data.get("source_locale", "")),
        "source_version": str(data.get("source_version", "")),
        "schema_version": str(data.get("schema_version", "")),
    }


def process_json_language_file(
    path: Path,
    args: Any,
    translator: Any,
) -> tuple[str, dict[str, Any], list[ReportEntry], int, int, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} 不是有效 JSON：{exc}") from exc
    schema, root, entries = parse_json_translation_payload(data, path.name)
    output_name = json_target_filename(path.name, args.source_locale, args.target_locale, schema)
    same_locale = str(args.source_locale or "").strip().lower() == str(args.target_locale or "").strip().lower()
    translatable_entries = dict(entries)
    if schema == "ui_locale":
        translatable_entries.update(ui_locale_doc_translation_entries(root))
    report: list[ReportEntry] = []
    items: list[TranslationItem] = []
    item_sources: dict[str, tuple[str, str]] = {}
    skipped = 0
    for key, value in translatable_entries.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, str):
            skipped += 1
            report.append(
                ReportEntry(
                    jar=path.name,
                    mod_id="json",
                    file=output_name,
                    key=key,
                    source="",
                    target="",
                    status="skipped",
                    message="non-string JSON value skipped",
                )
            )
            continue
        if value == "":
            if key in entries:
                entries[key] = value
            else:
                set_ui_locale_doc_translation(root, key, value)
            continue
        if same_locale:
            if key in entries:
                entries[key] = value
            else:
                set_ui_locale_doc_translation(root, key, value)
            report.append(
                ReportEntry(
                    jar=path.name,
                    mod_id="json",
                    file=output_name,
                    key=key,
                    source=value,
                    target=value,
                    status="existing",
                    message="source locale equals target locale",
                )
            )
            continue
        item_id = f"{path.name}\u001f{key}"
        item_sources[item_id] = (key, value)
        items.append(TranslationItem(id=item_id, key=key, text=value, mod_id="json"))

    translations, failed_items = translate_batch_with_failures(translator, items)
    translated_count = 0
    failed_count = 0
    for item_id, (key, source_text) in item_sources.items():
        if item_id in failed_items:
            failed_count += 1
            if key in entries:
                entries[key] = source_text
            else:
                set_ui_locale_doc_translation(root, key, source_text)
            report.append(
                ReportEntry(
                    jar=path.name,
                    mod_id="json",
                    file=output_name,
                    key=key,
                    source=source_text,
                    target=source_text,
                    status="api_failed",
                    message=str(failed_items[item_id]),
                )
            )
            continue
        translated = translations.get(item_id, source_text)
        errors = validate_translation(source_text, translated)
        if errors:
            failed_count += 1
            if key in entries:
                entries[key] = source_text
            else:
                set_ui_locale_doc_translation(root, key, source_text)
            report.append(
                ReportEntry(
                    jar=path.name,
                    mod_id="json",
                    file=output_name,
                    key=key,
                    source=source_text,
                    target=source_text,
                    status="failed",
                    message="; ".join(errors),
                )
            )
            continue
        if key in entries:
            entries[key] = translated
        else:
            set_ui_locale_doc_translation(root, key, translated)
        translated_count += 1
        report.append(
            ReportEntry(
                jar=path.name,
                mod_id="json",
                file=output_name,
                key=key,
                source=source_text,
                target=translated,
                status="translated",
                message="",
            )
        )

    if schema == "ui_locale":
        target_name, target_native_name = ui_locale_name_pair(args.target_locale)
        root["locale"] = args.target_locale
        root["name"] = target_name
        root["native_name"] = target_native_name
        root["source_locale"] = args.source_locale
        root["messages"] = entries
    else:
        root = entries
    return output_name, root, report, translated_count, failed_count, skipped
