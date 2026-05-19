from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import escape
import json
from pathlib import Path
import re
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .core import response_guard_warning, translate_batch_with_failures
from .pack import CHECKPOINT_DIR, sanitize_pack_name
from .report import ReportEntry
from .translator import TranslationItem
from .validator import validate_translation


FTBQUESTS_PROMPT_VERSION = "2026-05-12.ftbquests-lang-snbt.v1"
FTBQUESTS_CACHE_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class FTBQuestsSource:
    label: str
    root_prefix: str
    files: dict[str, str]


@dataclass(frozen=True)
class FTBQuestsOutputFile:
    path: str
    content: str


@dataclass(frozen=True)
class FTBQuestsResult:
    source_label: str
    mode: str
    source_locale: str
    target_locale: str
    source_hash: str
    output_files: list[FTBQuestsOutputFile]
    report_entries: list[ReportEntry]
    legacy_files: list[str]


@dataclass(frozen=True)
class FTBQuestStringLeaf:
    path: tuple[str | int, ...]
    key: str
    text: str


@dataclass
class SnbtString:
    value: str


@dataclass
class SnbtScalar:
    raw: str


@dataclass
class SnbtList:
    items: list["SnbtValue"]


@dataclass
class SnbtCompound:
    entries: list[tuple[str, "SnbtValue"]]


SnbtValue = SnbtString | SnbtScalar | SnbtList | SnbtCompound


class SnbtParseError(ValueError):
    pass


def process_ftbquests(input_path: Path, args: Any, translator: Any) -> FTBQuestsResult:
    source = load_ftbquests_source(input_path, getattr(args, "source_locale", "en_us"))
    return process_ftbquests_source(source, args, translator)


def process_ftbquests_source(source: FTBQuestsSource, args: Any, translator: Any) -> FTBQuestsResult:
    requested_source_locale = normalize_locale(getattr(args, "source_locale", "en_us"))
    target_locale = normalize_locale(getattr(args, "target_locale", "zh_cn"))
    source_hash = compute_ftbquests_source_hash(source)
    source_locale = infer_source_locale_from_files(source.files, requested_source_locale, target_locale)
    lang_pairs = find_lang_file_pairs(source.files, source_locale, target_locale)
    legacy_files = detect_legacy_snbt_files(source.files)

    if not lang_pairs:
        report = [
            ReportEntry(
                jar=source.label,
                mod_id="ftbquests",
                file="",
                key="",
                source="",
                target="",
                status="skipped",
                message=(
                    f"未找到 lang/{source_locale}.snbt；"
                    f"检测到 {len(legacy_files)} 个旧版 SNBT 文件，当前版本只报告不改写"
                ),
            )
        ]
        return FTBQuestsResult(
            source_label=source.label,
            mode="legacy_detected" if legacy_files else "no_lang",
            source_locale=source_locale,
            target_locale=target_locale,
            source_hash=source_hash,
            output_files=[],
            report_entries=report,
            legacy_files=legacy_files,
        )

    report: list[ReportEntry] = []
    output_files: list[FTBQuestsOutputFile] = []
    for source_lang_path, target_lang_path in lang_pairs:
        output_file, entries = process_ftbquests_lang_file(
            source,
            source_lang_path,
            target_lang_path,
            args,
            translator,
        )
        output_files.append(output_file)
        report.extend(entries)

    return FTBQuestsResult(
        source_label=source.label,
        mode="split_lang" if len(lang_pairs) > 1 else "lang",
        source_locale=source_locale,
        target_locale=target_locale,
        source_hash=source_hash,
        output_files=output_files,
        report_entries=report,
        legacy_files=legacy_files,
    )


