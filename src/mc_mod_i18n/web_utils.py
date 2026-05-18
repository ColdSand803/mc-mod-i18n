from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import unquote


def sanitize_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or "upload.bin"


def unique_filename(filename: str, used: set[str]) -> str:
    name = sanitize_filename(filename)
    stem = Path(name).stem or "file"
    suffix = Path(name).suffix
    candidate = name
    index = 2
    while candidate.lower() in used:
        candidate = f"{stem}-{index}{suffix}"
        index += 1
    used.add(candidate.lower())
    return candidate


def sanitize_relative_upload_path(filename: str) -> str:
    raw = str(filename or "").replace("\\", "/")
    segments: list[str] = []
    for segment in raw.split("/"):
        if not segment or segment in {".", ".."}:
            continue
        if ":" in segment:
            segment = segment.split(":", 1)[-1]
        cleaned = sanitize_filename(segment)
        if cleaned:
            segments.append(cleaned)
    return "/".join(segments) or "upload.snbt"


def sanitize_job_id(job_id: str) -> str:
    return re.sub(r"[^a-fA-F0-9]", "", job_id)[:32]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_run_path(workdir: Path, relative: str) -> Path:
    decoded = unquote(relative).replace("\\", "/")
    target = (workdir / decoded).resolve()
    if target != workdir and workdir not in target.parents:
        raise ValueError("invalid path")
    return target
