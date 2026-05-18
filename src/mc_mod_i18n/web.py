from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
import argparse
import html
import json
import mimetypes
from pathlib import Path
import re
from secrets import token_hex
import sys
import tempfile
from threading import Event, Lock, Thread
import time
from typing import Any
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse
import urllib.request
from zipfile import BadZipFile, ZipFile

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import compute_translation_config_hash, compute_zip_source_hash, create_translator, process_jar, report_has_uncacheable_failures, translate_batch_with_failures
from .ftbquests import (
    FTBQuestsResult,
    compute_ftbquests_config_hash,
    compute_ftbquests_source_hash,
    detect_legacy_snbt_files,
    find_lang_file_pairs,
    ftbquests_cache_key,
    infer_source_locale_from_files,
    load_ftbquests_checkpoint,
    load_ftbquests_checkpoint_config_hash,
    load_ftbquests_checkpoint_source_hash,
    load_ftbquests_source,
    process_ftbquests_source,
    save_ftbquests_checkpoint,
    write_ftbquests_html_report,
    write_ftbquests_json_report,
    write_ftbquests_outputs,
)
from .hardcoded import scan_jar_for_hardcoded
from .help_docs import (
    HELP_DOCS_DIRNAME,
    HELP_DOCS_INDEX_FILENAME,
    help_docs_dir,
    localized_help_docs_dir,
    list_help_docs,
    normalize_help_doc_slug,
    read_help_doc,
    render_help_doc_html,
    write_ui_locale_help_docs,
)
from .job_history import (
    DEFAULT_JOB_HISTORY_LIMIT,
    MAX_JOB_HISTORY_LIMIT,
    append_job_history,
    build_job_history_record,
    clear_job_history,
    delete_job_history_records,
    history_download_files,
    history_download_relative_path,
    history_download_status,
    history_downloads,
    history_primary_input_from_download,
    infer_history_primary_input,
    job_history_settings_path,
    normalize_history_input_files,
    normalize_job_history_limit,
    read_job_history,
    read_job_history_settings,
    sanitize_history_value,
    trim_job_history,
    write_job_history_settings,
)
from .job_utils import hardcoded_entry_to_dict, read_jsonl
from .json_processing import (
    json_output_metadata_preview,
    json_target_filename,
    parse_json_translation_payload,
    process_json_language_file,
    ui_locale_name_pair,
)
from .lang import collect_lang_documents, target_path_for
from .pack import OutputLangDocument, load_checkpoint, load_checkpoint_config_hash, load_checkpoint_source_hash, read_pack_icon, resolve_pack_format, resource_pack_filename, save_checkpoint, update_resource_pack_entries, write_resource_pack
from . import preflight as _preflight
from .preflight import preflight_ftbquests_paths, preflight_jar_paths, preflight_summary
from .report import (
    ReportEntry,
    build_hardcoded_map_template,
    write_hardcoded_map_template,
    write_hardcoded_report,
    write_report,
)
from .report_exports import (
    report_entry_dicts,
    report_failure_dicts,
    write_report_exports,
)
from .retry_outputs import (
    apply_ftbquests_retry_updates_to_text,
    apply_json_retry_updates,
    entry_id,
    ftbquests_result_from_retry_payload,
    merge_retry_result,
    refresh_retry_report_exports,
    retry_updates_for_ftbquests_path,
    successful_retry_entries,
    successful_retry_result_entries,
    successful_retry_updates,
    update_ftbquests_retry_file,
    update_ftbquests_retry_outputs,
    update_ftbquests_retry_zip,
    update_json_retry_file,
    update_json_retry_outputs,
    update_json_retry_zip,
)
from .translator import GlossaryTranslator, TranslationItem, get_provider_preset, is_ai_provider
from .ui_i18n import (
    BUILTIN_UI_LOCALES,
    FALLBACK_UI_LOCALE,
    MINECRAFT_LOCALES,
    build_ui_locale_filled_package,
    build_ui_locale_missing_template,
    check_ui_locale_package,
    export_ui_locale_package,
    list_ui_locales,
    minecraft_locale_display_names,
    parse_ui_locale_package,
    resolve_ui_locale,
    resolve_ui_locale_root,
    translate_ui,
    write_extension_package,
)
from .validator import validate_translation
from . import provider_checks as _provider_checks
from .web_assets import render_index_html
from . import web_branding as _web_branding
from .web_branding import (
    BRANDING_CONFIG_FILENAME,
    BRAND_LOGO_BY_ID,
    BRAND_LOGO_OPTIONS,
    DEFAULT_BRAND_LOGO,
    SYSTEM_SETTINGS_DIRNAME,
    SYSTEM_SETTINGS_FILENAME,
    brand_logo_options_payload,
    normalize_brand_logo_choice,
)
from .web_state import (
    DEFAULT_CACHE_DIRNAME,
    DEFAULT_UI_LOCALE_DIR,
    PRESET_ALLOWED_KEYS,
    PRESET_SCHEMA_VERSION,
    clear_cache_directory,
    clear_translation_memory,
    compact_translation_memory,
    default_cache_root,
    default_ui_locale_root,
    delete_config_preset,
    glossary_conflicts,
    list_config_presets,
    normalize_glossary_terms,
    normalize_preset_config,
    normalize_preset_name,
    preset_path,
    preset_slug,
    presets_dir,
    read_config_preset,
    read_translation_memory_rows,
    read_user_glossary,
    resolve_cache_root,
    shared_cache_key,
    shared_cache_scope_dir,
    translation_memory_path,
    translation_memory_scope_from_config,
    translation_memory_stats,
    user_glossary_path,
    validate_cache_clear_target,
    write_config_preset,
    write_user_glossary,
)
from .web_uploads import MultipartPart, collect_fields, glossary_upload_or_saved, parse_header_params, parse_multipart, parse_part_headers
from .web_utils import (
    safe_run_path,
    sanitize_filename,
    sanitize_job_id,
    sanitize_relative_upload_path,
    unique_filename,
    utc_timestamp,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MINECRAFT_LOCALES_JSON = json.dumps(MINECRAFT_LOCALES, ensure_ascii=False)

normalize_models_url = _provider_checks.normalize_models_url
fetch_provider_models = _provider_checks.fetch_provider_models
deep_free_smoke_test = _provider_checks.deep_free_smoke_test
argos_smoke_test = _provider_checks.argos_smoke_test
libretranslate_smoke_test = _provider_checks.libretranslate_smoke_test
azure_translator_smoke_test = _provider_checks.azure_translator_smoke_test
provider_test_error = _provider_checks.provider_test_error
elapsed_ms = _provider_checks.elapsed_ms
redact_secret = _provider_checks.redact_secret
provider_http_error_type = _provider_checks.provider_http_error_type
provider_http_error_message = _provider_checks.provider_http_error_message
provider_runtime_error_type = _provider_checks.provider_runtime_error_type
provider_test_help_slug = _provider_checks.provider_test_help_slug
parse_models_response = _provider_checks.parse_models_response


def _locale_options_html(selected_locale: str) -> str:
    rows: list[str] = []
    for value, label in MINECRAFT_LOCALES:
        selected = " selected" if value == selected_locale else ""
        option_text = f"{value} - {label}"
        rows.append(f'<option value="{html.escape(value)}"{selected}>{html.escape(option_text)}</option>')
    return "\n".join(f"              {row}" for row in rows)


def _ui_locale_options_html(selected_locale: str) -> str:
    rows: list[str] = []
    for value, entry in BUILTIN_UI_LOCALES.items():
        selected = " selected" if value == selected_locale else ""
        label = str(entry.get("name") or value)
        rows.append(f'<option value="{html.escape(value)}"{selected}>{html.escape(label)}</option>')
    return "\n".join(f"              {row}" for row in rows)

def bundled_resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", "")
    return Path(meipass) if meipass else PROJECT_ROOT


def logo_root(root: Path | None = None) -> Path:
    return _web_branding.logo_root(root or bundled_resource_root())


def brand_logo_asset_path(choice: Any, kind: str = "png", root: Path | None = None) -> Path:
    return _web_branding.brand_logo_asset_path(choice, kind, root or bundled_resource_root())


def sidebar_logo_path() -> Path:
    return _web_branding.sidebar_logo_path(bundled_resource_root())


def cat_ico_path() -> Path:
    return _web_branding.cat_ico_path(bundled_resource_root())


def system_settings_payload(workdir: Path, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    return _web_branding.system_settings_payload(
        workdir,
        settings=settings or read_system_settings(workdir),
        default_cache_dir=default_cache_root(workdir),
        default_ui_locale_dir=default_ui_locale_root(workdir),
    )


def system_settings_path(workdir: Path) -> Path:
    return _web_branding.system_settings_path(workdir)


def branding_config_path(root: Path | None = None) -> Path:
    return _web_branding.branding_config_path(root or bundled_resource_root())


def read_branding_build_config(root: Path | None = None) -> dict[str, str]:
    return _web_branding.read_branding_build_config(root or bundled_resource_root())


def write_branding_build_config(brand_logo: Any, root: Path | None = None) -> None:
    if getattr(sys, "_MEIPASS", ""):
        return
    _web_branding.write_branding_build_config(brand_logo, root or PROJECT_ROOT)


def should_sync_branding_build_config(workdir: Path, sync_build_config: bool = False) -> bool:
    return _web_branding.should_sync_branding_build_config(
        workdir,
        project_root=PROJECT_ROOT,
        frozen=bool(getattr(sys, "_MEIPASS", "")),
        sync_build_config=sync_build_config,
    )


def read_system_settings(workdir: Path) -> dict[str, Any]:
    return _web_branding.read_system_settings(workdir)


def write_system_settings(workdir: Path, *, brand_logo: Any, sync_build_config: bool = False) -> dict[str, Any]:
    payload = _web_branding.write_system_settings(workdir, brand_logo=brand_logo)
    if should_sync_branding_build_config(workdir, sync_build_config=sync_build_config):
        write_branding_build_config(payload["brand_logo"])
    return payload


def co1dsand_pack_logo_paths(
    root: Path | None = None,
    *,
    brand_logo: Any = DEFAULT_BRAND_LOGO,
) -> tuple[Path, ...]:
    cwd = Path.cwd() if root is None else None
    return _web_branding.co1dsand_pack_logo_paths(root or bundled_resource_root(), cwd, brand_logo=brand_logo)


INDEX_HTML = render_index_html(
    minecraft_locales_json=MINECRAFT_LOCALES_JSON,
    ui_locale_options_html=_ui_locale_options_html("zh_cn"),
    source_locale_options_html=_locale_options_html("en_us"),
    target_locale_options_html=_locale_options_html("zh_cn"),
)


def serve(host: str, port: int, workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    handler = make_handler(workdir.resolve())
    server = ThreadingHTTPServer((host, port), handler)
    print(f"mc-mod-i18n UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


def make_handler(workdir: Path, *, sync_branding_build_config: bool = False):
    jobs: dict[str, dict[str, Any]] = {}
    cancel_events: dict[str, Event] = {}
    jobs_lock = Lock()
    history_lock = Lock()

    def update_job(job_id: str, **values: Any) -> None:
        snapshot: dict[str, Any] | None = None
        with jobs_lock:
            job = jobs.setdefault(job_id, {})
            job.update(values)
            if job.get("status") in {"done", "error", "cancelled"}:
                snapshot = dict(job)
        if snapshot is not None:
            with history_lock:
                history_limit = read_job_history_settings(workdir).get("limit", DEFAULT_JOB_HISTORY_LIMIT)
                append_job_history(workdir, build_job_history_record(job_id, snapshot), limit=history_limit)

    def get_job(job_id: str) -> dict[str, Any] | None:
        with jobs_lock:
            job = jobs.get(job_id)
            return dict(job) if job is not None else None

    class WebHandler(BaseHTTPRequestHandler):
        server_version = "mc-mod-i18n/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            print("%s - %s" % (self.address_string(), format % args))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_bytes(INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/system-settings":
                self._send_json({"ok": True, **system_settings_payload(workdir)})
                return
            if parsed.path == "/assets/logo/current":
                self._send_brand_logo_asset("png")
                return
            if parsed.path == "/assets/logo/current-favicon":
                self._send_brand_favicon_asset()
                return
            if parsed.path in {"/assets/logo/current.ico", "/favicon.ico"}:
                self._send_brand_logo_asset("ico")
                return
            if parsed.path.startswith("/assets/logo/"):
                if self._send_named_logo_asset(parsed.path.removeprefix("/assets/logo/")):
                    return
            if parsed.path == "/assets/logo/minecraft.svg":
                logo_path = sidebar_logo_path()
                if not logo_path.is_file():
                    self.send_error(404)
                    return
                self._send_bytes(logo_path.read_bytes(), "image/svg+xml; charset=utf-8")
                return
            if parsed.path in {"/assets/co1dsand_logo_cat.ico", "/assets/logo/co1dsand_logo_cat.ico"}:
                icon_path = cat_ico_path()
                if not icon_path.is_file():
                    self.send_error(404)
                    return
                self._send_bytes(icon_path.read_bytes(), "image/x-icon")
                return
            if parsed.path.startswith("/api/progress/"):
                self._send_progress(parsed.path.removeprefix("/api/progress/"))
                return
            if parsed.path == "/api/jobs":
                self._send_json({"ok": True, "jobs": read_job_history(workdir)})
                return
            if parsed.path == "/api/jobs/settings":
                settings = read_job_history_settings(workdir)
                history_rows = read_job_history(workdir, limit=0)
                self._send_json({
                    "ok": True,
                    "limit": settings.get("limit", DEFAULT_JOB_HISTORY_LIMIT),
                    "count": len(history_rows),
                })
                return
            if parsed.path == "/api/docs":
                try:
                    values = parse_qs(parsed.query or "")
                    ui_locale = resolve_ui_locale(values.get("ui_locale", [""])[0])
                    ui_locale_root = self._ui_locale_root_from_query(parsed.query)
                    self._send_json({"ok": True, "docs": list_help_docs(bundled_resource_root(), ui_locale, ui_locale_root)})
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path.startswith("/api/docs/"):
                try:
                    slug = unquote(parsed.path.removeprefix("/api/docs/"))
                    values = parse_qs(parsed.query or "")
                    ui_locale = resolve_ui_locale(values.get("ui_locale", [""])[0])
                    ui_locale_root = self._ui_locale_root_from_query(parsed.query)
                    self._send_json({"ok": True, **read_help_doc(bundled_resource_root(), slug, ui_locale, ui_locale_root)})
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=404)
                return
            if parsed.path == "/api/glossary":
                try:
                    terms = read_user_glossary(workdir)
                    self._send_json(
                        {
                            "ok": True,
                            "terms": terms,
                            "count": len(terms),
                            "conflicts": glossary_conflicts(terms),
                            "path": str(user_glossary_path(workdir)),
                        }
                    )
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/presets":
                try:
                    self._send_json({"ok": True, "presets": list_config_presets(workdir)})
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path.startswith("/api/presets/"):
                try:
                    name = unquote(parsed.path.removeprefix("/api/presets/"))
                    self._send_json({"ok": True, "preset": read_config_preset(workdir, name)})
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=404)
                return
            if parsed.path == "/api/translation-memory":
                try:
                    payload = self._handle_translation_memory(parsed.query)
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/translation-memory/export":
                try:
                    self._send_translation_memory_export(parsed.query)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/ui-locales":
                try:
                    payload = self._handle_ui_locales(parsed.query)
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path.startswith("/api/ui-locales/export/"):
                try:
                    self._send_ui_locale_export(parsed.path.removeprefix("/api/ui-locales/export/"), parsed.query)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path.startswith("/api/ui-locales/missing-template/"):
                try:
                    self._send_ui_locale_missing_template(parsed.path.removeprefix("/api/ui-locales/missing-template/"), parsed.query)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path.startswith("/api/ui-locales/fill/"):
                try:
                    self._send_ui_locale_filled(parsed.path.removeprefix("/api/ui-locales/fill/"), parsed.query)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path.startswith("/download/"):
                self._serve_run_file(parsed.path.removeprefix("/download/"), download=True)
                return
            if parsed.path.startswith("/report/"):
                self._serve_run_file(parsed.path.removeprefix("/report/"), download=False)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/system-settings":
                try:
                    payload = self._handle_system_settings_save()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/models":
                try:
                    payload = self._handle_models()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/test-provider":
                try:
                    payload = self._handle_test_provider()
                    self._send_json(payload, status=200 if payload.get("ok") else 400)
                except Exception as exc:
                    self._send_json({"ok": False, "error_type": "bad_request", "message": str(exc)}, status=400)
                return
            if parsed.path == "/api/preflight":
                try:
                    payload = self._handle_preflight()
                    self._send_json(payload, status=200 if payload.get("ok") else 400)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/cache/clear":
                try:
                    payload = self._handle_clear_cache()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/jobs/settings":
                try:
                    payload = self._handle_job_history_settings()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/jobs/manage":
                try:
                    payload = self._handle_job_history_manage()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/translation-memory":
                try:
                    payload = self._handle_translation_memory_mutation()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/ui-locales/import":
                try:
                    payload = self._handle_ui_locale_import()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/ui-locales/check":
                try:
                    payload = self._handle_ui_locale_check()
                    self._send_json(payload, status=200 if payload.get("ok") else 400)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/glossary":
                try:
                    payload = self._handle_glossary_save()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/presets":
                try:
                    payload = self._handle_preset_save()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/translate":
                try:
                    payload = self._handle_translate()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path.startswith("/api/retry/"):
                try:
                    payload = self._handle_retry(parsed.path.removeprefix("/api/retry/"))
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/translate-hardcoded":
                try:
                    payload = self._handle_translate_hardcoded()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path.startswith("/api/cancel/"):
                cid = sanitize_job_id(parsed.path.removeprefix("/api/cancel/"))
                evt = cancel_events.get(cid)
                if evt:
                    evt.set()
                    update_job(cid, stage="cancelled")
                    self._send_json({"ok": True})
                else:
                    self._send_json({"ok": False, "error": "job not found"}, status=404)
                return
            if parsed.path != "/api/translate":
                self.send_error(404)
                return

        def do_DELETE(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/presets/"):
                try:
                    name = unquote(parsed.path.removeprefix("/api/presets/"))
                    delete_config_preset(workdir, name)
                    self._send_json({"ok": True, "presets": list_config_presets(workdir)})
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            self.send_error(404)

        def _send_progress(self, job_id: str) -> None:
            job = get_job(sanitize_job_id(job_id))
            if not job:
                self._send_json({"ok": False, "error": "job not found"}, status=404)
                return
            self._send_json({"ok": True, **job})

        def _handle_models(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            provider = str(payload.get("provider", "openai-compatible") or "openai-compatible")
            if not is_ai_provider(provider):
                raise ValueError("当前翻译器不支持模型列表")
            preset = get_provider_preset(provider)
            api_key_env = str(payload.get("api_key_env", preset.api_key_env) or preset.api_key_env)
            models = fetch_provider_models(
                provider=provider,
                base_url=str(payload.get("base_url") or payload.get("api_url") or preset.api_url),
                api_key=str(payload.get("api_key", "")).strip(),
                api_key_env=api_key_env,
                timeout=max(1.0, min(60.0, float(payload.get("api_timeout", "10") or "10"))),
            )
            return {"ok": True, "models": models}

        def _handle_system_settings_save(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            settings = write_system_settings(
                workdir,
                brand_logo=payload.get("brand_logo"),
                sync_build_config=sync_branding_build_config,
            )
            return {"ok": True, **system_settings_payload(workdir, settings)}

        def _send_brand_logo_asset(self, kind: str) -> None:
            settings = read_system_settings(workdir)
            choice = settings.get("brand_logo", DEFAULT_BRAND_LOGO)
            candidates: list[Path] = []
            if kind == "ico":
                candidates.append(brand_logo_asset_path(choice, "ico"))
                if choice != DEFAULT_BRAND_LOGO:
                    candidates.append(brand_logo_asset_path(DEFAULT_BRAND_LOGO, "ico"))
                content_type = "image/x-icon"
            else:
                candidates.append(brand_logo_asset_path(choice, "png"))
                if choice != DEFAULT_BRAND_LOGO:
                    candidates.append(brand_logo_asset_path(DEFAULT_BRAND_LOGO, "png"))
                content_type = "image/png"
            for path in candidates:
                if path.is_file():
                    self._send_bytes(path.read_bytes(), content_type)
                    return
            self.send_error(404)

        def _send_brand_favicon_asset(self) -> None:
            settings = read_system_settings(workdir)
            choice = normalize_brand_logo_choice(settings.get("brand_logo", DEFAULT_BRAND_LOGO))
            candidates: list[tuple[Path, str]] = []
            if choice == "grass":
                candidates.append((brand_logo_asset_path("grass", "svg"), "image/svg+xml; charset=utf-8"))
            candidates.append((brand_logo_asset_path(choice, "ico"), "image/x-icon"))
            if choice != DEFAULT_BRAND_LOGO:
                candidates.append((brand_logo_asset_path(DEFAULT_BRAND_LOGO, "ico"), "image/x-icon"))
            for path, content_type in candidates:
                if path.is_file():
                    self._send_bytes(path.read_bytes(), content_type)
                    return
            self.send_error(404)

        def _send_named_logo_asset(self, name: str) -> bool:
            aliases = {
                "cat.png": brand_logo_asset_path("cat", "png"),
                "grass.png": brand_logo_asset_path("grass", "png"),
                "sign.png": brand_logo_asset_path("sign", "png"),
                "minecraft.png": brand_logo_asset_path("grass", "png"),
                "minecraft.svg": brand_logo_asset_path("grass", "svg"),
                "co1dsand_logo_cat.png": brand_logo_asset_path("cat", "png"),
                "co1dsand_logo_sign.png": brand_logo_asset_path("sign", "png"),
                "co1dsand_logo_cat.ico": brand_logo_asset_path("cat", "ico"),
                "co1dsand_logo_sign.ico": brand_logo_asset_path("sign", "ico"),
                "minecraft.ico": brand_logo_asset_path("grass", "ico"),
            }
            path = aliases.get(name)
            if path is None:
                return False
            if not path.is_file():
                self.send_error(404)
                return True
            suffix = path.suffix.lower()
            content_type = {
                ".svg": "image/svg+xml; charset=utf-8",
                ".ico": "image/x-icon",
                ".png": "image/png",
            }.get(suffix, "application/octet-stream")
            self._send_bytes(path.read_bytes(), content_type)
            return True

        def _handle_preflight(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            parts = parse_multipart(self.headers.get("Content-Type", ""), body)
            fields = collect_fields(parts)
            input_kind = fields.get("input_kind", "jar") or "jar"
            source_locale = fields.get("source_locale", "en_us") or "en_us"
            target_locale = fields.get("target_locale", "zh_cn") or "zh_cn"
            with tempfile.TemporaryDirectory(prefix="preflight-", dir=workdir) as temp_dir:
                temp_root = Path(temp_dir)
                paths = save_preflight_uploads(input_kind, parts, temp_root, source_locale)
                return preflight_inputs(input_kind, paths, source_locale, target_locale)

        def _handle_test_provider(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            provider = str(payload.get("provider", "openai-compatible") or "openai-compatible")
            if not is_ai_provider(provider):
                return {
                    "ok": False,
                    "provider": provider,
                    "error_type": "unsupported_provider",
                    "message": "当前翻译器不需要 API 连接测试",
                }
            preset = get_provider_preset(provider)
            return test_provider_connection(
                provider=provider,
                api_url=str(payload.get("base_url") or payload.get("api_url") or preset.api_url),
                api_key=str(payload.get("api_key", "")).strip(),
                api_key_env=str(payload.get("api_key_env", preset.api_key_env) or preset.api_key_env),
                model=str(payload.get("model", preset.model) or preset.model),
                timeout=max(1.0, min(60.0, float(payload.get("api_timeout", "10") or "10"))),
                api_region=str(payload.get("api_region", "") or ""),
            )

        def _handle_clear_cache(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            cache_root = resolve_cache_root(workdir, str(payload.get("cache_dir", "") or ""))
            removed = clear_cache_directory(cache_root, workdir)
            return {"ok": True, "cache_dir": str(cache_root), "removed": removed}

        def _handle_job_history_settings(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            with history_lock:
                settings = write_job_history_settings(workdir, limit=payload.get("limit", DEFAULT_JOB_HISTORY_LIMIT))
                trimmed = trim_job_history(workdir, limit=settings["limit"])
                history_rows = read_job_history(workdir, limit=0)
            return {
                "ok": True,
                "limit": settings["limit"],
                "count": len(history_rows),
                "trimmed": trimmed,
            }

        def _handle_job_history_manage(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            action = str(payload.get("action", "") or "").strip()
            with history_lock:
                if action == "trim":
                    result = trim_job_history(workdir, limit=payload.get("limit"))
                elif action == "clear":
                    result = clear_job_history(workdir)
                elif action == "delete":
                    job_ids = payload.get("job_ids")
                    if not isinstance(job_ids, list):
                        raise ValueError("删除任务需要提供 job_ids 列表")
                    result = delete_job_history_records(workdir, [str(item or "") for item in job_ids])
                else:
                    raise ValueError("未知任务历史操作")
                history_rows = read_job_history(workdir, limit=0)
            result["limit"] = read_job_history_settings(workdir).get("limit", DEFAULT_JOB_HISTORY_LIMIT)
            result["count"] = len(history_rows)
            return result

        def _cache_root_from_query(self, query: str) -> Path:
            values = parse_qs(query or "")
            return resolve_cache_root(workdir, values.get("cache_dir", [""])[0])

        def _handle_translation_memory(self, query: str) -> dict[str, Any]:
            cache_root = self._cache_root_from_query(query)
            values = parse_qs(query or "")
            scope_config = values.get("scope_config", [""])[0]
            scope = translation_memory_scope_from_config(json.loads(scope_config)) if scope_config else ""
            return {"ok": True, **translation_memory_stats(cache_root, scope=scope)}

        def _send_translation_memory_export(self, query: str) -> None:
            cache_root = self._cache_root_from_query(query)
            path = translation_memory_path(cache_root)
            data = path.read_bytes() if path.is_file() else b""
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", 'attachment; filename="translation-memory.jsonl"')
            self.end_headers()
            self.wfile.write(data)

        def _handle_translation_memory_mutation(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            cache_root = resolve_cache_root(workdir, str(payload.get("cache_dir", "") or ""))
            action = str(payload.get("action", "") or "")
            scope_payload = payload.get("scope_config")
            scope = translation_memory_scope_from_config(scope_payload) if scope_payload else ""
            if action == "clear":
                removed = clear_translation_memory(cache_root, scope=scope)
            elif action == "compact":
                removed = compact_translation_memory(cache_root)
            else:
                raise ValueError("未知翻译记忆操作")
            return {"ok": True, "removed": removed, **translation_memory_stats(cache_root, scope=scope)}

        def _ui_locale_root_from_query(self, query: str) -> Path:
            values = parse_qs(query or "")
            raw_dir = values.get("ui_locale_dir", [""])[0]
            return resolve_ui_locale_root(workdir, raw_dir)

        def _handle_ui_locales(self, query: str) -> dict[str, Any]:
            root = self._ui_locale_root_from_query(query)
            locales = [
                {
                    "code": option.code,
                    "name": option.name,
                    "native_name": option.native_name,
                    "builtin": option.builtin,
                    "complete": option.complete,
                    "message_count": option.message_count,
                    "missing_count": option.missing_count,
                }
                for option in list_ui_locales(root)
            ]
            return {"ok": True, "ui_locale_dir": str(root), "locales": locales}

        def _send_ui_locale_export(self, locale: str, query: str) -> None:
            root = self._ui_locale_root_from_query(query)
            normalized = resolve_ui_locale(unquote(locale))
            package = export_ui_locale_package(
                normalized,
                root,
                minecraft_locale_display_names(),
                help_docs_dir(bundled_resource_root()),
            )
            data = json.dumps(package, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            filename = f"mc-mod-i18n-ui-{package['locale']}.json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def _send_ui_locale_missing_template(self, locale: str, query: str) -> None:
            root = self._ui_locale_root_from_query(query)
            normalized = resolve_ui_locale(unquote(locale))
            package = export_ui_locale_package(
                normalized,
                root,
                minecraft_locale_display_names(),
                help_docs_dir(bundled_resource_root()),
            )
            template = build_ui_locale_missing_template(package)
            data = json.dumps(template, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            filename = f"mc-mod-i18n-ui-{package['locale']}-missing.json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def _send_ui_locale_filled(self, locale: str, query: str) -> None:
            root = self._ui_locale_root_from_query(query)
            values = parse_qs(query or "")
            fill_locale = values.get("fill_locale", [FALLBACK_UI_LOCALE])[0]
            normalized = resolve_ui_locale(unquote(locale))
            package = export_ui_locale_package(
                normalized,
                root,
                minecraft_locale_display_names(),
                help_docs_dir(bundled_resource_root()),
            )
            filled = build_ui_locale_filled_package(package, fill_locale)
            data = json.dumps(filled, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            filename = f"mc-mod-i18n-ui-{filled['locale']}-filled-{resolve_ui_locale(fill_locale)}.json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def _parse_uploaded_ui_locale_package(self, parts: list[MultipartPart]) -> dict[str, Any]:
            part = next((item for item in parts if item.filename and item.name in {"ui_locale_file", "ui_locale_pack"} and item.data), None)
            if part is None:
                raise ValueError("请上传界面语言包 JSON")
            try:
                payload = json.loads(part.data.decode("utf-8-sig"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"语言包 JSON 无法解析：{exc}") from exc
            return parse_ui_locale_package(payload, part.filename or "")

        def _handle_ui_locale_check(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            parts = parse_multipart(self.headers.get("Content-Type", ""), body)
            package = self._parse_uploaded_ui_locale_package(parts)
            return {"ok": True, **package, **check_ui_locale_package(package)}

        def _handle_ui_locale_import(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            parts = parse_multipart(self.headers.get("Content-Type", ""), body)
            fields = collect_fields(parts)
            root = resolve_ui_locale_root(workdir, fields.get("ui_locale_dir", ""))
            package = self._parse_uploaded_ui_locale_package(parts)
            check = check_ui_locale_package(package)
            if check["placeholder_mismatches"]:
                raise ValueError("语言包占位符不匹配，请先修正后再导入")
            result = write_extension_package(root, package)
            docs_result = write_ui_locale_help_docs(root, package)
            return {"ok": True, "ui_locale_dir": str(root), **result, **docs_result}

        def _handle_glossary_save(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            terms = normalize_glossary_terms(payload.get("terms", {}))
            path = write_user_glossary(workdir, terms)
            return {
                "ok": True,
                "terms": terms,
                "count": len(terms),
                "conflicts": glossary_conflicts(terms),
                "path": str(path),
            }

        def _handle_preset_save(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            preset = write_config_preset(workdir, str(payload.get("name", "")), payload.get("config", {}))
            return {"ok": True, "preset": preset, "presets": list_config_presets(workdir)}

        def _handle_translate(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            parts = parse_multipart(self.headers.get("Content-Type", ""), body)
            fields = collect_fields(parts)
            ui_locale = resolve_ui_locale(fields.get("ui_locale"))
            ui_locale_root = resolve_ui_locale_root(workdir, fields.get("ui_locale_dir", ""))

            if fields.get("input_kind") == "json":
                return self._handle_translate_json(parts, fields)

            if fields.get("input_kind") == "ftbquests":
                return self._handle_translate_ftbquests(parts, fields)

            uploaded_jars = [part for part in parts if part.name == "jars" and part.filename and part.data]
            if not uploaded_jars:
                raise ValueError(translate_ui("error.jar_missing_input", ui_locale, ui_locale_root))

            job_id = token_hex(8)
            run_dir = workdir / job_id
            upload_dir = run_dir / "uploads"
            out_dir = run_dir / "out"
            upload_dir.mkdir(parents=True)
            out_dir.mkdir(parents=True)
            api_debug_log_path = out_dir / "api-debug.jsonl"

            jar_paths: list[Path] = []
            for index, part in enumerate(uploaded_jars, start=1):
                filename = sanitize_filename(part.filename or f"mod-{index}.jar")
                if not filename.lower().endswith(".jar"):
                    continue
                jar_path = upload_dir / filename
                jar_path.write_bytes(part.data)
                jar_paths.append(jar_path)

            if not jar_paths:
                raise ValueError(translate_ui("error.jar_no_file", ui_locale, ui_locale_root))

            glossary_path = glossary_upload_or_saved(parts, upload_dir, workdir)

            progress_total = max(1, int(fields.get("api_concurrency", "2") or "2"))
            api_batch_size = max(5, min(200, int(fields.get("api_batch_size", "40") or "40")))
            api_timeout = max(1.0, min(300.0, float(fields.get("api_timeout", "10") or "10")))
            progress_state = {"completed": 0, "total": 0}

            def progress_callback(*args: Any) -> None:
                if cancel_evt.is_set():
                    raise RuntimeError("cancelled")
                if len(args) == 1 and isinstance(args[0], dict):
                    event = args[0]
                    if event.get("type") == "retry_wait":
                        update_job(
                            job_id,
                            stage="retrying",
                            retry_attempt=event.get("next_attempt", event.get("attempt", 0)),
                            retry_max=event.get("max_retries", 0),
                            retry_delay=event.get("delay_seconds", 0),
                            retry_reason=event.get("reason", ""),
                            request_timeout=event.get("timeout_seconds", api_timeout),
                            batch_size=event.get("batch_size", api_batch_size),
                        )
                    elif event.get("type") == "request_attempt":
                        update_job(
                            job_id,
                            stage="translating",
                            retry_attempt=0,
                            retry_max=event.get("max_retries", 0),
                            retry_delay=0,
                            retry_reason="",
                            request_timeout=event.get("timeout_seconds", api_timeout),
                            batch_size=event.get("batch_size", api_batch_size),
                        )
                    return
                completed_delta = int(args[0] if args else 0)
                total_delta = int(args[1] if len(args) > 1 else 0)
                progress_state["completed"] += completed_delta
                progress_state["total"] += total_delta
                update_job(
                    job_id,
                    stage="translating",
                    completed=progress_state["completed"],
                    total=max(progress_state["total"], progress_state["completed"]),
                )

            update_job(
                job_id,
                status="running",
                stage="queued",
                completed=0,
                total=0,
                files_completed=0,
                files_total=len(jar_paths),
                cache_hits=0,
                cache_misses=0,
                current_file="",
                retry_attempt=0,
                retry_max=0,
                retry_delay=0,
                retry_reason="",
                request_timeout=api_timeout,
                batch_size=api_batch_size,
                result=None,
                error="",
                created_at=utc_timestamp(),
                input_kind="jar",
                input_files=[path.name for path in jar_paths],
                primary_input=jar_paths[0].name if jar_paths else "",
                target_locale=fields.get("target_locale", "zh_cn") or "zh_cn",
                provider=fields.get("provider", "glossary") or "glossary",
                model=fields.get("model", "gpt-4o-mini") or "gpt-4o-mini",
                args=None,
                api_debug_log_path=str(api_debug_log_path),
            )

            args = argparse.Namespace(
                source_locale=fields.get("source_locale", "en_us") or "en_us",
                target_locale=fields.get("target_locale", "zh_cn") or "zh_cn",
                provider=fields.get("provider", "glossary") or "glossary",
                glossary=str(glossary_path) if glossary_path else None,
                overwrite_existing=fields.get("overwrite_existing") == "on",
                skip_translated=fields.get("skip_translated") == "on",
                ignore_cache=fields.get("ignore_cache") == "on",
                ignore_translation_memory=fields.get("ignore_translation_memory") == "on",
                scan_hardcoded=fields.get("scan_hardcoded") == "on",
                hardcoded_limit=5000,
                pack_format=int(fields.get("pack_format", "15") or "15"),
                api_url=fields.get("api_url", "https://api.openai.com/v1"),
                api_key_env=fields.get("api_key_env", "OPENAI_API_KEY") or "OPENAI_API_KEY",
                api_key=fields.get("api_key", "").strip(),
                api_debug_log=str(api_debug_log_path) if fields.get("api_debug_log") == "on" else "",
                api_concurrency=progress_total,
                api_retries=max(1, min(10, int(fields.get("api_retries", "5") or "5"))),
                api_batch_size=api_batch_size,
                api_timeout=api_timeout,
                model=fields.get("model", "gpt-4o-mini") or "gpt-4o-mini",
                brand_logo=read_system_settings(workdir).get("brand_logo", DEFAULT_BRAND_LOGO),
                progress_callback=progress_callback,
            )
            cache_root = resolve_cache_root(workdir, fields.get("cache_dir", ""))
            args.translation_memory_path = str(translation_memory_path(cache_root))
            update_job(
                job_id,
                args={
                    "provider": args.provider,
                    "glossary": args.glossary,
                    "api_url": args.api_url,
                    "api_key_env": args.api_key_env,
                    "api_key": args.api_key,
                    "api_debug_log": args.api_debug_log,
                    "api_concurrency": args.api_concurrency,
                    "api_retries": args.api_retries,
                    "api_batch_size": args.api_batch_size,
                    "api_timeout": args.api_timeout,
                    "model": args.model,
                    "ignore_cache": args.ignore_cache,
                    "ignore_translation_memory": args.ignore_translation_memory,
                    "cache_dir": str(cache_root),
                    "translation_memory_path": args.translation_memory_path,
                },
            )

            cancel_evt = Event()
            cancel_events[job_id] = cancel_evt

            Thread(
                target=run_translate_job,
                args=(job_id, jar_paths, out_dir, cache_root, api_debug_log_path, args, update_job, cancel_evt),
                daemon=True,
            ).start()

            return {
                "ok": True,
                "job_id": job_id,
            }

        def _handle_translate_json(self, parts: list[MultipartPart], fields: dict[str, str]) -> dict[str, Any]:
            ui_locale = resolve_ui_locale(fields.get("ui_locale"))
            ui_locale_root = resolve_ui_locale_root(workdir, fields.get("ui_locale_dir", ""))
            uploaded = [part for part in parts if part.name == "json_files" and part.filename and part.data]
            if not uploaded:
                raise ValueError(translate_ui("error.json_missing_input", ui_locale, ui_locale_root))

            job_id = token_hex(8)
            run_dir = workdir / job_id
            upload_dir = run_dir / "uploads"
            out_dir = run_dir / "out"
            upload_dir.mkdir(parents=True)
            out_dir.mkdir(parents=True)
            api_debug_log_path = out_dir / "api-debug.jsonl"

            json_paths: list[Path] = []
            uploaded_names: set[str] = set()
            for index, part in enumerate(uploaded, start=1):
                filename = unique_filename(part.filename or f"language-{index}.json", uploaded_names)
                if not filename.lower().endswith(".json"):
                    continue
                path = upload_dir / filename
                path.write_bytes(part.data)
                json_paths.append(path)

            if not json_paths:
                raise ValueError(translate_ui("error.json_no_file", ui_locale, ui_locale_root))

            glossary_path = glossary_upload_or_saved(parts, upload_dir, workdir)

            api_batch_size = max(5, min(200, int(fields.get("api_batch_size", "40") or "40")))
            api_timeout = max(1.0, min(300.0, float(fields.get("api_timeout", "10") or "10")))
            progress_total = max(1, int(fields.get("api_concurrency", "2") or "2"))
            progress_state = {"completed": 0, "total": 0}

            def progress_callback(*args: Any) -> None:
                if cancel_evt.is_set():
                    raise RuntimeError("cancelled")
                if len(args) == 1 and isinstance(args[0], dict):
                    event = args[0]
                    if event.get("type") == "retry_wait":
                        update_job(
                            job_id,
                            stage="retrying",
                            retry_attempt=event.get("next_attempt", event.get("attempt", 0)),
                            retry_max=event.get("max_retries", 0),
                            retry_delay=event.get("delay_seconds", 0),
                            retry_reason=event.get("reason", ""),
                            request_timeout=event.get("timeout_seconds", api_timeout),
                            batch_size=event.get("batch_size", api_batch_size),
                        )
                    elif event.get("type") == "request_attempt":
                        update_job(
                            job_id,
                            stage="translating",
                            retry_attempt=0,
                            retry_max=event.get("max_retries", 0),
                            retry_delay=0,
                            retry_reason="",
                            request_timeout=event.get("timeout_seconds", api_timeout),
                            batch_size=event.get("batch_size", api_batch_size),
                        )
                    return
                completed_delta = int(args[0] if args else 0)
                total_delta = int(args[1] if len(args) > 1 else 0)
                progress_state["completed"] += completed_delta
                progress_state["total"] += total_delta
                update_job(
                    job_id,
                    stage="translating",
                    completed=progress_state["completed"],
                    total=max(progress_state["total"], progress_state["completed"]),
                )

            update_job(
                job_id,
                status="running",
                stage="queued",
                completed=0,
                total=0,
                files_completed=0,
                files_total=len(json_paths),
                cache_hits=0,
                cache_misses=0,
                current_file="",
                retry_attempt=0,
                retry_max=0,
                retry_delay=0,
                retry_reason="",
                request_timeout=api_timeout,
                batch_size=api_batch_size,
                result=None,
                error="",
                created_at=utc_timestamp(),
                input_kind="json",
                input_files=[path.name for path in json_paths],
                primary_input=json_paths[0].name if json_paths else "",
                target_locale=fields.get("target_locale", "zh_cn") or "zh_cn",
                provider=fields.get("provider", "glossary") or "glossary",
                model=fields.get("model", "gpt-4o-mini") or "gpt-4o-mini",
                args=None,
                api_debug_log_path=str(api_debug_log_path),
            )

            args = argparse.Namespace(
                source_locale=fields.get("source_locale", "en_us") or "en_us",
                target_locale=fields.get("target_locale", "zh_cn") or "zh_cn",
                provider=fields.get("provider", "glossary") or "glossary",
                glossary=str(glossary_path) if glossary_path else None,
                api_url=fields.get("api_url", "https://api.openai.com/v1"),
                api_key_env=fields.get("api_key_env", "OPENAI_API_KEY") or "OPENAI_API_KEY",
                api_key=fields.get("api_key", "").strip(),
                api_debug_log=str(api_debug_log_path) if fields.get("api_debug_log") == "on" else "",
                ignore_translation_memory=fields.get("ignore_translation_memory") == "on",
                api_concurrency=progress_total,
                api_retries=max(1, min(10, int(fields.get("api_retries", "5") or "5"))),
                api_batch_size=api_batch_size,
                api_timeout=api_timeout,
                model=fields.get("model", "gpt-4o-mini") or "gpt-4o-mini",
                progress_callback=progress_callback,
            )
            cache_root = resolve_cache_root(workdir, fields.get("cache_dir", ""))
            args.translation_memory_path = str(translation_memory_path(cache_root))
            update_job(
                job_id,
                args={
                    "provider": args.provider,
                    "glossary": args.glossary,
                    "api_url": args.api_url,
                    "api_key_env": args.api_key_env,
                    "api_key": args.api_key,
                    "api_debug_log": args.api_debug_log,
                    "api_concurrency": args.api_concurrency,
                    "api_retries": args.api_retries,
                    "api_batch_size": args.api_batch_size,
                    "api_timeout": args.api_timeout,
                    "model": args.model,
                    "ignore_cache": True,
                    "ignore_translation_memory": args.ignore_translation_memory,
                    "cache_dir": str(cache_root),
                    "translation_memory_path": args.translation_memory_path,
                },
            )

            cancel_evt = Event()
            cancel_events[job_id] = cancel_evt
            Thread(
                target=run_json_translate_job,
                args=(job_id, json_paths, out_dir, api_debug_log_path, args, update_job, cancel_evt),
                daemon=True,
            ).start()

            return {"ok": True, "job_id": job_id}

        def _handle_translate_ftbquests(self, parts: list[MultipartPart], fields: dict[str, str]) -> dict[str, Any]:
            ui_locale = resolve_ui_locale(fields.get("ui_locale"))
            ui_locale_root = resolve_ui_locale_root(workdir, fields.get("ui_locale_dir", ""))
            uploaded = [part for part in parts if part.name == "ftbquests_files" and part.filename and part.data]
            if not uploaded:
                raise ValueError(translate_ui("error.ftbquests_missing_input", ui_locale, ui_locale_root))

            job_id = token_hex(8)
            run_dir = workdir / job_id
            upload_dir = run_dir / "uploads"
            out_dir = run_dir / "out"
            upload_dir.mkdir(parents=True)
            out_dir.mkdir(parents=True)
            api_debug_log_path = out_dir / "api-debug.jsonl"

            source_locale = (fields.get("source_locale", "en_us") or "en_us").strip().lower()
            zip_paths: list[Path] = []
            snbt_parts: list[MultipartPart] = []
            for index, part in enumerate(uploaded, start=1):
                filename = sanitize_filename(part.filename or f"ftbquests-{index}.bin")
                lower = filename.lower()
                if lower.endswith(".zip"):
                    path = upload_dir / filename
                    path.write_bytes(part.data)
                    zip_paths.append(path)
                elif lower.endswith(".snbt"):
                    snbt_parts.append(part)

            if zip_paths and (len(zip_paths) > 1 or snbt_parts):
                raise ValueError("FTB Quests 模式一次只处理一个 ZIP，或上传一个/多个 SNBT 文件")

            if zip_paths:
                input_path = zip_paths[0]
            else:
                snbt_root = upload_dir / "ftbquests_input"
                for index, part in enumerate(snbt_parts, start=1):
                    relative = sanitize_relative_upload_path(part.filename or f"{source_locale}-{index}.snbt")
                    if "/" not in relative and re.match(r"^[a-z]{2}_[a-z]{2}\.snbt$", relative, flags=re.IGNORECASE):
                        relative = f"lang/{relative}"
                    target = safe_run_path(snbt_root, relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(part.data)
                input_path = snbt_root

            if not input_path.exists():
                raise ValueError("上传内容里没有可处理的 FTB Quests 文件")

            progress_total = max(1, int(fields.get("api_concurrency", "2") or "2"))
            api_batch_size = max(5, min(200, int(fields.get("api_batch_size", "40") or "40")))
            api_timeout = max(1.0, min(300.0, float(fields.get("api_timeout", "10") or "10")))
            progress_state = {"completed": 0, "total": 0}

            def progress_callback(*args: Any) -> None:
                if cancel_evt.is_set():
                    raise RuntimeError("cancelled")
                if len(args) == 1 and isinstance(args[0], dict):
                    event = args[0]
                    if event.get("type") == "retry_wait":
                        update_job(
                            job_id,
                            stage="retrying",
                            retry_attempt=event.get("next_attempt", event.get("attempt", 0)),
                            retry_max=event.get("max_retries", 0),
                            retry_delay=event.get("delay_seconds", 0),
                            retry_reason=event.get("reason", ""),
                            request_timeout=event.get("timeout_seconds", api_timeout),
                            batch_size=event.get("batch_size", api_batch_size),
                        )
                    elif event.get("type") == "request_attempt":
                        update_job(
                            job_id,
                            stage="translating",
                            retry_attempt=0,
                            retry_max=event.get("max_retries", 0),
                            retry_delay=0,
                            retry_reason="",
                            request_timeout=event.get("timeout_seconds", api_timeout),
                            batch_size=event.get("batch_size", api_batch_size),
                        )
                    return
                completed_delta = int(args[0] if args else 0)
                total_delta = int(args[1] if len(args) > 1 else 0)
                progress_state["completed"] += completed_delta
                progress_state["total"] += total_delta
                update_job(
                    job_id,
                    stage="translating",
                    completed=progress_state["completed"],
                    total=max(progress_state["total"], progress_state["completed"]),
                )

            update_job(
                job_id,
                status="running",
                stage="queued",
                completed=0,
                total=0,
                files_completed=0,
                files_total=1,
                cache_hits=0,
                cache_misses=0,
                current_file="",
                retry_attempt=0,
                retry_max=0,
                retry_delay=0,
                retry_reason="",
                request_timeout=api_timeout,
                batch_size=api_batch_size,
                result=None,
                error="",
                created_at=utc_timestamp(),
                input_kind="ftbquests",
                input_files=[input_path.name],
                primary_input=input_path.name,
                target_locale=fields.get("target_locale", "zh_cn") or "zh_cn",
                provider=fields.get("provider", "glossary") or "glossary",
                model=fields.get("model", "gpt-4o-mini") or "gpt-4o-mini",
                args=None,
                api_debug_log_path=str(api_debug_log_path),
            )

            glossary_path = glossary_upload_or_saved(parts, upload_dir, workdir)

            args = argparse.Namespace(
                source_locale=source_locale,
                target_locale=fields.get("target_locale", "zh_cn") or "zh_cn",
                provider=fields.get("provider", "glossary") or "glossary",
                glossary=str(glossary_path) if glossary_path else None,
                overwrite_existing=fields.get("overwrite_existing") == "on",
                ignore_cache=fields.get("ignore_cache") == "on",
                ignore_translation_memory=fields.get("ignore_translation_memory") == "on",
                output_mode=fields.get("ftbquests_output_mode", "both") or "both",
                api_url=fields.get("api_url", "https://api.openai.com/v1"),
                api_key_env=fields.get("api_key_env", "OPENAI_API_KEY") or "OPENAI_API_KEY",
                api_key=fields.get("api_key", "").strip(),
                api_debug_log=str(api_debug_log_path) if fields.get("api_debug_log") == "on" else "",
                api_concurrency=progress_total,
                api_retries=max(1, min(10, int(fields.get("api_retries", "5") or "5"))),
                api_batch_size=api_batch_size,
                api_timeout=api_timeout,
                model=fields.get("model", "gpt-4o-mini") or "gpt-4o-mini",
                progress_callback=progress_callback,
            )
            cache_root = resolve_cache_root(workdir, fields.get("cache_dir", ""))
            args.translation_memory_path = str(translation_memory_path(cache_root))
            update_job(
                job_id,
                args={
                    "provider": args.provider,
                    "glossary": args.glossary,
                    "api_url": args.api_url,
                    "api_key_env": args.api_key_env,
                    "api_key": args.api_key,
                    "api_debug_log": args.api_debug_log,
                    "api_concurrency": args.api_concurrency,
                    "api_retries": args.api_retries,
                    "api_batch_size": args.api_batch_size,
                    "api_timeout": args.api_timeout,
                    "model": args.model,
                    "ignore_cache": args.ignore_cache,
                    "ignore_translation_memory": args.ignore_translation_memory,
                    "cache_dir": str(cache_root),
                    "translation_memory_path": args.translation_memory_path,
                },
            )

            cancel_evt = Event()
            cancel_events[job_id] = cancel_evt

            Thread(
                target=run_ftbquests_job,
                args=(job_id, input_path, out_dir, cache_root, api_debug_log_path, args, update_job, cancel_evt),
                daemon=True,
            ).start()

            return {
                "ok": True,
                "job_id": job_id,
            }

        def _handle_retry(self, job_id: str) -> dict[str, Any]:
            job_id = sanitize_job_id(job_id)
            job = get_job(job_id)
            if not job or not job.get("result"):
                return {"ok": False, "error": "job not found"}
            result = dict(job["result"])
            failed_entries = result.get("api_failed_entries") or [
                entry for entry in result.get("entries", []) if entry.get("status") == "api_failed"
            ]
            if not failed_entries:
                return {"ok": True, "retried": 0, "result": result}

            args = argparse.Namespace(**job.get("args", {}))
            translator = create_translator(args)
            items = [
                TranslationItem(
                    id=entry_id(entry),
                    key=entry.get("key", ""),
                    text=entry.get("source", ""),
                    mod_id=entry.get("mod_id", ""),
                )
                for entry in failed_entries
            ]
            started_at = time.perf_counter()
            translations, failed_map = translate_batch_with_failures(translator, items)
            elapsed_seconds = time.perf_counter() - started_at
            updated, still_failed, _ = merge_retry_result(result, failed_entries, translations, failed_map)
            result["retry_elapsed_seconds"] = round(elapsed_seconds, 2)
            out_dir = workdir / job_id / "out"
            successful_entries = successful_retry_result_entries(result, failed_entries)
            pack_url = str(result.get("pack_url") or "")
            if updated and pack_url.startswith(f"/download/{job_id}/"):
                relative = pack_url.removeprefix(f"/download/{job_id}/")
                pack_path = safe_run_path(workdir / job_id, relative)
                update_resource_pack_entries(pack_path, successful_retry_updates(failed_entries, translations, failed_map))
            if updated and result.get("kind") == "json":
                update_json_retry_outputs(out_dir, successful_entries)
            if updated and result.get("kind") == "ftbquests":
                ftbquests_result = ftbquests_result_from_retry_payload(result)
                if ftbquests_result:
                    update_ftbquests_retry_outputs(out_dir, ftbquests_result, successful_entries)
                    result["ftbquests_output_files"] = [
                        {"path": item.path, "content": item.content}
                        for item in ftbquests_result.output_files
                    ]
            if updated:
                refresh_retry_report_exports(out_dir, result)
            result["api_debug_log_lines"] = read_jsonl(Path(job.get("api_debug_log_path", "")), limit=300)
            update_job(job_id, result=result)
            return {"ok": True, "retried": updated, "remaining": still_failed, "elapsed_seconds": round(elapsed_seconds, 2), "result": result}

        def _handle_translate_hardcoded(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
            entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
            if not entries:
                raise ValueError("没有选择需要翻译的硬编码候选")

            provider_name = str(config.get("provider", ""))
            if not is_ai_provider(provider_name):
                raise ValueError("请选择 AI 翻译器后再翻译硬编码映射")

            job_id = sanitize_job_id(str(payload.get("job_id", "")))
            api_debug_log_path: Path | None = None
            if job_id:
                api_debug_log_path = workdir / job_id / "out" / "api-debug.jsonl"

            args = argparse.Namespace(
                provider=provider_name,
                glossary=None,
                api_url=config.get("api_url", "https://api.openai.com/v1"),
                api_key_env=config.get("api_key_env", "OPENAI_API_KEY") or "OPENAI_API_KEY",
                api_key=str(config.get("api_key", "")).strip(),
                api_debug_log=str(api_debug_log_path) if api_debug_log_path else "",
                api_concurrency=max(1, int(config.get("api_concurrency", "1") or "1")),
                api_retries=max(1, min(10, int(config.get("api_retries", "5") or "5"))),
                api_batch_size=max(5, min(200, int(config.get("api_batch_size", "40") or "40"))),
                api_timeout=max(1.0, min(300.0, float(config.get("api_timeout", "10") or "10"))),
                model=config.get("model", "gpt-4o-mini") or "gpt-4o-mini",
            )
            translator = create_translator(args)
            items = [
                TranslationItem(
                    id=str(entry.get("index", "")),
                    key=str(entry.get("category", "hardcoded")),
                    text=str(entry.get("source", "")),
                    mod_id="hardcoded",
                )
                for entry in entries
                if str(entry.get("source", "")).strip()
            ]
            translations, failed_map = translate_batch_with_failures(translator, items)
            output: dict[str, str] = {}
            failed_count = 0
            for entry in entries:
                item_id = str(entry.get("index", ""))
                translated = translations.get(item_id)
                if not translated or item_id in failed_map:
                    failed_count += 1
                    continue
                errors = validate_translation(str(entry.get("source", "")), translated)
                if errors:
                    failed_count += 1
                    continue
                output[item_id] = translated
            return {
                "ok": True,
                "translations": output,
                "failed_count": failed_count,
                "api_debug_log_lines": read_jsonl(api_debug_log_path, limit=300) if api_debug_log_path else [],
            }

        def _serve_run_file(self, relative: str, download: bool) -> None:
            target = safe_run_path(workdir, relative)
            if not target.is_file():
                self.send_error(404)
                return
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_bytes(self, data: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return WebHandler


def test_provider_connection(
    provider: str,
    api_url: str,
    api_key: str,
    api_key_env: str,
    model: str,
    timeout: float = 10.0,
    api_region: str = "",
) -> dict[str, Any]:
    return _provider_checks._test_provider_connection(
        provider,
        api_url,
        api_key,
        api_key_env,
        model,
        timeout,
        api_region,
        azure_smoke_test=azure_translator_smoke_test,
        argos_smoke_test_func=argos_smoke_test,
        deep_free_smoke_test_func=deep_free_smoke_test,
        libretranslate_smoke_test_func=libretranslate_smoke_test,
        fetch_models_func=fetch_provider_models,
        provider_test_error_func=provider_test_error,
        elapsed_ms_func=elapsed_ms,
        provider_http_error_type_func=provider_http_error_type,
        provider_http_error_message_func=provider_http_error_message,
        provider_runtime_error_type_func=provider_runtime_error_type,
    )


def preflight_inputs(kind: str, paths: list[Path], source_locale: str, target_locale: str) -> dict[str, Any]:
    return _preflight.preflight_inputs(
        kind,
        paths,
        source_locale,
        target_locale,
        parse_json_payload=parse_json_translation_payload,
        json_target_namer=json_target_filename,
    )


save_preflight_uploads = _preflight.save_preflight_uploads
preflight_json_paths = _preflight.preflight_json_paths
json_schema_label = _preflight.json_schema_label


def run_json_translate_job(
    job_id: str,
    json_paths: list[Path],
    out_dir: Path,
    api_debug_log_path: Path,
    args: argparse.Namespace,
    update_job,
    cancel_event: Event | None = None,
) -> None:
    try:
        started_at = time.perf_counter()
        translator = create_translator(args)
        isolate_translator = args.provider == "deep-free"
        report_entries: list[ReportEntry] = []
        output_paths: list[Path] = []
        output_names: set[str] = set()
        json_metadata_preview: list[dict[str, str]] = []
        translated_total = 0
        failed_total = 0
        skipped_total = 0
        for index, path in enumerate(json_paths, start=1):
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("cancelled")
            update_job(job_id, stage="processing_file", files_completed=index - 1, files_total=len(json_paths), current_file=path.name)
            local_translator = create_translator(args) if isolate_translator else translator
            output_name, output_data, entries, translated_count, failed_count, skipped_count = process_json_language_file(path, args, local_translator)
            unique_output_name = unique_filename(output_name, output_names)
            if unique_output_name != output_name:
                entries = [replace(entry, file=unique_output_name) for entry in entries]
                output_name = unique_output_name
            metadata_preview = json_output_metadata_preview(output_name, output_data)
            if metadata_preview:
                json_metadata_preview.append(metadata_preview)
            target = out_dir / output_name
            target.write_text(json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output_paths.append(target)
            report_entries.extend(entries)
            translated_total += translated_count
            failed_total += failed_count
            skipped_total += skipped_count
            update_job(job_id, stage="processing_file", files_completed=index, files_total=len(json_paths), current_file=path.name)

        if len(output_paths) == 1:
            download_path = output_paths[0]
        else:
            download_path = out_dir / f"json-locales-{args.target_locale}.zip"
            with ZipFile(download_path, "w") as zf:
                for path in output_paths:
                    zf.write(path, path.name)
        summary: dict[str, int] = {
            "translated": translated_total,
            "failed": failed_total,
            "skipped": skipped_total,
        }
        for entry in report_entries:
            summary[entry.status] = summary.get(entry.status, 0) + 1
        elapsed_seconds = time.perf_counter() - started_at
        export_paths = write_report_exports(
            out_dir,
            report_entries,
            summary,
            {
                "job_id": job_id,
                "kind": "json",
                "provider": args.provider,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "cache_hits": 0,
                "cache_misses": translated_total,
                "memory_hits": getattr(translator, "memory_hits", 0),
            },
        )
        result = {
            "kind": "json",
            "job_id": job_id,
            "provider": args.provider,
            "processed_sources": len(json_paths),
            "generated_files": len(output_paths),
            "json_url": f"/download/{job_id}/out/{download_path.name}",
            "json_filename": download_path.name,
            "report_url": f"/download/{job_id}/out/report.json",
            "report_json_url": f"/download/{job_id}/out/{export_paths['report_json'].name}",
            "report_csv_url": f"/download/{job_id}/out/{export_paths['report_csv'].name}",
            "failed_items_url": f"/download/{job_id}/out/{export_paths['failed_json'].name}",
            "api_debug_log_url": f"/report/{job_id}/out/api-debug.jsonl" if api_debug_log_path.is_file() else "",
            "api_debug_log_lines": read_jsonl(api_debug_log_path, limit=300),
            "elapsed_seconds": round(elapsed_seconds, 2),
            "cache_hits": 0,
            "cache_misses": translated_total,
            "memory_hits": getattr(translator, "memory_hits", 0),
            "summary": summary,
            "api_failure_count": summary.get("api_failed", 0),
            "api_failed_entries": [entry.__dict__ for entry in report_entries if entry.status == "api_failed"],
            "entries": [entry.__dict__ for entry in report_entries],
            "json_metadata_preview": json_metadata_preview,
        }
        update_job(job_id, status="done", stage="done", completed=translated_total, total=translated_total, result=result)
    except Exception as exc:
        update_job(job_id, status="error", stage="error", error=str(exc), result=None)


def run_ftbquests_job(
    job_id: str,
    input_path: Path,
    out_dir: Path,
    shared_cache_root: Path,
    api_debug_log_path: Path,
    args: argparse.Namespace,
    update_job,
    cancel_event: Event | None = None,
) -> None:
    try:
        started_at = time.perf_counter()
        update_job(job_id, stage="processing_file", files_completed=0, files_total=1, current_file=input_path.name)
        source = load_ftbquests_source(input_path, args.source_locale)
        source_hash = compute_ftbquests_source_hash(source)
        config_hash = compute_ftbquests_config_hash(args)
        cache_key = ftbquests_cache_key(input_path)
        shared_cache_dir = shared_cache_root / config_hash[:16]
        shared_cache_dir.mkdir(parents=True, exist_ok=True)
        ignore_cache = bool(getattr(args, "ignore_cache", False))
        cache_hit = False
        result = None
        memory_hits = 0

        if not ignore_cache:
            cached_hash = load_ftbquests_checkpoint_source_hash(shared_cache_dir, cache_key)
            cached_config_hash = load_ftbquests_checkpoint_config_hash(shared_cache_dir, cache_key)
            if source_hash and cached_hash == source_hash and cached_config_hash == config_hash:
                cached = load_ftbquests_checkpoint(shared_cache_dir, cache_key)
                if cached is not None and not report_has_uncacheable_failures(cached.report_entries):
                    update_job(job_id, stage="reusing_cache", current_file=f"{input_path.name}（命中缓存）")
                    result = cached
                    cache_hit = True

        if result is None:
            translator = create_translator(args)
            if hasattr(translator, "task_id"):
                translator.task_id = job_id
            if args.provider in {"copy", "glossary"}:
                update_job(job_id, stage="translating", completed=1, total=1)
            result = process_ftbquests_source(source, args, translator)
            memory_hits = getattr(translator, "memory_hits", 0)
            if not report_has_uncacheable_failures(result.report_entries):
                save_ftbquests_checkpoint(shared_cache_dir, cache_key, result, config_hash=config_hash)

        if cancel_event and cancel_event.is_set():
            update_job(job_id, status="cancelled", stage="cancelled", error="用户已中断")
            return

        update_job(
            job_id,
            stage="writing",
            files_completed=1,
            files_total=1,
            cache_hits=1 if cache_hit else 0,
            cache_misses=0 if cache_hit else 1,
            current_file=input_path.name,
        )
        output_mode = getattr(args, "output_mode", "both")
        directory_path = None
        patch_path = None
        if result.output_files:
            directory_path, patch_path = write_ftbquests_outputs(out_dir, result, output_mode)
        report_path = out_dir / "ftbquests-report.html"
        json_report_path = out_dir / "ftbquests-report.json"
        write_ftbquests_html_report(report_path, result)
        write_ftbquests_json_report(json_report_path, result)

        summary: dict[str, int] = {}
        for entry in result.report_entries:
            summary[entry.status] = summary.get(entry.status, 0) + 1
        elapsed_seconds = time.perf_counter() - started_at
        export_paths = write_report_exports(
            out_dir,
            result.report_entries,
            summary,
            {
                "job_id": job_id,
                "kind": "ftbquests",
                "provider": args.provider,
                "mode": result.mode,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "cache_hits": 1 if cache_hit else 0,
                "cache_misses": 0 if cache_hit else 1,
                "memory_hits": memory_hits,
            },
        )
        patch_url = f"/download/{job_id}/out/{patch_path.name}" if patch_path and patch_path.is_file() else ""
        result_payload = {
            "ok": True,
            "kind": "ftbquests",
            "job_id": job_id,
            "processed_jars": 0,
            "processed_sources": 1,
            "generated_files": len(result.output_files),
            "mode": result.mode,
            "source_label": result.source_label,
            "source_locale": result.source_locale,
            "target_locale": result.target_locale,
            "source_hash": result.source_hash,
            "legacy_files": len(result.legacy_files),
            "ftbquests_patch_url": patch_url,
            "ftbquests_directory": str(directory_path) if directory_path else "",
            "report_url": f"/report/{job_id}/out/ftbquests-report.html",
            "ftbquests_json_report_url": f"/download/{job_id}/out/ftbquests-report.json",
            "report_json_url": f"/download/{job_id}/out/{export_paths['report_json'].name}",
            "report_csv_url": f"/download/{job_id}/out/{export_paths['report_csv'].name}",
            "failed_items_url": f"/download/{job_id}/out/{export_paths['failed_json'].name}",
            "api_debug_log_url": f"/report/{job_id}/out/api-debug.jsonl" if api_debug_log_path.is_file() else "",
            "hardcoded_count": 0,
            "hardcoded_map": {},
            "hardcoded_entries": [],
            "summary": summary,
            "provider": args.provider,
            "elapsed_seconds": round(elapsed_seconds, 2),
            "cache_hits": 1 if cache_hit else 0,
            "cache_misses": 0 if cache_hit else 1,
            "memory_hits": memory_hits,
            "api_failure_count": summary.get("api_failed", 0),
            "api_failed_entries": [entry.__dict__ for entry in result.report_entries if entry.status == "api_failed"],
            "entries": [entry.__dict__ for entry in result.report_entries],
            "ftbquests_output_files": [
                {"path": item.path, "content": item.content}
                for item in result.output_files
            ],
            "api_debug_log_lines": read_jsonl(api_debug_log_path, limit=300),
        }
        update_job(job_id, status="done", stage="done", result=result_payload)
    except Exception as exc:
        if cancel_event and cancel_event.is_set():
            update_job(job_id, status="cancelled", stage="cancelled", error="用户已中断")
        else:
            update_job(job_id, status="error", stage="error", error=str(exc))


def run_translate_job(
    job_id: str,
    jar_paths: list[Path],
    out_dir: Path,
    shared_cache_root: Path,
    api_debug_log_path: Path,
    args: argparse.Namespace,
    update_job,
    cancel_event: Event | None = None,
) -> None:
    try:
        started_at = time.perf_counter()
        translator = create_translator(args)
        if hasattr(translator, "task_id"):
            translator.task_id = job_id
        pack_format = resolve_pack_format(args.pack_format)
        if args.provider in {"copy", "glossary"}:
            update_job(job_id, stage="translating", completed=1, total=1)
        config_hash = compute_translation_config_hash(args)

        output_documents: list[OutputLangDocument] = []
        report_entries: list[ReportEntry] = []
        hardcoded_entries = []
        files_completed = 0
        files_total = len(jar_paths)
        cache_hits = 0
        cache_misses = 0
        shared_cache_dir = shared_cache_scope_dir(shared_cache_root, args)
        ignore_cache = bool(getattr(args, "ignore_cache", False))
        isolate_translator = args.provider == "deep-free"
        def process_single(jar_path: Path) -> tuple[Path, list[OutputLangDocument], list[ReportEntry], list, str, bool]:
            jar_docs: list[OutputLangDocument] = []
            jar_entries: list[ReportEntry] = []
            jar_hardcoded: list = []
            source_hash = ""
            local_translator = create_translator(args) if isolate_translator else translator
            cache_key = shared_cache_key(jar_path)
            try:
                with ZipFile(jar_path) as zf:
                    source_hash = compute_zip_source_hash(zf, args.source_locale)
            except (BadZipFile, OSError, ValueError):
                source_hash = ""
            if not ignore_cache:
                cached_hash = load_checkpoint_source_hash(shared_cache_dir, cache_key)
                cached_config_hash = load_checkpoint_config_hash(shared_cache_dir, cache_key)
                if source_hash and cached_hash and cached_hash == source_hash and cached_config_hash == config_hash:
                    cached = load_checkpoint(shared_cache_dir, cache_key)
                    if cached is not None:
                        jar_docs, jar_entries = cached
                    if cached is not None and not report_has_uncacheable_failures(jar_entries):
                        update_job(job_id, stage="reusing_cache", current_file=f"{jar_path.name}（命中缓存）")
                        if args.scan_hardcoded:
                            jar_hardcoded = scan_jar_for_hardcoded(str(jar_path), max_entries=args.hardcoded_limit)
                        save_checkpoint(out_dir, jar_path.stem, jar_docs, jar_entries, source_hash=source_hash, config_hash=config_hash)
                        return jar_path, jar_docs, jar_entries, jar_hardcoded, source_hash, True
            try:
                jar_docs, jar_entries, source_hash = process_jar(jar_path, args, local_translator)
                if args.scan_hardcoded:
                    jar_hardcoded = scan_jar_for_hardcoded(str(jar_path), max_entries=args.hardcoded_limit)
            except (BadZipFile, RuntimeError, ValueError) as exc:
                jar_entries.append(
                    ReportEntry(
                        jar=jar_path.name,
                        mod_id="unknown",
                        file="",
                        key="",
                        source="",
                        target="",
                        status="jar_failed",
                        message=str(exc),
                    )
                )
            save_checkpoint(out_dir, jar_path.stem, jar_docs, jar_entries, source_hash=source_hash, config_hash=config_hash)
            if not report_has_uncacheable_failures(jar_entries):
                save_checkpoint(shared_cache_dir, cache_key, jar_docs, jar_entries, source_hash=source_hash, config_hash=config_hash)
            return jar_path, jar_docs, jar_entries, jar_hardcoded, source_hash, False

        if len(jar_paths) <= 1:
            for jar_path in jar_paths:
                if cancel_event and cancel_event.is_set():
                    break
                update_job(
                    job_id,
                    stage="processing_file",
                    files_completed=files_completed,
                    files_total=files_total,
                    current_file=jar_path.name,
                )
                _, jar_docs, jar_entries, jar_hardcoded, _, used_cache = process_single(jar_path)
                output_documents.extend(jar_docs)
                report_entries.extend(jar_entries)
                hardcoded_entries.extend(jar_hardcoded)
                files_completed += 1
                cache_hits += 1 if used_cache else 0
                cache_misses += 0 if used_cache else 1
                update_job(
                    job_id,
                    files_completed=files_completed,
                    files_total=files_total,
                    cache_hits=cache_hits,
                    cache_misses=cache_misses,
                    current_file=jar_path.name,
                )
        else:
            worker_count = max(1, getattr(args, "api_concurrency", 1)) if is_ai_provider(args.provider) else len(jar_paths)
            update_job(
                job_id,
                stage="processing_file",
                files_completed=files_completed,
                files_total=files_total,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                current_file=f"并行处理中（{len(jar_paths)} 个 JAR）",
            )
            with ThreadPoolExecutor(max_workers=min(worker_count, len(jar_paths))) as executor:
                futures = {executor.submit(process_single, jar_path): jar_path for jar_path in jar_paths}
                for future in as_completed(futures):
                    if cancel_event and cancel_event.is_set():
                        break
                    jar_path, jar_docs, jar_entries, jar_hardcoded, _, used_cache = future.result()
                    output_documents.extend(jar_docs)
                    report_entries.extend(jar_entries)
                    hardcoded_entries.extend(jar_hardcoded)
                    files_completed += 1
                    cache_hits += 1 if used_cache else 0
                    cache_misses += 0 if used_cache else 1
                    update_job(
                        job_id,
                        files_completed=files_completed,
                        files_total=files_total,
                        cache_hits=cache_hits,
                        cache_misses=cache_misses,
                        current_file=jar_path.name,
                    )

        update_job(job_id, stage="writing")
        pack_filename = resource_pack_filename(jar_paths)
        pack_path = out_dir / pack_filename
        report_path = out_dir / "report.html"
        hardcoded_report_path = out_dir / "hardcoded-report.html"
        hardcoded_map_path = out_dir / "hardcoded-map.template.json"
        if output_documents:
            write_resource_pack(
                pack_path,
                output_documents,
                pack_format,
                "§b汉化工具§r§6By co1dsand",
                read_co1dsand_pack_icon(brand_logo=getattr(args, "brand_logo", DEFAULT_BRAND_LOGO)),
            )
        write_report(report_path, report_entries)
        if args.scan_hardcoded:
            write_hardcoded_report(hardcoded_report_path, hardcoded_entries)
            write_hardcoded_map_template(hardcoded_map_path, hardcoded_entries)
        hardcoded_map = build_hardcoded_map_template(hardcoded_entries) if args.scan_hardcoded else {}

        summary: dict[str, int] = {}
        for entry in report_entries:
            summary[entry.status] = summary.get(entry.status, 0) + 1
        elapsed_seconds = time.perf_counter() - started_at
        export_paths = write_report_exports(
            out_dir,
            report_entries,
            summary,
            {
                "job_id": job_id,
                "kind": "jar",
                "provider": args.provider,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "memory_hits": getattr(translator, "memory_hits", 0),
            },
        )

        result = {
            "ok": True,
            "job_id": job_id,
            "processed_jars": len(jar_paths),
            "generated_files": len(output_documents),
            "hardcoded_count": len(hardcoded_entries),
            "pack_url": f"/download/{job_id}/out/{pack_filename}" if output_documents else "",
            "pack_filename": pack_filename,
            "report_url": f"/report/{job_id}/out/report.html",
            "report_json_url": f"/download/{job_id}/out/{export_paths['report_json'].name}",
            "report_csv_url": f"/download/{job_id}/out/{export_paths['report_csv'].name}",
            "failed_items_url": f"/download/{job_id}/out/{export_paths['failed_json'].name}",
            "hardcoded_report_url": f"/report/{job_id}/out/hardcoded-report.html" if args.scan_hardcoded else "",
            "hardcoded_map_url": f"/download/{job_id}/out/hardcoded-map.template.json" if args.scan_hardcoded else "",
            "api_debug_log_url": f"/report/{job_id}/out/api-debug.jsonl" if api_debug_log_path.is_file() else "",
            "hardcoded_map": hardcoded_map,
            "hardcoded_entries": [hardcoded_entry_to_dict(entry) for entry in hardcoded_entries],
            "summary": summary,
            "provider": args.provider,
            "elapsed_seconds": round(elapsed_seconds, 2),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "memory_hits": getattr(translator, "memory_hits", 0),
            "api_failure_count": summary.get("api_failed", 0),
            "api_failed_entries": [entry.__dict__ for entry in report_entries if entry.status == "api_failed"],
            "entries": [entry.__dict__ for entry in report_entries],
            "api_debug_log_lines": read_jsonl(api_debug_log_path, limit=300),
        }
        update_job(job_id, status="done", stage="done", result=result)
    except Exception as exc:
        if cancel_event and cancel_event.is_set():
            update_job(job_id, status="cancelled", stage="cancelled", error="用户已中断")
        else:
            update_job(job_id, status="error", stage="error", error=str(exc))


def read_co1dsand_pack_icon(
    root: Path | None = None,
    *,
    workdir: Path | None = None,
    brand_logo: Any | None = None,
) -> bytes | None:
    selected = normalize_brand_logo_choice(
        brand_logo if brand_logo is not None else (
            read_system_settings(workdir).get("brand_logo") if workdir is not None else read_branding_build_config(root).get("brand_logo")
        )
    )
    for path in co1dsand_pack_logo_paths(root, brand_logo=selected):
        icon = read_pack_icon(path)
        if icon:
            return icon
    return None

