from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Callable
from zipfile import BadZipFile, ZipFile

from .ftbquests import detect_legacy_snbt_files, find_lang_file_pairs, infer_source_locale_from_files, load_ftbquests_source
from .lang import collect_lang_documents, target_path_for
from .web_uploads import MultipartPart
from .web_utils import safe_run_path, sanitize_filename, sanitize_relative_upload_path

JsonPayloadParser = Callable[[Any, str], tuple[str, dict[str, Any], dict[str, str]]]
JsonTargetNamer = Callable[[str, str, str, str], str]


def preflight_inputs(
    kind: str,
    paths: list[Path],
    source_locale: str,
    target_locale: str,
    *,
    parse_json_payload: JsonPayloadParser,
    json_target_namer: JsonTargetNamer,
) -> dict[str, Any]:
    normalized_kind = kind if kind in {"jar", "ftbquests", "json"} else "jar"
    messages: list[dict[str, str]] = []
    items: list[dict[str, Any]] = []
    source_locale = (source_locale or "en_us").strip().lower()
    target_locale = (target_locale or "zh_cn").strip().lower()
    if normalized_kind == "json":
        items = preflight_json_paths(paths, source_locale, target_locale, messages, parse_json_payload, json_target_namer)
    elif normalized_kind == "ftbquests":
        items = preflight_ftbquests_paths(paths, source_locale, target_locale, messages)
    else:
        items = preflight_jar_paths(paths, source_locale, target_locale, messages)
    blocking = any(message.get("level") == "blocking" for message in messages)
    if not messages:
        messages.append({"level": "info", "message": "预检通过，可以开始生成。"})
    return {
        "ok": not blocking,
        "kind": normalized_kind,
        "source_locale": source_locale,
        "target_locale": target_locale,
        "summary": preflight_summary(normalized_kind, items),
        "messages": messages,
        "items": items,
    }


