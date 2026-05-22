from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .app_db import app_db_path, connect_app_db
from .provider_checks import redact_secret
from .web_utils import safe_run_path, sanitize_job_id, utc_timestamp


DEFAULT_JOB_HISTORY_LIMIT = 100
MAX_JOB_HISTORY_LIMIT = 5000


def build_job_history_record(job_id: str, job: dict[str, Any]) -> dict[str, Any]:
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    input_kind = str(result.get("kind") or job.get("input_kind") or "jar")
    raw_input_files = result.get("input_files", job.get("input_files"))
    primary_input_value = result.get("primary_input", job.get("primary_input"))
    input_files = normalize_history_input_files(raw_input_files if raw_input_files is not None else primary_input_value)
    primary_input = str(primary_input_value or (input_files[0] if input_files else ""))
    success_count = int(summary.get("translated", 0) or 0) + int(summary.get("existing", 0) or 0)
    failure_count = (
        int(summary.get("api_failed", 0) or 0)
        + int(summary.get("failed", 0) or 0)
        + int(summary.get("jar_failed", 0) or 0)
        + int(summary.get("incomplete", 0) or 0)
    )
    return {
        "job_id": job_id,
        "created_at": str(job.get("created_at") or utc_timestamp()),
        "updated_at": utc_timestamp(),
        "status": str(job.get("status") or "unknown"),
        "input_kind": input_kind,
        "input_files": input_files,
        "primary_input": primary_input,
        "target_locale": str(job.get("target_locale") or result.get("target_locale") or ""),
        "provider": str(result.get("provider") or job.get("provider") or ""),
        "model": str(result.get("model") or job.get("model") or ""),
        "processed_sources": int(result.get("processed_sources") or result.get("processed_jars") or 0),
        "generated_files": int(result.get("generated_files") or 0),
        "success_count": success_count,
        "failure_count": failure_count,
        "summary": sanitize_history_value(summary),
        "downloads": history_downloads(result),
        "download_files": history_download_files(job_id, result),
        "error": str(job.get("error") or ""),
    }


