from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .report import ReportEntry


def report_entries_from_dicts(entries: list[Any]) -> list[ReportEntry]:
    fields = {"jar", "mod_id", "file", "key", "source", "target", "status", "message"}
    report_entries: list[ReportEntry] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        payload = {field: str(entry.get(field) or "") for field in fields}
        report_entries.append(ReportEntry(**payload))
    return report_entries

def report_entry_dicts(entries: list[ReportEntry]) -> list[dict[str, str]]:
    return [entry.__dict__ for entry in entries]


def report_failure_dicts(entries: list[ReportEntry]) -> list[dict[str, str]]:
    return [entry.__dict__ for entry in entries if entry.status in {"failed", "api_failed", "incomplete", "jar_failed"}]


def write_report_exports(out_dir: Path, report_entries: list[ReportEntry], summary: dict[str, int], metadata: dict[str, Any]) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_json = out_dir / "report.json"
    report_csv = out_dir / "report.csv"
    failed_json = out_dir / "failed-items.json"
    payload = {
        **metadata,
        "summary": summary,
        "entries": report_entry_dicts(report_entries),
    }
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed_json.write_text(
        json.dumps({**metadata, "summary": summary, "entries": report_failure_dicts(report_entries)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with report_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["jar", "mod_id", "file", "key", "source", "target", "status", "message"])
        writer.writeheader()
        writer.writerows(report_entry_dicts(report_entries))
    return {"report_json": report_json, "report_csv": report_csv, "failed_json": failed_json}