def save_preflight_uploads(kind: str, parts: list[MultipartPart], temp_root: Path, source_locale: str) -> list[Path]:
    if kind == "json":
        paths: list[Path] = []
        for index, part in enumerate([part for part in parts if part.name == "json_files" and part.filename and part.data], start=1):
            filename = sanitize_filename(part.filename or f"language-{index}.json")
            if not filename.lower().endswith(".json"):
                continue
            path = temp_root / filename
            path.write_bytes(part.data)
            paths.append(path)
        if not paths:
            raise ValueError("请上传语言 JSON 文件")
        return paths
    if kind == "ftbquests":
        uploaded = [part for part in parts if part.name == "ftbquests_files" and part.filename and part.data]
        if not uploaded:
            raise ValueError("请上传 FTB Quests ZIP/SNBT，或选择 quests/lang/en_us 目录")
        zip_paths: list[Path] = []
        snbt_parts: list[MultipartPart] = []
        for index, part in enumerate(uploaded, start=1):
            filename = sanitize_filename(part.filename or f"ftbquests-{index}.bin")
            if filename.lower().endswith(".zip"):
                path = temp_root / filename
                path.write_bytes(part.data)
                zip_paths.append(path)
            elif filename.lower().endswith(".snbt"):
                snbt_parts.append(part)
        if zip_paths and (len(zip_paths) > 1 or snbt_parts):
            raise ValueError("FTB Quests 模式一次只处理一个 ZIP，或上传一个/多个 SNBT 文件")
        if zip_paths:
            return [zip_paths[0]]
        snbt_root = temp_root / "ftbquests_input"
        for index, part in enumerate(snbt_parts, start=1):
            relative = sanitize_relative_upload_path(part.filename or f"{source_locale}-{index}.snbt")
            if "/" not in relative and re.match(r"^[a-z]{2}_[a-z]{2}\.snbt$", relative, flags=re.IGNORECASE):
                relative = f"lang/{relative}"
            target = safe_run_path(snbt_root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(part.data)
        return [snbt_root]
    paths = []
    for index, part in enumerate([part for part in parts if part.name == "jars" and part.filename and part.data], start=1):
        filename = sanitize_filename(part.filename or f"mod-{index}.jar")
        if not filename.lower().endswith(".jar"):
            continue
        path = temp_root / filename
        path.write_bytes(part.data)
        paths.append(path)
    if not paths:
        raise ValueError("请上传 Mod JAR 文件")
    return paths


def preflight_summary(kind: str, items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "inputs": len(items),
        "source_files": 0,
        "existing_target_files": 0,
        "output_files": 0,
    }
    if kind == "jar":
        summary["source_files"] = sum(int(item.get("source_files", 0)) for item in items)
        summary["existing_target_files"] = sum(int(item.get("existing_target_files", 0)) for item in items)
        summary["output_files"] = summary["source_files"]
    elif kind == "ftbquests":
        summary["source_files"] = sum(int(item.get("source_files", 0)) for item in items)
        summary["existing_target_files"] = sum(int(item.get("existing_target_files", 0)) for item in items)
        summary["output_files"] = sum(int(item.get("output_files", 0)) for item in items)
    else:
        summary["source_files"] = len([item for item in items if not item.get("error")])
        summary["output_files"] = summary["source_files"]
    return summary


def preflight_jar_paths(paths: list[Path], source_locale: str, target_locale: str, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in paths:
        try:
            with ZipFile(path) as zf:
                source_docs = collect_lang_documents(zf, source_locale)
                target_docs = collect_lang_documents(zf, target_locale)
                source_paths = [doc.path for doc in source_docs]
                target_paths = {doc.path for doc in target_docs}
                expected_targets = [target_path_for(doc.path, source_locale, target_locale) for doc in source_docs]
                existing_targets = [target for target in expected_targets if target in target_paths]
                if not source_docs:
                    messages.append({"level": "blocking", "message": f"{path.name} 没有找到 {source_locale} 语言文件。"})
                elif existing_targets:
                    messages.append({"level": "info", "message": f"{path.name} 已包含 {len(existing_targets)} 个 {target_locale} 目标语言文件。"})
                else:
                    messages.append({"level": "info", "message": f"{path.name} 将生成 {len(expected_targets)} 个目标语言文件。"})
                items.append(
                    {
                        "input": path.name,
                        "source_files": len(source_docs),
                        "existing_target_files": len(existing_targets),
                        "source_paths": source_paths,
                        "target_paths": expected_targets,
                        "target_path": expected_targets[0] if expected_targets else "",
                    }
                )
        except (BadZipFile, OSError, ValueError) as exc:
            messages.append({"level": "blocking", "message": f"{path.name} 不是可读取的 JAR：{exc}"})
            items.append({"input": path.name, "error": str(exc), "source_files": 0, "existing_target_files": 0})
    return items


def preflight_json_paths(
    paths: list[Path],
    source_locale: str,
    target_locale: str,
    messages: list[dict[str, str]],
    parse_json_payload: JsonPayloadParser,
    json_target_namer: JsonTargetNamer,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            schema, _root, entries = parse_json_payload(data, path.name)
            output_name = json_target_namer(path.name, source_locale, target_locale, schema)
            messages.append({"level": "info", "message": f"{path.name} 识别为 {json_schema_label(schema)}，将输出 {output_name}。"})
            items.append(
                {
                    "input": path.name,
                    "schema": schema,
                    "entries": len(entries),
                    "output_name": output_name,
                }
            )
        except json.JSONDecodeError as exc:
            messages.append({"level": "blocking", "message": f"{path.name} 不是有效 JSON：{exc}"})
            items.append({"input": path.name, "error": str(exc)})
        except ValueError as exc:
            messages.append({"level": "blocking", "message": f"{path.name} 无法作为语言 JSON 处理：{exc}"})
            items.append({"input": path.name, "error": str(exc)})
    return items


def json_schema_label(schema: str) -> str:
    if schema == "ui_locale":
        return "UI 语言包 JSON"
    return "普通语言 JSON"


def preflight_ftbquests_paths(paths: list[Path], source_locale: str, target_locale: str, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in paths:
        try:
            source = load_ftbquests_source(path, source_locale)
            detected_source = infer_source_locale_from_files(source.files, source_locale, target_locale)
            lang_pairs = find_lang_file_pairs(source.files, detected_source, target_locale)
            legacy_files = detect_legacy_snbt_files(source.files)
            root = source.root_prefix or "quests"
            if not lang_pairs:
                level = "warning" if legacy_files else "blocking"
                messages.append({"level": level, "message": f"{path.name} 未找到可处理的 lang/{detected_source}.snbt。"})
            else:
                messages.append({"level": "info", "message": f"{path.name} 识别到 {root} 根目录，将生成 {len(lang_pairs)} 个任务书语言文件。"})
            items.append(
                {
                    "input": path.name,
                    "root": root,
                    "source_locale": detected_source,
                    "source_files": len(lang_pairs),
                    "existing_target_files": sum(1 for _source, target in lang_pairs if target in source.files),
                    "output_files": len(lang_pairs),
                    "source_paths": [source_path for source_path, _target_path in lang_pairs],
                    "target_paths": [target_path for _source_path, target_path in lang_pairs],
                    "legacy_files": len(legacy_files),
                }
            )
        except (OSError, ValueError, BadZipFile) as exc:
            messages.append({"level": "blocking", "message": f"{path.name} 无法作为 FTB Quests 输入处理：{exc}"})
            items.append({"input": path.name, "error": str(exc)})
    return items
