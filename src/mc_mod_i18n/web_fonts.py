"""Font catalog / upload / delete services for the web UI.

Pure functions (no module-level state). Two scopes:
  - builtin: bundled fonts under ``<resource_root>/字体/`` (read-only)
  - user:    user-uploaded fonts under ``<workdir>/cache/fonts/``

The catalog is consumed by the frontend font-picker; binaries are served via
``GET /assets/fonts/<scope>/<urlencoded relative path>`` in :mod:`web`.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .web_state import default_cache_root


ALLOWED_EXTS: set[str] = {".ttf", ".otf", ".woff", ".woff2"}
MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB

# Magic-number -> (extension without dot, content type)
FONT_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\x00\x01\x00\x00": ("ttf", "font/ttf"),
    b"OTTO": ("otf", "font/otf"),
    b"wOFF": ("woff", "font/woff"),
    b"wOF2": ("woff2", "font/woff2"),
    b"true": ("ttf", "font/ttf"),  # legacy macOS TrueType
    b"typ1": ("ttf", "font/ttf"),
}

_EXT_CONTENT_TYPE: dict[str, str] = {
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

_EXT_TO_FORMAT: dict[str, str] = {
    ".ttf": "truetype",
    ".otf": "opentype",
    ".woff": "woff",
    ".woff2": "woff2",
}

_BUILTIN_DIRNAME = "字体"
_USER_DIRNAME = "fonts"


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def font_dirs(workdir: Path, resource_root: Path) -> dict[str, Path]:
    """Return the canonical font directories for both scopes.

    The user directory is created on demand so callers can rely on it
    existing after this call. The builtin directory is left untouched.
    """
    builtin = (Path(resource_root) / _BUILTIN_DIRNAME).resolve()
    user = (default_cache_root(Path(workdir)) / _USER_DIRNAME).resolve()
    try:
        user.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return {"builtin": builtin, "user": user}


# ---------------------------------------------------------------------------
# Slug / label helpers
# ---------------------------------------------------------------------------

_SLUG_KEEP_RE = re.compile(r"[^a-z0-9_-]+")
_SLUG_COLLAPSE_RE = re.compile(r"-{2,}")


def _slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"\s+", "-", text)
    text = _SLUG_KEEP_RE.sub("-", text)
    text = _SLUG_COLLAPSE_RE.sub("-", text).strip("-")
    return text or "font"


def _relative_id_parts(root: Path, path: Path) -> list[str]:
    """Return slug pieces from ``root`` to ``path`` (without extension)."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = Path(path.name)
    pieces: list[str] = []
    for piece in rel.parent.parts:
        slug = _slugify(piece)
        if slug:
            pieces.append(slug)
    pieces.append(_slugify(rel.stem))
    return pieces


def _label_from_path(path: Path) -> str:
    return path.stem


def _format_from_ext(ext: str) -> str:
    return _EXT_TO_FORMAT.get(ext.lower(), "truetype")


# ---------------------------------------------------------------------------
# Catalog scanning
# ---------------------------------------------------------------------------

def _iter_font_files(root: Path, *, recursive: bool) -> list[Path]:
    if not root.is_dir():
        return []
    iterator = root.rglob("*") if recursive else root.iterdir()
    results: list[Path] = []
    for entry in iterator:
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in ALLOWED_EXTS:
            continue
        results.append(entry)
    results.sort(key=lambda p: str(p).casefold())
    return results