def process_ftbquests_lang_file(
    source: FTBQuestsSource,
    source_lang_path: str,
    target_lang_path: str,
    args: Any,
    translator: Any,
) -> tuple[FTBQuestsOutputFile, list[ReportEntry]]:
    source_root = parse_snbt(source.files[source_lang_path])
    existing_root = None
    if target_lang_path in source.files:
        existing_root = parse_snbt(source.files[target_lang_path])

    output_root = clone_snbt(source_root)
    existing_leaf_map = {leaf.path: leaf.text for leaf in collect_string_leaves(existing_root)} if existing_root else {}
    source_leaves = collect_string_leaves(source_root)
    report: list[ReportEntry] = []
    items: list[TranslationItem] = []
    item_by_id: dict[str, FTBQuestStringLeaf] = {}
    output_values: dict[tuple[str | int, ...], str] = {}
    overwrite_existing = bool(getattr(args, "overwrite_existing", False))

    for leaf in source_leaves:
        if leaf.path in existing_leaf_map and not overwrite_existing:
            target_text = existing_leaf_map[leaf.path]
            output_values[leaf.path] = target_text
            report.append(
                ReportEntry(
                    jar=source.label,
                    mod_id="ftbquests",
                    file=target_lang_path,
                    key=leaf.key,
                    source=leaf.text,
                    target=target_text,
                    status="existing",
                    message="kept existing target translation",
                )
            )
            continue
        if not leaf.text.strip():
            output_values[leaf.path] = leaf.text
            report.append(
                ReportEntry(
                    jar=source.label,
                    mod_id="ftbquests",
                    file=target_lang_path,
                    key=leaf.key,
                    source=leaf.text,
                    target=leaf.text,
                    status="skipped",
                    message="empty text",
                )
            )
            continue
        if is_non_translatable_text(leaf.text):
            output_values[leaf.path] = leaf.text
            report.append(
                ReportEntry(
                    jar=source.label,
                    mod_id="ftbquests",
                    file=target_lang_path,
                    key=leaf.key,
                    source=leaf.text,
                    target=leaf.text,
                    status="skipped",
                    message="looks like an id, url, command, or placeholder-only value",
                )
            )
            continue
        item_id = f"{source.label}\x1f{source_lang_path}\x1f{leaf.key}"
        item_by_id[item_id] = leaf
        items.append(TranslationItem(id=item_id, key=leaf.key, text=leaf.text, mod_id="ftbquests"))

    translations, failed_items = translate_batch_with_failures(translator, items)
    for item_id, leaf in item_by_id.items():
        if item_id in failed_items:
            output_values[leaf.path] = leaf.text
            report.append(
                ReportEntry(
                    jar=source.label,
                    mod_id="ftbquests",
                    file=target_lang_path,
                    key=leaf.key,
                    source=leaf.text,
                    target=leaf.text,
                    status="api_failed",
                    message=str(failed_items[item_id]),
                )
            )
            continue
        translated = translations.get(item_id, leaf.text)
        errors = validate_translation(leaf.text, translated)
        if errors:
            output_values[leaf.path] = leaf.text
            report.append(
                ReportEntry(
                    jar=source.label,
                    mod_id="ftbquests",
                    file=target_lang_path,
                    key=leaf.key,
                    source=leaf.text,
                    target=leaf.text,
                    status="failed",
                    message="; ".join(errors),
                )
            )
            continue
        output_values[leaf.path] = translated
        report.append(
            ReportEntry(
                jar=source.label,
                mod_id="ftbquests",
                file=target_lang_path,
                key=leaf.key,
                source=leaf.text,
                target=translated,
                status="translated",
                message=response_guard_warning(translator, item_id),
            )
        )

    for path, value in output_values.items():
        set_snbt_string(output_root, path, value)
    if isinstance(source_root, SnbtCompound) and isinstance(existing_root, SnbtCompound):
        append_extra_top_level_entries(output_root, source_root, existing_root)

    output_path = join_ftbquests_output_path(source.root_prefix, target_lang_path)
    return FTBQuestsOutputFile(path=output_path, content=render_snbt(output_root) + "\n"), report


def load_ftbquests_source(input_path: Path, source_locale: str = "en_us") -> FTBQuestsSource:
    if input_path.is_dir():
        return load_ftbquests_directory(input_path, source_locale)
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        return load_ftbquests_zip(input_path, source_locale)
    if input_path.is_file() and input_path.suffix.lower() == ".snbt":
        locale = normalize_locale(source_locale)
        rel_path = f"lang/{locale}.snbt" if input_path.stem.lower() == locale else input_path.name
        if input_path.parent.name.lower() == "lang":
            root_prefix = "config/ftbquests/quests/lang"
            rel_path = input_path.name
        elif input_path.parent.parent.name.lower() == "lang":
            root_prefix = "config/ftbquests/quests/lang"
            rel_path = f"{input_path.parent.name}/{input_path.name}"
        else:
            root_prefix = "config/ftbquests/quests"
        return FTBQuestsSource(
            label=input_path.name,
            root_prefix=root_prefix,
            files={normalize_rel_path(rel_path): input_path.read_text(encoding="utf-8-sig", errors="replace")},
        )
    raise ValueError(f"不支持的 FTB Quests 输入：{input_path}")


