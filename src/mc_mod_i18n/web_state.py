from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .core import compute_translation_config_hash
from .translator import GlossaryTranslator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIRNAME = "cache"
DEFAULT_UI_LOCALE_DIR = Path("extensions") / "ui-locales"


def default_cache_root(workdir: Path) -> Path:
    return (workdir / DEFAULT_CACHE_DIRNAME).resolve()


def default_ui_locale_root(workdir: Path) -> Path:
    return (workdir / DEFAULT_UI_LOCALE_DIR).resolve()

def user_glossary_path(workdir: Path) -> Path:
    return workdir / "glossaries" / "user-glossary.json"


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
    path = user_glossary_path(workdir)
    if not path.is_file():
        return {}
    return normalize_glossary_terms(json.loads(path.read_text(encoding="utf-8-sig")))


def write_user_glossary(workdir: Path, terms: dict[str, str]) -> Path:
    path = user_glossary_path(workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize_glossary_terms(terms), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


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
    return path if path.is_file() and read_user_glossary(workdir) else None


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
    path = preset_path(workdir, name)
    if not path.is_file():
        raise ValueError("预设不存在")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return {
        "schema": int(payload.get("schema", PRESET_SCHEMA_VERSION) or PRESET_SCHEMA_VERSION),
        "name": normalize_preset_name(str(payload.get("name", name))),
        "config": normalize_preset_config(payload.get("config", {})),
    }


def list_config_presets(workdir: Path) -> list[dict[str, Any]]:
    root = presets_dir(workdir)
    if not root.is_dir():
        return []
    presets: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            preset = json.loads(path.read_text(encoding="utf-8-sig"))
            presets.append(
                {
                    "name": normalize_preset_name(str(preset.get("name", path.stem))),
                    "config": normalize_preset_config(preset.get("config", {})),
                }
            )
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return sorted(presets, key=lambda item: item["name"].lower())


def write_config_preset(workdir: Path, name: str, config: Any) -> dict[str, Any]:
    normalized_name = normalize_preset_name(name)
    preset = {
        "schema": PRESET_SCHEMA_VERSION,
        "name": normalized_name,
        "config": normalize_preset_config(config),
    }
    root = presets_dir(workdir)
    root.mkdir(parents=True, exist_ok=True)
    preset_path(workdir, normalized_name).write_text(json.dumps(preset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return preset


def delete_config_preset(workdir: Path, name: str) -> None:
    path = preset_path(workdir, name)
    if not path.is_file():
        raise ValueError("预设不存在")
    path.unlink()

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
    return cache_root / "translation-memory.jsonl"


def read_translation_memory_rows(cache_root: Path) -> list[dict[str, str]]:
    path = translation_memory_path(cache_root)
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
    path = translation_memory_path(cache_root)
    rows = read_translation_memory_rows(cache_root)
    scopes = {row["scope"] for row in rows}
    recent_rows = list(reversed(rows[-max(0, limit):])) if limit > 0 else []
    scope_rows_all = [row for row in rows if row["scope"] == scope] if scope else []
    scope_rows = list(reversed(scope_rows_all[-max(0, limit):])) if limit > 0 else list(reversed(scope_rows_all))
    return {
        "cache_dir": str(cache_root),
        "path": str(path),
        "exists": path.is_file(),
        "entries": len(rows),
        "scopes": len(scopes),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "scope": scope,
        "scope_entries": len(scope_rows_all),
        "scope_rows": scope_rows,
        "recent_rows": recent_rows,
    }


def clear_translation_memory(cache_root: Path, scope: str = "") -> int:
    path = translation_memory_path(cache_root)
    rows = read_translation_memory_rows(cache_root)
    if not scope:
        if path.is_file():
            path.unlink()
        return len(rows)
    kept = [row for row in rows if row["scope"] != scope]
    removed = len(rows) - len(kept)
    if kept:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in kept) + "\n", encoding="utf-8")
    elif path.is_file():
        path.unlink()
    return max(0, removed)


def compact_translation_memory(cache_root: Path) -> int:
    path = translation_memory_path(cache_root)
    rows = read_translation_memory_rows(cache_root)
    latest: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        latest[(row["scope"], row["source"])] = row
    compacted = list(latest.values())
    removed = max(0, len(rows) - len(compacted))
    if compacted:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in compacted) + "\n", encoding="utf-8")
    elif path.is_file():
        path.unlink()
    return removed


def shared_cache_scope_dir(cache_root: Path, args: argparse.Namespace) -> Path:
    digest = compute_translation_config_hash(args)[:16]
    scope_dir = cache_root / digest
    scope_dir.mkdir(parents=True, exist_ok=True)
    return scope_dir


def shared_cache_key(jar_path: Path) -> str:
    name_hash = hashlib.sha1(jar_path.name.encode("utf-8")).hexdigest()[:10]
    return f"{jar_path.stem}-{name_hash}"
