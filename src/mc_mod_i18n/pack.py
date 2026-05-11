from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from .lang import parse_json_lang, parse_legacy_lang, render_lang


@dataclass(frozen=True)
class OutputLangDocument:
    path: str
    format: str
    entries: dict[str, str | dict[str, object]]


def write_resource_pack(
    output_zip: Path,
    documents: list[OutputLangDocument],
    pack_format: int,
    description: str,
    icon_bytes: bytes | None = None,
) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    pack_meta = {
        "pack": {
            "pack_format": pack_format,
            "description": description,
        }
    }

    with ZipFile(output_zip, "w", ZIP_DEFLATED) as zf:
        zf.writestr("pack.mcmeta", json.dumps(pack_meta, ensure_ascii=False, indent=2) + "\n")
        if icon_bytes:
            zf.writestr("pack.png", icon_bytes)
        for document in sorted(documents, key=lambda item: item.path):
            zf.writestr(document.path, render_lang(document.entries, document.format))


def read_pack_icon(path: Path) -> bytes | None:
    try:
        if path.is_file():
            return path.read_bytes()
    except OSError:
        return None
    return None


def update_resource_pack_entries(output_zip: Path, updates: dict[str, dict[str, str]]) -> None:
    if not updates or not output_zip.is_file():
        return
    temp_zip = output_zip.with_suffix(output_zip.suffix + ".tmp")
    with ZipFile(output_zip, "r") as src, ZipFile(temp_zip, "w", ZIP_DEFLATED) as dst:
        written: set[str] = set()
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename in updates:
                fmt = "json" if info.filename.lower().endswith(".json") else "lang"
                raw = data.decode("utf-8-sig", errors="replace")
                entries = parse_json_lang(raw) if fmt == "json" else parse_legacy_lang(raw)
                entries.update(updates[info.filename])
                dst.writestr(info.filename, render_lang(entries, fmt))
                written.add(info.filename)
            else:
                dst.writestr(info, data)
        for path, entries in updates.items():
            if path not in written:
                fmt = "json" if path.lower().endswith(".json") else "lang"
                dst.writestr(path, render_lang(entries, fmt))
    temp_zip.replace(output_zip)


def resource_pack_filename(jar_paths: list[Path]) -> str:
    if not jar_paths:
        return "auto-i18n-resourcepack.zip"
    if len(jar_paths) == 1:
        stem = jar_paths[0].stem
    else:
        stem = f"{jar_paths[0].stem}-and-{len(jar_paths) - 1}-more"
    return f"{sanitize_pack_name(stem)}.zip"


def sanitize_pack_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" ._")
    return cleaned or "auto-i18n-resourcepack"


def read_pack_icon_from_jar(jar_path: Path) -> bytes | None:
    try:
        with ZipFile(jar_path) as zf:
            icon_path = find_pack_icon_path(zf)
            return zf.read(icon_path) if icon_path else None
    except (BadZipFile, OSError, KeyError):
        return None


def find_pack_icon_path(zf: ZipFile) -> str | None:
    names = set(zf.namelist())
    for metadata_path in ("fabric.mod.json", "quilt.mod.json"):
        if metadata_path not in names:
            continue
        try:
            data = json.loads(zf.read(metadata_path).decode("utf-8-sig"))
        except Exception:
            continue
        icon = data.get("icon")
        if isinstance(icon, str):
            normalized = icon.lstrip("/")
            if normalized in names and normalized.lower().endswith(".png"):
                return normalized

    if "META-INF/mods.toml" in names:
        try:
            text = zf.read("META-INF/mods.toml").decode("utf-8", errors="replace")
        except Exception:
            text = ""
        match = re.search(r"(?m)^\s*logoFile\s*=\s*['\"]([^'\"]+\.png)['\"]", text)
        if match:
            logo = match.group(1).lstrip("/")
            for candidate in (logo, f"META-INF/{logo}"):
                if candidate in names:
                    return candidate

    for candidate in ("pack.png", "icon.png", "assets/icon.png", "logo.png", "META-INF/logo.png"):
        if candidate in names:
            return candidate
    for name in sorted(names):
        lower = name.lower()
        if lower.endswith(".png") and ("icon" in lower or "logo" in lower):
            return name
    return None