def load_ftbquests_directory(input_path: Path, source_locale: str = "en_us") -> FTBQuestsSource:
    if is_lang_root(input_path):
        files = read_snbt_tree(input_path)
        if not files:
            raise ValueError("没有找到 FTB Quests SNBT 文件")
        return FTBQuestsSource(label=input_path.name or str(input_path), root_prefix="config/ftbquests/quests/lang", files=files)
    if has_locale_child_dirs(input_path):
        files = read_snbt_tree(input_path)
        if not files:
            raise ValueError("没有找到 FTB Quests SNBT 文件")
        return FTBQuestsSource(label=input_path.name or str(input_path), root_prefix="config/ftbquests/quests/lang", files=files)
    if input_path.parent.name.lower() == "lang" and input_path.name.lower() == normalize_locale(source_locale):
        files = read_snbt_tree(input_path.parent)
        if not files:
            raise ValueError("没有找到 FTB Quests SNBT 文件")
        return FTBQuestsSource(label=input_path.name or str(input_path), root_prefix="config/ftbquests/quests/lang", files=files)
    quests_root, root_prefix = resolve_quests_directory(input_path)
    files = read_snbt_tree(quests_root)
    if not files:
        raise ValueError("没有找到 FTB Quests SNBT 文件")
    return FTBQuestsSource(label=input_path.name or str(input_path), root_prefix=root_prefix, files=files)


