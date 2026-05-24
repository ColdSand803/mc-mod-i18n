from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def index_html_template() -> str:
    return files(__package__).joinpath("templates/index.html").read_text(encoding="utf-8")


_STATIC_NAME_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")


@lru_cache(maxsize=64)
def read_static_asset(subdir: str, filename: str) -> bytes | None:
    """Read a bundled static asset under templates/{subdir}/{filename}.

    Returns None when the asset does not exist or the path is unsafe.
    """
    if subdir not in {"css", "js"}:
        return None
    if not filename or not _STATIC_NAME_RE.match(filename) or ".." in filename.split("/"):
        return None
    resource = files(__package__).joinpath(f"templates/{subdir}/{filename}")
    try:
        if not resource.is_file():
            return None
        return resource.read_bytes()
    except (FileNotFoundError, OSError):
        return None


def render_index_html(
    *,
    minecraft_locales_json: str,
    ui_locale_options_html: str,
    source_locale_options_html: str,
    target_locale_options_html: str,
) -> str:
    return (
        index_html_template()
        .replace("__MINECRAFT_LOCALES_JSON__", minecraft_locales_json)
        .replace("__UI_LOCALE_OPTIONS_HTML__", ui_locale_options_html)
        .replace("__SOURCE_LOCALE_OPTIONS_HTML__", source_locale_options_html)
        .replace("__TARGET_LOCALE_OPTIONS_HTML__", target_locale_options_html)
    )
