from __future__ import annotations

from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def index_html_template() -> str:
    return files(__package__).joinpath("templates/index.html").read_text(encoding="utf-8")


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