def _encode_relative(root: Path, path: Path) -> str:
    """Return path relative to ``root`` using forward slashes (NOT URL-encoded)."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = Path(path.name)
    return rel.as_posix()


def _url_quote(value: str) -> str:
    # Use quote here so '/' is preserved as-is is NOT desired; we want each
    # segment encoded. quote with safe='' would do that, but we keep '/'
    # as a separator (it's already path-safe) and only encode unsafe chars.
    from urllib.parse import quote

    return quote(value, safe="/")


def _scope_entry(
    *,
    scope: str,
    root: Path,
    path: Path,
    uploaded_at: str | None = None,
) -> dict[str, object]:
    ext = path.suffix.lower()
    rel_posix = _encode_relative(root, path)
    slug_pieces = _relative_id_parts(root, path)
    font_id = f"{scope}-" + "-".join(slug_pieces)
    label = _label_from_path(path)
    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = 0
    entry: dict[str, object] = {
        "id": font_id,
        "label": label,
        "family": label,
        "url": f"/assets/fonts/{scope}/{_url_quote(rel_posix)}",
        "size_bytes": int(size_bytes),
        "format": _format_from_ext(ext),
        "scope": scope,
        "recommend_slot": "decorative",
        "relative_path": rel_posix,
    }
    if uploaded_at is not None:
        entry["uploaded_at"] = uploaded_at
    return entry


def _iso_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def list_font_catalog(workdir: Path, resource_root: Path) -> dict[str, object]:
    """Return the JSON-serialisable font catalog consumed by the frontend."""
    dirs = font_dirs(workdir, resource_root)
    builtin_root = dirs["builtin"]
    user_root = dirs["user"]

    builtin_entries: list[dict[str, object]] = []
    for path in _iter_font_files(builtin_root, recursive=True):
        builtin_entries.append(_scope_entry(scope="builtin", root=builtin_root, path=path))

    user_entries: list[dict[str, object]] = []
    for path in _iter_font_files(user_root, recursive=False):
        user_entries.append(
            _scope_entry(
                scope="user",
                root=user_root,
                path=path,
                uploaded_at=_iso_mtime(path),
            )
        )

    return {
        "default": {
            "sans": {
                "id": "default-sans",
                "label": "默认 Fira Sans",
                "family": "Fira Sans",
            },
            "mono": {
                "id": "default-mono",
                "label": "默认 Fira Code",
                "family": "Fira Code",
            },
        },
        "builtin": builtin_entries,
        "user": user_entries,
    }


# ---------------------------------------------------------------------------
# Path safety / resolution
# ---------------------------------------------------------------------------

def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def resolve_font_file(
    workdir: Path,
    resource_root: Path,
    scope: str,
    name: str,
) -> tuple[Path, str] | None:
    """Resolve ``<scope>/<name>`` to an on-disk font file.

    Returns ``(absolute_path, content_type)`` or ``None`` if the resource
    cannot be located safely.
    """
    if scope not in {"builtin", "user"}:
        return None
    if not name:
        return None
    # Reject absolute paths / drive letters / parent traversals
    if name.startswith(("/", "\\")):
        return None
    if re.match(r"^[A-Za-z]:[\\/]", name):
        return None
    parts = re.split(r"[\\/]+", name)
    if any(part in {"", "..", "."} for part in parts):
        return None

    dirs = font_dirs(workdir, resource_root)
    root = dirs[scope]
    candidate = (root / Path(*parts))
    if candidate.suffix.lower() not in ALLOWED_EXTS:
        return None
    if not candidate.is_file():
        return None
    if not _is_within(candidate, root):
        return None
    content_type = _EXT_CONTENT_TYPE.get(candidate.suffix.lower(), "application/octet-stream")
    return candidate.resolve(), content_type


# ---------------------------------------------------------------------------
# Upload pipeline
# ---------------------------------------------------------------------------

def sniff_font_format(data: bytes) -> tuple[str, str] | None:
    """Inspect the first 4 bytes of ``data`` and return ``(ext, content_type)``."""
    if not data or len(data) < 4:
        return None
    head = data[:4]
    return FONT_MAGIC.get(head)


_FILENAME_ILLEGAL_RE = re.compile(r"[\x00-\x1f<>:\"/\\|?*]")


def sanitize_font_filename(filename: str) -> str:
    """Strip path components, control characters, and traversal sequences.

    Keeps Chinese characters, letters, digits, and common punctuation.
    Truncates the stem so the final name is at most 80 characters.
    """
    if not filename:
        return "font"
    # Drop directories
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    base = _FILENAME_ILLEGAL_RE.sub("", base)
    base = base.replace("..", "").strip().strip(".")
    if not base:
        return "font"
    suffix = Path(base).suffix.lower()
    stem = Path(base).stem.strip() or "font"
    if len(stem) > 80 - len(suffix):
        stem = stem[: 80 - len(suffix)]
    return stem + suffix


def _unique_user_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    for index in range(1, 1000):
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("无法生成唯一字体文件名")


def upload_user_font(workdir: Path, filename: str, data: bytes) -> dict[str, object]:
    """Persist a user-uploaded font to ``<workdir>/cache/fonts/``."""
    if not isinstance(data, (bytes, bytearray)):
        return {"ok": False, "error": "字体内容无效"}
    if len(data) == 0:
        return {"ok": False, "error": "字体文件为空"}
    if len(data) > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        return {"ok": False, "error": f"字体文件过大，最大允许 {mb}MB"}

    safe_name = sanitize_font_filename(filename or "")
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTS:
        return {
            "ok": False,
            "error": f"仅支持 {', '.join(sorted(ALLOWED_EXTS))} 格式的字体",
        }

    sniff = sniff_font_format(bytes(data[:4]))
    if sniff is None:
        return {"ok": False, "error": "文件内容不是有效的字体（无法识别魔数）"}
    sniffed_ext, _ = sniff
    if "." + sniffed_ext != ext:
        return {
            "ok": False,
            "error": f"文件后缀（{ext}）与内容（.{sniffed_ext}）不匹配",
        }

    dirs = font_dirs(workdir, Path("."))
    user_root = dirs["user"]
    try:
        user_root.mkdir(parents=True, exist_ok=True)
        target = _unique_user_path(user_root, safe_name)
        target.write_bytes(bytes(data))
    except OSError as exc:
        return {"ok": False, "error": f"无法保存字体：{exc}"}

    entry = _scope_entry(
        scope="user",
        root=user_root,
        path=target,
        uploaded_at=_iso_mtime(target),
    )
    return {
        "ok": True,
        "id": entry["id"],
        "label": entry["label"],
        "family": entry["family"],
        "url": entry["url"],
        "size_bytes": entry["size_bytes"],
        "format": entry["format"],
        "uploaded_at": entry["uploaded_at"],
    }


def delete_user_font(workdir: Path, font_id: str) -> dict[str, object]:
    """Delete a user font by id. Builtin / default scopes are rejected."""
    if not font_id or not isinstance(font_id, str):
        return {"ok": False, "error": "缺少字体 id"}
    if not font_id.startswith("user-"):
        return {"ok": False, "error": "仅允许删除用户上传的字体"}

    dirs = font_dirs(workdir, Path("."))
    user_root = dirs["user"]
    if not user_root.is_dir():
        return {"ok": False, "error": "未找到字体"}

    for path in _iter_font_files(user_root, recursive=False):
        entry_id = "user-" + "-".join(_relative_id_parts(user_root, path))
        if entry_id == font_id:
            if not _is_within(path, user_root):
                return {"ok": False, "error": "非法路径"}
            try:
                path.unlink()
            except OSError as exc:
                return {"ok": False, "error": f"删除失败：{exc}"}
            return {"ok": True, "id": font_id}
    return {"ok": False, "error": "未找到字体"}
