from __future__ import annotations

import json
from pathlib import Path

from .hardcoded import HardcodedEntry, hardcoded_category_label, hardcoded_category_order


def hardcoded_entry_to_dict(entry: HardcodedEntry) -> dict[str, str]:
    return {
        "jar": entry.jar,
        "class": entry.class_path,
        "source": entry.text,
        "category": entry.category,
        "category_label": hardcoded_category_label(entry.category),
        "category_order": str(hardcoded_category_order(entry.category)),
        "risk": entry.risk,
        "suggestion": entry.suggestion,
    }


def read_jsonl(path: Path, limit: int = 300) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = {"type": "raw", "raw_body": line}
        if isinstance(value, dict):
            rows.append(value)
        if len(rows) >= limit:
            break
    return rows
