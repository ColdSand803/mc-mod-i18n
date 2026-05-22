from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .app_db import app_db_path, connect_app_db
from .core import compute_translation_config_hash
from .translator import GlossaryTranslator
from .web_utils import utc_timestamp


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIRNAME = "cache"
DEFAULT_UI_LOCALE_DIR = Path("extensions") / "ui-locales"


def default_cache_root(workdir: Path) -> Path:
    return (workdir / DEFAULT_CACHE_DIRNAME).resolve()


def default_ui_locale_root(workdir: Path) -> Path:
    return (workdir / DEFAULT_UI_LOCALE_DIR).resolve()

def user_glossary_path(workdir: Path) -> Path:
    return workdir / "glossaries" / "user-glossary.json"


def glossary_import_marker(workdir: Path) -> str:
    return f"import:{user_glossary_path(workdir).resolve()}"


def normalize_glossary_terms(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("术语表必须是 JSON 对象")
    terms: dict[str, str] = {}
    for key, target in value.items():
        source = str(key).strip()
        translation = str(target).strip()
        if source and translation:
            terms[source] = translation
    return dict(sorted(terms.items(), key=lambda item: item[0].casefold()))


def read_user_glossary(workdir: Path) -> dict[str, str]:
    ensure_user_glossary_migrated(workdir)
    with connect_app_db(app_db_path(workdir)) as connection:
        rows = connection.execute("SELECT source, target FROM glossary_terms ORDER BY lower(source), source").fetchall()
    return {str(row["source"]): str(row["target"]) for row in rows}


def write_user_glossary(workdir: Path, terms: dict[str, str]) -> Path:
    ensure_user_glossary_migrated(workdir)
    normalized = normalize_glossary_terms(terms)
    with connect_app_db(app_db_path(workdir)) as connection:
        connection.execute("DELETE FROM glossary_terms")
        connection.executemany(
            "INSERT INTO glossary_terms(source, target, updated_at) VALUES (?, ?, ?)",
            [(source, target, utc_timestamp()) for source, target in normalized.items()],
        )
    path = user_glossary_path(workdir)
    sync_user_glossary_file(path, normalized)
    return path


def sync_user_glossary_file(path: Path, terms: dict[str, str]) -> None:
    if terms:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(terms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


def ensure_user_glossary_migrated(workdir: Path) -> None:
    marker = glossary_import_marker(workdir)
    path = user_glossary_path(workdir)
    with connect_app_db(app_db_path(workdir)) as connection:
        imported = connection.execute("SELECT 1 FROM schema_migrations WHERE key = ?", (marker,)).fetchone()
        if imported:
            return
        if path.is_file():
            try:
                terms = normalize_glossary_terms(json.loads(path.read_text(encoding="utf-8-sig")))
            except (OSError, ValueError, json.JSONDecodeError):
                terms = {}
            if terms:
                connection.executemany(
                    "INSERT OR REPLACE INTO glossary_terms(source, target, updated_at) VALUES (?, ?, ?)",
                    [(source, target, utc_timestamp()) for source, target in terms.items()],
                )
        connection.execute(
            "INSERT OR REPLACE INTO schema_migrations(key, applied_at) VALUES (?, ?)",
            (marker, utc_timestamp()),
        )


def glossary_conflicts(terms: dict[str, str]) -> dict[str, dict[str, str]]:
    builtin = {**GlossaryTranslator.BUILTIN_GLOSSARY, **GlossaryTranslator.BUILTIN_PHRASES}
    conflicts: dict[str, dict[str, str]] = {}
    for source, target in terms.items():
        builtin_target = builtin.get(source)
        if builtin_target is not None and builtin_target != target:
            conflicts[source] = {"builtin": builtin_target, "user": target}
    return conflicts


def saved_glossary_path_if_present(workdir: Path) -> Path | None:
    path = user_glossary_path(workdir)
    terms = read_user_glossary(workdir)
    if not terms:
        sync_user_glossary_file(path, terms)
        return None
    sync_user_glossary_file(path, terms)
    return path


PRESET_SCHEMA_VERSION = 1
PRESET_ALLOWED_KEYS = {
    "provider",
    "api_url",
    "api_region",
    "model",
    "api_key_env",
    "api_concurrency",
    "api_retries",
    "api_batch_size",
    "api_timeout",
    "pack_format",
    "overwrite_existing",
    "skip_translated",
    "ignore_cache",
    "ignore_translation_memory",
    "ignore_preflight_blockers",
    "scan_hardcoded",
}


def presets_dir(workdir: Path) -> Path:
    return workdir / "presets"


def normalize_preset_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", str(name or "").strip())
    if not normalized:
        raise ValueError("预设名称不能为空")
    if len(normalized) > 80:
        raise ValueError("预设名称不能超过 80 个字符")
    return normalized


def preset_slug(name: str) -> str:
    normalized = normalize_preset_name(name)
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized).strip(".-_").lower()
    if not slug:
        slug = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return slug[:80]


def normalize_preset_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("预设配置必须是对象")
    config = {key: value[key] for key in PRESET_ALLOWED_KEYS if key in value}
    config.pop("api_key", None)
    for key in ("api_concurrency", "api_retries", "api_batch_size", "api_timeout", "pack_format"):
        if key in config:
            config[key] = int(config[key] or 0)
    for key in ("overwrite_existing", "skip_translated", "ignore_cache", "ignore_translation_memory", "ignore_preflight_blockers", "scan_hardcoded"):
        if key in config:
            config[key] = bool(config[key])
    for key in ("provider", "api_url", "api_region", "model", "api_key_env"):
        if key in config:
            config[key] = str(config[key] or "").strip()
    return config


def preset_path(workdir: Path, name: str) -> Path:
    return presets_dir(workdir) / f"{preset_slug(name)}.json"


def read_config_preset(workdir: Path, name: str) -> dict[str, Any]:
    ensure_config_presets_migrated(workdir)
    slug = preset_slug(name)
    with connect_app_db(app_db_path(workdir)) as connection:
        row = connection.execute(
            "SELECT name, config_json FROM config_presets WHERE slug = ?", (slug,)
        ).fetchone()
    if not row:
        raise ValueError("预设不存在")
    return {
        "schema": PRESET_SCHEMA_VERSION,
        "name": row["name"],
        "config": json.loads(row["config_json"]),
    }


def list_config_presets(workdir: Path) -> list[dict[str, Any]]:
    ensure_config_presets_migrated(workdir)
    with connect_app_db(app_db_path(workdir)) as connection:
        rows = connection.execute(
            "SELECT name, config_json FROM config_presets ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [
        {"name": row["name"], "config": json.loads(row["config_json"])}
        for row in rows
    ]


def write_config_preset(workdir: Path, name: str, config: Any) -> dict[str, Any]:
    ensure_config_presets_migrated(workdir)
    normalized_name = normalize_preset_name(name)
    slug = preset_slug(normalized_name)
    normalized_config = normalize_preset_config(config)
    config_json = json.dumps(normalized_config, ensure_ascii=False)
    now = utc_timestamp()
    with connect_app_db(app_db_path(workdir)) as connection:
        connection.execute(
            "INSERT INTO config_presets(slug, name, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(slug) DO UPDATE SET name = excluded.name, config_json = excluded.config_json, updated_at = excluded.updated_at",
            (slug, normalized_name, config_json, now, now),
        )
    return {"schema": PRESET_SCHEMA_VERSION, "name": normalized_name, "config": normalized_config}


def delete_config_preset(workdir: Path, name: str) -> None:
    ensure_config_presets_migrated(workdir)
    slug = preset_slug(name)
    with connect_app_db(app_db_path(workdir)) as connection:
        exists = connection.execute("SELECT 1 FROM config_presets WHERE slug = ?", (slug,)).fetchone()
        if not exists:
            raise ValueError("预设不存在")
        connection.execute("DELETE FROM config_presets WHERE slug = ?", (slug,))


def _preset_import_marker(workdir: Path) -> str:
    return f"import:{(workdir / 'presets').resolve()}"


def ensure_config_presets_migrated(workdir: Path) -> None:
    marker = _preset_import_marker(workdir)
    root = presets_dir(workdir)
    with connect_app_db(app_db_path(workdir)) as connection:
        if connection.execute("SELECT 1 FROM schema_migrations WHERE key = ?", (marker,)).fetchone():
            return
        if root.is_dir():
            now = utc_timestamp()
            for path in root.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8-sig"))
                    slug = path.stem
                    name = normalize_preset_name(str(payload.get("name", slug)))
                    config = normalize_preset_config(payload.get("config", {}))
                    connection.execute(
                        "INSERT OR IGNORE INTO config_presets(slug, name, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (slug, name, json.dumps(config, ensure_ascii=False), now, now),
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
        connection.execute(
            "INSERT INTO schema_migrations(key, applied_at) VALUES (?, ?)",
            (marker, utc_timestamp()),
        )


def resolve_cache_root(workdir: Path, raw_cache_dir: str | None) -> Path:
    raw = (raw_cache_dir or "").strip()
    if not raw:
        return default_cache_root(workdir)
    expanded = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not expanded.is_absolute():
        expanded = workdir / expanded
    target = expanded.resolve()
    if target.exists() and not target.is_dir():
        raise ValueError("缓存目录不能是文件")
    return target


def validate_cache_clear_target(cache_root: Path, workdir: Path) -> Path:
    target = cache_root.resolve()
    forbidden: list[Path] = []
    if target.anchor:
        forbidden.append(Path(target.anchor).resolve())
    for base in (Path.home(), PROJECT_ROOT, workdir):
        try:
            forbidden.append(base.resolve())
        except OSError:
            continue
    for base in forbidden:
        if target == base or target in base.parents:
            raise ValueError("缓存目录过于宽泛，已拒绝清空")
    if target.exists() and not target.is_dir():
        raise ValueError("缓存目录不能是文件")
    return target


def clear_cache_directory(cache_root: Path, workdir: Path) -> int:
    target = validate_cache_clear_target(cache_root, workdir)
    target.mkdir(parents=True, exist_ok=True)
    removed = 0
    for child in target.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
        removed += 1
    return removed


def translation_memory_path(cache_root: Path) -> Path:
    return app_db_path(cache_root)


def legacy_translation_memory_jsonl_path(cache_root: Path) -> Path:
    return cache_root / "translation-memory.jsonl"


def translation_memory_import_marker(cache_root: Path) -> str:
    return f"import:{legacy_translation_memory_jsonl_path(cache_root).resolve()}"


def ensure_translation_memory_migrated(cache_root: Path) -> None:
    db_path = translation_memory_path(cache_root)
    legacy_path = legacy_translation_memory_jsonl_path(cache_root)
    with connect_app_db(db_path) as connection:
        marker = translation_memory_import_marker(cache_root)
        exists = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE key = ?",
            (marker,),
        ).fetchone()
        if exists:
            return
        rows = read_legacy_translation_memory_rows(legacy_path)
        if rows:
            now = utc_timestamp()
            connection.executemany(
                """
                INSERT INTO translation_memory(scope, source, target, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scope, source) DO UPDATE SET
                  target = excluded.target,
                  updated_at = excluded.updated_at
                """,
                [(row["scope"], row["source"], row["target"], now) for row in rows],
            )
        connection.execute(
            "INSERT OR REPLACE INTO schema_migrations(key, applied_at) VALUES (?, ?)",
            (marker, utc_timestamp()),
        )


def read_translation_memory_rows(cache_root: Path) -> list[dict[str, str]]:
    ensure_translation_memory_migrated(cache_root)
    path = translation_memory_path(cache_root)
    with connect_app_db(path) as connection:
        rows = connection.execute(
            """
            SELECT scope, source, target
            FROM translation_memory
            ORDER BY updated_at, rowid
            """
        ).fetchall()
    return [{"scope": row["scope"], "source": row["source"], "target": row["target"]} for row in rows]


def read_legacy_translation_memory_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and isinstance(row.get("scope"), str) and isinstance(row.get("source"), str) and isinstance(row.get("target"), str):
            rows.append({"scope": row["scope"], "source": row["source"], "target": row["target"]})
    return rows


def translation_memory_scope_from_config(value: Any) -> str:
    if not isinstance(value, dict):
        raise ValueError("翻译记忆 scope 配置必须是对象")
    namespace = argparse.Namespace(
        source_locale=str(value.get("source_locale", "en_us") or "en_us"),
        target_locale=str(value.get("target_locale", "zh_cn") or "zh_cn"),
        provider=str(value.get("provider", "glossary") or "glossary"),
        model=str(value.get("model", "") or ""),
        api_url=str(value.get("api_url", "") or ""),
        overwrite_existing=bool(value.get("overwrite_existing", False)),
        skip_translated=bool(value.get("skip_translated", False)),
        ignore_translation_memory=bool(value.get("ignore_translation_memory", False)),
        pack_format=str(value.get("pack_format", "") or ""),
        glossary=None,
    )
    return compute_translation_config_hash(namespace)


def translation_memory_stats(cache_root: Path, scope: str = "", limit: int = 5) -> dict[str, Any]:
    ensure_translation_memory_migrated(cache_root)
    path = translation_memory_path(cache_root)
    with connect_app_db(path) as connection:
        entries = int(connection.execute("SELECT COUNT(*) FROM translation_memory").fetchone()[0])
        scopes = int(connection.execute("SELECT COUNT(DISTINCT scope) FROM translation_memory").fetchone()[0])
        recent_rows = [
            {"scope": row["scope"], "source": row["source"], "target": row["target"]}
            for row in connection.execute(
                """
                SELECT scope, source, target
                FROM translation_memory
                ORDER BY updated_at DESC, rowid DESC
                LIMIT ?
                """,
                (max(0, limit),),
            ).fetchall()
        ] if limit > 0 else []
        scope_entries = 0
        scope_rows: list[dict[str, str]] = []
        if scope:
            scope_entries = int(
                connection.execute("SELECT COUNT(*) FROM translation_memory WHERE scope = ?", (scope,)).fetchone()[0]
            )
            query_limit = max(0, limit)
            scope_rows = [
                {"scope": row["scope"], "source": row["source"], "target": row["target"]}
                for row in connection.execute(
                    """
                    SELECT scope, source, target
                    FROM translation_memory
                    WHERE scope = ?
                    ORDER BY updated_at DESC, rowid DESC
                    LIMIT ?
                    """,
                    (scope, query_limit),
                ).fetchall()
            ] if limit > 0 else [
                {"scope": row["scope"], "source": row["source"], "target": row["target"]}
                for row in connection.execute(
                    """
                    SELECT scope, source, target
                    FROM translation_memory
                    WHERE scope = ?
                    ORDER BY updated_at DESC, rowid DESC
                    """,
                    (scope,),
                ).fetchall()
            ]
    return {
        "cache_dir": str(cache_root),
        "path": str(path),
        "exists": path.is_file(),
        "entries": entries,
        "scopes": scopes,
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "scope": scope,
        "scope_entries": scope_entries,
        "scope_rows": scope_rows,
        "recent_rows": recent_rows,
    }


def clear_translation_memory(cache_root: Path, scope: str = "") -> int:
    ensure_translation_memory_migrated(cache_root)
    path = translation_memory_path(cache_root)
    with connect_app_db(path) as connection:
        if scope:
            removed = int(connection.execute("SELECT COUNT(*) FROM translation_memory WHERE scope = ?", (scope,)).fetchone()[0])
            connection.execute("DELETE FROM translation_memory WHERE scope = ?", (scope,))
        else:
            removed = int(connection.execute("SELECT COUNT(*) FROM translation_memory").fetchone()[0])
            connection.execute("DELETE FROM translation_memory")
    return removed


def import_translation_memory(cache_root: Path, jsonl_path: Path) -> dict[str, Any]:
    """从 JSONL 文件导入翻译记忆，返回导入结果。"""
    ensure_translation_memory_migrated(cache_root)
    from .app_db import app_db_path, import_translation_memory_from_jsonl
    db = app_db_path(cache_root)
    count = import_translation_memory_from_jsonl(db, jsonl_path)
    return {"ok": True, "imported": count}


def compact_translation_memory(cache_root: Path) -> int:
    # SQLite 模式下 upsert 天然去重，无需 compact
    ensure_translation_memory_migrated(cache_root)
    return 0


def update_translation_memory_entry(cache_root: Path, scope: str, source: str, target: str) -> dict[str, Any]:
    ensure_translation_memory_migrated(cache_root)
    with connect_app_db(app_db_path(cache_root)) as connection:
        existing = connection.execute(
            "SELECT 1 FROM translation_memory WHERE scope = ? AND source = ?",
            (scope, source),
        ).fetchone()
        if not existing:
            raise ValueError("翻译记忆条目不存在")
        connection.execute(
            "UPDATE translation_memory SET target = ?, updated_at = ? WHERE scope = ? AND source = ?",
            (target, utc_timestamp(), scope, source),
        )
    return {"ok": True}


def delete_translation_memory_entry(cache_root: Path, scope: str, source: str) -> dict[str, Any]:
    ensure_translation_memory_migrated(cache_root)
    with connect_app_db(app_db_path(cache_root)) as connection:
        result = connection.execute(
            "DELETE FROM translation_memory WHERE scope = ? AND source = ?",
            (scope, source),
        )
        if result.rowcount == 0:
            raise ValueError("翻译记忆条目不存在")
    return {"ok": True}


def shared_cache_scope_dir(cache_root: Path, args: argparse.Namespace) -> Path:
    digest = compute_translation_config_hash(args)[:16]
    scope_dir = cache_root / digest
    scope_dir.mkdir(parents=True, exist_ok=True)
    return scope_dir


def shared_cache_key(jar_path: Path) -> str:
    name_hash = hashlib.sha1(jar_path.name.encode("utf-8")).hexdigest()[:10]
    return f"{jar_path.stem}-{name_hash}"
