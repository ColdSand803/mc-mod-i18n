from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from .ftbquests import (
    FTBQuestsOutputFile,
    FTBQuestsResult,
    collect_string_leaves,
    parse_snbt,
    render_snbt,
    set_snbt_string,
)
from .report_exports import report_entries_from_dicts, write_report_exports
from .validator import validate_translation
from .web_utils import safe_run_path


def entry_id(entry: dict[str, Any]) -> str:
    return f"{entry.get('jar', '')}\x1f{entry.get('file', '')}\x1f{entry.get('key', '')}"


def successful_retry_entries(failed_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        entry
        for entry in failed_entries
        if isinstance(entry, dict) and str(entry.get("status") or "") == "translated"
    ]


def successful_retry_result_entries(result: dict[str, Any], failed_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    retried_ids = {entry_id(entry) for entry in failed_entries if isinstance(entry, dict)}
    entries = result.get("entries") if isinstance(result.get("entries"), list) else []
    return [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry_id(entry) in retried_ids
        and str(entry.get("status") or "") == "translated"
    ]


def refresh_retry_report_exports(out_dir: Path, result: dict[str, Any]) -> None:
    entries = report_entries_from_dicts(result.get("entries", []))
    if not entries:
        return
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    metadata = {
        "job_id": str(result.get("job_id") or ""),
        "kind": str(result.get("kind") or "jar"),
        "provider": str(result.get("provider") or ""),
        "model": str(result.get("model") or ""),
        "elapsed_seconds": result.get("elapsed_seconds", 0),
        "retry_elapsed_seconds": result.get("retry_elapsed_seconds", 0),
        "cache_hits": result.get("cache_hits", 0),
        "cache_misses": result.get("cache_misses", 0),
        "memory_hits": result.get("memory_hits", 0),
    }
    write_report_exports(
        out_dir,
        entries,
        {str(key): int(value) for key, value in summary.items() if isinstance(value, int)},
        metadata,
    )


def ftbquests_result_from_retry_payload(result: dict[str, Any]) -> FTBQuestsResult | None:
    output_files = result.get("ftbquests_output_files")
    if not isinstance(output_files, list):
        return None
    return FTBQuestsResult(
        source_label=str(result.get("source_label") or ""),
        mode=str(result.get("mode") or ""),
        source_locale=str(result.get("source_locale") or ""),
        target_locale=str(result.get("target_locale") or ""),
        source_hash=str(result.get("source_hash") or ""),
        output_files=[
            FTBQuestsOutputFile(path=str(item.get("path") or ""), content=str(item.get("content") or ""))
            for item in output_files
            if isinstance(item, dict)
        ],
        report_entries=report_entries_from_dicts(result.get("entries", [])),
        legacy_files=[str(item) for item in result.get("legacy_files", [])] if isinstance(result.get("legacy_files"), list) else [],
    )


def update_json_retry_outputs(out_dir: Path, successful_entries: list[dict[str, Any]]) -> int:
    updates_by_file: dict[str, dict[str, str]] = {}
    for entry in successful_entries:
        file_name = str(entry.get("file") or "")
        key = str(entry.get("key") or "")
        if not file_name or not key:
            continue
        updates_by_file.setdefault(file_name, {})[key] = str(entry.get("target") or "")
    if not updates_by_file:
        return 0

    updated = 0
    for file_name, updates in updates_by_file.items():
        target = safe_run_path(out_dir, file_name)
        if target.is_file() and update_json_retry_file(target, updates):
            updated += 1

    for archive in sorted(out_dir.glob("*.zip")):
        if update_json_retry_zip(archive, updates_by_file):
            updated += 1
    return updated


def update_json_retry_file(path: Path, updates: dict[str, str]) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    changed = apply_json_retry_updates(data, updates)
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def apply_json_retry_updates(data: Any, updates: dict[str, str]) -> bool:
    if not isinstance(data, dict):
        return False
    target = data.get("messages") if isinstance(data.get("messages"), dict) else data
    changed = False
    for key, value in updates.items():
        if key in target:
            target[key] = value
            changed = True
    return changed


def update_json_retry_zip(path: Path, updates_by_file: dict[str, dict[str, str]]) -> bool:
    try:
        with ZipFile(path) as zf:
            members = [(info, zf.read(info.filename)) for info in zf.infolist()]
    except (OSError, BadZipFile):
        return False

    changed = False
    replacement: list[tuple[Any, bytes]] = []
    for info, data in members:
        updates = updates_by_file.get(Path(info.filename).name) or updates_by_file.get(info.filename)
        if updates:
            try:
                payload = json.loads(data.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                replacement.append((info, data))
                continue
            if apply_json_retry_updates(payload, updates):
                data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                changed = True
        replacement.append((info, data))

    if changed:
        with ZipFile(path, "w") as zf:
            for info, data in replacement:
                zf.writestr(info, data)
    return changed


def update_ftbquests_retry_outputs(out_dir: Path, result: FTBQuestsResult, successful_entries: list[dict[str, Any]]) -> int:
    updates_by_file: dict[str, dict[str, str]] = {}
    for entry in successful_entries:
        file_name = str(entry.get("file") or "")
        key = str(entry.get("key") or "")
        if not file_name or not key:
            continue
        updates_by_file.setdefault(file_name, {})[key] = str(entry.get("target") or "")
    if not updates_by_file:
        return 0

    full_path_updates: dict[str, dict[str, str]] = {}
    for output_file in result.output_files:
        matched = retry_updates_for_ftbquests_path(output_file.path, updates_by_file)
        if not matched:
            continue
        new_content = apply_ftbquests_retry_updates_to_text(output_file.content, matched)
        if new_content != output_file.content:
            object.__setattr__(output_file, "content", new_content)
        full_path_updates[output_file.path] = matched

    updated = 0
    for output_path, updates in full_path_updates.items():
        target = safe_run_path(out_dir / "ftbquests", output_path)
        if target.is_file() and update_ftbquests_retry_file(target, updates):
            updated += 1

    for archive in sorted(out_dir.glob("ftbquests-*-patch.zip")):
        if update_ftbquests_retry_zip(archive, full_path_updates):
            updated += 1
    return updated


def retry_updates_for_ftbquests_path(path: str, updates_by_file: dict[str, dict[str, str]]) -> dict[str, str]:
    normalized = path.replace("\\", "/").strip("/")
    basename = Path(normalized).name
    matches: dict[str, str] = {}
    for file_name, updates in updates_by_file.items():
        requested = file_name.replace("\\", "/").strip("/")
        if normalized == requested or normalized.endswith(f"/{requested}") or basename == requested:
            matches.update(updates)
    return matches


def update_ftbquests_retry_file(path: Path, updates: dict[str, str]) -> bool:
    try:
        original = path.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    updated = apply_ftbquests_retry_updates_to_text(original, updates)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def apply_ftbquests_retry_updates_to_text(content: str, updates: dict[str, str]) -> str:
    try:
        root = parse_snbt(content)
    except ValueError:
        return content
    changed = False
    for leaf in collect_string_leaves(root):
        if leaf.key in updates:
            set_snbt_string(root, leaf.path, updates[leaf.key])
            changed = True
    return render_snbt(root) if changed else content


def update_ftbquests_retry_zip(path: Path, updates_by_path: dict[str, dict[str, str]]) -> bool:
    try:
        with ZipFile(path) as zf:
            members = [(info, zf.read(info.filename)) for info in zf.infolist()]
    except (OSError, BadZipFile):
        return False

    changed = False
    replacement: list[tuple[Any, bytes]] = []
    for info, data in members:
        updates = retry_updates_for_ftbquests_path(info.filename, updates_by_path)
        if updates:
            try:
                original = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                replacement.append((info, data))
                continue
            updated = apply_ftbquests_retry_updates_to_text(original, updates)
            if updated != original:
                data = updated.encode("utf-8")
                changed = True
        replacement.append((info, data))

    if changed:
        with ZipFile(path, "w") as zf:
            for info, data in replacement:
                zf.writestr(info, data)
    return changed


def successful_retry_updates(
    failed_entries: list[dict[str, Any]],
    translations: dict[str, str],
    failed_map: dict[str, str],
) -> dict[str, dict[str, str]]:
    updates: dict[str, dict[str, str]] = {}
    for entry in failed_entries:
        item_id = entry_id(entry)
        if item_id in failed_map or item_id not in translations:
            continue
        translated = translations[item_id]
        if validate_translation(entry.get("source", ""), translated):
            continue
        file_path = entry.get("file", "")
        key = entry.get("key", "")
        if not file_path or not key:
            continue
        updates.setdefault(file_path, {})[key] = translated
    return updates


def merge_retry_result(
    result: dict[str, Any],
    failed_entries: list[dict[str, Any]],
    translations: dict[str, str],
    failed_map: dict[str, str],
) -> tuple[int, int, list[dict[str, Any]]]:
    updated = 0
    still_failed = 0
    remaining_failed_entries: list[dict[str, Any]] = []
    visible_entries = result.get("entries", [])
    visible_by_id = {entry_id(entry): entry for entry in visible_entries if isinstance(entry, dict)}
    for failed_entry in failed_entries:
        item_id = entry_id(failed_entry)
        entry = visible_by_id.get(item_id, failed_entry)
        previous_status = str(entry.get("status") or failed_entry.get("status") or "api_failed")
        previous_message = str(entry.get("message") or failed_entry.get("message") or "")
        entry["retry_previous_status"] = previous_status
        entry["retry_previous_message"] = previous_message
        if item_id in failed_map or item_id not in translations:
            entry["message"] = str(failed_map.get(item_id, "retry did not return translation"))
            still_failed += 1
            remaining_failed_entries.append(dict(entry))
            continue
        translated = translations[item_id]
        errors = validate_translation(entry.get("source", ""), translated)
        if errors:
            entry["message"] = "; ".join(errors)
            still_failed += 1
            remaining_failed_entries.append(dict(entry))
            continue
        entry["target"] = translated
        entry["status"] = "translated"
        entry["message"] = "手动重试成功"
        updated += 1

    summary: dict[str, int] = {}
    base_summary = result.get("summary", {})
    if isinstance(base_summary, dict):
        summary.update({str(key): int(value) for key, value in base_summary.items()})
        summary["api_failed"] = still_failed
        summary["translated"] = max(0, summary.get("translated", 0)) + updated
    result["summary"] = summary
    result["api_failure_count"] = still_failed
    result["api_failed_entries"] = remaining_failed_entries
    return updated, still_failed, remaining_failed_entries