CHECKPOINT_DIR = ".checkpoints"


def save_checkpoint(
    out_dir: Path,
    jar_stem: str,
    documents: list[OutputLangDocument],
    report_entries: list[object],
    source_hash: str = "",
    config_hash: str = "",
) -> None:
    ckpt_dir = out_dir / CHECKPOINT_DIR
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = ckpt_dir / f"{sanitize_pack_name(jar_stem)}.json"

    from .report import ReportEntry

    data: dict[str, object] = {
        "jar_stem": jar_stem,
        "documents": [
            {"path": d.path, "format": d.format, "entries": d.entries}
            for d in documents
        ],
        "report_entries": [
            {
                "jar": r.jar, "mod_id": r.mod_id, "file": r.file,
                "key": r.key, "source": r.source, "target": r.target,
                "status": r.status, "message": r.message,
            }
            for r in report_entries
            if hasattr(r, "jar")
        ],
    }
    if source_hash:
        data["source_hash"] = source_hash
    if config_hash:
        data["translation_config_hash"] = config_hash

    with open(ckpt_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_checkpoint_data(out_dir: Path, jar_stem: str) -> dict[str, object] | None:
    ckpt_path = (out_dir / CHECKPOINT_DIR) / f"{sanitize_pack_name(jar_stem)}.json"
    if not ckpt_path.is_file():
        return None
    with open(ckpt_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_checkpoint(
    out_dir: Path,
    jar_stem: str,
) -> tuple[list[OutputLangDocument], list[object]] | None:
    data = _load_checkpoint_data(out_dir, jar_stem)
    if data is None:
        return None

    from .report import ReportEntry

    documents = [
        OutputLangDocument(path=d["path"], format=d["format"], entries=d["entries"])
        for d in data.get("documents", [])
    ]
    report_entries = [
        ReportEntry(**r) for r in data.get("report_entries", [])
    ]
    return documents, report_entries


def load_checkpoint_source_hash(out_dir: Path, jar_stem: str) -> str:
    data = _load_checkpoint_data(out_dir, jar_stem)
    if data is None:
        return ""
    value = data.get("source_hash", "")
    return value if isinstance(value, str) else ""


def load_checkpoint_config_hash(out_dir: Path, jar_stem: str) -> str:
    data = _load_checkpoint_data(out_dir, jar_stem)
    if data is None:
        return ""
    value = data.get("translation_config_hash", "")
    return value if isinstance(value, str) else ""


def completed_jar_stems(out_dir: Path) -> set[str]:
    ckpt_dir = out_dir / CHECKPOINT_DIR
    if not ckpt_dir.is_dir():
        return set()
    return {p.stem for p in ckpt_dir.glob("*.json")}


PACK_FORMAT_MAP: dict[str, int] = {
    "1.16.2": 6, "1.16.3": 6, "1.16.4": 6, "1.16.5": 6,
    "1.17": 7, "1.17.1": 7,
    "1.18": 9, "1.18.1": 9, "1.18.2": 9,
    "1.19": 13, "1.19.1": 13, "1.19.2": 13,
    "1.19.3": 14,
    "1.19.4": 15,
    "1.20": 18, "1.20.1": 18,
    "1.20.2": 22, "1.20.3": 22, "1.20.4": 22,
    "1.20.5": 32, "1.20.6": 32,
    "1.21": 34, "1.21.1": 34,
    "1.21.2": 46, "1.21.3": 46,
    "1.21.4": 55, "1.21.5": 55,
}


def resolve_pack_format(value: str | int) -> int:
    if isinstance(value, int):
        return value
    value = value.strip()
    if value in PACK_FORMAT_MAP:
        return PACK_FORMAT_MAP[value]
    try:
        return int(value)
    except ValueError:
        pass
    for key, fmt in sorted(PACK_FORMAT_MAP.items(), reverse=True):
        if key.startswith(value + ".") or key == value:
            return fmt
    raise ValueError(
        f"Unknown Minecraft version '{value}'. "
        f"Use a numeric value or one of: {', '.join(sorted(PACK_FORMAT_MAP.keys(), key=lambda x: [int(p) for p in x.split('.')]))}"
    )