def read_snbt_tree(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*.snbt")):
        rel = normalize_rel_path(path.relative_to(root).as_posix())
        files[rel] = path.read_text(encoding="utf-8-sig", errors="replace")
    return files


def load_ftbquests_zip(input_path: Path, source_locale: str = "en_us") -> FTBQuestsSource:
    with ZipFile(input_path) as zf:
        names = [normalize_rel_path(name) for name in zf.namelist() if not name.endswith("/")]
        root = find_quests_root_prefix(names)
        if is_locale_path_segment(root):
            root = ""
        files: dict[str, str] = {}
        for name in names:
            rel = strip_quest_root_prefix(name, root)
            if not rel or not rel.lower().endswith(".snbt"):
                continue
            files[rel] = zf.read(name).decode("utf-8-sig", errors="replace")
    if not files:
        raise ValueError("ZIP 内没有找到 FTB Quests SNBT 文件")
    if not looks_like_lang_root_files(files) and looks_like_split_locale_contents(files):
        locale = normalize_locale(source_locale)
        files = {f"{locale}/{path}": content for path, content in files.items()}
    root_prefix = root or ("config/ftbquests/quests/lang" if looks_like_lang_root_files(files) else "config/ftbquests/quests")
    return FTBQuestsSource(label=input_path.name, root_prefix=root_prefix, files=files)


def resolve_quests_directory(input_path: Path) -> tuple[Path, str]:
    if is_quests_root(input_path):
        return input_path, "config/ftbquests/quests"
    packed_root = input_path / "config" / "ftbquests" / "quests"
    if is_quests_root(packed_root):
        return packed_root, "config/ftbquests/quests"
    matches = sorted(path for path in input_path.rglob("quests") if is_quests_root(path) and "ftbquests" in [p.lower() for p in path.parts])
    if matches:
        return matches[0], "config/ftbquests/quests"
    raise ValueError("未找到 config/ftbquests/quests 任务书目录")


def is_quests_root(path: Path) -> bool:
    return path.is_dir() and (
        (path / "lang").is_dir()
        or (path / "chapters").is_dir()
        or (path / "chapter_groups.snbt").is_file()
        or (path / "data.snbt").is_file()
    )


def is_lang_root(path: Path) -> bool:
    if not path.is_dir() or path.name.lower() != "lang":
        return False
    return any(child.is_dir() and re.fullmatch(r"[a-z]{2}_[a-z]{2}", child.name, flags=re.IGNORECASE) for child in path.iterdir())


def has_locale_child_dirs(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(child.is_dir() and is_locale_path_segment(child.name) for child in path.iterdir())


def is_locale_path_segment(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z]{2}_[a-z]{2}", str(value or "").strip(), flags=re.IGNORECASE))


def looks_like_lang_root_files(files: dict[str, str]) -> bool:
    return any(re.match(r"^[a-z]{2}_[a-z]{2}/", normalize_rel_path(path), flags=re.IGNORECASE) for path in files)


def looks_like_split_locale_contents(files: dict[str, str]) -> bool:
    paths = {normalize_rel_path(path).lower() for path in files}
    if any(path.startswith(("lang/", "chapters/")) for path in paths):
        return bool({"chapter.snbt", "chapter_group.snbt", "reward_table.snbt", "file.snbt"} & paths)
    return bool({"chapter.snbt", "chapter_group.snbt", "reward_table.snbt", "file.snbt"} & paths)


def find_quests_root_prefix(names: list[str]) -> str:
    for name in names:
        lower = name.lower()
        marker = "config/ftbquests/quests/"
        index = lower.find(marker)
        if index >= 0:
            return name[: index + len(marker)].rstrip("/")
    candidate_roots: set[str] = set()
    for name in names:
        lower = name.lower()
        if "/lang/" in lower:
            candidate_roots.add(name[: lower.rfind("/lang/")])
        elif "/chapters/" in lower:
            candidate_roots.add(name[: lower.rfind("/chapters/")])
        elif lower.startswith("lang/") or lower.startswith("chapters/"):
            candidate_roots.add("")
    if candidate_roots:
        return sorted(candidate_roots, key=len)[0].rstrip("/")
    return ""


def strip_quest_root_prefix(name: str, root: str) -> str:
    if not root:
        return normalize_rel_path(name)
    prefix = root.rstrip("/") + "/"
    if name.startswith(prefix):
        return normalize_rel_path(name[len(prefix) :])
    return ""


def find_lang_file_pairs(files: dict[str, str], source_locale: str, target_locale: str) -> list[tuple[str, str]]:
    source_locale = normalize_locale(source_locale)
    target_locale = normalize_locale(target_locale)
    pairs: list[tuple[str, str]] = []
    source_file = find_single_lang_file(files, source_locale)
    if source_file:
        pairs.append((source_file, target_path_for_lang(source_file, source_locale, target_locale)))
    split_pairs = find_split_lang_file_pairs(files, source_locale, target_locale)
    if split_pairs:
        return split_pairs
    return pairs


def infer_source_locale_from_files(files: dict[str, str], requested_locale: str, target_locale: str) -> str:
    requested_locale = normalize_locale(requested_locale)
    target_locale = normalize_locale(target_locale)
    locales = available_lang_locales(files)
    if requested_locale in locales:
        return requested_locale
    candidates = sorted(locale for locale in locales if locale != target_locale)
    if len(candidates) == 1:
        return candidates[0]
    return requested_locale


def available_lang_locales(files: dict[str, str]) -> set[str]:
    locales: set[str] = set()
    for path in files:
        normalized = normalize_rel_path(path).lower()
        for pattern in (
            r"^lang/([a-z]{2}_[a-z]{2})\.snbt$",
            r"^([a-z]{2}_[a-z]{2})\.snbt$",
            r"^lang/([a-z]{2}_[a-z]{2})/",
            r"^([a-z]{2}_[a-z]{2})/",
        ):
            match = re.match(pattern, normalized, flags=re.IGNORECASE)
            if match:
                locales.add(normalize_locale(match.group(1)))
                break
    return locales


def find_single_lang_file(files: dict[str, str], locale: str) -> str:
    target = f"lang/{normalize_locale(locale)}.snbt"
    direct = f"{normalize_locale(locale)}.snbt"
    for path in sorted(files):
        normalized = normalize_rel_path(path).lower()
        if normalized in {target, direct}:
            return path
    return ""


def find_split_lang_file_pairs(files: dict[str, str], source_locale: str, target_locale: str) -> list[tuple[str, str]]:
    source_locale = normalize_locale(source_locale)
    target_locale = normalize_locale(target_locale)
    pairs: list[tuple[str, str]] = []
    for path in sorted(files):
        normalized = normalize_rel_path(path)
        lower = normalized.lower()
        for prefix in (f"lang/{source_locale}/", f"{source_locale}/"):
            if lower.startswith(prefix) and lower.endswith(".snbt"):
                suffix = normalized[len(prefix) :]
                target_prefix = f"lang/{target_locale}/" if prefix.startswith("lang/") else f"{target_locale}/"
                pairs.append((path, target_prefix + suffix))
                break
    return pairs


def target_path_for_lang(source_path: str, source_locale: str, target_locale: str) -> str:
    source_locale = normalize_locale(source_locale)
    target_locale = normalize_locale(target_locale)
    escaped = re.escape(source_locale)
    return re.sub(rf"(^|/){escaped}\.snbt$", lambda match: f"{match.group(1)}{target_locale}.snbt", source_path, flags=re.IGNORECASE)


def detect_legacy_snbt_files(files: dict[str, str]) -> list[str]:
    legacy_markers = ("chapters/", "reward_tables/", "chapter_groups.snbt", "data.snbt")
    return [
        path for path in sorted(files)
        if path.lower().endswith(".snbt") and any(marker in path.lower() for marker in legacy_markers)
    ]


def compute_ftbquests_source_hash(source: FTBQuestsSource) -> str:
    payload = {
        "root_prefix": source.root_prefix,
        "files": source.files,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def compute_ftbquests_config_hash(args: Any) -> str:
    glossary_hash = ""
    glossary_path = getattr(args, "glossary", None)
    if glossary_path:
        try:
            glossary_hash = hashlib.sha256(Path(glossary_path).read_bytes()).hexdigest()
        except OSError:
            glossary_hash = ""
    scope = {
        "schema": FTBQUESTS_CACHE_SCHEMA_VERSION,
        "prompt": FTBQUESTS_PROMPT_VERSION,
        "source_locale": normalize_locale(getattr(args, "source_locale", "en_us")),
        "target_locale": normalize_locale(getattr(args, "target_locale", "zh_cn")),
        "provider": getattr(args, "provider", "glossary"),
        "model": getattr(args, "model", ""),
        "api_url": getattr(args, "api_url", ""),
        "overwrite_existing": bool(getattr(args, "overwrite_existing", False)),
        "glossary_hash": glossary_hash,
    }
    return hashlib.sha256(json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def ftbquests_cache_key(input_path: Path) -> str:
    name_hash = hashlib.sha1(str(input_path).encode("utf-8")).hexdigest()[:10]
    return f"ftbquests-{sanitize_pack_name(input_path.stem or input_path.name)}-{name_hash}"


def save_ftbquests_checkpoint(
    out_dir: Path,
    key: str,
    result: FTBQuestsResult,
    config_hash: str = "",
) -> None:
    ckpt_dir = out_dir / CHECKPOINT_DIR
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = ckpt_dir / f"{sanitize_pack_name(key)}.json"
    data = ftbquests_result_to_dict(result)
    data["translation_config_hash"] = config_hash
    ckpt_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_ftbquests_checkpoint(out_dir: Path, key: str) -> FTBQuestsResult | None:
    data = load_ftbquests_checkpoint_data(out_dir, key)
    if data is None:
        return None
    return ftbquests_result_from_dict(data)


def load_ftbquests_checkpoint_source_hash(out_dir: Path, key: str) -> str:
    data = load_ftbquests_checkpoint_data(out_dir, key)
    value = data.get("source_hash", "") if data else ""
    return value if isinstance(value, str) else ""


def load_ftbquests_checkpoint_config_hash(out_dir: Path, key: str) -> str:
    data = load_ftbquests_checkpoint_data(out_dir, key)
    value = data.get("translation_config_hash", "") if data else ""
    return value if isinstance(value, str) else ""


def load_ftbquests_checkpoint_data(out_dir: Path, key: str) -> dict[str, Any] | None:
    ckpt_path = (out_dir / CHECKPOINT_DIR) / f"{sanitize_pack_name(key)}.json"
    if not ckpt_path.is_file():
        return None
    return json.loads(ckpt_path.read_text(encoding="utf-8"))


def ftbquests_result_to_dict(result: FTBQuestsResult) -> dict[str, Any]:
    return {
        "source_label": result.source_label,
        "mode": result.mode,
        "source_locale": result.source_locale,
        "target_locale": result.target_locale,
        "source_hash": result.source_hash,
        "legacy_files": result.legacy_files,
        "output_files": [{"path": item.path, "content": item.content} for item in result.output_files],
        "report_entries": [entry.__dict__ for entry in result.report_entries],
    }


def ftbquests_result_from_dict(data: dict[str, Any]) -> FTBQuestsResult:
    return FTBQuestsResult(
        source_label=str(data.get("source_label", "")),
        mode=str(data.get("mode", "")),
        source_locale=str(data.get("source_locale", "en_us")),
        target_locale=str(data.get("target_locale", "zh_cn")),
        source_hash=str(data.get("source_hash", "")),
        output_files=[
            FTBQuestsOutputFile(path=str(item.get("path", "")), content=str(item.get("content", "")))
            for item in data.get("output_files", [])
            if isinstance(item, dict)
        ],
        report_entries=[
            ReportEntry(**entry)
            for entry in data.get("report_entries", [])
            if isinstance(entry, dict)
        ],
        legacy_files=[str(item) for item in data.get("legacy_files", [])],
    )


def write_ftbquests_outputs(out_dir: Path, result: FTBQuestsResult, output_mode: str = "both") -> tuple[Path | None, Path | None]:
    out_dir.mkdir(parents=True, exist_ok=True)
    output_mode = str(output_mode or "both").lower()
    directory_root = out_dir / "ftbquests"
    patch_path = out_dir / f"ftbquests-{sanitize_pack_name(result.target_locale)}-patch.zip"
    directory_written: Path | None = None
    patch_written: Path | None = None

    if output_mode in {"directory", "both"}:
        for item in result.output_files:
            target = safe_output_path(directory_root, item.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.content, encoding="utf-8")
        directory_written = directory_root

    if output_mode in {"zip", "patch", "both"}:
        with ZipFile(patch_path, "w", ZIP_DEFLATED) as zf:
            for item in result.output_files:
                zf.writestr(item.path, item.content)
        patch_written = patch_path

    return directory_written, patch_written


def write_ftbquests_json_report(path: Path, result: FTBQuestsResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = ftbquests_result_to_dict(result)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_ftbquests_html_report(path: Path, result: FTBQuestsResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    totals: dict[str, int] = {}
    for entry in result.report_entries:
        totals[entry.status] = totals.get(entry.status, 0) + 1
    summary = "".join(f"<li>{escape(status)}: {count}</li>" for status, count in sorted(totals.items()))
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(entry.status)}</td>"
        f"<td>{escape(entry.file)}</td>"
        f"<td>{escape(entry.key)}</td>"
        f"<td>{escape(entry.source)}</td>"
        f"<td>{escape(entry.target)}</td>"
        f"<td>{escape(entry.message)}</td>"
        "</tr>"
        for entry in result.report_entries
    )
    legacy = "".join(f"<li>{escape(item)}</li>" for item in result.legacy_files)
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>FTB Quests report</title>
  <style>
    body {{ font-family: Segoe UI, Microsoft YaHei, sans-serif; margin: 24px; color: #1f2937; background: #f8fafc; }}
    section {{ background: #fff; border: 1px solid #dbe3ef; border-radius: 8px; padding: 16px; margin: 14px 0; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; background: #fff; }}
    th, td {{ border: 1px solid #dbe3ef; padding: 8px; vertical-align: top; word-break: break-word; }}
    th {{ background: #f1f5f9; text-align: left; }}
  </style>
</head>
<body>
  <h1>FTB Quests 翻译报告</h1>
  <section>
    <h2>摘要</h2>
    <ul>{summary}</ul>
    <div>模式：{escape(result.mode)}；源语言：{escape(result.source_locale)}；目标语言：{escape(result.target_locale)}</div>
  </section>
  <section>
    <h2>旧版 SNBT 检测</h2>
    <ul>{legacy or "<li>未检测到旧版章节 SNBT。</li>"}</ul>
  </section>
  <table>
    <thead><tr><th>状态</th><th>文件</th><th>Key</th><th>原文</th><th>译文</th><th>信息</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="6">无条目</td></tr>'}</tbody>
  </table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def parse_snbt(raw: str) -> SnbtValue:
    parser = SnbtParser(raw)
    value = parser.parse_value()
    parser.skip_ws_comments()
    if not parser.at_end():
        raise SnbtParseError(f"unexpected trailing SNBT at offset {parser.index}")
    return value


class SnbtParser:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.index = 0

    def at_end(self) -> bool:
        return self.index >= len(self.raw)

    def peek(self) -> str:
        return "" if self.at_end() else self.raw[self.index]

    def consume(self) -> str:
        ch = self.peek()
        self.index += 1
        return ch

    def skip_ws_comments(self) -> None:
        while not self.at_end():
            ch = self.peek()
            if ch.isspace():
                self.index += 1
                continue
            if ch == "#":
                self.skip_line_comment()
                continue
            if self.raw.startswith("//", self.index):
                self.skip_line_comment()
                continue
            if self.raw.startswith("/*", self.index):
                end = self.raw.find("*/", self.index + 2)
                self.index = len(self.raw) if end < 0 else end + 2
                continue
            break

    def skip_line_comment(self) -> None:
        end = self.raw.find("\n", self.index)
        self.index = len(self.raw) if end < 0 else end + 1

    def parse_value(self) -> SnbtValue:
        self.skip_ws_comments()
        ch = self.peek()
        if ch == "{":
            return self.parse_compound()
        if ch == "[":
            return self.parse_list()
        if ch in {"'", '"'}:
            return SnbtString(self.parse_quoted_string())
        return SnbtScalar(self.parse_bare_token())

    def parse_compound(self) -> SnbtCompound:
        self.expect("{")
        entries: list[tuple[str, SnbtValue]] = []
        while True:
            self.skip_ws_comments()
            if self.peek() == "}":
                self.consume()
                break
            key = self.parse_key()
            self.skip_ws_comments()
            self.expect(":")
            value = self.parse_value()
            entries.append((key, value))
            self.skip_ws_comments()
            if self.peek() == ",":
                self.consume()
                continue
            if self.peek() == "}":
                continue
            if self.at_end():
                raise SnbtParseError("unterminated compound")
            continue
        return SnbtCompound(entries)

    def parse_list(self) -> SnbtList:
        self.expect("[")
        items: list[SnbtValue] = []
        while True:
            self.skip_ws_comments()
            if self.peek() == "]":
                self.consume()
                break
            items.append(self.parse_value())
            self.skip_ws_comments()
            if self.peek() == ",":
                self.consume()
                continue
            if self.peek() == "]":
                continue
            if self.at_end():
                raise SnbtParseError("unterminated list")
            continue
        return SnbtList(items)

    def parse_key(self) -> str:
        self.skip_ws_comments()
        if self.peek() in {"'", '"'}:
            return self.parse_quoted_string()
        return self.parse_bare_token(stop_chars={":"})

    def parse_quoted_string(self) -> str:
        quote = self.consume()
        chars: list[str] = []
        while not self.at_end():
            ch = self.consume()
            if ch == quote:
                return "".join(chars)
            if ch == "\\" and not self.at_end():
                nxt = self.consume()
                chars.append({"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(nxt, nxt))
            else:
                chars.append(ch)
        raise SnbtParseError("unterminated string")

    def parse_bare_token(self, stop_chars: set[str] | None = None) -> str:
        stop_chars = stop_chars or {",", "]", "}"}
        start = self.index
        while not self.at_end():
            ch = self.peek()
            if ch.isspace() or ch in stop_chars:
                break
            self.index += 1
        token = self.raw[start:self.index].strip()
        if not token:
            raise SnbtParseError(f"expected token at offset {start}")
        return token

    def expect(self, expected: str) -> None:
        self.skip_ws_comments()
        if self.peek() != expected:
            raise SnbtParseError(f"expected {expected!r} at offset {self.index}")
        self.consume()


def collect_string_leaves(value: SnbtValue | None, prefix: tuple[str | int, ...] = ()) -> list[FTBQuestStringLeaf]:
    if value is None:
        return []
    if isinstance(value, SnbtString):
        return [FTBQuestStringLeaf(path=prefix, key=snbt_path_label(prefix), text=value.value)]
    if isinstance(value, SnbtList):
        leaves: list[FTBQuestStringLeaf] = []
        for index, item in enumerate(value.items):
            leaves.extend(collect_string_leaves(item, (*prefix, index)))
        return leaves
    if isinstance(value, SnbtCompound):
        leaves = []
        for key, item in value.entries:
            leaves.extend(collect_string_leaves(item, (*prefix, key)))
        return leaves
    return []


def clone_snbt(value: SnbtValue) -> SnbtValue:
    if isinstance(value, SnbtString):
        return SnbtString(value.value)
    if isinstance(value, SnbtScalar):
        return SnbtScalar(value.raw)
    if isinstance(value, SnbtList):
        return SnbtList([clone_snbt(item) for item in value.items])
    return SnbtCompound([(key, clone_snbt(item)) for key, item in value.entries])


def set_snbt_string(value: SnbtValue, path: tuple[str | int, ...], text: str) -> None:
    if not path:
        if isinstance(value, SnbtString):
            value.value = text
        return
    head, *tail = path
    if isinstance(value, SnbtCompound) and isinstance(head, str):
        for index, (key, child) in enumerate(value.entries):
            if key == head:
                if tail:
                    set_snbt_string(child, tuple(tail), text)
                else:
                    value.entries[index] = (key, SnbtString(text))
                return
        value.entries.append((head, SnbtString(text)))
        return
    if isinstance(value, SnbtList) and isinstance(head, int) and 0 <= head < len(value.items):
        if tail:
            set_snbt_string(value.items[head], tuple(tail), text)
        else:
            value.items[head] = SnbtString(text)


def append_extra_top_level_entries(output_root: SnbtValue, source_root: SnbtCompound, existing_root: SnbtCompound) -> None:
    if not isinstance(output_root, SnbtCompound):
        return
    source_keys = {key for key, _ in source_root.entries}
    output_keys = {key for key, _ in output_root.entries}
    for key, value in existing_root.entries:
        if key not in source_keys and key not in output_keys:
            output_root.entries.append((key, clone_snbt(value)))
            output_keys.add(key)


def render_snbt(value: SnbtValue, indent: int = 0) -> str:
    if isinstance(value, SnbtString):
        return quote_snbt_string(value.value)
    if isinstance(value, SnbtScalar):
        return value.raw
    if isinstance(value, SnbtList):
        if not value.items:
            return "[]"
        inner_indent = indent + 2
        pieces = [
            " " * inner_indent + render_snbt(item, inner_indent) + ("," if index < len(value.items) - 1 else "")
            for index, item in enumerate(value.items)
        ]
        return "[\n" + "\n".join(pieces) + "\n" + " " * indent + "]"
    if not value.entries:
        return "{}"
    inner_indent = indent + 2
    pieces = [
        " " * inner_indent
        + quote_snbt_key(key)
        + ": "
        + render_snbt(item, inner_indent)
        + ("," if index < len(value.entries) - 1 else "")
        for index, (key, item) in enumerate(value.entries)
    ]
    return "{\n" + "\n".join(pieces) + "\n" + " " * indent + "}"


def quote_snbt_key(value: str) -> str:
    return quote_snbt_string(value)


def quote_snbt_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def snbt_path_label(path: tuple[str | int, ...]) -> str:
    parts: list[str] = []
    for item in path:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(item)
    return ".".join(parts)


def is_non_translatable_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", stripped, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"#[a-z0-9_.-]+:[a-z0-9_./-]+", stripped, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"https?://\S+", stripped, flags=re.IGNORECASE):
        return True
    if stripped.startswith("/"):
        return True
    if re.fullmatch(r"[%{}A-Za-z0-9_.:-]+", stripped) and re.fullmatch(r"(?:\{[A-Za-z0-9_.:-]+\}|%s|%\d+\$s)+", stripped):
        return True
    return False


def join_ftbquests_output_path(root_prefix: str, rel_path: str) -> str:
    root = normalize_rel_path(root_prefix or "config/ftbquests/quests").strip("/")
    rel = normalize_rel_path(rel_path).strip("/")
    return f"{root}/{rel}" if root else rel


def normalize_rel_path(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("/")


def normalize_locale(locale: str) -> str:
    return str(locale or "").strip().lower() or "en_us"


def safe_output_path(root: Path, relative: str) -> Path:
    target = (root / normalize_rel_path(relative)).resolve()
    root_resolved = root.resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ValueError("输出路径越界")
    return target