def normalize_history_input_files(value: Any) -> list[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                normalized.append(text)
        return normalized
    return []


def history_downloads(result: dict[str, Any]) -> dict[str, str]:
    mapping = {
        "pack": "pack_url",
        "json": "json_url",
        "ftbquests_patch": "ftbquests_patch_url",
        "report": "report_url",
        "report_json": "report_json_url",
        "report_csv": "report_csv_url",
        "failed_items": "failed_items_url",
        "hardcoded_report": "hardcoded_report_url",
        "hardcoded_map": "hardcoded_map_url",
        "api_debug_log": "api_debug_log_url",
    }
    return {
        label: str(result.get(key) or "")
        for label, key in mapping.items()
        if result.get(key)
    }


def history_download_files(job_id: str, result: dict[str, Any]) -> dict[str, str]:
    files: dict[str, str] = {}
    for label, url in history_downloads(result).items():
        relative = history_download_relative_path(job_id, url)
        if relative:
            files[label] = relative
    return files


def history_download_relative_path(job_id: str, url: str) -> str:
    path = urlparse(str(url or "")).path
    for prefix in (f"/download/{job_id}/", f"/report/{job_id}/"):
        if path.startswith(prefix):
            return path.removeprefix(prefix)
    return ""


def history_download_status(workdir: Path, record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    job_id = str(record.get("job_id") or "")
    downloads = record.get("downloads") if isinstance(record.get("downloads"), dict) else {}
    files = record.get("download_files") if isinstance(record.get("download_files"), dict) else {}
    status: dict[str, dict[str, Any]] = {}
    for label, url in downloads.items():
        relative = str(files.get(label) or history_download_relative_path(job_id, str(url or "")) or "")
        exists = False
        if relative:
            try:
                exists = safe_run_path(workdir, f"{job_id}/{relative}" if not relative.startswith(f"{job_id}/") else relative).is_file()
            except ValueError:
                exists = False
        status[str(label)] = {"exists": exists, "relative_path": relative}
    return status


def sanitize_history_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if "api_key" in key_text.lower() or key_text.lower() in {"authorization", "x-api-key"}:
                continue
            sanitized[key_text] = sanitize_history_value(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_history_value(item) for item in value]
    if isinstance(value, str):
        return redact_secret(value, value if value.startswith("sk-") else "")
    return value


def job_history_db_path(workdir: Path) -> Path:
    return app_db_path(workdir)


def legacy_job_history_index_path(workdir: Path) -> Path:
    return workdir / "jobs" / "index.jsonl"


def job_history_import_marker(workdir: Path) -> str:
    return f"import:{legacy_job_history_index_path(workdir).resolve()}"


def ensure_job_history_migrated(workdir: Path) -> None:
    marker = job_history_import_marker(workdir)
    with connect_app_db(job_history_db_path(workdir)) as connection:
        imported = connection.execute("SELECT 1 FROM schema_migrations WHERE key = ?", (marker,)).fetchone()
        if imported:
            return
        for record in read_legacy_job_history_records(workdir):
            upsert_job_history_record(connection, record)
        settings_path = job_history_settings_path(workdir)
        if settings_path.is_file():
            try:
                payload = json.loads(settings_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            if isinstance(payload, dict):
                limit = normalize_job_history_limit(payload.get("limit"))
                connection.execute(
                    """
                    INSERT INTO app_settings(key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                      value_json = excluded.value_json,
                      updated_at = excluded.updated_at
                    """,
                    ("job_history.limit", json.dumps({"limit": limit}, ensure_ascii=False, sort_keys=True), utc_timestamp()),
                )
        connection.execute(
            "INSERT OR REPLACE INTO schema_migrations(key, applied_at) VALUES (?, ?)",
            (marker, utc_timestamp()),
        )


def read_legacy_job_history_records(workdir: Path) -> list[dict[str, Any]]:
    index_path = legacy_job_history_index_path(workdir)
    if not index_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in index_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(normalize_job_history_record(value))
    return records


def normalize_job_history_record(record: dict[str, Any]) -> dict[str, Any]:
    value = dict(record)
    value["job_id"] = sanitize_job_id(str(value.get("job_id") or ""))
    value["created_at"] = str(value.get("created_at") or utc_timestamp())
    value["updated_at"] = str(value.get("updated_at") or value.get("created_at") or utc_timestamp())
    value["status"] = str(value.get("status") or "unknown")
    value["input_kind"] = str(value.get("input_kind") or "jar")
    input_files = normalize_history_input_files(value.get("input_files", value.get("primary_input")))
    value["input_files"] = input_files
    if not value.get("primary_input"):
        inferred = infer_history_primary_input(value)
        value["primary_input"] = inferred or (input_files[0] if input_files else "")
    value["primary_input"] = str(value.get("primary_input") or "")
    value["target_locale"] = str(value.get("target_locale") or "")
    value["provider"] = str(value.get("provider") or "")
    value["model"] = str(value.get("model") or "")
    value["processed_sources"] = int(value.get("processed_sources") or 0)
    value["generated_files"] = int(value.get("generated_files") or 0)
    value["success_count"] = int(value.get("success_count") or 0)
    value["failure_count"] = int(value.get("failure_count") or 0)
    value["summary"] = sanitize_history_value(value.get("summary") if isinstance(value.get("summary"), dict) else {})
    value["downloads"] = sanitize_history_value(value.get("downloads") if isinstance(value.get("downloads"), dict) else {})
    value["download_files"] = sanitize_history_value(value.get("download_files") if isinstance(value.get("download_files"), dict) else {})
    value["error"] = str(value.get("error") or "")
    value.pop("download_status", None)
    return value


def write_job_history_record(workdir: Path, record: dict[str, Any]) -> None:
    with connect_app_db(job_history_db_path(workdir)) as connection:
        upsert_job_history_record(connection, normalize_job_history_record(record))


def upsert_job_history_record(connection, record: dict[str, Any]) -> None:
    job_id = str(record.get("job_id") or "")
    if not job_id:
        return
    connection.execute(
        """
        INSERT INTO job_history(
          job_id, created_at, updated_at, status, input_kind, primary_input,
          target_locale, provider, model, processed_sources, generated_files,
          success_count, failure_count, summary_json, downloads_json,
          download_files_json, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
          created_at = excluded.created_at,
          updated_at = excluded.updated_at,
          status = excluded.status,
          input_kind = excluded.input_kind,
          primary_input = excluded.primary_input,
          target_locale = excluded.target_locale,
          provider = excluded.provider,
          model = excluded.model,
          processed_sources = excluded.processed_sources,
          generated_files = excluded.generated_files,
          success_count = excluded.success_count,
          failure_count = excluded.failure_count,
          summary_json = excluded.summary_json,
          downloads_json = excluded.downloads_json,
          download_files_json = excluded.download_files_json,
          error = excluded.error
        """,
        (
            job_id,
            record["created_at"],
            record["updated_at"],
            record["status"],
            record["input_kind"],
            record["primary_input"],
            record["target_locale"],
            record["provider"],
            record["model"],
            record["processed_sources"],
            record["generated_files"],
            record["success_count"],
            record["failure_count"],
            json.dumps(record["summary"], ensure_ascii=False, sort_keys=True),
            json.dumps(record["downloads"], ensure_ascii=False, sort_keys=True),
            json.dumps(record["download_files"], ensure_ascii=False, sort_keys=True),
            record["error"],
        ),
    )
    connection.execute("DELETE FROM job_input_files WHERE job_id = ?", (job_id,))
    connection.executemany(
        "INSERT INTO job_input_files(job_id, position, path) VALUES (?, ?, ?)",
        [(job_id, index, path) for index, path in enumerate(normalize_history_input_files(record.get("input_files")), start=1)],
    )


def job_history_record_from_row(workdir: Path, row: Any, input_files: list[str]) -> dict[str, Any]:
    def decode_json(text: Any) -> dict[str, Any]:
        try:
            value = json.loads(str(text or "{}"))
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    record = {
        "job_id": str(row["job_id"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "status": str(row["status"]),
        "input_kind": str(row["input_kind"]),
        "input_files": input_files,
        "primary_input": str(row["primary_input"]),
        "target_locale": str(row["target_locale"]),
        "provider": str(row["provider"]),
        "model": str(row["model"]),
        "processed_sources": int(row["processed_sources"] or 0),
        "generated_files": int(row["generated_files"] or 0),
        "success_count": int(row["success_count"] or 0),
        "failure_count": int(row["failure_count"] or 0),
        "summary": decode_json(row["summary_json"]),
        "downloads": decode_json(row["downloads_json"]),
        "download_files": decode_json(row["download_files_json"]),
        "error": str(row["error"] or ""),
    }
    record["download_status"] = history_download_status(workdir, record)
    return record


def append_job_history(workdir: Path, record: dict[str, Any], limit: int = 100) -> None:
    ensure_job_history_migrated(workdir)
    write_job_history_record(workdir, record)
    if limit > 0:
        trim_job_history(workdir, limit=limit)


def job_history_settings_path(workdir: Path) -> Path:
    jobs_dir = workdir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir / "settings.json"


def normalize_job_history_limit(value: Any, default: int = DEFAULT_JOB_HISTORY_LIMIT) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(MAX_JOB_HISTORY_LIMIT, limit))


def read_job_history_settings(workdir: Path) -> dict[str, int]:
    ensure_job_history_migrated(workdir)
    with connect_app_db(job_history_db_path(workdir)) as connection:
        row = connection.execute("SELECT value_json FROM app_settings WHERE key = ?", ("job_history.limit",)).fetchone()
    if row is not None:
        try:
            payload = json.loads(str(row["value_json"] or "{}"))
        except json.JSONDecodeError:
            payload = {}
        return {"limit": normalize_job_history_limit(payload.get("limit"))}
    path = job_history_settings_path(workdir)
    if not path.is_file():
        return {"limit": DEFAULT_JOB_HISTORY_LIMIT}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"limit": DEFAULT_JOB_HISTORY_LIMIT}
    if not isinstance(payload, dict):
        return {"limit": DEFAULT_JOB_HISTORY_LIMIT}
    return {"limit": normalize_job_history_limit(payload.get("limit"))}


def write_job_history_settings(workdir: Path, *, limit: int) -> dict[str, int]:
    ensure_job_history_migrated(workdir)
    normalized_limit = normalize_job_history_limit(limit)
    payload = {"limit": normalized_limit}
    with connect_app_db(job_history_db_path(workdir)) as connection:
        connection.execute(
            """
            INSERT INTO app_settings(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value_json = excluded.value_json,
              updated_at = excluded.updated_at
            """,
            ("job_history.limit", json.dumps(payload, ensure_ascii=False, sort_keys=True), utc_timestamp()),
        )
    return payload


def trim_job_history(workdir: Path, *, limit: int | None = None) -> dict[str, Any]:
    settings = read_job_history_settings(workdir)
    normalized_limit = normalize_job_history_limit(limit if limit is not None else settings.get("limit", DEFAULT_JOB_HISTORY_LIMIT))
    with connect_app_db(job_history_db_path(workdir)) as connection:
        before = int(connection.execute("SELECT COUNT(*) FROM job_history").fetchone()[0])
        rows = connection.execute(
            """
            SELECT job_id FROM job_history
            ORDER BY created_at DESC, updated_at DESC, job_id DESC
            LIMIT -1 OFFSET ?
            """,
            (normalized_limit,),
        ).fetchall()
        remove_ids = [str(row["job_id"]) for row in rows]
        if remove_ids:
            connection.executemany("DELETE FROM job_history WHERE job_id = ?", [(job_id,) for job_id in remove_ids])
        after = before - len(remove_ids)
    return {"ok": True, "before": before, "after": after, "removed": len(remove_ids), "limit": normalized_limit}


def delete_job_history_records(workdir: Path, job_ids: list[str]) -> dict[str, Any]:
    ensure_job_history_migrated(workdir)
    normalized_ids = {sanitize_job_id(job_id) for job_id in job_ids if sanitize_job_id(job_id)}
    with connect_app_db(job_history_db_path(workdir)) as connection:
        before = int(connection.execute("SELECT COUNT(*) FROM job_history").fetchone()[0])
        placeholders = ",".join("?" for _ in normalized_ids)
        query = "SELECT job_id FROM job_history WHERE job_id IN ({})".format(placeholders)
        existing = {
            str(row["job_id"])
            for row in connection.execute(query, tuple(normalized_ids)).fetchall()
        } if normalized_ids else set()
        if existing:
            connection.executemany("DELETE FROM job_history WHERE job_id = ?", [(job_id,) for job_id in existing])
        after = int(connection.execute("SELECT COUNT(*) FROM job_history").fetchone()[0])
    return {
        "ok": True,
        "before": before,
        "after": after,
        "removed": max(0, before - after),
        "removed_job_ids": sorted(existing),
    }


def clear_job_history(workdir: Path) -> dict[str, Any]:
    ensure_job_history_migrated(workdir)
    with connect_app_db(job_history_db_path(workdir)) as connection:
        before = int(connection.execute("SELECT COUNT(*) FROM job_history").fetchone()[0])
        connection.execute("DELETE FROM job_history")
    return {"ok": True, "before": before, "after": 0, "removed": before}


def read_job_history(workdir: Path, limit: int = 100) -> list[dict[str, Any]]:
    ensure_job_history_migrated(workdir)
    with connect_app_db(job_history_db_path(workdir)) as connection:
        query = """
            SELECT *
            FROM job_history
            ORDER BY created_at DESC, updated_at DESC, job_id DESC
        """
        params: tuple[Any, ...] = ()
        if limit > 0:
            query += " LIMIT ?"
            params = (limit,)
        rows = connection.execute(query, params).fetchall()
        job_ids = [str(row["job_id"]) for row in rows]
        input_files_by_job: dict[str, list[str]] = {job_id: [] for job_id in job_ids}
        if job_ids:
            placeholders = ",".join("?" for _ in job_ids)
            for file_row in connection.execute(
                f"""
                SELECT job_id, path
                FROM job_input_files
                WHERE job_id IN ({placeholders})
                ORDER BY job_id, position
                """,
                tuple(job_ids),
            ).fetchall():
                input_files_by_job.setdefault(str(file_row["job_id"]), []).append(str(file_row["path"]))
    return [job_history_record_from_row(workdir, row, input_files_by_job.get(str(row["job_id"]), [])) for row in rows]


def infer_history_primary_input(record: dict[str, Any]) -> str:
    input_files = normalize_history_input_files(record.get("input_files"))
    if input_files:
        return input_files[0]
    downloads = record.get("downloads") if isinstance(record.get("downloads"), dict) else {}
    preferred_labels = ["pack", "json", "ftbquests_patch"]
    for label in preferred_labels:
        candidate = history_primary_input_from_download(downloads.get(label))
        if candidate:
            return candidate
    return ""


def history_primary_input_from_download(url: Any) -> str:
    path = urlparse(str(url or "")).path
    filename = Path(unquote(path)).name
    cleaned = filename.strip()
    return cleaned if cleaned else ""
