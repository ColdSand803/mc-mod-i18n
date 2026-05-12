from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
from secrets import token_hex
from threading import Event, Lock, Thread
import time
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import urllib.error
import urllib.request
from zipfile import BadZipFile, ZipFile

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import compute_translation_config_hash, compute_zip_source_hash, create_translator, process_jar, report_has_uncacheable_failures, translate_batch_with_failures
from .ftbquests import (
    compute_ftbquests_config_hash,
    compute_ftbquests_source_hash,
    ftbquests_cache_key,
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
from .hardcoded import HardcodedEntry, hardcoded_category_label, hardcoded_category_order
from .hardcoded import scan_jar_for_hardcoded
from .pack import OutputLangDocument, load_checkpoint, load_checkpoint_config_hash, load_checkpoint_source_hash, read_pack_icon, resolve_pack_format, resource_pack_filename, save_checkpoint, update_resource_pack_entries, write_resource_pack
from .report import (
    ReportEntry,
    build_hardcoded_map_template,
    write_hardcoded_map_template,
    write_hardcoded_report,
    write_report,
)
from .translator import LOCALE_DISPLAY_NAMES, TranslationItem, get_provider_preset, is_ai_provider
from .ui_i18n import (
    export_ui_locale_package,
    list_ui_locales,
    parse_ui_locale_package,
    resolve_ui_locale,
    resolve_ui_locale_root,
    translate_ui,
    write_extension_package,
)
from .validator import validate_translation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIDEBAR_LOGO_PATH = PROJECT_ROOT / "ui优化方案" / "logo" / "minecraft.svg"
CO1DSAND_PACK_LOGO_PATHS = (Path.cwd() / "co1dsand_logo.png", PROJECT_ROOT / "co1dsand_logo.png")


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>mc-mod-i18n</title>
  <link rel="icon" href="/assets/logo/minecraft.svg" type="image/svg+xml">
  <link href="https://cdn.jsdelivr.net/npm/remixicon@4.5.0/fonts/remixicon.css" rel="stylesheet">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script>
    (() => {
      try {
        const key = 'mc-mod-i18n-theme';
        const lightThemes = ['light', 'forest', 'monet', 'qingming-scroll', 'cezanne', 'sisley', 'pissarro', 'morandi', 'gauguin', 'matisse', 'qi-baishi', 'healing-sea-blue', 'mint-tea-green', 'cream-berry-purple', 'seafoam-apricot', 'klein-gold', 'honey-sunset', 'crimson-ivory', 'sakura-mist'];
        const darkThemes = ['dark', 'midnight', 'dongbei-rain', 'rainbow-rgb', 'bleach-tybw', 'eva', 'starry-night', 'p-site', 'neon-track', 'orange-slate'];
        const knownThemes = ['auto'].concat(lightThemes, darkThemes);
        const stored = localStorage.getItem(key) || 'auto';
        const mode = knownThemes.includes(stored) ? stored : 'auto';
        const resolved = mode === 'auto'
          ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
          : mode;
        const scheme = darkThemes.includes(resolved) ? 'dark' : 'light';
        document.documentElement.dataset.themeMode = mode;
        document.documentElement.dataset.theme = resolved;
        document.documentElement.style.colorScheme = scheme;
      } catch (error) {}
    })();
  </script>
  <style>
    :root {
      color-scheme: light;
      --bg: #f8f9ff;
      --surface: #f8fafc;
      --panel: #ffffff;
      --panel-2: #eff4ff;
      --text: #0b1c30;
      --muted: #5f6f86;
      --line: #dbe3ef;
      --accent: #004ac6;
      --accent-2: #2563eb;
      --button-text: #ffffff;
      --danger: #ba1a1a;
      --danger-text: #ffffff;
      --success: #16a34a;
      --warning: #f97316;
      --sidebar: #f1f5f9;
      --nav-text: #32445c;
      --tab-text: #34465c;
      --field-bg: #ffffff;
      --field-bg-soft: #f1f5f9;
      --chip-bg: #ffffff;
      --accent-soft: #eaf2ff;
      --accent-soft-hover: #eff6ff;
      --accent-soft-active: #dbeafe;
      --accent-soft-line: #cfe1fb;
      --accent-active-line: #93c5fd;
      --danger-bg: #fff0ea;
      --danger-line: #f0c6b8;
      --loading-from: #fbfcfe;
      --loading-to: #f5f8fb;
      --overlay: rgba(15, 23, 42, .34);
      --scroll-thumb: #c0ccd9;
      --scroll-track: rgba(203, 213, 225, .36);
      --dropdown-scroll-track: rgba(219, 227, 239, .7);
      --dropdown-scroll-thumb: rgba(37, 99, 235, .34);
      --dropdown-scroll-thumb-hover: rgba(37, 99, 235, .54);
      --dropdown-scroll-thumb-active: rgba(0, 74, 198, .74);
      --dropdown-scroll-shadow: rgba(37, 99, 235, .16);
      --check-bg: linear-gradient(180deg, #ffffff, #f4f8ff);
      --check-border: #b9c9dc;
      --check-border-hover: #7ea8ea;
      --check-checked: linear-gradient(180deg, #2563eb, #004ac6);
      --check-checked-border: #004ac6;
      --check-tick: #ffffff;
      --check-shadow: rgba(37, 99, 235, .16);
      --control-hover-bg: linear-gradient(180deg, #f8fbff, #eff6ff);
      --control-hover-border: #9fc0f7;
      --control-hover-text: #004ac6;
      --control-active-bg: linear-gradient(135deg, #2563eb, #004ac6);
      --control-active-border: #004ac6;
      --control-active-text: #ffffff;
      --control-active-shadow: 0 12px 28px rgba(37, 99, 235, .22);
      --field-border: #d4deeb;
      --field-border-hover: #9fc0f7;
      --field-surface: linear-gradient(180deg, #ffffff, #f7faff);
      --field-surface-soft: linear-gradient(180deg, #f8fbff, #eef4fb);
      --field-shadow: inset 0 1px 0 rgba(255, 255, 255, .9), 0 6px 18px rgba(15, 23, 42, .05);
      --field-shadow-hover: inset 0 1px 0 rgba(255, 255, 255, .95), 0 12px 28px rgba(37, 99, 235, .10);
      --help-bg: rgba(234, 242, 255, .88);
      --help-border: rgba(159, 192, 247, .56);
      --help-text: #4d6483;
      --status-info-bg: linear-gradient(180deg, #fbfdff, #eef4fb);
      --status-info-border: #d8e4f2;
      --status-info-text: #4d6483;
      --status-success-bg: linear-gradient(180deg, #f2fff7, #e8fbef);
      --status-success-border: #bbf7d0;
      --status-success-text: #166534;
      --status-error-bg: linear-gradient(180deg, #fff7f4, #fff0ea);
      --status-error-border: #f0c6b8;
      --status-error-text: #ba1a1a;
      --status-accent-shadow: inset 4px 0 0 rgba(37, 99, 235, .22);
      --card-surface: linear-gradient(180deg, #ffffff, #f7fbff);
      --card-surface-soft: linear-gradient(180deg, #fbfdff, #f1f6fc);
      --card-surface-strong: linear-gradient(135deg, #f8fbff, #edf4ff);
      --card-border: #dbe5f0;
      --card-shadow-soft: 0 10px 28px rgba(15, 23, 42, .06);
      --card-shadow-strong: 0 18px 38px rgba(15, 23, 42, .10);
      --card-highlight: rgba(37, 99, 235, .10);
      --table-alt: #fcfdff;
      --table-hover: #eef6ff;
      --shadow: 0 4px 14px rgba(15, 23, 42, .07);
      --radius-sm: 10px;
      --radius-md: 14px;
      --radius-lg: 18px;
      --motion-fast: 160ms;
      --motion-base: 220ms;
      --focus-ring: 0 0 0 3px rgba(38, 104, 168, .14);
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --bg: #020617;
      --surface: #040b18;
      --panel: #0b1220;
      --panel-2: #101a2d;
      --text: #e5eefb;
      --muted: #8da0ba;
      --line: #22314a;
      --accent: #60a5fa;
      --accent-2: #3b82f6;
      --button-text: #03111f;
      --danger: #fca5a5;
      --danger-text: #2a0505;
      --success: #22c55e;
      --warning: #fb923c;
      --sidebar: #06101f;
      --nav-text: #c0d2e8;
      --tab-text: #c7d6ea;
      --field-bg: #0f172a;
      --field-bg-soft: #0b1527;
      --chip-bg: #0f172a;
      --accent-soft: rgba(96, 165, 250, .16);
      --accent-soft-hover: rgba(96, 165, 250, .14);
      --accent-soft-active: rgba(96, 165, 250, .20);
      --accent-soft-line: rgba(96, 165, 250, .24);
      --accent-active-line: rgba(147, 197, 253, .32);
      --danger-bg: rgba(239, 68, 68, .14);
      --danger-line: rgba(248, 113, 113, .24);
      --loading-from: #081120;
      --loading-to: #0b1628;
      --overlay: rgba(2, 6, 23, .72);
      --scroll-thumb: #314158;
      --scroll-track: rgba(30, 41, 59, .52);
      --dropdown-scroll-track: rgba(15, 23, 42, .88);
      --dropdown-scroll-thumb: rgba(96, 165, 250, .34);
      --dropdown-scroll-thumb-hover: rgba(125, 211, 252, .54);
      --dropdown-scroll-thumb-active: rgba(147, 197, 253, .74);
      --dropdown-scroll-shadow: rgba(96, 165, 250, .22);
      --check-bg: linear-gradient(180deg, #111c31, #0b1527);
      --check-border: #325072;
      --check-border-hover: #60a5fa;
      --check-checked: linear-gradient(180deg, #60a5fa, #2563eb);
      --check-checked-border: #7dd3fc;
      --check-tick: #03111f;
      --check-shadow: rgba(96, 165, 250, .24);
      --control-hover-bg: linear-gradient(180deg, rgba(96, 165, 250, .18), rgba(37, 99, 235, .24));
      --control-hover-border: rgba(125, 211, 252, .5);
      --control-hover-text: #d8ebff;
      --control-active-bg: linear-gradient(135deg, #7dd3fc, #3b82f6);
      --control-active-border: #93c5fd;
      --control-active-text: #03111f;
      --control-active-shadow: 0 14px 32px rgba(37, 99, 235, .28);
      --field-border: #28405f;
      --field-border-hover: #60a5fa;
      --field-surface: linear-gradient(180deg, #101a2d, #0b1527);
      --field-surface-soft: linear-gradient(180deg, #0f1a2f, #0a1426);
      --field-shadow: inset 0 1px 0 rgba(255, 255, 255, .03), 0 10px 26px rgba(0, 0, 0, .18);
      --field-shadow-hover: inset 0 1px 0 rgba(255, 255, 255, .04), 0 16px 34px rgba(37, 99, 235, .18);
      --help-bg: rgba(15, 23, 42, .84);
      --help-border: rgba(59, 130, 246, .24);
      --help-text: #9fb4cf;
      --status-info-bg: linear-gradient(180deg, #101b30, #0b1629);
      --status-info-border: #22314a;
      --status-info-text: #9db2cc;
      --status-success-bg: linear-gradient(180deg, rgba(34, 197, 94, .14), rgba(21, 128, 61, .14));
      --status-success-border: rgba(74, 222, 128, .32);
      --status-success-text: #86efac;
      --status-error-bg: linear-gradient(180deg, rgba(248, 113, 113, .12), rgba(239, 68, 68, .16));
      --status-error-border: rgba(248, 113, 113, .28);
      --status-error-text: #fecaca;
      --status-accent-shadow: inset 4px 0 0 rgba(96, 165, 250, .28);
      --card-surface: linear-gradient(180deg, #0d172a, #0a1324);
      --card-surface-soft: linear-gradient(180deg, #101b31, #0b1527);
      --card-surface-strong: linear-gradient(135deg, rgba(96, 165, 250, .12), rgba(15, 23, 42, .92));
      --card-border: #22314a;
      --card-shadow-soft: 0 16px 34px rgba(0, 0, 0, .22);
      --card-shadow-strong: 0 22px 46px rgba(0, 0, 0, .30);
      --card-highlight: rgba(96, 165, 250, .16);
      --table-alt: #0e1626;
      --table-hover: #122036;
      --shadow: 0 18px 40px rgba(0, 0, 0, .34);
      --focus-ring: 0 0 0 3px rgba(96, 165, 250, .22);
    }
    :root[data-theme="forest"],
    :root[data-theme="dongbei-rain"],
    :root[data-theme="rainbow-rgb"],
    :root[data-theme="bleach-tybw"],
    :root[data-theme="eva"],
    :root[data-theme="starry-night"],
    :root[data-theme="monet"],
    :root[data-theme="qingming-scroll"],
    :root[data-theme="cezanne"],
    :root[data-theme="sisley"],
    :root[data-theme="pissarro"],
    :root[data-theme="morandi"],
    :root[data-theme="gauguin"],
    :root[data-theme="matisse"],
    :root[data-theme="qi-baishi"],
    :root[data-theme="p-site"],
    :root[data-theme="sakura-mist"],
    :root[data-theme="healing-sea-blue"],
    :root[data-theme="mint-tea-green"],
    :root[data-theme="neon-track"],
    :root[data-theme="cream-berry-purple"],
    :root[data-theme="orange-slate"],
    :root[data-theme="seafoam-apricot"],
    :root[data-theme="klein-gold"],
    :root[data-theme="honey-sunset"],
    :root[data-theme="crimson-ivory"],
    :root[data-theme="midnight"] {
      color-scheme: var(--sv-color-scheme);
      --bg: var(--sv-bg);
      --surface: var(--sv-bg-deep);
      --panel: var(--sv-surface);
      --panel-2: var(--sv-surface-dark);
      --text: var(--sv-ink);
      --muted: var(--sv-muted);
      --line: color-mix(in srgb, var(--sv-muted) 28%, var(--sv-bg-deep));
      --accent: var(--sv-accent);
      --accent-2: var(--sv-accent-strong-ui, var(--sv-accent-strong));
      --button-text: var(--sv-on-accent);
      --danger: var(--sv-danger);
      --danger-text: var(--sv-on-danger, var(--sv-on-accent));
      --success: var(--sv-signal);
      --warning: var(--sv-warning, color-mix(in srgb, var(--sv-signal) 52%, var(--sv-danger)));
      --sidebar: color-mix(in srgb, var(--sv-bg-deep) 74%, var(--sv-surface));
      --nav-text: var(--sv-muted);
      --tab-text: color-mix(in srgb, var(--sv-muted) 72%, var(--sv-ink));
      --field-bg: var(--sv-surface);
      --field-bg-soft: var(--sv-surface-dark);
      --chip-bg: var(--sv-surface);
      --accent-soft: color-mix(in srgb, var(--sv-accent) 12%, var(--sv-surface));
      --accent-soft-hover: color-mix(in srgb, var(--sv-accent) 16%, var(--sv-surface));
      --accent-soft-active: color-mix(in srgb, var(--sv-accent) 22%, var(--sv-surface));
      --accent-soft-line: color-mix(in srgb, var(--sv-accent) 34%, var(--sv-bg-deep));
      --accent-active-line: color-mix(in srgb, var(--sv-accent) 48%, var(--sv-bg-deep));
      --danger-bg: color-mix(in srgb, var(--sv-danger) 12%, var(--sv-surface));
      --danger-line: color-mix(in srgb, var(--sv-danger) 28%, var(--sv-surface-dark));
      --loading-from: var(--sv-surface);
      --loading-to: var(--sv-surface-dark);
      --overlay: var(--sv-overlay);
      --scroll-thumb: color-mix(in srgb, var(--sv-muted) 58%, var(--sv-accent));
      --scroll-track: color-mix(in srgb, var(--sv-bg-deep) 46%, transparent);
      --dropdown-scroll-track: color-mix(in srgb, var(--sv-bg-deep) 72%, var(--sv-surface));
      --dropdown-scroll-thumb: color-mix(in srgb, var(--sv-accent) 42%, transparent);
      --dropdown-scroll-thumb-hover: color-mix(in srgb, var(--sv-accent) 60%, transparent);
      --dropdown-scroll-thumb-active: color-mix(in srgb, var(--sv-accent) 78%, transparent);
      --dropdown-scroll-shadow: color-mix(in srgb, var(--sv-accent) 18%, transparent);
      --check-bg: linear-gradient(180deg, var(--sv-surface), var(--sv-surface-dark));
      --check-border: color-mix(in srgb, var(--sv-muted) 48%, var(--sv-bg-deep));
      --check-border-hover: var(--sv-accent);
      --check-checked: linear-gradient(180deg, var(--sv-accent), var(--sv-accent-strong-ui, var(--sv-accent-strong)));
      --check-checked-border: var(--sv-accent);
      --check-tick: var(--sv-on-accent);
      --check-shadow: color-mix(in srgb, var(--sv-accent) 18%, transparent);
      --control-hover-bg: linear-gradient(180deg, color-mix(in srgb, var(--sv-accent) 10%, var(--sv-surface)), color-mix(in srgb, var(--sv-accent) 16%, var(--sv-surface-dark)));
      --control-hover-border: color-mix(in srgb, var(--sv-accent) 48%, var(--sv-bg-deep));
      --control-hover-text: var(--sv-accent);
      --control-active-bg: linear-gradient(135deg, var(--sv-accent), var(--sv-accent-strong-ui, var(--sv-accent-strong)));
      --control-active-border: var(--sv-accent);
      --control-active-text: var(--sv-on-accent);
      --control-active-shadow: 0 12px 28px color-mix(in srgb, var(--sv-accent) 24%, transparent);
      --field-border: color-mix(in srgb, var(--sv-muted) 30%, var(--sv-bg-deep));
      --field-border-hover: color-mix(in srgb, var(--sv-accent) 54%, var(--sv-bg-deep));
      --field-surface: linear-gradient(180deg, var(--sv-surface), color-mix(in srgb, var(--sv-bg) 58%, var(--sv-surface)));
      --field-surface-soft: linear-gradient(180deg, color-mix(in srgb, var(--sv-surface) 72%, var(--sv-surface-dark)), var(--sv-surface-dark));
      --field-shadow: inset 0 1px 0 var(--sv-inner-highlight), 0 8px 22px var(--sv-shadow-soft);
      --field-shadow-hover: inset 0 1px 0 var(--sv-inner-highlight), 0 12px 28px color-mix(in srgb, var(--sv-accent) 12%, transparent);
      --help-bg: color-mix(in srgb, var(--sv-accent) 10%, var(--sv-surface));
      --help-border: color-mix(in srgb, var(--sv-accent) 24%, var(--sv-bg-deep));
      --help-text: color-mix(in srgb, var(--sv-muted) 64%, var(--sv-ink));
      --status-info-bg: linear-gradient(180deg, var(--sv-surface), color-mix(in srgb, var(--sv-bg) 72%, var(--sv-surface-dark)));
      --status-info-border: color-mix(in srgb, var(--sv-muted) 24%, var(--sv-bg-deep));
      --status-info-text: color-mix(in srgb, var(--sv-muted) 72%, var(--sv-ink));
      --status-success-bg: linear-gradient(180deg, color-mix(in srgb, var(--sv-signal) 10%, var(--sv-surface)), color-mix(in srgb, var(--sv-signal) 14%, var(--sv-surface-dark)));
      --status-success-border: color-mix(in srgb, var(--sv-signal) 34%, var(--sv-surface-dark));
      --status-success-text: color-mix(in srgb, var(--sv-signal) 68%, var(--sv-ink));
      --status-error-bg: linear-gradient(180deg, color-mix(in srgb, var(--sv-danger) 10%, var(--sv-surface)), color-mix(in srgb, var(--sv-danger) 14%, var(--sv-surface-dark)));
      --status-error-border: color-mix(in srgb, var(--sv-danger) 34%, var(--sv-surface-dark));
      --status-error-text: color-mix(in srgb, var(--sv-danger) 72%, var(--sv-ink));
      --status-accent-shadow: inset 4px 0 0 color-mix(in srgb, var(--sv-accent) 28%, transparent);
      --card-surface: linear-gradient(180deg, var(--sv-surface), color-mix(in srgb, var(--sv-bg) 66%, var(--sv-surface)));
      --card-surface-soft: linear-gradient(180deg, color-mix(in srgb, var(--sv-surface) 82%, var(--sv-bg)), var(--sv-surface-dark));
      --card-surface-strong: linear-gradient(135deg, color-mix(in srgb, var(--sv-accent) 10%, var(--sv-surface)), color-mix(in srgb, var(--sv-bg) 76%, var(--sv-surface)));
      --card-border: color-mix(in srgb, var(--sv-muted) 24%, var(--sv-bg-deep));
      --card-shadow-soft: 0 10px 28px var(--sv-shadow-soft);
      --card-shadow-strong: 0 18px 38px var(--sv-shadow-strong);
      --card-highlight: color-mix(in srgb, var(--sv-accent) 12%, transparent);
      --table-alt: color-mix(in srgb, var(--sv-bg) 76%, var(--sv-surface));
      --table-hover: color-mix(in srgb, var(--sv-accent) 12%, var(--sv-surface));
      --shadow: 0 6px 18px var(--sv-shadow-soft);
      --focus-ring: 0 0 0 3px color-mix(in srgb, var(--sv-accent) 20%, transparent);
    }
    :root[data-theme="forest"] {
      --sv-color-scheme: light;
      --sv-accent: #2f6b3f;
      --sv-accent-strong: #1f4d2b;
      --sv-signal: #0f766e;
      --sv-danger: #b54432;
      --sv-warning: #b7791f;
      --sv-bg: #f3f7f0;
      --sv-bg-deep: #e6efe2;
      --sv-ink: #172313;
      --sv-muted: #53624d;
      --sv-surface: #ffffff;
      --sv-surface-dark: #e6efe2;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(23, 35, 19, .34);
      --sv-inner-highlight: rgba(255, 255, 255, .82);
      --sv-shadow-soft: rgba(23, 35, 19, .08);
      --sv-shadow-strong: rgba(23, 35, 19, .14);
    }
    :root[data-theme="midnight"] {
      --sv-color-scheme: dark;
      --sv-accent: #4f8cff;
      --sv-accent-strong: #7aa7ff;
      --sv-signal: #4fd1c5;
      --sv-danger: #fb7185;
      --sv-warning: #fbbf24;
      --sv-bg: #07111f;
      --sv-bg-deep: #020617;
      --sv-ink: #eaf2ff;
      --sv-muted: #9fb1c8;
      --sv-surface: #0e1b2e;
      --sv-surface-dark: #14243a;
      --sv-on-accent: #06101f;
      --sv-overlay: rgba(2, 6, 23, .72);
      --sv-inner-highlight: rgba(255, 255, 255, .04);
      --sv-shadow-soft: rgba(0, 0, 0, .24);
      --sv-shadow-strong: rgba(0, 0, 0, .34);
    }
    :root[data-theme="monet"] {
      --sv-color-scheme: light;
      --sv-accent: #6b9f8a;
      --sv-accent-strong: #4e806f;
      --sv-signal: #5d927d;
      --sv-danger: #b85f73;
      --sv-warning: #a57940;
      --sv-bg: #eef4f2;
      --sv-bg-deep: #dcebe8;
      --sv-ink: #243a3a;
      --sv-muted: #60706b;
      --sv-surface: #fffffa;
      --sv-surface-dark: #e4efeb;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(36, 58, 58, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .86);
      --sv-shadow-soft: rgba(36, 58, 58, .08);
      --sv-shadow-strong: rgba(36, 58, 58, .14);
    }
    :root[data-theme="morandi"] {
      --sv-color-scheme: light;
      --sv-accent: #8d8580;
      --sv-accent-strong: #6f6662;
      --sv-signal: #748375;
      --sv-danger: #a06b68;
      --sv-warning: #9a784f;
      --sv-bg: #eeece8;
      --sv-bg-deep: #d9d5cf;
      --sv-ink: #2f2d2b;
      --sv-muted: #66615c;
      --sv-surface: #faf8f4;
      --sv-surface-dark: #dfdbd4;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(47, 45, 43, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .82);
      --sv-shadow-soft: rgba(47, 45, 43, .08);
      --sv-shadow-strong: rgba(47, 45, 43, .14);
    }
    :root[data-theme="sakura-mist"] {
      --sv-color-scheme: light;
      --sv-accent: #535369;
      --sv-accent-strong: #3d3d52;
      --sv-signal: #767692;
      --sv-danger: #c9617d;
      --sv-warning: #b7796b;
      --sv-bg: #ffe3ee;
      --sv-bg-deep: #f6d7e4;
      --sv-ink: #272333;
      --sv-muted: #6f6474;
      --sv-surface: #fffafd;
      --sv-surface-dark: #eadae3;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(39, 35, 51, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .84);
      --sv-shadow-soft: rgba(39, 35, 51, .08);
      --sv-shadow-strong: rgba(39, 35, 51, .14);
    }
    :root[data-theme="healing-sea-blue"] {
      --sv-color-scheme: light;
      --sv-accent: #0081ff;
      --sv-accent-strong: #005ec4;
      --sv-signal: #7b7a00;
      --sv-danger: #d34f4f;
      --sv-warning: #a79f00;
      --sv-bg: #eef7ff;
      --sv-bg-deep: #d8ecff;
      --sv-ink: #08204a;
      --sv-muted: #4d6280;
      --sv-surface: #ffffff;
      --sv-surface-dark: #dbefff;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(8, 32, 74, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .86);
      --sv-shadow-soft: rgba(8, 32, 74, .08);
      --sv-shadow-strong: rgba(8, 32, 74, .14);
    }
    :root[data-theme="mint-tea-green"] {
      --sv-color-scheme: light;
      --sv-accent: #178b85;
      --sv-accent-strong: #0f6d68;
      --sv-signal: #4f8f4f;
      --sv-danger: #b85f73;
      --sv-warning: #a57940;
      --sv-bg: #eefaf7;
      --sv-bg-deep: #d0efea;
      --sv-ink: #173a36;
      --sv-muted: #55706b;
      --sv-surface: #fffffa;
      --sv-surface-dark: #dff3ee;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(23, 58, 54, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .86);
      --sv-shadow-soft: rgba(23, 58, 54, .08);
      --sv-shadow-strong: rgba(23, 58, 54, .14);
    }
    :root[data-theme="klein-gold"] {
      --sv-color-scheme: light;
      --sv-accent: #002fa7;
      --sv-accent-strong: #ffcf14;
      --sv-accent-strong-ui: #005ec4;
      --sv-signal: #967800;
      --sv-danger: #e05252;
      --sv-warning: #e6b800;
      --sv-bg: #f5f8ff;
      --sv-bg-deep: #d9e5ff;
      --sv-ink: #061a4d;
      --sv-muted: #52617b;
      --sv-surface: #ffffff;
      --sv-surface-dark: #e8efff;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(6, 26, 77, .34);
      --sv-inner-highlight: rgba(255, 255, 255, .86);
      --sv-shadow-soft: rgba(6, 26, 77, .08);
      --sv-shadow-strong: rgba(6, 26, 77, .14);
    }
    :root[data-theme="dongbei-rain"] {
      --sv-color-scheme: dark;
      --sv-accent: #c9162f;
      --sv-accent-strong: #f2f0e9;
      --sv-accent-strong-ui: #8f1022;
      --sv-signal: #3f7f35;
      --sv-danger: #e34f86;
      --sv-warning: #d28b37;
      --sv-bg: #4d2f1f;
      --sv-bg-deep: #2f1c14;
      --sv-ink: #fffaf0;
      --sv-muted: #e2cfc0;
      --sv-surface: #632d27;
      --sv-surface-dark: #5b3022;
      --sv-on-accent: #fffaf0;
      --sv-overlay: rgba(47, 28, 20, .74);
      --sv-inner-highlight: rgba(255, 255, 255, .05);
      --sv-shadow-soft: rgba(0, 0, 0, .24);
      --sv-shadow-strong: rgba(0, 0, 0, .34);
    }
    :root[data-theme="rainbow-rgb"] {
      --sv-color-scheme: dark;
      --sv-accent: #00d4ff;
      --sv-accent-strong: #ffffff;
      --sv-accent-strong-ui: #3b82f6;
      --sv-signal: #00ff85;
      --sv-danger: #ff3366;
      --sv-warning: #ff8a00;
      --sv-bg: #070711;
      --sv-bg-deep: #02040d;
      --sv-ink: #f8fbff;
      --sv-muted: #b9c7da;
      --sv-surface: #0a0e1c;
      --sv-surface-dark: #101427;
      --sv-on-accent: #02040d;
      --sv-overlay: rgba(2, 4, 13, .76);
      --sv-inner-highlight: rgba(255, 255, 255, .04);
      --sv-shadow-soft: rgba(0, 0, 0, .25);
      --sv-shadow-strong: rgba(0, 0, 0, .36);
    }
    :root[data-theme="bleach-tybw"] {
      --sv-color-scheme: dark;
      --sv-accent: #e6397c;
      --sv-accent-strong: #ff78ad;
      --sv-signal: #f8f4f7;
      --sv-danger: #ff477e;
      --sv-warning: #f0b54c;
      --sv-bg: #1a1a1d;
      --sv-bg-deep: #0d0d10;
      --sv-ink: #fff7fb;
      --sv-muted: #c9b8c1;
      --sv-surface: #1f1f24;
      --sv-surface-dark: #141418;
      --sv-on-accent: #fff7fb;
      --sv-overlay: rgba(13, 13, 16, .76);
      --sv-inner-highlight: rgba(255, 255, 255, .04);
      --sv-shadow-soft: rgba(0, 0, 0, .25);
      --sv-shadow-strong: rgba(0, 0, 0, .36);
    }
    :root[data-theme="eva"] {
      --sv-color-scheme: dark;
      --sv-accent: #b7ff2a;
      --sv-accent-strong: #8b5cf6;
      --sv-signal: #ff9f1c;
      --sv-danger: #ff4fb3;
      --sv-warning: #ff9f1c;
      --sv-bg: #090812;
      --sv-bg-deep: #030208;
      --sv-ink: #f6ffe8;
      --sv-muted: #d3c6ff;
      --sv-surface: #120e22;
      --sv-surface-dark: #0c0918;
      --sv-on-accent: #090812;
      --sv-overlay: rgba(3, 2, 8, .78);
      --sv-inner-highlight: rgba(255, 255, 255, .04);
      --sv-shadow-soft: rgba(0, 0, 0, .26);
      --sv-shadow-strong: rgba(0, 0, 0, .38);
    }
    :root[data-theme="starry-night"] {
      --sv-color-scheme: dark;
      --sv-accent: #f6c945;
      --sv-accent-strong: #ffe27a;
      --sv-signal: #5eead4;
      --sv-danger: #fb7185;
      --sv-warning: #f6c945;
      --sv-bg: #07142e;
      --sv-bg-deep: #030817;
      --sv-ink: #f8efcb;
      --sv-muted: #b8c7e6;
      --sv-surface: #0d1f3f;
      --sv-surface-dark: #162d58;
      --sv-on-accent: #07142e;
      --sv-overlay: rgba(3, 8, 23, .76);
      --sv-inner-highlight: rgba(255, 255, 255, .04);
      --sv-shadow-soft: rgba(0, 0, 0, .25);
      --sv-shadow-strong: rgba(0, 0, 0, .36);
    }
    :root[data-theme="qingming-scroll"] {
      --sv-color-scheme: light;
      --sv-accent: #2f6673;
      --sv-accent-strong: #1e4c57;
      --sv-signal: #5f7f4f;
      --sv-danger: #b34a32;
      --sv-warning: #9b7136;
      --sv-bg: #f3e8d2;
      --sv-bg-deep: #e4d2ad;
      --sv-ink: #2a241b;
      --sv-muted: #6d6253;
      --sv-surface: #fff9eb;
      --sv-surface-dark: #eadbbb;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(42, 36, 27, .34);
      --sv-inner-highlight: rgba(255, 255, 255, .78);
      --sv-shadow-soft: rgba(42, 36, 27, .09);
      --sv-shadow-strong: rgba(42, 36, 27, .15);
    }
    :root[data-theme="cezanne"] {
      --sv-color-scheme: light;
      --sv-accent: #8f4f2f;
      --sv-accent-strong: #6f3a22;
      --sv-signal: #5e7a4d;
      --sv-danger: #a64735;
      --sv-warning: #9b7136;
      --sv-bg: #efe6d8;
      --sv-bg-deep: #d7c4aa;
      --sv-ink: #2f241d;
      --sv-muted: #685b4f;
      --sv-surface: #fff9ee;
      --sv-surface-dark: #e0cfb6;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(47, 36, 29, .34);
      --sv-inner-highlight: rgba(255, 255, 255, .78);
      --sv-shadow-soft: rgba(47, 36, 29, .09);
      --sv-shadow-strong: rgba(47, 36, 29, .15);
    }
    :root[data-theme="sisley"] {
      --sv-color-scheme: light;
      --sv-accent: #5f8fa8;
      --sv-accent-strong: #3f718a;
      --sv-signal: #6b946d;
      --sv-danger: #a85d55;
      --sv-warning: #9a784f;
      --sv-bg: #eef4ef;
      --sv-bg-deep: #d7e5dc;
      --sv-ink: #24343a;
      --sv-muted: #5d6d70;
      --sv-surface: #fafeff;
      --sv-surface-dark: #dcebe3;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(36, 52, 58, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .84);
      --sv-shadow-soft: rgba(36, 52, 58, .08);
      --sv-shadow-strong: rgba(36, 52, 58, .14);
    }
    :root[data-theme="pissarro"] {
      --sv-color-scheme: light;
      --sv-accent: #7f8f4e;
      --sv-accent-strong: #5f6f35;
      --sv-signal: #607e4a;
      --sv-danger: #a05742;
      --sv-warning: #9a784f;
      --sv-bg: #f1eddf;
      --sv-bg-deep: #ded5ba;
      --sv-ink: #2d2a1e;
      --sv-muted: #675f4c;
      --sv-surface: #fffcef;
      --sv-surface-dark: #e5ddc4;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(45, 42, 30, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .82);
      --sv-shadow-soft: rgba(45, 42, 30, .09);
      --sv-shadow-strong: rgba(45, 42, 30, .15);
    }
    :root[data-theme="gauguin"] {
      --sv-color-scheme: light;
      --sv-accent: #b65f2a;
      --sv-accent-strong: #8f431f;
      --sv-signal: #247a72;
      --sv-danger: #b33b4b;
      --sv-warning: #b65f2a;
      --sv-bg: #f1e0c2;
      --sv-bg-deep: #d6ad73;
      --sv-ink: #2c2117;
      --sv-muted: #6e5944;
      --sv-surface: #fff6e0;
      --sv-surface-dark: #e8c790;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(44, 33, 23, .34);
      --sv-inner-highlight: rgba(255, 255, 255, .78);
      --sv-shadow-soft: rgba(44, 33, 23, .10);
      --sv-shadow-strong: rgba(44, 33, 23, .16);
    }
    :root[data-theme="matisse"] {
      --sv-color-scheme: light;
      --sv-accent: #2468c9;
      --sv-accent-strong: #174d9b;
      --sv-signal: #1f8f78;
      --sv-danger: #d33732;
      --sv-warning: #b7791f;
      --sv-bg: #f4efe5;
      --sv-bg-deep: #d8e0e8;
      --sv-ink: #18243a;
      --sv-muted: #536176;
      --sv-surface: #fffcf4;
      --sv-surface-dark: #e2e8ef;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(24, 36, 58, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .84);
      --sv-shadow-soft: rgba(24, 36, 58, .08);
      --sv-shadow-strong: rgba(24, 36, 58, .14);
    }
    :root[data-theme="qi-baishi"] {
      --sv-color-scheme: light;
      --sv-accent: #b7352d;
      --sv-accent-strong: #8d251f;
      --sv-signal: #386a55;
      --sv-danger: #9f2f2a;
      --sv-warning: #9a784f;
      --sv-bg: #f6f0e3;
      --sv-bg-deep: #e3d7c1;
      --sv-ink: #211f1b;
      --sv-muted: #635c52;
      --sv-surface: #fffcf3;
      --sv-surface-dark: #e8dec9;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(33, 31, 27, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .84);
      --sv-shadow-soft: rgba(33, 31, 27, .08);
      --sv-shadow-strong: rgba(33, 31, 27, .14);
    }
    :root[data-theme="p-site"] {
      --sv-color-scheme: dark;
      --sv-accent: #ff9900;
      --sv-accent-strong: #f2b400;
      --sv-signal: #f2b400;
      --sv-danger: #ff4d4d;
      --sv-warning: #f2b400;
      --sv-bg: #050505;
      --sv-bg-deep: #000000;
      --sv-ink: #f7f7f7;
      --sv-muted: #b8b8b8;
      --sv-surface: #161616;
      --sv-surface-dark: #101010;
      --sv-on-accent: #050505;
      --sv-overlay: rgba(0, 0, 0, .78);
      --sv-inner-highlight: rgba(255, 255, 255, .04);
      --sv-shadow-soft: rgba(0, 0, 0, .28);
      --sv-shadow-strong: rgba(0, 0, 0, .40);
    }
    :root[data-theme="neon-track"] {
      --sv-color-scheme: dark;
      --sv-accent: #00fd00;
      --sv-accent-strong: #0947fe;
      --sv-signal: #2cff5a;
      --sv-danger: #ff3d7a;
      --sv-warning: #a3ff12;
      --sv-bg: #07180b;
      --sv-bg-deep: #020a04;
      --sv-ink: #efffee;
      --sv-muted: #b7d7c1;
      --sv-surface: #09180f;
      --sv-surface-dark: #0d2316;
      --sv-on-accent: #020a04;
      --sv-overlay: rgba(2, 10, 4, .78);
      --sv-inner-highlight: rgba(255, 255, 255, .04);
      --sv-shadow-soft: rgba(0, 0, 0, .28);
      --sv-shadow-strong: rgba(0, 0, 0, .40);
    }
    :root[data-theme="cream-berry-purple"] {
      --sv-color-scheme: light;
      --sv-accent: #652c97;
      --sv-accent-strong: #4c1f74;
      --sv-signal: #c85c8b;
      --sv-danger: #b63f65;
      --sv-warning: #a57940;
      --sv-bg: #fff0f2;
      --sv-bg-deep: #f3d7df;
      --sv-ink: #2d183a;
      --sv-muted: #745d7e;
      --sv-surface: #fffafb;
      --sv-surface-dark: #f7dfe7;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(45, 24, 58, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .84);
      --sv-shadow-soft: rgba(45, 24, 58, .08);
      --sv-shadow-strong: rgba(45, 24, 58, .14);
    }
    :root[data-theme="orange-slate"] {
      --sv-color-scheme: dark;
      --sv-accent: #ff7400;
      --sv-accent-strong: #ff9a3d;
      --sv-signal: #7ad0b1;
      --sv-danger: #ff5f55;
      --sv-warning: #ff9a3d;
      --sv-bg: #172728;
      --sv-bg-deep: #0d1718;
      --sv-ink: #fff2e5;
      --sv-muted: #c8d0cc;
      --sv-surface: #2b3c3d;
      --sv-surface-dark: #213132;
      --sv-on-accent: #172728;
      --sv-overlay: rgba(13, 23, 24, .76);
      --sv-inner-highlight: rgba(255, 255, 255, .04);
      --sv-shadow-soft: rgba(0, 0, 0, .25);
      --sv-shadow-strong: rgba(0, 0, 0, .36);
    }
    :root[data-theme="seafoam-apricot"] {
      --sv-color-scheme: light;
      --sv-accent: #01847f;
      --sv-accent-strong: #006b67;
      --sv-signal: #d9775f;
      --sv-danger: #c74d5a;
      --sv-warning: #d9775f;
      --sv-bg: #effaf7;
      --sv-bg-deep: #d3eee9;
      --sv-ink: #123936;
      --sv-muted: #5c706d;
      --sv-surface: #fffbf7;
      --sv-surface-dark: #f4ded6;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(18, 57, 54, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .84);
      --sv-shadow-soft: rgba(18, 57, 54, .08);
      --sv-shadow-strong: rgba(18, 57, 54, .14);
    }
    :root[data-theme="honey-sunset"] {
      --sv-color-scheme: light;
      --sv-accent: #ff6067;
      --sv-accent-strong: #d9434a;
      --sv-signal: #a47600;
      --sv-danger: #d9434a;
      --sv-warning: #d89d00;
      --sv-bg: #fff7d6;
      --sv-bg-deep: #ffeaa0;
      --sv-ink: #3b2b19;
      --sv-muted: #76694d;
      --sv-surface: #fffcee;
      --sv-surface-dark: #ffe8a3;
      --sv-on-accent: #3b2b19;
      --sv-overlay: rgba(59, 43, 25, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .78);
      --sv-shadow-soft: rgba(59, 43, 25, .09);
      --sv-shadow-strong: rgba(59, 43, 25, .15);
    }
    :root[data-theme="crimson-ivory"] {
      --sv-color-scheme: light;
      --sv-accent: #990033;
      --sv-accent-strong: #740026;
      --sv-signal: #7f6a4f;
      --sv-danger: #b52a3f;
      --sv-warning: #9a784f;
      --sv-bg: #f4eee5;
      --sv-bg-deep: #ddcdb7;
      --sv-ink: #341019;
      --sv-muted: #6f5b57;
      --sv-surface: #fffaf2;
      --sv-surface-dark: #e8dac8;
      --sv-on-accent: #ffffff;
      --sv-overlay: rgba(52, 16, 25, .32);
      --sv-inner-highlight: rgba(255, 255, 255, .82);
      --sv-shadow-soft: rgba(52, 16, 25, .08);
      --sv-shadow-strong: rgba(52, 16, 25, .14);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Fira Sans", Inter, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
      min-height: 100vh;
      overflow: hidden;
    }
    .app-shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: minmax(260px, 300px) minmax(0, 1fr);
      background: var(--surface);
    }
    .side-nav {
      border-right: 1px solid var(--line);
      background: var(--sidebar);
      display: flex;
      flex-direction: column;
      min-height: 100vh;
      padding: 22px 18px;
      overflow: auto;
    }
    .side-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 30px;
      padding: 0 6px;
    }
    .side-brand strong {
      display: block;
      font-size: 17px;
      line-height: 1.2;
    }
    .side-brand span {
      color: var(--muted);
      font-size: 12px;
    }
    .nav-list {
      display: grid;
      gap: 4px;
    }
    .nav-item {
      display: flex;
      align-items: center;
      gap: 12px;
      min-height: 44px;
      padding: 0 14px;
      border: 1px solid transparent;
      color: var(--nav-text);
      border-radius: var(--radius-sm);
      font-size: 14px;
      font-weight: 600;
      transition: background-color var(--motion-fast) ease, border-color var(--motion-fast) ease, color var(--motion-fast) ease, box-shadow var(--motion-fast) ease, transform var(--motion-fast) ease;
    }
    button.nav-item,
    .tab-pill {
      width: 100%;
      border: 1px solid transparent;
      background: transparent;
      color: var(--nav-text);
      text-align: left;
      justify-content: flex-start;
    }
    .tab-pill {
      width: auto;
      height: 34px;
      padding: 0 12px;
      color: var(--tab-text);
      font-size: 14px;
      font-weight: 700;
      border-radius: 999px;
      transition: color var(--motion-fast) ease, border-color var(--motion-fast) ease, background-color var(--motion-fast) ease, box-shadow var(--motion-fast) ease, opacity var(--motion-fast) ease;
    }
    .tab-pill.active {
      color: var(--control-active-text);
      border-color: var(--control-active-border);
      background: var(--control-active-bg);
      box-shadow: var(--control-active-shadow);
    }
    .nav-item.active {
      color: var(--control-active-text);
      border-color: var(--control-active-border);
      background: var(--control-active-bg);
      box-shadow: var(--control-active-shadow);
    }
    .nav-footer {
      margin-top: auto;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      display: grid;
      gap: 4px;
    }
    .mark {
      width: 40px;
      height: 40px;
      display: grid;
      place-items: center;
      overflow: hidden;
      background: transparent;
      border-radius: 8px;
    }
    .mark img {
      width: 82%;
      height: 82%;
      display: block;
      object-fit: contain;
    }
    .content-shell {
      min-width: 0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    header {
      height: 64px;
      flex: 0 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      box-shadow: 0 1px 3px rgba(15, 23, 42, .04);
      z-index: 5;
    }
    .top-left {
      display: flex;
      align-items: center;
      gap: 34px;
    }
    .brand {
      font-weight: 800;
      font-size: 18px;
      letter-spacing: -0.01em;
    }
    .top-tabs {
      display: flex;
      align-items: center;
      gap: 24px;
      color: var(--tab-text);
      font-size: 14px;
      font-weight: 600;
      overflow-x: auto;
      scrollbar-width: none;
      max-width: 100%;
    }
    .top-tabs::-webkit-scrollbar {
      display: none;
    }
    .top-tabs span:first-child {
      color: var(--accent);
    }
    .header-meta {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
    }
    .header-task {
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .header-task strong {
      color: var(--text);
      font-size: 14px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--chip-bg);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .top-search {
      width: min(320px, 32vw);
      height: 40px;
      border: 1px solid transparent;
      border-radius: var(--radius-sm);
      background: var(--field-bg-soft);
      padding: 0 14px;
      color: var(--text);
      transition: border-color var(--motion-fast) ease, box-shadow var(--motion-fast) ease, background-color var(--motion-fast) ease;
    }
    .top-search:focus {
      border-color: var(--accent-2);
      box-shadow: var(--focus-ring);
      background: var(--field-bg);
    }
    .ghost-select,
    .ghost-file {
      position: relative;
      display: grid;
      gap: 6px;
    }
    .ghost-select .control,
    .ghost-file .control,
    .ghost-input,
    .ghost-textarea {
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: var(--field-bg);
      color: var(--text);
      padding: 0 12px;
      font: inherit;
      outline: none;
      transition: border-color var(--motion-fast) ease, box-shadow var(--motion-fast) ease, background-color var(--motion-fast) ease, transform var(--motion-fast) ease;
    }
    .ghost-select .control,
    .ghost-file .control {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      cursor: pointer;
    }
    .ghost-select.open .control,
    .ghost-file.open .control {
      border-color: var(--accent);
      box-shadow: var(--focus-ring);
    }
    .ghost-select .control:hover,
    .ghost-file .control:hover {
      border-color: var(--accent);
      box-shadow: var(--focus-ring);
    }
    .ghost-select .value,
    .ghost-file .value {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text);
    }
    .ghost-select .chevron,
    .ghost-file .icon {
      color: var(--muted);
      flex: 0 0 auto;
    }
    .mode-switch {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }
    .mode-switch button {
      justify-content: flex-start;
      min-height: 46px;
      padding: 0 12px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: var(--field-bg);
      color: var(--text);
      box-shadow: none;
    }
    .mode-switch button.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent);
      box-shadow: var(--focus-ring);
    }
    .mode-dependent[hidden] {
      display: none !important;
    }
    .header-meta .ui-locale-select {
      width: 190px;
    }
    .header-meta .ui-locale-select .control {
      min-height: 40px;
      background: var(--field-bg-soft);
    }
    .ghost-menu {
      position: absolute;
      left: 0;
      right: 0;
      top: calc(100% + 6px);
      z-index: 30;
      display: grid;
      gap: 4px;
      max-height: 280px;
      overflow: auto;
      padding: 6px 8px 6px 6px;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      background: var(--field-bg);
      box-shadow: 0 18px 40px rgba(15, 23, 42, .16);
      scrollbar-width: thin;
      scrollbar-color: var(--dropdown-scroll-thumb) var(--dropdown-scroll-track);
      scrollbar-gutter: stable;
      overscroll-behavior: contain;
    }
    .ghost-menu::-webkit-scrollbar {
      width: 14px;
      height: 14px;
    }
    .ghost-menu::-webkit-scrollbar-track {
      margin: 6px 0;
      border-radius: 999px;
      background: var(--dropdown-scroll-track);
      box-shadow: inset 0 0 0 1px var(--line);
    }
    .ghost-menu::-webkit-scrollbar-thumb {
      min-height: 40px;
      border: 3px solid transparent;
      border-radius: 999px;
      background: linear-gradient(180deg, var(--dropdown-scroll-thumb-hover), var(--dropdown-scroll-thumb));
      background-clip: padding-box;
      box-shadow: inset 0 0 0 1px var(--dropdown-scroll-shadow);
    }
    .ghost-menu::-webkit-scrollbar-thumb:hover {
      background: linear-gradient(180deg, var(--dropdown-scroll-thumb-hover), var(--dropdown-scroll-thumb-active));
      background-clip: padding-box;
    }
    .ghost-menu::-webkit-scrollbar-thumb:active {
      background: linear-gradient(180deg, var(--dropdown-scroll-thumb-active), var(--dropdown-scroll-thumb-active));
      background-clip: padding-box;
    }
    .ghost-menu::-webkit-scrollbar-corner {
      background: transparent;
    }
    .ghost-menu[hidden] {
      display: none;
    }
    .locale-control {
      position: relative;
    }
    .locale-control-input {
      display: none;
      width: 100%;
      min-width: 0;
      min-height: 36px;
      height: 36px;
      border: 0;
      border-radius: 0;
      background: transparent;
      color: var(--text);
      padding: 0;
      font: inherit;
      outline: none;
      box-shadow: none;
      -webkit-appearance: none;
      appearance: none;
    }
    .locale-select.open .locale-control-value {
      display: none;
    }
    .locale-select.open .locale-control-input {
      display: block;
    }
    .locale-control-input:hover,
    .locale-control-input:focus,
    .locale-control-input:focus-visible {
      border: 0;
      background: transparent;
      box-shadow: none;
      outline: none;
    }
    .locale-control-input::-webkit-search-cancel-button {
      cursor: pointer;
    }
    .locale-control-input::-webkit-search-decoration,
    .locale-control-input::-webkit-search-results-button,
    .locale-control-input::-webkit-search-results-decoration {
      -webkit-appearance: none;
      appearance: none;
    }
    .ghost-options {
      display: grid;
      gap: 4px;
    }
    .ghost-empty {
      padding: 10px 12px;
      border: 1px dashed var(--line);
      border-radius: var(--radius-sm);
      color: var(--muted);
      background: var(--field-bg-soft);
      font-size: 12px;
      line-height: 1.45;
    }
    .ghost-option {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 38px;
      padding: 8px 10px;
      border: 1px solid transparent;
      border-radius: var(--radius-sm);
      background: var(--field-bg);
      color: var(--text);
      cursor: pointer;
      font: inherit;
      text-align: left;
      transition: background-color var(--motion-fast) ease, border-color var(--motion-fast) ease, color var(--motion-fast) ease;
    }
    .ghost-option:hover {
      background: var(--accent-soft-hover);
      border-color: var(--accent-soft-line);
      color: var(--accent);
      transform: none;
    }
    .ghost-option.active {
      background: var(--accent-soft-active);
      border-color: var(--accent-active-line);
      color: var(--accent);
    }
    .ghost-option strong {
      font-size: 13px;
      font-weight: 700;
    }
    .ghost-option span {
      color: var(--muted);
      font-size: 12px;
    }
    .ghost-select select,
    .ghost-file input[type="file"] {
      position: absolute;
      inset: 0;
      opacity: 0;
      cursor: pointer;
      width: 100%;
      height: 100%;
      padding: 0;
      border: 0;
    }
    .ghost-select select {
      width: 100%;
      height: 100%;
    }
    .ghost-select select {
      pointer-events: none;
    }
    .ghost-textarea {
      min-height: 76px;
      padding: 9px 12px;
      resize: vertical;
      line-height: 1.45;
    }
    main {
      min-height: 0;
      flex: 1;
      margin: 0;
      padding: 20px;
      display: grid;
      grid-template-columns: minmax(400px, 460px) minmax(0, 1fr);
      gap: 20px;
      align-items: start;
      overflow: hidden;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .config-panel,
    .results-panel {
      max-height: calc(100vh - 104px);
      overflow: auto;
    }
    .panel-head {
      padding: 16px 20px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: var(--panel);
    }
    h1, h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.35;
      letter-spacing: -0.01em;
    }
    .muted { color: var(--muted); font-size: 13px; }
    form {
      padding: 0;
      display: grid;
      gap: 0;
    }
    .form-card {
      padding: 18px 20px;
      border-bottom: 1px solid var(--line);
      display: grid;
      gap: 14px;
      background: var(--panel);
    }
    .form-card h3 {
      margin: 0;
      display: flex;
      align-items: center;
      gap: 9px;
      font-size: 15px;
      line-height: 1.4;
    }
    details.form-card summary {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 0;
      cursor: pointer;
      list-style: none;
      font-size: 15px;
      line-height: 1.4;
      font-weight: 800;
    }
    details.form-card summary::-webkit-details-marker {
      display: none;
    }
    details.form-card summary span {
      display: inline-flex;
      align-items: center;
      gap: 9px;
    }
    details.form-card summary::after {
      content: "+";
      color: var(--muted);
      font-size: 16px;
      font-weight: 800;
    }
    details.form-card[open] summary::after {
      content: "-";
    }
    details.form-card > :not(summary) {
      margin-top: 14px;
    }
    label {
      display: grid;
      gap: 7px;
      font-size: 13px;
      font-weight: 600;
      color: var(--nav-text);
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--field-border);
      border-radius: var(--radius-sm);
      background: var(--field-surface);
      color: var(--text);
      padding: 0 12px;
      font: inherit;
      outline: none;
      box-shadow: var(--field-shadow);
      transition: border-color var(--motion-fast) ease, box-shadow var(--motion-fast) ease, background var(--motion-fast) ease, color var(--motion-fast) ease, transform var(--motion-fast) ease;
    }
    input:hover,
    select:hover,
    textarea:hover {
      border-color: var(--field-border-hover);
      box-shadow: var(--field-shadow-hover);
    }
    input:focus, select:focus, textarea:focus {
      border-color: var(--accent-2);
      background: var(--field-surface);
      box-shadow: var(--focus-ring), var(--field-shadow-hover);
    }
    input, select {
      height: 42px;
    }
    input::placeholder,
    textarea::placeholder {
      color: color-mix(in srgb, var(--muted) 84%, transparent);
    }
    .secret-input input::-ms-reveal,
    .secret-input input::-ms-clear {
      display: none;
      width: 0;
      height: 0;
    }
    .secret-input input::-webkit-credentials-auto-fill-button,
    .secret-input input::-webkit-contacts-auto-fill-button {
      visibility: hidden;
      display: none !important;
      pointer-events: none;
    }
    .secret-input input {
      -webkit-appearance: none;
      appearance: none;
    }
    .locale-control .locale-control-input,
    .locale-control .locale-control-input:hover,
    .locale-control .locale-control-input:focus,
    .locale-control .locale-control-input:focus-visible {
      height: 36px;
      border: 0;
      border-radius: 0;
      background: transparent;
      box-shadow: none;
      padding: 0;
      outline: none;
      -webkit-appearance: none;
      appearance: none;
    }
    textarea {
      min-height: 76px;
      padding: 10px 12px;
      resize: vertical;
      line-height: 1.45;
    }
    input[type="file"] {
      height: auto;
      padding: 14px;
      border-style: dashed;
      background: var(--field-surface-soft);
    }
    input[type="checkbox"] {
      -webkit-appearance: none;
      appearance: none;
      width: 18px;
      height: 18px;
      margin: 0;
      padding: 0;
      border: 1.5px solid var(--check-border);
      border-radius: 6px;
      background: var(--check-bg);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, .35), 0 6px 16px var(--check-shadow);
      display: inline-grid;
      place-content: center;
      cursor: pointer;
      position: relative;
      flex: 0 0 auto;
      transition: border-color var(--motion-fast) ease, background var(--motion-fast) ease, box-shadow var(--motion-fast) ease, transform var(--motion-fast) ease;
    }
    input[type="checkbox"]::after {
      content: "";
      width: 5px;
      height: 9px;
      border-right: 2px solid transparent;
      border-bottom: 2px solid transparent;
      transform: rotate(45deg) scale(.7);
      transform-origin: center;
      opacity: 0;
      transition: transform var(--motion-fast) ease, opacity var(--motion-fast) ease, border-color var(--motion-fast) ease;
    }
    input[type="checkbox"]:hover {
      border-color: var(--check-border-hover);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, .35), 0 10px 22px var(--check-shadow);
      transform: translateY(-1px);
    }
    input[type="checkbox"]:focus-visible {
      outline: none;
      border-color: var(--accent);
      box-shadow: var(--focus-ring), inset 0 1px 0 rgba(255, 255, 255, .35), 0 10px 22px var(--check-shadow);
    }
    input[type="checkbox"]:checked {
      background: var(--check-checked);
      border-color: var(--check-checked-border);
      box-shadow: 0 10px 22px var(--check-shadow);
    }
    input[type="checkbox"]:checked::after {
      opacity: 1;
      border-color: var(--check-tick);
      transform: rotate(45deg) scale(1);
    }
    input[type="checkbox"]:disabled {
      cursor: not-allowed;
      opacity: .56;
      transform: none;
      box-shadow: none;
    }
    input[type="checkbox"]:disabled:hover {
      border-color: var(--check-border);
      transform: none;
      box-shadow: none;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 12px;
    }
    .field-help {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      width: fit-content;
      max-width: 100%;
      padding: 4px 10px;
      border: 1px solid var(--help-border);
      border-radius: 999px;
      background: var(--help-bg);
      color: var(--help-text);
      font-size: 12px;
      line-height: 1.45;
      font-weight: 600;
    }
    .api-box label {
      position: relative;
    }
    .api-box label .field-help {
      position: absolute;
      left: 0;
      top: calc(100% + 7px);
      z-index: 16;
      display: flex;
      width: max-content;
      max-width: min(420px, 100%);
      min-height: auto;
      padding: 8px 10px;
      border-radius: 12px;
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      transform: translateY(-6px) scale(.98);
      transform-origin: top left;
      transition: opacity var(--motion-base) ease, visibility var(--motion-base) ease, transform var(--motion-base) ease, box-shadow var(--motion-base) ease;
      box-shadow: 0 14px 34px rgba(15, 23, 42, .14);
    }
    .api-box label .field-help::before {
      content: "";
      position: absolute;
      left: 18px;
      top: -5px;
      width: 9px;
      height: 9px;
      border-left: 1px solid var(--help-border);
      border-top: 1px solid var(--help-border);
      background: var(--help-bg);
      transform: rotate(45deg);
    }
    .api-box label:focus-within {
      z-index: 18;
    }
    .api-box label:focus-within .field-help {
      opacity: 1;
      visibility: visible;
      transform: translateY(0) scale(1);
    }
    .api-debug-log-line {
      position: relative;
    }
    .api-debug-log-line > [data-i18n="advanced.debug_log"]:hover + .field-help,
    .api-debug-log-line:focus-within .field-help {
      opacity: 1;
      visibility: visible;
      transform: translateY(0) scale(1);
    }
    .api-box {
      display: grid;
      gap: 12px;
      padding: 14px;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-md);
      background:
        radial-gradient(circle at top right, var(--card-highlight), transparent 42%),
        linear-gradient(180deg, var(--panel-2), var(--field-bg));
      box-shadow: var(--card-shadow-soft), inset 0 1px 0 rgba(255, 255, 255, .06);
    }
    .api-box[hidden] {
      display: none;
    }
    .api-box-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
    }
    .api-box-head strong {
      display: block;
      font-size: 13px;
    }
    .api-box-title {
      display: grid;
      gap: 6px;
      min-width: 0;
    }
    .api-box-title > div {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      min-width: 0;
    }
    .checkline {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 500;
      cursor: pointer;
      user-select: none;
    }
    .checkline input {
      margin-top: -1px;
    }
    .checkline input:checked {
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--check-checked-border) 20%, transparent), 0 10px 22px var(--check-shadow);
    }
    .checkline input:checked + span,
    .checkline input:checked ~ span {
      color: var(--text);
      font-weight: 700;
    }
    button {
      border: 0;
      border-radius: var(--radius-sm);
      height: 42px;
      padding: 0 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      background: var(--accent);
      color: var(--button-text);
      transition: transform var(--motion-fast) ease, opacity var(--motion-fast) ease, background-color var(--motion-fast) ease, box-shadow var(--motion-fast) ease;
    }
    button:hover:not(:disabled) { transform: translateY(-1px); }
    button:focus-visible,
    a:focus-visible,
    .ghost-select .control:focus-visible,
    .ghost-file .control:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
    }
    button.secondary {
      background: var(--accent-2);
    }
    button:disabled {
      cursor: not-allowed;
      opacity: .65;
    }
    button[aria-busy="true"] {
      cursor: wait;
    }
    .status {
      min-height: 52px;
      padding: 12px 14px;
      border: 1px solid var(--status-info-border);
      border-radius: var(--radius-md);
      background: var(--status-info-bg);
      color: var(--status-info-text);
      font-size: 13px;
      line-height: 1.45;
      box-shadow: var(--status-accent-shadow);
    }
    .status.error {
      background: var(--status-error-bg);
      color: var(--status-error-text);
      border-color: var(--status-error-border);
    }
    .loading-card {
      min-height: 260px;
      display: grid;
      place-items: center;
      gap: 16px;
      padding: 28px;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-lg);
      text-align: center;
      background:
        radial-gradient(circle at top, var(--card-highlight), transparent 52%),
        linear-gradient(180deg, var(--loading-from), var(--loading-to));
      box-shadow: var(--card-shadow-strong);
      position: relative;
      overflow: hidden;
    }
    .spinner {
      width: 46px;
      height: 46px;
      border: 4px solid var(--line);
      border-top-color: var(--accent);
      border-radius: 999px;
      animation: spin .9s linear infinite;
    }
    .loading-title {
      margin: 0;
      font-size: 16px;
      font-weight: 800;
    }
    .loading-meta {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
      max-width: 520px;
      text-wrap: balance;
    }
    .loading-progress {
      width: min(420px, 100%);
      height: 8px;
      overflow: hidden;
      border-radius: 999px;
      background: var(--field-bg-soft);
    }
    .loading-progress span {
      display: block;
      width: 38%;
      height: 100%;
      border-radius: inherit;
      background: var(--accent);
      animation: progress 1.4s ease-in-out infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @keyframes progress {
      0% { transform: translateX(-105%); }
      100% { transform: translateX(270%); }
    }
    @keyframes fadeInUp {
      from {
        opacity: 0;
        transform: translateY(8px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    .results {
      padding: 20px;
      display: grid;
      gap: 16px;
      overflow-x: auto;
    }
    .system-views {
      display: grid;
      gap: 16px;
    }
    .view-shell {
      display: none;
      gap: 16px;
    }
    .view-shell.active {
      display: grid;
      animation: fadeInUp var(--motion-base) ease;
    }
    .view-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: var(--card-surface-soft);
      box-shadow: inset 0 -1px 0 rgba(255, 255, 255, .04);
    }
    .view-head strong {
      font-size: 14px;
    }
    .view-frame {
      border: 1px solid var(--card-border);
      border-radius: var(--radius-md);
      background: var(--card-surface);
      box-shadow: var(--card-shadow-soft);
      overflow: hidden;
    }
    .view-body {
      padding: 16px;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .actions a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      padding: 0 13px;
      border-radius: var(--radius-sm);
      background: var(--accent-2);
      color: var(--button-text);
      text-decoration: none;
      font-weight: 700;
      font-size: 13px;
    }
    .actions button {
      min-height: 38px;
      height: 38px;
      background: var(--accent-2);
      font-size: 13px;
    }
    .pack-name-dialog {
      position: fixed;
      inset: 0;
      z-index: 100;
      display: grid;
      place-items: center;
      padding: 20px;
      background: var(--overlay);
    }
    .pack-name-dialog[hidden] {
      display: none;
    }
    .pack-name-card {
      width: min(460px, 100%);
      display: grid;
      gap: 16px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--panel);
      box-shadow: 0 24px 64px rgba(15, 23, 42, .24);
    }
    .settings-page {
      grid-column: 1 / -1;
      height: calc(100vh - 104px);
      max-height: calc(100vh - 104px);
      overflow: hidden;
    }
    .settings-page[hidden] {
      display: none;
    }
    .settings-card {
      width: 100%;
      height: 100%;
      min-height: 100%;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 0;
      border: 0;
      border-radius: 0;
      background: var(--panel);
      box-shadow: none;
    }
    .pack-name-head,
    .settings-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
    }
    .settings-head {
      align-items: center;
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    .pack-name-head strong,
    .settings-head strong {
      display: block;
      font-size: 16px;
      line-height: 1.35;
    }
    .pack-name-head span,
    .settings-head span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .pack-name-close,
    .settings-close {
      width: 34px;
      height: 34px;
      min-height: 34px;
      padding: 0;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--field-bg);
      color: var(--muted);
    }
    .pack-name-actions,
    .settings-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      flex-wrap: wrap;
    }
    .settings-actions {
      flex: 0 0 auto;
    }
    .pack-name-actions button,
    .settings-actions button,
    .settings-section-actions button {
      border-radius: 10px;
    }
    .pack-name-actions .secondary,
    .settings-actions .secondary,
    .settings-section-actions .secondary {
      border: 1px solid var(--line);
      background: var(--field-bg);
      color: var(--text);
    }
    .settings-section-actions .danger {
      border: 1px solid var(--danger-line);
      background: var(--danger-bg);
      color: var(--danger);
    }
    .pack-name-field,
    .settings-field {
      display: grid;
      gap: 7px;
    }
    .settings-status {
      min-height: 18px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      line-height: 1.45;
    }
    .settings-status.error {
      color: var(--danger);
    }
    .settings-current {
      display: grid;
      gap: 3px;
      padding-top: 2px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .settings-current strong {
      color: var(--text);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .settings-layout {
      min-height: 0;
      display: grid;
      grid-template-columns: repeat(2, minmax(280px, 1fr));
      align-items: start;
      gap: 16px;
      padding: 18px 22px;
      overflow: auto;
      scrollbar-width: thin;
      scrollbar-color: var(--scroll-thumb) transparent;
    }
    .settings-section {
      display: grid;
      gap: 14px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      background: var(--card-surface-soft);
      box-shadow: var(--card-shadow-soft);
    }
    .settings-section-title {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text);
      font-size: 13px;
      font-weight: 800;
      line-height: 1.4;
    }
    .settings-section-title i {
      color: var(--accent);
      font-size: 18px;
    }
    .settings-section-actions {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 10px;
      flex-wrap: wrap;
      padding-top: 2px;
    }
    .settings-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 22px;
      border-top: 1px solid var(--line);
      background: var(--panel);
    }
    .settings-footer .settings-status {
      flex: 1 1 auto;
    }
    .theme-preview {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 44px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: var(--field-bg-soft);
    }
    .theme-preview strong {
      display: block;
      color: var(--text);
      font-size: 13px;
      line-height: 1.35;
    }
    .theme-preview span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .theme-swatches {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      flex: 0 0 auto;
    }
    .theme-swatch {
      width: 24px;
      height: 24px;
      border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
      border-radius: 8px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, .28);
    }
    .pack-name-input-wrap,
    .secret-input {
      position: relative;
      display: flex;
      align-items: center;
      min-width: 0;
    }
    .pack-name-input-wrap input {
      padding-right: 56px;
    }
    .pack-name-suffix {
      position: absolute;
      right: 12px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      pointer-events: none;
    }
    .pack-name-error {
      min-height: 18px;
      color: var(--danger);
      font-size: 12px;
      font-weight: 700;
      line-height: 1.45;
    }
    .secret-input input {
      padding-right: 46px;
    }
    .secret-toggle {
      position: absolute;
      right: 5px;
      width: 34px;
      min-width: 34px;
      height: 32px;
      min-height: 32px;
      padding: 0;
      display: grid;
      place-items: center;
      border: 1px solid transparent;
      border-radius: 8px;
      background: transparent;
      color: var(--muted);
      transform: none;
    }
    .secret-toggle:hover:not(:disabled),
    .secret-toggle:focus-visible {
      border-color: var(--accent-soft-line);
      background: var(--accent-soft-hover);
      color: var(--accent);
      transform: none;
    }
    .model-field {
      display: grid;
      gap: 7px;
    }
    .model-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: end;
    }
    .model-row .ghost-select {
      min-width: 0;
      gap: 0;
    }
    .model-row .ghost-menu {
      top: calc(100% + 6px);
    }
    .model-control-input {
      display: none;
      width: 100%;
      min-width: 0;
      height: 36px;
      border: 0;
      border-radius: 0;
      background: transparent;
      color: var(--text);
      padding: 0;
      font: inherit;
      outline: none;
      box-shadow: none;
      -webkit-appearance: none;
      appearance: none;
    }
    .model-select.open .model-control-value {
      display: none;
    }
    .model-select.open .model-control-input {
      display: block;
    }
    .model-control .model-control-input,
    .model-control .model-control-input:hover,
    .model-control .model-control-input:focus,
    .model-control .model-control-input:focus-visible {
      height: 36px;
      border: 0;
      border-radius: 0;
      background: transparent;
      box-shadow: none;
      padding: 0;
      outline: none;
      -webkit-appearance: none;
      appearance: none;
    }
    .model-control-input::-webkit-search-decoration,
    .model-control-input::-webkit-search-results-button,
    .model-control-input::-webkit-search-results-decoration {
      -webkit-appearance: none;
      appearance: none;
    }
    .model-refresh {
      width: 42px;
      min-width: 42px;
      height: 42px;
      min-height: 42px;
      padding: 0;
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      background: var(--field-bg);
      color: var(--muted);
      transform: none;
    }
    .model-refresh:hover:not(:disabled),
    .model-refresh:focus-visible {
      border-color: var(--accent-soft-line);
      background: var(--accent-soft-hover);
      color: var(--accent);
      transform: none;
    }
    .model-refresh[aria-busy="true"] i {
      animation: spin 900ms linear infinite;
    }
    .model-status {
      min-height: 18px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      line-height: 1.45;
    }
    .model-status.error {
      color: var(--danger);
    }
    #retry-api-failures {
      min-width: 132px;
      white-space: nowrap;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .toolbar button {
      height: 40px;
      border: 1px solid var(--line);
      background: var(--field-bg);
      color: var(--text);
      font-size: 12px;
      font-weight: 700;
    }
    .toolbar button.active {
      background: var(--control-active-bg);
      border-color: var(--control-active-border);
      color: var(--control-active-text);
      box-shadow: var(--control-active-shadow);
    }
    .theme-picker {
      position: relative;
      flex: 0 0 auto;
    }
    .theme-toggle {
      min-width: 210px;
      max-width: 260px;
      padding: 0 10px;
      border: 1px solid var(--line);
      background: var(--field-bg);
      color: var(--text);
      box-shadow: none;
      display: inline-flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .theme-trigger-main {
      min-width: 0;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .theme-trigger-main span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 12px;
      font-weight: 700;
    }
    .theme-trigger-swatches {
      margin-left: auto;
    }
    .theme-trigger-swatches .theme-swatch {
      width: 16px;
      height: 16px;
      border-radius: 5px;
    }
    .theme-toggle .chevron {
      color: var(--muted);
      flex: 0 0 auto;
    }
    .theme-menu {
      position: absolute;
      right: 0;
      top: calc(100% + 8px);
      z-index: 70;
      width: min(380px, calc(100vw - 32px));
      max-height: min(520px, calc(100vh - 92px));
      overflow: auto;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      background: var(--panel);
      box-shadow: 0 18px 44px rgba(15, 23, 42, .18);
      scrollbar-width: thin;
      scrollbar-color: var(--dropdown-scroll-thumb) var(--dropdown-scroll-track);
    }
    .theme-menu[hidden] {
      display: none;
    }
    .theme-group {
      display: grid;
      gap: 4px;
    }
    .theme-group + .theme-group {
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--line);
    }
    .theme-group-title {
      padding: 4px 8px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      line-height: 1.35;
    }
    .theme-option {
      width: 100%;
      height: auto;
      min-height: 46px;
      padding: 8px 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border: 1px solid transparent;
      border-radius: var(--radius-sm);
      background: var(--field-bg);
      color: var(--text);
      box-shadow: none;
      transform: none;
    }
    .theme-option:hover:not(:disabled),
    .theme-option:focus-visible {
      border-color: var(--accent-soft-line);
      background: var(--accent-soft-hover);
      color: var(--text);
      transform: none;
    }
    .theme-option.active {
      border-color: var(--accent-active-line);
      background: var(--accent-soft-active);
      color: var(--text);
    }
    .theme-option-copy {
      min-width: 0;
      display: grid;
      gap: 2px;
      text-align: left;
    }
    .theme-option-copy strong {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 13px;
      line-height: 1.35;
    }
    .theme-option-copy span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      line-height: 1.35;
    }
    .toolbar input {
      flex: 1;
      min-width: 190px;
    }
    .toolbar .ghost-select.jar-filter {
      display: inline-flex;
      gap: 0;
      flex: 0 1 clamp(240px, 28vw, 420px);
      min-width: 240px;
      max-width: min(100%, 420px);
    }
    .toolbar .ghost-select.jar-filter .control {
      min-height: 40px;
      padding: 0 10px;
      font-size: 12px;
      font-weight: 700;
    }
    .toolbar .ghost-select.jar-filter .value {
      min-width: 0;
    }
    .toolbar .ghost-select.jar-filter .ghost-menu {
      left: 0;
      right: auto;
      width: max-content;
      min-width: 100%;
      max-width: min(78vw, 720px);
      top: calc(100% + 4px);
      overflow-x: hidden;
    }
    .toolbar .ghost-select.jar-filter .ghost-option {
      align-items: flex-start;
    }
    .toolbar .ghost-select.jar-filter .jar-tree-option {
      justify-content: flex-start;
      gap: 10px;
      height: auto;
      min-height: 38px;
    }
    .jar-tree-label {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }
    .jar-tree-label i {
      flex: 0 0 auto;
      color: var(--muted);
      font-size: 15px;
    }
    .jar-tree-path {
      margin-left: auto;
      max-width: 260px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
    .toolbar .ghost-select.jar-filter .ghost-option strong {
      display: block;
      min-width: 0;
      white-space: normal;
      overflow-wrap: anywhere;
      line-height: 1.4;
    }
    .pager {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--line);
    }
    .pager-info {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .pager-controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
    }
    .pager button {
      min-width: 34px;
      height: 32px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--field-bg);
      color: var(--text);
      font-size: 12px;
      font-weight: 800;
      cursor: pointer;
    }
    .pager button.active {
      border-color: var(--control-active-border);
      background: var(--control-active-bg);
      color: var(--control-active-text);
      box-shadow: var(--control-active-shadow);
    }
    .pager button:disabled {
      cursor: not-allowed;
      opacity: .45;
      transform: none;
    }
    .pager button.active:disabled {
      opacity: 1;
    }
    .tabs {
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 10px;
    }
    .tabs button {
      height: 34px;
      border: 1px solid var(--line);
      background: var(--field-bg);
      color: var(--text);
      font-size: 13px;
    }
    .tabs button.active {
      background: var(--control-active-bg);
      border-color: var(--control-active-border);
      color: var(--control-active-text);
      box-shadow: var(--control-active-shadow);
    }
    .tabs button[data-result-tab="report"] { min-width: 110px; }
    .tab-panel {
      display: grid;
      gap: 12px;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }
    .summary-group {
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-md);
      background: var(--card-surface-soft);
      box-shadow: var(--card-shadow-soft);
    }
    .summary-group h3 {
      margin: 0;
      font-size: 13px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .summary-group-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
      gap: 10px;
    }
    .metric {
      border: 1px solid var(--card-border);
      border-radius: var(--radius-md);
      padding: 14px 12px 12px;
      background:
        radial-gradient(circle at top right, var(--card-highlight), transparent 48%),
        linear-gradient(180deg, var(--card-surface-strong), var(--field-bg));
      position: relative;
      overflow: hidden;
      min-height: 82px;
      box-shadow: var(--card-shadow-soft);
    }
    .metric::after {
      content: "";
      position: absolute;
      inset: auto -24px -26px auto;
      width: 96px;
      height: 96px;
      border-radius: 999px;
      background: radial-gradient(circle, var(--card-highlight), transparent 70%);
      pointer-events: none;
    }
    .metric strong {
      display: block;
      font-size: clamp(22px, 2vw, 28px);
      line-height: 1.1;
      margin-bottom: 8px;
      letter-spacing: 0;
      color: var(--text);
    }
    .metric span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .hardcoded-workbench {
      border-top: 1px solid var(--line);
      padding-top: 16px;
      display: grid;
      gap: 12px;
    }
    .hardcoded-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-md);
      background: var(--card-surface-soft);
      box-shadow: var(--card-shadow-soft);
    }
    .hardcoded-head h3 {
      margin: 0;
      font-size: 15px;
    }
    .hardcoded-row textarea.invalid {
      border-color: var(--status-error-border);
      background: var(--status-error-bg);
      color: var(--status-error-text);
      box-shadow: 0 0 0 1px color-mix(in srgb, var(--status-error-border) 72%, transparent);
    }
    .hardcoded-row {
      cursor: pointer;
    }
    .hardcoded-row.selected td {
      background: var(--accent-soft-hover);
    }
    .select-cell {
      width: 48px;
      text-align: center;
      vertical-align: middle;
    }
    .select-cell input {
      width: 18px;
      height: 18px;
      margin-inline: auto;
    }
    .hardcoded-row.selected .select-cell input {
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 18%, transparent), 0 10px 22px var(--check-shadow);
    }
    .hardcoded-errors {
      color: var(--danger);
      font-size: 12px;
      line-height: 1.45;
      margin-top: 6px;
    }
    .hidden-file {
      display: none;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 13px;
      background: var(--panel);
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 12px 10px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
    }
    th {
      background: var(--panel-2);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .05em;
    }
    tr:hover td {
      background: var(--table-hover);
    }
    .provider-badge {
      color: var(--accent);
      background: var(--accent-soft);
      border-color: var(--accent-soft-line);
    }
    .btn-key-apply {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      white-space: nowrap;
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
      background: var(--accent-soft);
      border: 1px solid var(--accent-soft-line);
      border-radius: var(--radius-sm);
      text-decoration: none;
      cursor: pointer;
      transition: background-color var(--motion-fast) ease, border-color var(--motion-fast) ease, color var(--motion-fast) ease;
    }
    .btn-key-apply:hover {
      background: var(--accent-soft-hover);
    }
    .empty {
      padding: 36px 18px;
      color: var(--muted);
      text-align: center;
    }
    .nav-item {
      cursor: pointer;
    }
    .panel-copy {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .metric::before {
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      width: 100%;
      height: 4px;
      background: var(--accent);
    }
    .metric:nth-child(2)::before { background: var(--accent-2); }
    .metric:nth-child(3)::before { background: var(--success); }
    .metric:nth-child(4)::before { background: var(--warning); }
    .metric:nth-child(5)::before { background: color-mix(in srgb, var(--accent) 72%, var(--danger)); }
    .metric:nth-child(6)::before { background: color-mix(in srgb, var(--success) 72%, var(--accent)); }
    .metric:nth-child(7)::before { background: color-mix(in srgb, var(--warning) 72%, var(--danger)); }
    .metric:nth-child(8)::before { background: var(--danger); }
    .metric strong,
    .job-pill {
      font-family: "Fira Code", ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    .job-pill {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--field-bg-soft);
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0;
    }
    .status.success {
      background: var(--status-success-bg);
      color: var(--status-success-text);
      border: 1px solid var(--status-success-border);
    }
    .results .actions a,
    .results .actions button,
    .toolbar button,
    .tabs button,
    #submit {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    #cancel-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      background: var(--danger);
      color: var(--danger-text);
      border: 0;
      border-radius: 8px;
      padding: 10px 22px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
    }
    #cancel-btn:hover { opacity: .85; }
    .results .actions a i,
    .results .actions button i,
    .toolbar button i,
    .tabs button i,
    #submit i {
      font-size: 16px;
      line-height: 1;
      flex: 0 0 auto;
    }
    .results .actions a span,
    .results .actions button span {
      display: inline-flex;
      align-items: center;
      height: 1em;
      line-height: 1;
    }
    .actions button.is-loading i {
      display: inline-block;
      transform-origin: 50% 50%;
      animation: spin .9s linear infinite;
    }
    .actions a,
    .actions button,
    .toolbar button,
    .tabs button,
    #submit {
      border-radius: 12px;
    }
    .actions a,
    .actions button {
      box-shadow: 0 8px 18px rgba(37, 99, 235, .12);
    }
    .toolbar button,
    .tabs button {
      box-shadow: none;
    }
    .loading-card {
      position: relative;
      overflow: hidden;
    }
    .loading-card::after {
      content: "";
      position: absolute;
      inset: auto 0 0;
      height: 4px;
      background: linear-gradient(90deg, var(--accent), var(--success), var(--accent));
      background-size: 200% 100%;
      animation: flow 2.2s linear infinite;
    }
    .loading-status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft-hover);
      color: var(--control-hover-text);
      font-size: 12px;
      font-weight: 700;
    }
    .loading-status i {
      font-size: 14px;
      line-height: 1;
    }
    .loading-progress {
      height: 10px;
      border-radius: 999px;
      background: var(--field-bg-soft);
    }
    .loading-progress span {
      border-radius: inherit;
      background: var(--accent);
    }
    .loading-lanes {
      width: min(520px, 100%);
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }
    .loading-lane {
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr) 64px;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border: 1px solid var(--card-border);
      border-radius: 14px;
      background: var(--card-surface-soft);
      box-shadow: var(--card-shadow-soft);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-align: left;
    }
    .loading-lane b {
      color: var(--text);
      font-family: "Fira Code", ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 12px;
      font-weight: 700;
      text-align: right;
    }
    .loading-lane-bar {
      height: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: color-mix(in srgb, var(--card-highlight) 55%, var(--field-bg-soft));
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--line) 72%, transparent);
    }
    .loading-lane-bar span {
      display: block;
      height: 100%;
      width: 0%;
      border-radius: inherit;
      background: linear-gradient(90deg, #2563eb, #60a5fa);
      transition: width 260ms ease;
    }
    .loading-lane-bar span.indeterminate {
      width: 44%;
      animation: progress-full 1.45s ease-in-out infinite;
    }
    .loading-lane:nth-child(2n) .loading-lane-bar span {
      animation-delay: .18s;
      background: linear-gradient(90deg, #16a34a, #4ade80);
    }
    .loading-lane:nth-child(3n) .loading-lane-bar span {
      animation-delay: .36s;
      background: linear-gradient(90deg, #f97316, #fb923c);
    }
    @keyframes sweep {
      0% { transform: translateX(-110%); }
      100% { transform: translateX(110%); }
    }
    @keyframes flow {
      0% { background-position: 0% 50%; }
      100% { background-position: 200% 50%; }
    }
    @keyframes progress-full {
      0% { transform: translateX(-120%); }
      100% { transform: translateX(230%); }
    }
    .section-hint {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }
    .section-hint span {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 0 10px;
      border-radius: 999px;
      background: #eef4fb;
      color: #35506b;
      font-size: 12px;
      font-weight: 600;
    }
    .side-nav .nav-item,
    .top-tabs .tab-pill,
    .pill,
    .toolbar button,
    .pager button,
    .tabs button,
    .actions a,
    .actions button,
    #submit,
    input,
    select,
    textarea,
    .status,
    .metric,
    section,
    .loading-card {
      transition: transform var(--motion-base) ease, background-color var(--motion-base) ease, border-color var(--motion-base) ease, color var(--motion-base) ease, box-shadow var(--motion-base) ease, opacity var(--motion-base) ease;
    }
    .nav-item:hover,
    .tab-pill:hover:not(.active),
    .toolbar button:hover:not(:disabled):not(.active),
    .pager button:hover:not(:disabled):not(.active),
    .tabs button:hover:not(:disabled):not(.active),
    .actions a:hover,
    .actions button:hover,
    #submit:hover:not(:disabled) {
      transform: translateY(-1px);
    }
    .nav-item:hover:not(.active),
    .tab-pill:hover:not(.active) {
      border-color: var(--control-hover-border);
      background: var(--control-hover-bg);
      color: var(--control-hover-text);
    }
    .toolbar button:hover:not(:disabled):not(.active),
    .pager button:hover:not(:disabled):not(.active),
    .tabs button:hover:not(:disabled):not(.active) {
      border-color: var(--control-hover-border);
      background: var(--control-hover-bg);
      color: var(--control-hover-text);
    }
    .results-panel .results table thead th {
      position: sticky;
      top: 0;
      z-index: 1;
    }
    .results-panel .results table tbody tr:nth-child(2n) td {
      background: var(--table-alt);
    }
    .results-panel .results table tbody tr:hover td {
      background: var(--table-hover);
    }
    .api-log-table {
      table-layout: fixed;
    }
    .api-log-table th:nth-child(1),
    .api-log-table td:nth-child(1) { width: 150px; }
    .api-log-table th:nth-child(2),
    .api-log-table td:nth-child(2) { width: 90px; }
    .api-log-table th:nth-child(3),
    .api-log-table td:nth-child(3) { width: 120px; }
    .api-log-table th:nth-child(4),
    .api-log-table td:nth-child(4) { width: 76px; }
    .api-log-table textarea {
      min-height: 180px;
      max-height: 360px;
      resize: vertical;
      font-family: "Fira Code", ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 12px;
      line-height: 1.5;
      white-space: pre;
      overflow: auto;
    }
    .view-content {
      display: grid;
      gap: 12px;
    }
    .loading-card,
    .metric,
    .api-box,
    .status {
      border-radius: var(--radius-md);
    }
    .loading-meta,
    .field-help,
    .muted {
      line-height: 1.55;
    }
    .muted {
      color: var(--muted);
    }
    .status {
      min-height: 48px;
      display: flex;
      align-items: center;
    }
    .results {
      scrollbar-width: thin;
      scrollbar-color: #b9c7d8 transparent;
    }
    .results::-webkit-scrollbar,
    .config-panel::-webkit-scrollbar,
    .results-panel::-webkit-scrollbar,
    .settings-layout::-webkit-scrollbar {
      width: 12px;
      height: 12px;
    }
    .results::-webkit-scrollbar-thumb,
    .config-panel::-webkit-scrollbar-thumb,
    .results-panel::-webkit-scrollbar-thumb,
    .settings-layout::-webkit-scrollbar-thumb {
      border: 3px solid transparent;
      background-clip: padding-box;
      background-color: var(--scroll-thumb);
      border-radius: 999px;
    }
    .results::-webkit-scrollbar-track,
    .config-panel::-webkit-scrollbar-track,
    .results-panel::-webkit-scrollbar-track,
    .settings-layout::-webkit-scrollbar-track {
      background: transparent;
    }
    :root[data-theme="dark"] .nav-item:hover {
      background: rgba(96, 165, 250, .08);
    }
    :root[data-theme="dark"] .btn-key-apply,
    :root[data-theme="dark"] .top-search,
    :root[data-theme="dark"] .pill,
    :root[data-theme="dark"] .ghost-select .control,
    :root[data-theme="dark"] .ghost-file .control,
    :root[data-theme="dark"] .ghost-menu,
    :root[data-theme="dark"] .ghost-option,
    :root[data-theme="dark"] input,
    :root[data-theme="dark"] select,
    :root[data-theme="dark"] textarea,
    :root[data-theme="dark"] .toolbar button,
    :root[data-theme="dark"] .pack-name-close,
    :root[data-theme="dark"] .settings-close,
    :root[data-theme="dark"] .pack-name-actions .secondary,
    :root[data-theme="dark"] .settings-actions .secondary,
    :root[data-theme="dark"] .settings-section-actions .secondary {
      background: var(--field-bg);
      color: var(--text);
    }
    :root[data-theme="dark"] .btn-key-apply {
      border-color: var(--accent-soft-line);
      color: var(--accent);
    }
    :root[data-theme="dark"] .btn-key-apply:hover {
      background: var(--accent-soft-hover);
      border-color: var(--accent);
    }
    :root[data-theme="dark"] .panel-copy,
    :root[data-theme="dark"] .field-help,
    :root[data-theme="dark"] .pack-name-head span,
    :root[data-theme="dark"] .settings-head span,
    :root[data-theme="dark"] .loading-meta {
      color: var(--muted);
    }
    :root[data-theme="dark"] input[type="file"],
    :root[data-theme="dark"] .loading-progress,
    :root[data-theme="dark"] .ghost-empty {
      background: var(--field-bg-soft);
    }
    :root[data-theme="dark"] .loading-lane {
      border-color: var(--card-border);
      background: var(--card-surface-soft);
    }
    :root[data-theme="dark"] .results table thead th,
    :root[data-theme="dark"] .api-log-table thead th {
      background: var(--panel-2);
    }
    :root[data-theme="dark"] .metric,
    :root[data-theme="dark"] .job-pill,
    :root[data-theme="dark"] .status {
      border-color: var(--line);
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }
      .view-shell.active {
        animation: none !important;
      }
      .nav-item:hover,
      .tab-pill:hover:not(.active),
      .toolbar button:hover:not(:disabled):not(.active),
      .pager button:hover:not(:disabled):not(.active),
      .tabs button:hover:not(:disabled):not(.active),
      .actions a:hover,
      .actions button:hover,
      #submit:hover:not(:disabled) {
        transform: none !important;
      }
    }
    @media (max-width: 880px) {
      body { overflow: auto; }
      .app-shell {
        grid-template-columns: 1fr;
      }
      .side-nav {
        display: none;
      }
      .content-shell {
        height: auto;
        min-height: 100vh;
      }
      header {
        padding: 12px 16px;
        align-items: flex-start;
        height: auto;
        flex-wrap: wrap;
      }
      .top-left {
        width: 100%;
        gap: 14px;
        flex-wrap: wrap;
      }
      .top-tabs {
        width: 100%;
        gap: 18px;
        padding-bottom: 2px;
      }
      .tab-pill {
        flex: 0 0 auto;
      }
      .header-meta {
        width: 100%;
        justify-content: flex-start;
        flex-wrap: wrap;
      }
      .theme-picker {
        width: 100%;
      }
      .theme-toggle {
        width: 100%;
        max-width: none;
      }
      .theme-menu {
        left: 0;
        right: auto;
        width: min(100%, calc(100vw - 32px));
      }
      .top-search {
        width: 100%;
        min-width: 0;
      }
      main {
        grid-template-columns: 1fr;
        padding: 16px;
        overflow: visible;
      }
      .config-panel,
      .results-panel,
      .settings-page {
        height: auto;
        max-height: none;
      }
      .settings-card {
        height: auto;
        min-height: auto;
      }
      .panel-head,
      .form-card,
      .view-head,
      .view-body,
      .settings-head,
      .settings-layout,
      .settings-footer {
        padding-left: 16px;
        padding-right: 16px;
      }
      .settings-layout {
        grid-template-columns: 1fr;
        overflow: visible;
      }
      .settings-footer {
        align-items: stretch;
        flex-direction: column;
      }
      .grid-2,
      .grid-3 {
        grid-template-columns: 1fr;
      }
      .summary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }
      .api-box-head,
      .hardcoded-head,
      .pack-name-head,
      .pager,
      .view-head {
        align-items: flex-start;
        flex-direction: column;
      }
      .actions,
      .toolbar,
      .tabs,
      .settings-actions {
        width: 100%;
      }
      .actions a,
      .actions button,
      .toolbar button,
      .settings-actions button,
      #submit,
      #cancel-btn {
        width: 100%;
      }
      .toolbar input {
        min-width: 0;
        width: 100%;
      }
      .loading-lanes {
        width: 100%;
      }
      .loading-lane {
        grid-template-columns: 1fr;
        gap: 6px;
      }
      .loading-lane b {
        text-align: left;
      }
      .api-log-table {
        min-width: 760px;
      }
      .metric {
        min-height: 88px;
      }
      .summary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .section-hint {
        display: none;
      }
    }
    @media (max-width: 560px) {
      main {
        padding: 12px;
        gap: 12px;
      }
      .panel-head,
      .form-card,
      .view-head,
      .view-body,
      .settings-head,
      .settings-layout,
      .settings-footer {
        padding-left: 14px;
        padding-right: 14px;
      }
      .settings-layout {
        gap: 12px;
      }
      .settings-section {
        padding: 14px;
      }
      .summary {
        grid-template-columns: 1fr;
      }
      .pager {
        align-items: stretch;
      }
      .pager-controls,
      .actions,
      .toolbar,
      .tabs {
        width: 100%;
      }
      .actions a,
      .actions button,
      .toolbar button,
      .tabs button,
      .settings-section-actions button,
      #submit,
      #cancel-btn,
      .pager button {
        width: 100%;
      }
      .panel-copy,
      .field-help,
      .muted {
        text-wrap: pretty;
      }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="side-nav">
      <div class="side-brand">
        <div class="mark"><img src="/assets/logo/minecraft.svg" alt="翻译工作台" data-i18n-aria-label="app.brand.alt"></div>
        <div><strong data-i18n="app.brand.name">翻译工作台</strong><span data-i18n="app.brand.subtitle">mc-mod-i18n 本地版</span></div>
      </div>
      <nav class="nav-list">
        <button type="button" class="nav-item active" data-view="language"><i class="ri-folder-open-line"></i><span data-i18n="nav.workspace">工作区</span></button>
        <button type="button" class="nav-item" data-view="report"><i class="ri-history-line"></i><span data-i18n="nav.report">翻译报告</span></button>
        <button type="button" class="nav-item" data-view="hardcoded"><i class="ri-tools-line"></i><span data-i18n="nav.hardcoded">硬编码</span></button>
        <button type="button" class="nav-item" data-view="api-log"><i class="ri-bug-line"></i><span data-i18n="nav.api_log">API 日志</span></button>
      </nav>
      <div class="nav-footer">
        <button type="button" class="nav-item" id="settings-open" data-view="settings"><i class="ri-settings-3-line"></i><span data-i18n="nav.settings">设置</span></button>
        <div class="nav-item"><i class="ri-file-list-3-line"></i><span data-i18n="nav.docs">文档</span></div>
        <div class="nav-item"><i class="ri-question-line"></i><span data-i18n="nav.help">帮助</span></div>
      </div>
    </aside>
    <div class="content-shell">
      <header>
        <div class="top-left">
          <div class="brand">MC-LocaliZ</div>
          <div class="header-task"><span data-i18n="header.current_task">当前任务</span><strong id="header-job">未开始</strong></div>
        </div>
        <div class="header-meta">
          <div class="ghost-select ui-locale-select" id="ui-locale-select" title="界面语言" data-i18n-title="ui_locale.title">
            <button type="button" class="control" data-select-trigger="ui_locale" aria-haspopup="listbox" aria-expanded="false" aria-controls="ui-locale-menu"><span class="value" id="ui-locale-display">简体中文</span><i class="ri-global-line chevron"></i></button>
            <div class="ghost-menu" id="ui-locale-menu" role="listbox" hidden></div>
            <select id="ui_locale" tabindex="-1" aria-hidden="true">
              <option value="zh_cn" selected>简体中文</option>
              <option value="en_us">English</option>
            </select>
          </div>
          <div class="theme-picker" id="theme-picker">
            <button type="button" id="theme-toggle" class="theme-toggle" title="主题" data-i18n-title="theme.title_plain" aria-haspopup="listbox" aria-expanded="false" aria-controls="theme-menu">
              <span class="theme-trigger-main"><i class="ri-computer-line" data-theme-icon></i><span data-theme-label>跟随系统</span></span>
              <span class="theme-swatches theme-trigger-swatches" data-theme-trigger-swatches aria-hidden="true"></span>
              <i class="ri-arrow-down-s-line chevron" aria-hidden="true"></i>
            </button>
            <div class="theme-menu" id="theme-menu" role="listbox" hidden></div>
          </div>
          <span class="pill" data-i18n="header.local">本地处理</span>
          <span class="pill provider-badge" data-i18n="header.create_by">作者: co1dsand</span>
        </div>
      </header>
      <main>
    <section class="config-panel">
      <div class="panel-head">
        <div>
          <h1 data-i18n="panel.title">生成汉化资源包</h1>
          <div class="panel-copy" data-i18n="panel.copy">上传 JAR，配置翻译器和资源包版本，直接生成资源包、报告和硬编码映射。</div>
        </div>
      </div>
      <form id="translate-form">
        <div class="form-card">
          <h3><i class="ri-archive-2-line"></i><span data-i18n="input.title">输入类型</span></h3>
          <input type="hidden" name="input_kind" id="input_kind" value="jar">
          <div class="mode-switch" role="radiogroup" aria-label="处理类型" data-i18n-aria-label="input.title">
            <button type="button" class="active" data-input-kind="jar" aria-pressed="true"><i class="ri-file-zip-line"></i><span data-i18n="input.jar">Mod JAR 语言文件</span></button>
            <button type="button" data-input-kind="ftbquests" aria-pressed="false"><i class="ri-book-open-line"></i><span data-i18n="input.ftbquests">FTB Quests 任务书</span></button>
            <button type="button" data-input-kind="json" aria-pressed="false"><i class="ri-braces-line"></i><span data-i18n="input.json">语言 JSON 文件</span></button>
          </div>
        <label class="ghost-file mode-dependent" id="jar-file-wrap"><span data-i18n="file.jar">Mod JAR</span>
          <span class="control"><span class="value" id="jars-display">选择一个或多个 JAR</span><i class="ri-folder-upload-line icon"></i></span>
          <input id="jars" name="jars" type="file" accept=".jar" multiple required>
        </label>
        <label class="ghost-file mode-dependent" id="ftbquests-file-wrap" hidden><span data-i18n="file.ftbquests">FTB Quests / 整合包 ZIP</span>
          <span class="control"><span class="value" id="ftbquests-display">选择整合包 ZIP、quests ZIP 或 en_us.snbt</span><i class="ri-folder-upload-line icon"></i></span>
          <input id="ftbquests-files" name="ftbquests_files" type="file" accept=".zip,.snbt" multiple>
        </label>
        <label class="ghost-file mode-dependent" id="ftbquests-directory-wrap" hidden><span data-i18n="file.ftbquests_dir">FTB Quests 目录</span>
          <span class="control"><span class="value" id="ftbquests-directory-display">选择 quests、lang 或 en_us 目录</span><i class="ri-folder-open-line icon"></i></span>
          <input id="ftbquests-directory" name="ftbquests_directory_files" type="file" webkitdirectory directory multiple>
        </label>
        <label class="ghost-file mode-dependent" id="json-file-wrap" hidden><span data-i18n="file.json">语言 JSON</span>
          <span class="control"><span class="value" id="json-display">选择 en_us.json 或界面语言包 JSON</span><i class="ri-braces-line icon"></i></span>
          <input id="json-files" name="json_files" type="file" accept=".json,application/json" multiple>
        </label>
        </div>
        <div class="form-card">
          <h3><i class="ri-translate-2"></i><span data-i18n="language.title">Language Settings</span></h3>
        <div class="grid-2">
          <label class="ghost-select locale-select" id="source-locale-select"><span data-i18n="language.source">源语言</span>
            <div class="control locale-control" data-select-trigger="source_locale" role="combobox" tabindex="0" aria-haspopup="listbox" aria-expanded="false" aria-controls="source-locale-menu"><span class="value locale-control-value" id="source-locale-display"></span><input type="search" class="locale-control-input" data-locale-control-search="source_locale" placeholder="搜索代码或语言" data-i18n-placeholder="language.search_source" autocomplete="off" spellcheck="false" aria-label="搜索源语言" data-i18n-aria-label="language.search_source"><i class="ri-arrow-down-s-line chevron"></i></div>
            <div class="ghost-menu" id="source-locale-menu" role="listbox" hidden></div>
            <select name="source_locale" id="source_locale" tabindex="-1" aria-hidden="true">
              <option value="en_us" selected>en_us - English (US)</option>
              <option value="en_gb">en_gb - English (UK)</option>
              <option value="zh_cn">zh_cn - 简体中文</option>
              <option value="zh_tw">zh_tw - 繁体中文</option>
              <option value="ja_jp">ja_jp - 日本語</option>
              <option value="ko_kr">ko_kr - 한국어</option>
            </select>
          </label>
          <label class="ghost-select locale-select" id="target-locale-select"><span data-i18n="language.target">目标语言</span>
            <div class="control locale-control" data-select-trigger="target_locale" role="combobox" tabindex="0" aria-haspopup="listbox" aria-expanded="false" aria-controls="target-locale-menu"><span class="value locale-control-value" id="target-locale-display"></span><input type="search" class="locale-control-input" data-locale-control-search="target_locale" placeholder="搜索代码或语言" data-i18n-placeholder="language.search_target" autocomplete="off" spellcheck="false" aria-label="搜索目标语言" data-i18n-aria-label="language.search_target"><i class="ri-arrow-down-s-line chevron"></i></div>
            <div class="ghost-menu" id="target-locale-menu" role="listbox" hidden></div>
            <select name="target_locale" id="target_locale" tabindex="-1" aria-hidden="true">
              <option value="zh_cn" selected>zh_cn - 简体中文</option>
              <option value="zh_tw">zh_tw - 繁体中文</option>
              <option value="en_us">en_us - English (US)</option>
              <option value="ja_jp">ja_jp - 日本語</option>
              <option value="ko_kr">ko_kr - 한국어</option>
            </select>
          </label>
        </div>
        </div>
        <div class="form-card">
          <h3><i class="ri-cpu-line"></i><span data-i18n="translator.title">Translator & Resource Pack</span></h3>
        <div class="grid-2">
        <label class="ghost-select" id="provider-select"><span data-i18n="translator.provider">翻译器</span>
            <button type="button" class="control" data-select-trigger="provider"><span class="value" id="provider-display"></span><i class="ri-arrow-down-s-line chevron"></i></button>
            <div class="ghost-menu" id="provider-menu" hidden></div>
            <select name="provider" id="provider" tabindex="-1" aria-hidden="true">
              <option value="glossary">离线术语表（有限）</option>
              <option value="copy">复制原文</option>
              <option value="openai-compatible">兼容 OpenAI</option>
              <option value="anthropic-compatible">兼容 Anthropic</option>
            </select>
          </label>
          <label class="ghost-select" id="pack-format-select"><span data-i18n="translator.pack_format">资源包格式</span>
            <button type="button" class="control" data-select-trigger="pack_format"><span class="value" id="pack-format-display"></span><i class="ri-arrow-down-s-line chevron"></i></button>
            <div class="ghost-menu" id="pack-format-menu" hidden></div>
            <select name="pack_format" id="pack_format" tabindex="-1" aria-hidden="true">
              <option value="1">1 - Minecraft 1.6.1-1.8.9</option>
              <option value="2">2 - Minecraft 1.9-1.10.2</option>
              <option value="3">3 - Minecraft 1.11-1.12.2</option>
              <option value="4">4 - Minecraft 1.13-1.14.4</option>
              <option value="5">5 - Minecraft 1.15-1.16.1</option>
              <option value="6">6 - Minecraft 1.16.2-1.16.5</option>
              <option value="7">7 - Minecraft 1.17-1.17.1</option>
              <option value="8">8 - Minecraft 1.18-1.18.2</option>
              <option value="9">9 - Minecraft 1.19-1.19.2</option>
              <option value="11">11 - Snapshot 22w42a-22w44a</option>
              <option value="12">12 - Minecraft 1.19.3</option>
              <option value="13">13 - Minecraft 1.19.4</option>
              <option value="14">14 - Snapshot 23w14a-23w16a</option>
              <option value="15" selected>15 - Minecraft 1.20-1.20.1</option>
              <option value="16">16 - Snapshot 23w31a</option>
              <option value="17">17 - Snapshot 23w32a-1.20.2-pre1</option>
              <option value="18">18 - Minecraft 1.20.2</option>
              <option value="19">19 - Snapshot 23w42a</option>
              <option value="20">20 - Snapshot 23w43a-23w44a</option>
              <option value="21">21 - Snapshot 23w45a-23w46a</option>
              <option value="22">22 - Minecraft 1.20.3-1.20.4</option>
              <option value="24">24 - Snapshot 24w03a-24w04a</option>
              <option value="25">25 - Snapshot 24w05a-24w05b</option>
              <option value="26">26 - Snapshot 24w06a-24w07a</option>
              <option value="28">28 - Snapshot 24w09a-24w10a</option>
              <option value="29">29 - Snapshot 24w11a</option>
              <option value="30">30 - Snapshot 24w12a</option>
              <option value="31">31 - Snapshot 24w13a-1.20.5-pre3</option>
              <option value="32">32 - Minecraft 1.20.5-1.20.6</option>
              <option value="34">34 - Minecraft 1.21-1.21.3</option>
              <option value="46">46 - Minecraft 1.21.4</option>
              <option value="55">55 - Minecraft 1.21.5</option>
              <option value="56">56 - Snapshot 25w15a</option>
              <option value="57">57 - Snapshot 25w16a</option>
              <option value="58">58 - Snapshot 25w17a</option>
              <option value="59">59 - Snapshot 25w18a</option>
              <option value="60">60 - Snapshot 25w19a</option>
              <option value="61">61 - Snapshot 25w20a</option>
              <option value="62">62 - Snapshot 25w21a</option>
              <option value="63">63 - Minecraft 1.21.6</option>
              <option value="64">64 - Minecraft 1.21.7-1.21.8</option>
            </select>
          </label>
        </div>
        <label class="ghost-file"><span data-i18n="translator.glossary">术语表 JSON</span>
          <span class="control"><span class="value" id="glossary-display">可选 .json 术语表</span><i class="ri-file-list-3-line icon"></i></span>
          <input name="glossary" type="file" accept=".json">
        </label>
        </div>
        <details class="form-card" data-advanced-panel>
          <summary><span><i class="ri-flashlight-line"></i><span data-i18n="advanced.title">高级 API 设置</span></span></summary>
        <div id="api-box" class="api-box" hidden>
          <div class="api-box-head api-box-title">
            <div>
              <strong data-i18n="advanced.api_title">AI 接口配置</strong>
              <span id="provider-badge" class="pill provider-badge">AI</span>
              <a id="api-key-link" href="#" target="_blank" rel="noopener" class="btn-key-apply" hidden>申请 Key <i class="ri-external-link-line"></i></a>
            </div>
            <div id="provider-help" class="field-help" data-i18n="advanced.provider_help">选择翻译器后会自动填入推荐 BaseURL 和模型。</div>
          </div>
          <label class="model-field"><span data-i18n="advanced.model">模型</span>
            <div class="model-row">
              <span class="ghost-select model-select" id="model-select">
                <div class="control model-control" data-model-trigger role="combobox" tabindex="0" aria-haspopup="listbox" aria-expanded="false" aria-controls="model-menu"><span class="value model-control-value" id="model-display">gpt-4o-mini</span><input type="search" class="model-control-input" id="model-search" placeholder="搜索模型" data-i18n-placeholder="advanced.model_search" autocomplete="off" spellcheck="false" aria-label="搜索模型" data-i18n-aria-label="advanced.model_search"><i class="ri-arrow-down-s-line chevron"></i></div>
                <div class="ghost-menu" id="model-menu" role="listbox" hidden></div>
                <input type="hidden" name="model" id="model" value="gpt-4o-mini">
              </span>
              <button type="button" id="model-refresh" class="model-refresh" title="获取模型列表" aria-label="获取模型列表" data-i18n-title="advanced.model_refresh" data-i18n-aria-label="advanced.model_refresh"><i class="ri-refresh-line"></i></button>
            </div>
            <span id="model-status" class="model-status"></span>
          </label>
          <label><span data-i18n="advanced.api_key">API Key</span>
            <div class="secret-input">
              <input name="api_key" id="api_key" type="password" autocomplete="new-password" placeholder="可直接粘贴 Key" data-i18n-placeholder="advanced.api_key_placeholder" autocapitalize="none" spellcheck="false">
              <button type="button" id="api-key-toggle" class="secret-toggle" aria-label="查看 API Key" data-i18n-aria-label="advanced.api_key_reveal" aria-pressed="false"><i class="ri-eye-line"></i></button>
            </div>
          </label>
          <label><span data-i18n="advanced.base_url">BaseURL</span>
            <input name="api_url" id="api_base_url" value="https://api.openai.com/v1">
            <span class="field-help" data-i18n="advanced.base_url_help">填写接口 BaseURL，例如 https://api.openai.com/v1；完整 /chat/completions 或 /messages 也兼容。</span>
          </label>
          <label><span data-i18n="advanced.api_key_env">API Key 环境变量</span>
            <input name="api_key_env" id="api_key_env" value="OPENAI_API_KEY">
            <span class="field-help" data-i18n="advanced.api_key_env_help">API Key 留空时使用该环境变量；直接填写 Key 可避免本地 UI 读不到环境变量导致报错。</span>
          </label>
          <label><span data-i18n="advanced.concurrency">并发请求数</span>
            <input name="api_concurrency" id="api_concurrency" type="number" value="2" min="1" placeholder="正在计算推荐并发...">
            <span class="field-help" id="api-concurrency-help" data-i18n="advanced.concurrency_help">内容很多时可并发翻译多个批次；中转站限流时调低到 1。</span>
          </label>
          <label><span data-i18n="advanced.retries">断线重试次数</span>
            <input name="api_retries" id="api_retries" type="number" value="5" min="1" max="10">
            <span class="field-help" data-i18n="advanced.retries_help">单个批次遇到断线、超时、429 或 5xx 时自动重试。</span>
          </label>
          <div class="grid-2">
            <label><span data-i18n="advanced.batch_size">每次请求条数</span>
              <input name="api_batch_size" id="api_batch_size" type="number" value="40" min="5" max="200">
              <span class="field-help" data-i18n="advanced.batch_size_help">控制一个 API 请求包含多少条文本；不稳定中转站建议 20。</span>
            </label>
            <label><span data-i18n="advanced.timeout">请求超时秒数</span>
              <input name="api_timeout" id="api_timeout" type="number" value="10" min="1" max="300">
              <span class="field-help" data-i18n="advanced.timeout_help">连接或读取响应超过该秒数，会进入下一次重试。</span>
            </label>
          </div>
          <label class="checkline api-debug-log-line">
            <input name="api_debug_log" type="checkbox">
            <span data-i18n="advanced.debug_log">记录 API 调试日志</span>
            <span class="field-help" data-i18n="advanced.debug_log_help">会记录请求体、响应头和原始响应到本次任务目录；Authorization/API Key 会被隐藏。</span>
          </label>
        </div>
        </details>
        <details class="form-card" data-advanced-panel open>
          <summary><span><i class="ri-equalizer-line"></i><span data-i18n="output.title">输出策略</span></span></summary>
        <label class="checkline">
          <input name="overwrite_existing" type="checkbox">
          <span data-i18n="output.overwrite">覆盖 JAR 内已有中文</span>
        </label>
        <label class="checkline">
          <input name="skip_translated" type="checkbox">
          <span data-i18n="output.skip_translated">跳过已包含目标语言的 JAR</span>
        </label>
        <label class="checkline">
          <input name="ignore_cache" type="checkbox">
          <span data-i18n="output.ignore_cache">忽略缓存并重新翻译</span>
        </label>
        <input type="hidden" name="cache_dir" id="cache_dir">
        <input type="hidden" name="ui_locale" id="ui_locale_field" value="zh_cn">
        <input type="hidden" name="ui_locale_dir" id="ui_locale_dir">
        <input type="hidden" name="ftbquests_output_mode" id="ftbquests_output_mode" value="both">
        <label class="checkline">
          <input name="scan_hardcoded" type="checkbox" checked>
          <span data-i18n="output.scan_hardcoded">扫描 Ponder / 配置硬编码英文</span>
        </label>
        <button id="submit" type="submit"><i class="ri-rocket-2-line"></i><span data-i18n="action.start">开始生成</span></button>
        <button id="cancel-btn" type="button" hidden><i class="ri-stop-circle-line"></i><span data-i18n="action.cancel">中断</span></button>
        <div id="status" class="status">等待选择 JAR。</div>
        </details>
      </form>
    </section>

    <section class="results-panel">
      <div class="panel-head">
        <div>
          <h2 data-i18n="results.title">结果</h2>
          <div class="panel-copy" data-i18n="results.copy">处理完成后可直接下载资源包，或切换到硬编码映射继续补全译文。</div>
        </div>
        <span id="job" class="job-pill"></span>
      </div>
      <div id="results" class="results">
        <div class="empty" data-i18n="results.empty">还没有生成结果。</div>
      </div>
    </section>
    <section class="settings-page" id="settings-page" data-main-view="settings" hidden>
      <div class="settings-card">
        <div class="settings-head">
          <div>
            <strong id="settings-title" data-i18n="settings.title">设置</strong>
            <span data-i18n="settings.subtitle">缓存、语言包与本地维护</span>
          </div>
          <button type="button" class="settings-close" id="settings-close" aria-label="关闭设置" data-i18n-aria-label="settings.close"><i class="ri-close-line"></i></button>
        </div>
        <div class="settings-layout">
          <section class="settings-section" id="settings-cache-section" aria-labelledby="settings-cache-title">
            <div class="settings-section-title" id="settings-cache-title"><i class="ri-database-2-line"></i><span data-i18n="settings.cache_section">缓存设置</span></div>
            <label class="settings-field"><span data-i18n="settings.cache_dir">缓存目录</span>
              <input class="ghost-input" id="settings-cache-dir" placeholder="默认：服务工作目录/.shared-cache" data-i18n-placeholder="settings.cache_placeholder" autocomplete="off" spellcheck="false">
            </label>
            <div class="settings-current">
              <span data-i18n="settings.current">当前</span>
              <strong id="settings-cache-effective">默认：服务工作目录/.shared-cache</strong>
            </div>
            <div class="settings-section-actions">
              <button type="button" class="secondary" id="settings-cache-default" data-i18n="settings.default">恢复默认</button>
              <button type="button" class="danger" id="settings-cache-clear"><i class="ri-delete-bin-6-line"></i><span data-i18n="settings.clear_cache">清空缓存</span></button>
            </div>
          </section>
          <section class="settings-section" id="settings-locale-section" aria-labelledby="settings-locale-title">
            <div class="settings-section-title" id="settings-locale-title"><i class="ri-translate-2"></i><span data-i18n="settings.language_section">界面语言</span></div>
            <label class="settings-field"><span data-i18n="settings.ui_locale_dir">语言拓展包目录</span>
              <input class="ghost-input" id="settings-ui-locale-dir" placeholder="默认：服务工作目录/.ui-locales" data-i18n-placeholder="settings.ui_locale_placeholder" autocomplete="off" spellcheck="false">
            </label>
            <div class="settings-current">
              <span data-i18n="settings.current">当前</span>
              <strong id="settings-ui-locale-effective">默认：服务工作目录/.ui-locales</strong>
            </div>
            <div class="settings-current">
              <span data-i18n="settings.language_tools">界面语言包</span>
              <strong id="settings-ui-locale-summary" data-i18n="settings.ui_locale_builtin_summary">内置 2 个语言</strong>
            </div>
            <div class="settings-section-actions">
              <button type="button" class="secondary" id="settings-ui-locale-default" data-i18n="settings.ui_locale_default">语言目录默认</button>
              <button type="button" class="secondary" id="settings-ui-locale-refresh"><i class="ri-refresh-line"></i><span data-i18n="ui_locale.refresh">刷新语言包</span></button>
              <button type="button" class="secondary" id="settings-ui-locale-import"><i class="ri-upload-2-line"></i><span data-i18n="ui_locale.import">导入语言包</span></button>
              <button type="button" class="secondary" id="settings-ui-locale-download"><i class="ri-download-2-line"></i><span data-i18n="ui_locale.download">下载所选语言包</span></button>
            </div>
          </section>
        </div>
        <input id="ui-locale-import-file" type="file" accept=".json,application/json" hidden>
        <div class="settings-footer">
          <div class="settings-status" id="settings-status"></div>
          <div class="settings-actions">
            <button type="button" id="settings-save" data-i18n="settings.save">保存</button>
          </div>
        </div>
      </div>
    </section>
  </main>
    </div>
  </div>
  <script>
    const form = document.getElementById('translate-form');
    const submit = document.getElementById('submit');
    const cancelBtn = document.getElementById('cancel-btn');
    const statusBox = document.getElementById('status');
    const results = document.getElementById('results');
    const job = document.getElementById('job');
    const headerJob = document.getElementById('header-job');
    const sourceLocale = document.getElementById('source_locale');
    const targetLocale = document.getElementById('target_locale');
    const provider = document.getElementById('provider');
    const packFormat = document.getElementById('pack_format');
    const inputKind = document.getElementById('input_kind');
    const uiLocale = document.getElementById('ui_locale');
    const uiLocaleField = document.getElementById('ui_locale_field');
    const uiLocaleDirField = document.getElementById('ui_locale_dir');
    const jarsInput = document.getElementById('jars');
    const ftbquestsInput = document.getElementById('ftbquests-files');
    const ftbquestsDirectoryInput = document.getElementById('ftbquests-directory');
    const jsonInput = document.getElementById('json-files');
    const glossaryInput = document.querySelector('input[name="glossary"]');
    const sourceLocaleDisplay = document.getElementById('source-locale-display');
    const targetLocaleDisplay = document.getElementById('target-locale-display');
    const providerDisplay = document.getElementById('provider-display');
    const packFormatDisplay = document.getElementById('pack-format-display');
    const jarsDisplay = document.getElementById('jars-display');
    const ftbquestsDisplay = document.getElementById('ftbquests-display');
    const ftbquestsDirectoryDisplay = document.getElementById('ftbquests-directory-display');
    const jsonDisplay = document.getElementById('json-display');
    const glossaryDisplay = document.getElementById('glossary-display');
    const cacheDirField = document.getElementById('cache_dir');
    const settingsOpen = document.getElementById('settings-open');
    const settingsDialog = document.getElementById('settings-page');
    const settingsClose = document.getElementById('settings-close');
    const settingsCacheDir = document.getElementById('settings-cache-dir');
    const settingsCacheEffective = document.getElementById('settings-cache-effective');
    const settingsUiLocaleDir = document.getElementById('settings-ui-locale-dir');
    const settingsUiLocaleEffective = document.getElementById('settings-ui-locale-effective');
    const settingsUiLocaleSummary = document.getElementById('settings-ui-locale-summary');
    const settingsStatus = document.getElementById('settings-status');
    const settingsCacheDefault = document.getElementById('settings-cache-default');
    const settingsCacheClear = document.getElementById('settings-cache-clear');
    const settingsUiLocaleRefresh = document.getElementById('settings-ui-locale-refresh');
    const settingsUiLocaleDefault = document.getElementById('settings-ui-locale-default');
    const settingsUiLocaleImport = document.getElementById('settings-ui-locale-import');
    const settingsUiLocaleDownload = document.getElementById('settings-ui-locale-download');
    const uiLocaleImportFile = document.getElementById('ui-locale-import-file');
    const settingsSave = document.getElementById('settings-save');
    let loadingTimer = null;
    let progressTimer = null;
    let activeJobId = '';
    let loadingStartedAt = 0;
    let loadingProgress = {
      completed: 0,
      total: 0,
      stage: 'idle',
      filesCompleted: 0,
      filesTotal: 0,
      cacheHits: 0,
      cacheMisses: 0,
      currentFile: '',
      retryAttempt: 0,
      retryMax: 0,
      retryDelay: 0,
      retryReason: '',
      requestTimeout: 10,
      batchSize: 40
    };
    const resultState = {
      payload: null,
      activeTab: 'language',
      languageSearch: '',
      languageJarFilter: '全部',
      languageFilteredCacheKey: '',
      languageFilteredEntries: [],
      languageEdits: {},
      languagePage: 1,
      activeView: 'language',
      reportSearch: '',
      hardcodedSearch: '',
      apiLogSearch: '',
      reportPage: 1,
      hardcodedPage: 1,
      apiLogPage: 1
    };
    let languageSearchDebounce = 0;
    let reportSearchDebounce = 0;
    let hardcodedReportSearchDebounce = 0;
    let apiLogSearchDebounce = 0;
    let hardcodedWorkbenchSearchDebounce = 0;
    let modelFetchDebounce = 0;
    let modelFetchSequence = 0;
    let modelOptions = [];
    const themePicker = document.getElementById('theme-picker');
    const themeToggle = document.getElementById('theme-toggle');
    const themeMenu = document.getElementById('theme-menu');
    const themeTriggerSwatches = document.querySelector('[data-theme-trigger-swatches]');
    const THEME_STORAGE_KEY = 'mc-mod-i18n-theme';
    const CACHE_DIR_STORAGE_KEY = 'mc-mod-i18n-cache-dir';
    const UI_LOCALE_STORAGE_KEY = 'mc-mod-i18n-ui-locale';
    const UI_LOCALE_DIR_STORAGE_KEY = 'mc-mod-i18n-ui-locale-dir';
    const builtinUiMessages = {
      "zh_cn": {
        "header.not_started": "未开始",
        "header.uploading": "上传中",
        "status.waiting_jar": "等待选择 JAR。",
        "status.waiting_ftbquests": "等待选择 FTB Quests 输入。",
        "status.waiting_json": "等待选择语言 JSON。",
        "status.uploading": "正在上传并处理...",
        "status.failed": "生成失败。",
        "status.process_failed": "处理失败",
        "status.progress_read_failed": "进度读取失败",
        "status.cancelled_short": "已中断。",
        "status.cancelled_task": "任务已中断。",
        "status.cancel_failed": "中断请求失败：{message}",
        "error.ftbquests_missing_input": "请上传 FTB Quests ZIP/SNBT，或选择 quests/lang/en_us 目录",
        "error.json_missing_input": "请上传语言 JSON 文件"
      },
      "en_us": {
        "header.not_started": "Not started",
        "header.uploading": "Uploading",
        "status.waiting_jar": "Waiting for JAR files.",
        "status.waiting_ftbquests": "Waiting for FTB Quests input.",
        "status.waiting_json": "Waiting for language JSON.",
        "status.uploading": "Uploading and processing...",
        "status.failed": "Generation failed.",
        "status.process_failed": "Processing failed",
        "status.progress_read_failed": "Failed to read progress",
        "status.cancelled_short": "Cancelled.",
        "status.cancelled_task": "Task cancelled.",
        "status.cancel_failed": "Cancel request failed: {message}",
        "error.ftbquests_missing_input": "Upload an FTB Quests ZIP/SNBT, or choose a quests/lang/en_us directory",
        "error.json_missing_input": "Upload a language JSON file"
      }
    };
    const uiLocaleFallbackMessages = builtinUiMessages.zh_cn;
    let uiLocaleOptions = [
      { code: 'zh_cn', name: '简体中文', native_name: '简体中文', builtin: true, complete: true, message_count: 0, missing_count: 0 },
      { code: 'en_us', name: 'English', native_name: 'English', builtin: true, complete: true, message_count: 0, missing_count: 0 }
    ];
    let currentUiMessages = uiLocaleFallbackMessages;
    const themeCatalog = [
      { id: 'auto', label: '跟随系统', group: '基础主题', icon: 'ri-computer-line', scheme: 'auto', colors: ['#2563eb', '#f8fafc', '#0f172a'] },
      { id: 'light', label: '默认浅色', group: '基础主题', icon: 'ri-sun-line', scheme: 'light', colors: ['#004ac6', '#f8f9ff', '#0b1c30'] },
      { id: 'dark', label: '默认深色', group: '基础主题', icon: 'ri-moon-clear-line', scheme: 'dark', colors: ['#60a5fa', '#020617', '#e5eefb'] },
      { id: 'forest', label: '森林安全', group: '专注主题', icon: 'ri-leaf-line', scheme: 'light', colors: ['#2f6b3f', '#f3f7f0', '#172313'] },
      { id: 'midnight', label: '午夜蓝', group: '专注主题', icon: 'ri-moon-foggy-line', scheme: 'dark', colors: ['#4f8cff', '#07111f', '#eaf2ff'] },
      { id: 'dongbei-rain', label: '东北雨', group: '趣味主题', icon: 'ri-cloudy-2-line', scheme: 'dark', colors: ['#c9162f', '#4d2f1f', '#fffaf0'] },
      { id: 'rainbow-rgb', label: '彩虹 RGB', group: '趣味主题', icon: 'ri-rainbow-line', scheme: 'dark', colors: ['#00d4ff', '#070711', '#f8fbff'] },
      { id: 'bleach-tybw', label: '死神:千年血战', group: '联名主题', icon: 'ri-sword-line', scheme: 'dark', colors: ['#e6397c', '#1a1a1d', '#fff7fb'] },
      { id: 'eva', label: 'EVA', group: '联名主题', icon: 'ri-robot-2-line', scheme: 'dark', colors: ['#b7ff2a', '#090812', '#f6ffe8'] },
      { id: 'p-site', label: 'P站', group: '联名主题', icon: 'ri-copyright-line', scheme: 'dark', colors: ['#ff9900', '#050505', '#f7f7f7'] },
      { id: 'starry-night', label: '梵高星空', group: '艺术主题', icon: 'ri-star-line', scheme: 'dark', colors: ['#f6c945', '#07142e', '#f8efcb'] },
      { id: 'monet', label: '莫奈', group: '艺术主题', icon: 'ri-palette-line', scheme: 'light', colors: ['#6b9f8a', '#eef4f2', '#243a3a'] },
      { id: 'qingming-scroll', label: '清明上河图', group: '艺术主题', icon: 'ri-landscape-line', scheme: 'light', colors: ['#2f6673', '#f3e8d2', '#2a241b'] },
      { id: 'cezanne', label: '塞尚', group: '艺术主题', icon: 'ri-brush-line', scheme: 'light', colors: ['#8f4f2f', '#efe6d8', '#2f241d'] },
      { id: 'sisley', label: '西斯莱', group: '艺术主题', icon: 'ri-brush-3-line', scheme: 'light', colors: ['#5f8fa8', '#eef4ef', '#24343a'] },
      { id: 'pissarro', label: '毕沙罗', group: '艺术主题', icon: 'ri-image-line', scheme: 'light', colors: ['#7f8f4e', '#f1eddf', '#2d2a1e'] },
      { id: 'morandi', label: '莫兰迪', group: '艺术主题', icon: 'ri-contrast-drop-line', scheme: 'light', colors: ['#8d8580', '#eeece8', '#2f2d2b'] },
      { id: 'gauguin', label: '高更', group: '艺术主题', icon: 'ri-paint-brush-line', scheme: 'light', colors: ['#b65f2a', '#f1e0c2', '#2c2117'] },
      { id: 'matisse', label: '马蒂斯', group: '艺术主题', icon: 'ri-shape-2-line', scheme: 'light', colors: ['#2468c9', '#f4efe5', '#18243a'] },
      { id: 'qi-baishi', label: '齐白石', group: '艺术主题', icon: 'ri-quill-pen-line', scheme: 'light', colors: ['#b7352d', '#f6f0e3', '#211f1b'] },
      { id: 'healing-sea-blue', label: '治愈海盐蓝', group: 'Stitch 配色', icon: 'ri-water-flash-line', scheme: 'light', colors: ['#0081ff', '#eef7ff', '#08204a'] },
      { id: 'mint-tea-green', label: '薄荷茶青', group: 'Stitch 配色', icon: 'ri-seedling-line', scheme: 'light', colors: ['#178b85', '#eefaf7', '#173a36'] },
      { id: 'neon-track', label: '荧光赛道绿', group: 'Stitch 配色', icon: 'ri-road-map-line', scheme: 'dark', colors: ['#00fd00', '#07180b', '#efffee'] },
      { id: 'cream-berry-purple', label: '奶油莓紫', group: 'Stitch 配色', icon: 'ri-cake-3-line', scheme: 'light', colors: ['#652c97', '#fff0f2', '#2d183a'] },
      { id: 'orange-slate', label: '橙灰机能', group: 'Stitch 配色', icon: 'ri-tools-line', scheme: 'dark', colors: ['#ff7400', '#172728', '#fff2e5'] },
      { id: 'seafoam-apricot', label: '海风杏桃', group: 'Stitch 配色', icon: 'ri-water-percent-line', scheme: 'light', colors: ['#01847f', '#effaf7', '#123936'] },
      { id: 'klein-gold', label: '克莱因金', group: 'Stitch 配色', icon: 'ri-vip-diamond-line', scheme: 'light', colors: ['#002fa7', '#ffcf14', '#061a4d'] },
      { id: 'honey-sunset', label: '蜜糖落日', group: 'Stitch 配色', icon: 'ri-sunset-line', scheme: 'light', colors: ['#ff6067', '#fff7d6', '#3b2b19'] },
      { id: 'crimson-ivory', label: '酒红象牙', group: 'Stitch 配色', icon: 'ri-goblet-line', scheme: 'light', colors: ['#990033', '#f4eee5', '#341019'] },
      { id: 'sakura-mist', label: '樱雾灰紫', group: 'Stitch 配色', icon: 'ri-blur-off-line', scheme: 'light', colors: ['#535369', '#ffe3ee', '#272333'] }
    ];
    const themeMeta = Object.fromEntries(themeCatalog.map(theme => [theme.id, theme]));
    const themeModes = themeCatalog.map(theme => theme.id);
    const systemThemeQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const apiBox = document.getElementById('api-box');
    const providerHelp = document.getElementById('provider-help');
    const providerBadge = document.getElementById('provider-badge');
    const apiBaseUrl = document.getElementById('api_base_url');
    const apiKey = document.getElementById('api_key');
    const apiKeyToggle = document.getElementById('api-key-toggle');
    const apiKeyEnv = document.getElementById('api_key_env');
    const model = document.getElementById('model');
    const modelSelectShell = document.getElementById('model-select');
    const modelTrigger = document.querySelector('[data-model-trigger]');
    const modelDisplay = document.getElementById('model-display');
    const modelSearch = document.getElementById('model-search');
    const modelMenu = document.getElementById('model-menu');
    const modelRefresh = document.getElementById('model-refresh');
    const modelStatus = document.getElementById('model-status');
    const apiConcurrency = document.getElementById('api_concurrency');
    const apiConcurrencyHelp = document.getElementById('api-concurrency-help');
    const uiLocaleSelectShell = document.getElementById('ui-locale-select');
    const uiLocaleDisplay = document.getElementById('ui-locale-display');
    const uiLocaleMenu = document.getElementById('ui-locale-menu');
    const sourceLocaleSelectShell = document.getElementById('source-locale-select');
    const targetLocaleSelectShell = document.getElementById('target-locale-select');
    const providerSelectShell = document.getElementById('provider-select');
    const packFormatSelectShell = document.getElementById('pack-format-select');
    const sourceLocaleMenu = document.getElementById('source-locale-menu');
    const targetLocaleMenu = document.getElementById('target-locale-menu');
    const providerMenu = document.getElementById('provider-menu');
    const packFormatMenu = document.getElementById('pack-format-menu');
    const minecraftLocales = [
      ["af_za", "Afrikaans"],
      ["ar_sa", "العربية"],
      ["ast_es", "Asturianu"],
      ["az_az", "Azərbaycanca"],
      ["ba_ru", "Башҡортса"],
      ["bar", "Boarisch"],
      ["be_by", "Беларуская"],
      ["bg_bg", "Български"],
      ["br_fr", "Brezhoneg"],
      ["brb", "Brabants"],
      ["bs_ba", "Bosanski"],
      ["ca_es", "Català"],
      ["cs_cz", "Čeština"],
      ["cy_gb", "Cymraeg"],
      ["da_dk", "Dansk"],
      ["de_at", "Österreichisches Deutsch"],
      ["de_ch", "Schweizerdeutsch"],
      ["de_de", "Deutsch"],
      ["el_gr", "Ελληνικά"],
      ["en_au", "English (Australia)"],
      ["en_ca", "English (Canada)"],
      ["en_gb", "English (UK)"],
      ["en_nz", "English (New Zealand)"],
      ["en_pt", "Pirate Speak"],
      ["en_ud", "ɥsᴉꞁƃuƎ"],
      ["en_us", "English (US)"],
      ["enp", "Anglish"],
      ["enws", "Shakespearean English"],
      ["eo_uy", "Esperanto"],
      ["es_ar", "Español (Argentina)"],
      ["es_cl", "Español (Chile)"],
      ["es_ec", "Español (Ecuador)"],
      ["es_es", "Español (España)"],
      ["es_mx", "Español (México)"],
      ["es_uy", "Español (Uruguay)"],
      ["es_ve", "Español (Venezuela)"],
      ["et_ee", "Eesti"],
      ["eu_es", "Euskara"],
      ["fa_ir", "فارسی"],
      ["fi_fi", "Suomi"],
      ["fil_ph", "Filipino"],
      ["fo_fo", "Føroyskt"],
      ["fr_ca", "Français (Canada)"],
      ["fr_fr", "Français"],
      ["fra_de", "Fränggisch"],
      ["fy_nl", "Frysk"],
      ["ga_ie", "Gaeilge"],
      ["gd_gb", "Gàidhlig"],
      ["gl_es", "Galego"],
      ["gv_im", "Gaelg"],
      ["haw_us", "ʻŌlelo Hawaiʻi"],
      ["he_il", "עברית"],
      ["hi_in", "हिन्दी"],
      ["hr_hr", "Hrvatski"],
      ["hu_hu", "Magyar"],
      ["hy_am", "Հայերեն"],
      ["id_id", "Bahasa Indonesia"],
      ["ig_ng", "Igbo"],
      ["io_en", "Ido"],
      ["is_is", "Íslenska"],
      ["isv", "Medžuslovjansky"],
      ["it_it", "Italiano"],
      ["ja_jp", "日本語"],
      ["jbo_en", "Lojban"],
      ["ka_ge", "ქართული"],
      ["kk_kz", "Қазақша"],
      ["kn_in", "ಕನ್ನಡ"],
      ["ko_kr", "한국어"],
      ["ksh", "Kölsch"],
      ["kw_gb", "Kernewek"],
      ["la_la", "Latina"],
      ["lb_lu", "Lëtzebuergesch"],
      ["li_li", "Limburgs"],
      ["lol_us", "LOLCAT"],
      ["lt_lt", "Lietuvių"],
      ["lv_lv", "Latviešu"],
      ["lzh", "文言"],
      ["mi_nz", "Māori"],
      ["mk_mk", "Македонски"],
      ["mn_mn", "Монгол"],
      ["moh_us", "Kanien'kéha"],
      ["ms_my", "Bahasa Melayu"],
      ["mt_mt", "Malti"],
      ["nah", "Nahuatl"],
      ["nds_de", "Plattdüütsch"],
      ["nl_be", "Vlaams"],
      ["nl_nl", "Nederlands"],
      ["nn_no", "Norsk nynorsk"],
      ["no_no", "Norsk bokmål"],
      ["oc_fr", "Occitan"],
      ["ovd", "Övdalsk"],
      ["pl_pl", "Polski"],
      ["pt_br", "Português (Brasil)"],
      ["pt_pt", "Português (Portugal)"],
      ["qya_aa", "Quenya"],
      ["ro_ro", "Română"],
      ["rpr", "Дореформенный русский"],
      ["ru_ru", "Русский"],
      ["ry_ua", "Русиньскый"],
      ["sah_sah", "Саха тыла"],
      ["se_no", "Davvisámegiella"],
      ["sk_sk", "Slovenčina"],
      ["sl_si", "Slovenščina"],
      ["so_so", "Af-Soomaali"],
      ["sq_al", "Shqip"],
      ["sr_sp", "Српски"],
      ["sv_se", "Svenska"],
      ["swg", "Schwäbisch"],
      ["sxu", "Säggs'sch"],
      ["szl", "Ślōnskŏ"],
      ["ta_in", "தமிழ்"],
      ["th_th", "ไทย"],
      ["tl_ph", "Tagalog"],
      ["tlh_aa", "tlhIngan Hol"],
      ["tok", "Toki Pona"],
      ["tr_tr", "Türkçe"],
      ["tt_ru", "Татарча"],
      ["uk_ua", "Українська"],
      ["val_es", "Català (Valencià)"],
      ["vec_it", "Vèneto"],
      ["vi_vn", "Tiếng Việt"],
      ["yi_de", "ייִדיש"],
      ["yo_ng", "Yorùbá"],
      ["zh_cn", "简体中文"],
      ["zh_hk", "繁體中文（香港）"],
      ["zh_tw", "繁體中文"],
      ["zlm_arab", "بهاس ملايو"]
    ];
    const providerPresets = {
      'openai-compatible': {
        label: '兼容 OpenAI',
        url: 'https://api.openai.com/v1',
        model: 'gpt-4o-mini',
        env: 'OPENAI_API_KEY',
        help: '适用于任何兼容 OpenAI Chat Completions 的服务。',
        keyUrl: ''
      },
      'anthropic-compatible': {
        label: '兼容 Anthropic',
        url: 'https://api.anthropic.com/v1',
        model: 'claude-3-5-haiku-latest',
        env: 'ANTHROPIC_API_KEY',
        help: '适用于 Anthropic Messages API 或兼容该格式的服务。',
        keyUrl: ''
      }
    };
    const hardcodedState = {
      entries: [],
      filter: 'all',
      search: '',
      page: 1,
      selected: new Set()
    };
    let apiLogLines = [];

    function storedThemeMode() {
      try {
        const stored = localStorage.getItem(THEME_STORAGE_KEY) || document.documentElement.dataset.themeMode || 'auto';
        return themeMeta[stored] ? stored : 'auto';
      } catch (error) {
        const stored = document.documentElement.dataset.themeMode || 'auto';
        return themeMeta[stored] ? stored : 'auto';
      }
    }

    function resolveThemeMode(mode) {
      const requested = themeMeta[mode] ? mode : 'auto';
      if (requested === 'auto') {
        return systemThemeQuery.matches ? 'dark' : 'light';
      }
      return requested;
    }

    function themeColorScheme(themeId) {
      const meta = themeMeta[themeId] || themeMeta.light;
      return meta.scheme === 'dark' ? 'dark' : 'light';
    }

    function themeSwatchesHtml(colors, extraClass = '') {
      return `<span class="theme-swatches ${escapeHtml(extraClass)}" aria-hidden="true">
        ${(colors || []).map(color => `<span class="theme-swatch" style="background:${escapeHtml(color)}"></span>`).join('')}
      </span>`;
    }

    const themeGroupMessageKeys = {
      '基础主题': 'theme.group.basic',
      '专注主题': 'theme.group.focus',
      '趣味主题': 'theme.group.playful',
      '联名主题': 'theme.group.crossover',
      '艺术主题': 'theme.group.art',
      'Stitch 配色': 'theme.group.stitch'
    };

    function themeMessageKey(theme) {
      return `theme.${String(theme?.id || '').replace(/[^a-z0-9_-]/gi, '_')}`;
    }

    function themeGroupMessageKey(theme) {
      return themeGroupMessageKeys[theme?.group] || `theme.group.${String(theme?.group || '').replace(/[^a-z0-9_-]/gi, '_')}`;
    }

    function themeLabel(theme) {
      return ui(themeMessageKey(theme), theme?.label || '');
    }

    function themeGroupLabel(theme) {
      return ui(themeGroupMessageKey(theme), theme?.group || '');
    }

    function themeModeText(theme) {
      if (!theme || theme.id === 'auto') {
        const resolvedMeta = themeMeta[resolveThemeMode('auto')] || themeMeta.light;
        return formatUi('theme.mode.auto_resolved', '当前解析为 {theme}', { theme: themeLabel(resolvedMeta) });
      }
      return theme.scheme === 'dark' ? ui('theme.mode.dark', '深色') : ui('theme.mode.light', '浅色');
    }

    function renderThemeMenu(activeMode) {
      if (!themeMenu) {
        return;
      }
      const groups = [];
      const groupMap = new Map();
      themeCatalog.forEach(theme => {
        const groupKey = themeGroupMessageKey(theme);
        if (!groupMap.has(groupKey)) {
          const group = { label: themeGroupLabel(theme), items: [] };
          groupMap.set(groupKey, group);
          groups.push(group);
        }
        groupMap.get(groupKey).items.push(theme);
      });
      themeMenu.innerHTML = groups.map(group => `
        <div class="theme-group" role="group" aria-label="${escapeHtml(group.label)}">
          <div class="theme-group-title">${escapeHtml(group.label)}</div>
          ${group.items.map(theme => {
            const active = activeMode === theme.id;
            const label = themeLabel(theme);
            const groupLabel = themeGroupLabel(theme);
            return `
              <button type="button" class="theme-option ${active ? 'active' : ''}" data-theme-value="${escapeHtml(theme.id)}" role="option" aria-selected="${active ? 'true' : 'false'}">
                <span class="theme-option-copy"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(groupLabel)} · ${escapeHtml(themeModeText(theme))}</span></span>
                ${themeSwatchesHtml(theme.colors || [])}
              </button>
            `;
          }).join('')}
        </div>
      `).join('');
    }

    function setThemeMenuOpen(open) {
      if (!themePicker || !themeMenu || !themeToggle) {
        return;
      }
      themePicker.classList.toggle('open', open);
      themeMenu.hidden = !open;
      themeToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    function applyThemeMode(mode, persist = false) {
      const requested = themeMeta[mode] ? mode : 'auto';
      const resolved = resolveThemeMode(requested);
      const scheme = themeColorScheme(resolved);
      document.documentElement.dataset.themeMode = requested;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = scheme;
      if (persist) {
        try {
          localStorage.setItem(THEME_STORAGE_KEY, requested);
        } catch (error) {}
      }
      if (themeToggle) {
        const meta = themeMeta[requested] || themeMeta.auto;
        const resolvedMeta = themeMeta[resolved] || themeMeta.light;
        const icon = themeToggle.querySelector('[data-theme-icon]');
        const label = themeToggle.querySelector('[data-theme-label]');
        if (icon) {
          icon.className = meta.icon;
        }
        if (label) {
          label.textContent = themeLabel(meta);
        }
        if (themeTriggerSwatches) {
          const colors = requested === 'auto' ? resolvedMeta.colors : meta.colors;
          themeTriggerSwatches.innerHTML = (colors || []).map(color => `<span class="theme-swatch" style="background:${escapeHtml(color)}"></span>`).join('');
        }
        themeToggle.dataset.themeMode = requested;
        themeToggle.title = formatUi('theme.title', '主题：{theme}', { theme: themeLabel(meta) });
      }
      renderThemeMenu(requested);
    }

    applyThemeMode(storedThemeMode());
    const handleSystemThemeChange = () => {
      if ((document.documentElement.dataset.themeMode || 'auto') === 'auto') {
        applyThemeMode('auto');
      }
    };
    if (typeof systemThemeQuery.addEventListener === 'function') {
      systemThemeQuery.addEventListener('change', handleSystemThemeChange);
    } else if (typeof systemThemeQuery.addListener === 'function') {
      systemThemeQuery.addListener(handleSystemThemeChange);
    }

    function bindThemePicker() {
      renderThemeMenu(document.documentElement.dataset.themeMode || storedThemeMode());
      if (!themePicker || !themeToggle || !themeMenu) {
        return;
      }
      themeToggle.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        setThemeMenuOpen(themeMenu.hidden);
      });
      themeMenu.addEventListener('click', event => {
        const option = event.target.closest('[data-theme-value]');
        if (!option) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        applyThemeMode(option.dataset.themeValue || 'auto', true);
        setThemeMenuOpen(false);
      });
      themeMenu.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
          event.preventDefault();
          setThemeMenuOpen(false);
          themeToggle.focus();
        }
      });
      document.addEventListener('click', event => {
        if (!themePicker.contains(event.target)) {
          setThemeMenuOpen(false);
        }
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
          setThemeMenuOpen(false);
        }
      });
    }

    bindThemePicker();

    function normalizeCacheDirSetting(value) {
      return String(value || '').trim();
    }

    function storedCacheDirSetting() {
      try {
        return normalizeCacheDirSetting(localStorage.getItem(CACHE_DIR_STORAGE_KEY) || '');
      } catch (error) {
        return '';
      }
    }

    function cacheDirDisplayLabel(value) {
      const normalized = normalizeCacheDirSetting(value);
      return normalized || ui('settings.cache_placeholder', '默认：服务工作目录/.shared-cache');
    }

    function normalizeUiLocaleDirSetting(value) {
      return String(value || '').trim();
    }

    function storedUiLocaleDirSetting() {
      try {
        return normalizeUiLocaleDirSetting(localStorage.getItem(UI_LOCALE_DIR_STORAGE_KEY) || '');
      } catch (error) {
        return '';
      }
    }

    function uiLocaleDirDisplayLabel(value) {
      const normalized = normalizeUiLocaleDirSetting(value);
      return normalized || ui('settings.ui_locale_placeholder', '默认：服务工作目录/.ui-locales');
    }

    function refreshSettingsDirectoryLabels() {
      if (settingsCacheEffective) {
        settingsCacheEffective.textContent = cacheDirDisplayLabel(cacheDirField ? cacheDirField.value : storedCacheDirSetting());
      }
      if (settingsUiLocaleEffective) {
        settingsUiLocaleEffective.textContent = uiLocaleDirDisplayLabel(uiLocaleDirField ? uiLocaleDirField.value : storedUiLocaleDirSetting());
      }
    }

    function applyCacheDirSetting(value, persist = false) {
      const normalized = normalizeCacheDirSetting(value);
      if (cacheDirField) {
        cacheDirField.value = normalized;
      }
      if (settingsCacheDir && settingsCacheDir.value !== normalized) {
        settingsCacheDir.value = normalized;
      }
      if (settingsCacheEffective) {
        settingsCacheEffective.textContent = cacheDirDisplayLabel(normalized);
      }
      if (persist) {
        try {
          if (normalized) {
            localStorage.setItem(CACHE_DIR_STORAGE_KEY, normalized);
          } else {
            localStorage.removeItem(CACHE_DIR_STORAGE_KEY);
          }
        } catch (error) {}
      }
      return normalized;
    }

    function applyUiLocaleDirSetting(value, persist = false) {
      const normalized = normalizeUiLocaleDirSetting(value);
      if (uiLocaleDirField) {
        uiLocaleDirField.value = normalized;
      }
      if (settingsUiLocaleDir && settingsUiLocaleDir.value !== normalized) {
        settingsUiLocaleDir.value = normalized;
      }
      if (settingsUiLocaleEffective) {
        settingsUiLocaleEffective.textContent = uiLocaleDirDisplayLabel(normalized);
      }
      if (persist) {
        try {
          if (normalized) {
            localStorage.setItem(UI_LOCALE_DIR_STORAGE_KEY, normalized);
          } else {
            localStorage.removeItem(UI_LOCALE_DIR_STORAGE_KEY);
          }
        } catch (error) {}
      }
      return normalized;
    }

    function uiLocaleLabel(option) {
      if (!option) {
        return ui('ui_locale.zh_cn', '简体中文');
      }
      const suffix = option.missing_count ? formatUi('ui_locale.missing_suffix', '（缺 {count}）', { count: option.missing_count }) : '';
      return `${option.native_name || option.name || option.code}${suffix}`;
    }

    function uiLocaleQuery() {
      const dir = uiLocaleDirField ? uiLocaleDirField.value : '';
      return dir ? `?ui_locale_dir=${encodeURIComponent(dir)}` : '';
    }

    function syncUiLocaleDisplay() {
      const option = uiLocaleOptions.find(item => item.code === uiLocale.value) || uiLocaleOptions[0];
      if (uiLocaleDisplay) {
        uiLocaleDisplay.textContent = uiLocaleLabel(option);
      }
      if (uiLocaleField) {
        uiLocaleField.value = uiLocale.value || 'zh_cn';
      }
      if (uiLocaleMenu) {
        updateSelectMenuActive(uiLocaleMenu, uiLocale.value);
      }
    }

    function buildUiLocaleMenu() {
      if (!uiLocaleMenu) {
        return;
      }
      uiLocaleMenu.innerHTML = uiLocaleOptions.map(option => `
        <button type="button" class="ghost-option ${option.code === uiLocale.value ? 'active' : ''}" data-select-value="ui_locale" data-value="${escapeHtml(option.code)}" role="option" aria-selected="${option.code === uiLocale.value ? 'true' : 'false'}">
          <strong>${escapeHtml(uiLocaleLabel(option))}</strong><span>${escapeHtml(option.code)} · ${escapeHtml(option.builtin ? ui('ui_locale.builtin', '内置') : ui('ui_locale.extension', '扩展'))}</span>
        </button>
      `).join('');
    }

    async function refreshUiLocales(silent = false) {
      try {
        const response = await fetch(`/api/ui-locales${uiLocaleQuery()}`);
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.error || '语言包列表读取失败');
        }
        uiLocaleOptions = payload.locales || uiLocaleOptions;
        const current = normalizeLocaleValue(uiLocale.value || storedUiLocaleSetting());
        uiLocale.innerHTML = uiLocaleOptions.map(option => `<option value="${escapeHtml(option.code)}">${escapeHtml(uiLocaleLabel(option))}</option>`).join('');
        uiLocale.value = uiLocaleOptions.some(option => option.code === current) ? current : 'zh_cn';
      if (settingsUiLocaleSummary) {
          const extensionCount = uiLocaleOptions.filter(option => !option.builtin).length;
          settingsUiLocaleSummary.textContent = formatUi('settings.ui_locale_summary', '可用 {total} 个语言，扩展 {extension} 个', { total: uiLocaleOptions.length, extension: extensionCount });
        }
        buildUiLocaleMenu();
        syncUiLocaleDisplay();
        if (!silent) {
          setSettingsStatus(ui('settings.ui_locale_refreshed', '语言包列表已刷新。'));
        }
      } catch (error) {
        if (!silent) {
          setSettingsStatus(error.message || ui('settings.ui_locale_read_failed', '语言包列表读取失败'), true);
        }
      }
    }

    function storedUiLocaleSetting() {
      try {
        return normalizeLocaleValue(localStorage.getItem(UI_LOCALE_STORAGE_KEY) || '');
      } catch (error) {
        return '';
      }
    }

    function urlUiLocaleSetting() {
      try {
        return normalizeLocaleValue(new URLSearchParams(window.location.search).get('ui_locale') || '');
      } catch (error) {
        return '';
      }
    }

    function browserUiLocaleSetting() {
      const candidates = [navigator.language, ...(navigator.languages || [])]
        .map(value => normalizeLocaleValue(value))
        .filter(Boolean);
      for (const candidate of candidates) {
        if (candidate.startsWith('zh')) {
          return 'zh_cn';
        }
        if (candidate.startsWith('en')) {
          return 'en_us';
        }
        if (uiLocaleOptions.some(option => option.code === candidate)) {
          return candidate;
        }
      }
      return '';
    }

    function preferredUiLocaleSetting() {
      return urlUiLocaleSetting() || storedUiLocaleSetting() || browserUiLocaleSetting() || 'zh_cn';
    }

    function applyUiLocale(value, persist = false) {
      const normalized = normalizeLocaleValue(value || 'zh_cn') || 'zh_cn';
      uiLocale.value = uiLocaleOptions.some(option => option.code === normalized) ? normalized : 'zh_cn';
      currentUiMessages = builtinUiMessages[uiLocale.value] || uiLocaleFallbackMessages;
      document.documentElement.lang = uiLocale.value.replace('_', '-');
      if (persist) {
        try {
          localStorage.setItem(UI_LOCALE_STORAGE_KEY, uiLocale.value);
        } catch (error) {}
      }
      syncUiLocaleDisplay();
      fetch(`/api/ui-locales/export/${encodeURIComponent(uiLocale.value)}${uiLocaleQuery()}`)
        .then(response => response.ok ? response.json() : null)
        .then(packageData => {
          if (packageData && packageData.messages && uiLocale.value === packageData.locale) {
            currentUiMessages = { ...currentUiMessages, ...packageData.messages };
            applyUiMessageNodes();
            refreshDynamicUi();
          }
        })
        .catch(() => {});
      applyUiMessageNodes();
      refreshDynamicUi();
    }

    function t(key, params = {}) {
      const template = currentUiMessages[key] || uiLocaleFallbackMessages[key] || key;
      return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (match, name) => (
        Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
      ));
    }

    function ui(key, fallback) {
      return currentUiMessages[key] || uiLocaleFallbackMessages[key] || fallback || key;
    }

    function formatUi(key, fallback, params = {}) {
      const template = ui(key, fallback);
      return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (match, name) => (
        Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
      ));
    }

    function refreshDynamicUi() {
      syncHeaderJobIdle();
      applyThemeMode(document.documentElement.dataset.themeMode || storedThemeMode());
      renderThemeMenu(document.documentElement.dataset.themeMode || storedThemeMode());
      syncInputKind();
      syncFiles();
      syncProvider(false);
      syncPackFormat();
      syncSourceLocale();
      syncTargetLocale();
      syncConcurrencyHint();
      refreshSettingsDirectoryLabels();
      refreshSelectMenusForCurrentLocale();
      if (resultState.payload) {
        renderResultShell();
      }
    }

    function applyUiMessageNodes() {
      document.querySelectorAll('[data-i18n]').forEach(node => {
        const key = node.dataset.i18n;
        const value = currentUiMessages[key] || uiLocaleFallbackMessages[key];
        if (value) {
          node.textContent = value;
        }
      });
      document.querySelectorAll('[data-i18n-placeholder]').forEach(node => {
        const key = node.dataset.i18nPlaceholder;
        const value = currentUiMessages[key] || uiLocaleFallbackMessages[key];
        if (value) {
          node.setAttribute('placeholder', value);
        }
      });
      document.querySelectorAll('[data-i18n-title]').forEach(node => {
        const key = node.dataset.i18nTitle;
        const value = currentUiMessages[key] || uiLocaleFallbackMessages[key];
        if (value) {
          node.setAttribute('title', value);
        }
      });
      document.querySelectorAll('[data-i18n-aria-label]').forEach(node => {
        const key = node.dataset.i18nAriaLabel;
        const value = currentUiMessages[key] || uiLocaleFallbackMessages[key];
        if (value) {
          node.setAttribute('aria-label', value);
        }
      });
    }

    function syncHeaderJobIdle() {
      if (!activeJobId && !resultState.payload && headerJob) {
        headerJob.textContent = ui('header.not_started', '未开始');
      }
    }

    function setSettingsStatus(message, isError = false) {
      if (!settingsStatus) {
        return;
      }
      settingsStatus.textContent = message || '';
      settingsStatus.classList.toggle('error', Boolean(isError));
    }

    function openSettingsDialog() {
      if (!settingsDialog) {
        return;
      }
      applyThemeMode(document.documentElement.dataset.themeMode || storedThemeMode());
      applyCacheDirSetting(cacheDirField ? cacheDirField.value : storedCacheDirSetting());
      applyUiLocaleDirSetting(uiLocaleDirField ? uiLocaleDirField.value : storedUiLocaleDirSetting());
      setSettingsStatus('');
      switchView('settings');
      window.setTimeout(() => {
        if (settingsCacheDir) {
          settingsCacheDir.focus();
        }
      }, 0);
    }

    function closeSettingsDialog() {
      switchView('language');
    }

    function bindSettingsMenu() {
      applyCacheDirSetting(storedCacheDirSetting());
      applyUiLocaleDirSetting(storedUiLocaleDirSetting());
      if (!settingsDialog) {
        return;
      }
      if (settingsOpen) {
        settingsOpen.addEventListener('click', openSettingsDialog);
      }
      if (settingsClose) {
        settingsClose.addEventListener('click', closeSettingsDialog);
      }
      if (settingsCacheDir) {
        settingsCacheDir.addEventListener('input', () => {
          applyCacheDirSetting(settingsCacheDir.value, false);
          setSettingsStatus('');
        });
      }
      if (settingsUiLocaleDir) {
        settingsUiLocaleDir.addEventListener('input', () => {
          applyUiLocaleDirSetting(settingsUiLocaleDir.value, false);
          setSettingsStatus('');
        });
      }
      if (settingsCacheDefault) {
        settingsCacheDefault.addEventListener('click', () => {
          applyCacheDirSetting('', true);
          setSettingsStatus(ui('settings.cache_default_done', '已恢复默认缓存目录。'));
        });
      }
      if (settingsUiLocaleDefault) {
        settingsUiLocaleDefault.addEventListener('click', () => {
          applyUiLocaleDirSetting('', true);
          setSettingsStatus(ui('settings.ui_locale_default_done', '已恢复默认语言拓展包目录。'));
          refreshUiLocales(true);
        });
      }
      if (settingsSave) {
        settingsSave.addEventListener('click', () => {
          applyCacheDirSetting(settingsCacheDir ? settingsCacheDir.value : '', true);
          applyUiLocaleDirSetting(settingsUiLocaleDir ? settingsUiLocaleDir.value : '', true);
          setSettingsStatus(ui('settings.saved', '设置已保存。'));
          refreshUiLocales(true);
        });
      }
      if (settingsUiLocaleRefresh) {
        settingsUiLocaleRefresh.addEventListener('click', () => refreshUiLocales(false));
      }
      if (settingsUiLocaleDownload) {
        settingsUiLocaleDownload.addEventListener('click', () => {
          const locale = uiLocale.value || 'zh_cn';
          window.location.href = `/api/ui-locales/export/${encodeURIComponent(locale)}${uiLocaleQuery()}`;
        });
      }
      if (settingsUiLocaleImport && uiLocaleImportFile) {
        settingsUiLocaleImport.addEventListener('click', () => uiLocaleImportFile.click());
        uiLocaleImportFile.addEventListener('change', async () => {
          const file = uiLocaleImportFile.files[0];
          if (!file) {
            return;
          }
          const data = new FormData();
          data.append('ui_locale_dir', uiLocaleDirField ? uiLocaleDirField.value : '');
          data.append('ui_locale_file', file, file.name);
          settingsUiLocaleImport.disabled = true;
          setSettingsStatus(ui('settings.ui_locale_importing', '正在导入语言包...'));
          try {
            const response = await fetch('/api/ui-locales/import', { method: 'POST', body: data });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
              throw new Error(payload.error || ui('settings.ui_locale_import_failed', '语言包导入失败'));
            }
            setSettingsStatus(formatUi('settings.ui_locale_imported', '已导入 {locale}，缺失 {missing} 个 key。', { locale: payload.locale, missing: payload.missing_count || 0 }));
            await refreshUiLocales(true);
          } catch (error) {
            setSettingsStatus(error.message || ui('settings.ui_locale_import_failed', '语言包导入失败'), true);
          } finally {
            settingsUiLocaleImport.disabled = false;
            uiLocaleImportFile.value = '';
          }
        });
      }
      if (settingsCacheClear) {
        settingsCacheClear.addEventListener('click', async () => {
          const cacheDir = applyCacheDirSetting(settingsCacheDir ? settingsCacheDir.value : '', true);
          settingsCacheClear.disabled = true;
          setSettingsStatus(ui('settings.cache_clearing', '正在清空缓存...'));
          try {
            const response = await fetch('/api/cache/clear', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ cache_dir: cacheDir })
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
              throw new Error(payload.error || ui('settings.cache_clear_failed', '清空缓存失败'));
            }
            setSettingsStatus(formatUi('settings.cache_cleared', '已清空 {removed} 项：{path}', { removed: payload.removed || 0, path: payload.cache_dir || cacheDirDisplayLabel(cacheDir) }));
          } catch (error) {
            setSettingsStatus(error.message || ui('settings.cache_clear_failed', '清空缓存失败'), true);
          } finally {
            settingsCacheClear.disabled = false;
          }
        });
      }
    }

    bindSettingsMenu();

    function normalizeLocaleValue(value) {
      return String(value || '').trim().toLowerCase().replace(/-/g, '_');
    }

    function isValidLocaleValue(value) {
      return /^[a-z0-9_]{2,24}$/.test(normalizeLocaleValue(value));
    }

    function labelForLocale(value) {
      const normalized = normalizeLocaleValue(value);
      const found = minecraftLocales.find(([code]) => code === normalized);
      return found ? found[1] : ui('language.custom', '自定义语言');
    }

    function localeOptionText(value, label) {
      return `${value} - ${label || labelForLocale(value)}`;
    }

    function ensureSelectOption(select, value, label) {
      const normalized = normalizeLocaleValue(value);
      if (!normalized) {
        return null;
      }
      let option = Array.from(select.options).find(item => item.value === normalized);
      if (!option) {
        option = document.createElement('option');
        option.value = normalized;
        select.appendChild(option);
      }
      option.textContent = localeOptionText(normalized, label || labelForLocale(normalized));
      return option;
    }

    function populateLocaleSelect(select, fallbackValue) {
      const selectedValue = normalizeLocaleValue(select.value || fallbackValue);
      select.innerHTML = minecraftLocales.map(([value, label]) => {
        const selected = value === selectedValue ? ' selected' : '';
        return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(localeOptionText(value, label))}</option>`;
      }).join('');
      if (!Array.from(select.options).some(option => option.value === selectedValue)) {
        ensureSelectOption(select, selectedValue, labelForLocale(selectedValue));
      }
      select.value = selectedValue;
    }

    function localeSearchLabel(name) {
      if (name === 'source_locale') {
        return ui('language.search_source', '搜索源语言');
      }
      if (name === 'target_locale') {
        return ui('language.search_target', '搜索目标语言');
      }
      return ui('language.search_source', '搜索语言');
    }

    function normalizeSearchValue(value) {
      return String(value || '').trim().toLowerCase().replace(/-/g, '_');
    }

    function compactSearchValue(value) {
      return normalizeSearchValue(value).replace(/[\s_()（）]+/g, '');
    }

    function localeOptionExists(select, value) {
      const normalized = normalizeLocaleValue(value);
      return Array.from(select.options).some(option => normalizeLocaleValue(option.value) === normalized);
    }

    function isKnownMinecraftLocale(value) {
      const normalized = normalizeLocaleValue(value);
      return minecraftLocales.some(([code]) => code === normalized);
    }

    function isLikelyFtbquestsLocale(value) {
      const normalized = normalizeLocaleValue(value);
      const localePattern = /^[a-z]{2,3}_[a-z0-9]{2,8}$/;
      return isKnownMinecraftLocale(normalized) || localePattern.test(normalized);
    }

    function inferLocaleFromFtbquestsUploadPath(path) {
      const parts = String(path || '')
        .replace(/\\/g, '/')
        .split('/')
        .map(part => part.trim())
        .filter(Boolean);
      if (!parts.length) {
        return '';
      }
      const filename = parts[parts.length - 1].toLowerCase();
      if (filename.endsWith('.snbt')) {
        const basename = normalizeLocaleValue(filename.slice(0, -5));
        if (isLikelyFtbquestsLocale(basename)) {
          return basename;
        }
      }
      for (let index = 0; index < parts.length - 1; index += 1) {
        const segment = normalizeLocaleValue(parts[index]);
        if (!isLikelyFtbquestsLocale(segment)) {
          continue;
        }
        const previous = index > 0 ? parts[index - 1].toLowerCase() : '';
        const next = index + 1 < parts.length ? parts[index + 1].toLowerCase() : '';
        if (!index || previous === 'lang' || next === 'chapters' || filename.endsWith('.snbt')) {
          return segment;
        }
      }
      return '';
    }

    function inferFtbquestsSourceLocaleFromFiles(files) {
      const locales = Array.from(files || [])
        .map(file => inferLocaleFromFtbquestsUploadPath(file.webkitRelativePath || file.name))
        .filter(Boolean);
      const uniqueLocales = [...new Set(locales)];
      if (uniqueLocales.length === 1) {
        return uniqueLocales[0];
      }
      return '';
    }

    function syncFtbquestsSourceLocaleFromInput() {
      if (inputKind.value !== 'ftbquests') {
        return;
      }
      const files = [
        ...Array.from(ftbquestsInput.files || []),
        ...Array.from(ftbquestsDirectoryInput.files || [])
      ];
      const inferredLocale = inferFtbquestsSourceLocaleFromFiles(files);
      if (!inferredLocale || inferredLocale === normalizeLocaleValue(sourceLocale.value)) {
        return;
      }
      ensureSelectOption(sourceLocale, inferredLocale, labelForLocale(inferredLocale));
      sourceLocale.value = inferredLocale;
      syncSourceLocale();
      if (sourceLocaleMenu.dataset.localeName) {
        sourceLocaleMenu.innerHTML = buildLocaleSelectMenuOptions(sourceLocale, 'source_locale');
      }
    }

    function localeMatchesOption(option, query) {
      const rawQuery = String(query || '').trim().toLowerCase();
      if (!rawQuery) {
        return true;
      }
      const value = normalizeLocaleValue(option.value);
      const label = labelForLocale(value);
      const text = String(option.textContent || '');
      const haystack = `${value} ${value.replace(/_/g, ' ')} ${label} ${text}`.toLowerCase();
      const normalizedQuery = normalizeSearchValue(rawQuery);
      const compactQuery = compactSearchValue(rawQuery);
      return normalizeSearchValue(haystack).includes(normalizedQuery)
        || haystack.includes(rawQuery)
        || Boolean(compactQuery && compactSearchValue(haystack).includes(compactQuery));
    }

    function buildLocaleOptionButtons(select, name, query = '') {
      return Array.from(select.options)
        .filter(option => localeMatchesOption(option, query))
        .map(option => {
          const value = normalizeLocaleValue(option.value);
          const label = labelForLocale(value);
          const selected = value === normalizeLocaleValue(select.value);
          return `
            <button type="button" class="ghost-option ${selected ? 'active' : ''}" data-select-value="${escapeHtml(name)}" data-value="${escapeHtml(value)}" role="option" aria-selected="${selected ? 'true' : 'false'}">
              <strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span>
            </button>
          `;
        }).join('');
    }

    function buildLocaleApplyOption(select, name, query = '') {
      const normalized = normalizeLocaleValue(query);
      const hidden = !isValidLocaleValue(normalized) || localeOptionExists(select, normalized) ? ' hidden' : '';
      const label = normalized ? formatUi('language.use_locale', '使用 {locale}', { locale: normalized }) : ui('language.use_input', '使用输入值');
      return `
        <button type="button" class="ghost-option locale-custom-option" data-select-value="${escapeHtml(name)}" data-value="${escapeHtml(normalized)}" data-custom-locale="true" data-locale-apply role="option" aria-selected="false"${hidden}>
          <strong>${escapeHtml(label)}</strong><span>${escapeHtml(ui('language.custom_code', '自定义语言代码'))}</span>
        </button>
      `;
    }

    function buildLocaleSelectMenuOptions(select, name, query = '') {
      const optionsHtml = buildLocaleOptionButtons(select, name, query);
      const emptyHidden = optionsHtml.trim() ? ' hidden' : '';
      return `
        ${buildLocaleApplyOption(select, name, query)}
        <div class="ghost-options" data-locale-options>
          ${optionsHtml}
        </div>
        <div class="ghost-empty" data-locale-empty${emptyHidden}>${escapeHtml(ui('language.no_builtin_match', '没有匹配的内置语言。可输入有效 Minecraft 语言代码后使用自定义语言。'))}</div>
      `;
    }

    function updateLocaleApply(menu, select, value) {
      const apply = menu.querySelector('[data-locale-apply]');
      if (!apply) {
        return;
      }
      const normalized = normalizeLocaleValue(value);
      apply.hidden = !isValidLocaleValue(normalized) || localeOptionExists(select, normalized);
      apply.dataset.value = normalized;
      const label = apply.querySelector('strong');
      if (label) {
        label.textContent = normalized ? formatUi('language.use_locale', '使用 {locale}', { locale: normalized }) : ui('language.use_input', '使用输入值');
      }
    }

    function refreshLocaleMenuSearch(menu, select, query) {
      const options = menu.querySelector('[data-locale-options]');
      if (options) {
        options.innerHTML = buildLocaleOptionButtons(select, menu.dataset.localeName, query);
      }
      const empty = menu.querySelector('[data-locale-empty]');
      if (empty) {
        empty.hidden = Boolean(options && options.children.length);
      }
      updateLocaleApply(menu, select, query);
      updateSelectMenuActive(menu, select.value);
    }

    function localeChoiceNodes(menu) {
      const nodes = Array.from(menu.querySelectorAll('[data-locale-apply]:not([hidden]), [data-locale-options] [data-select-value]'));
      return nodes.filter((node, index) => nodes.indexOf(node) === index);
    }

    function focusLocaleChoice(menu, current, direction, input = null) {
      const choices = localeChoiceNodes(menu);
      if (!choices.length) {
        return;
      }
      if (current === input) {
        choices[direction < 0 ? choices.length - 1 : 0].focus();
        return;
      }
      const option = current.closest ? current.closest('[data-select-value]') : null;
      const currentIndex = choices.indexOf(option);
      const nextIndex = currentIndex + direction;
      if (nextIndex < 0) {
        if (input) {
          input.focus();
        }
        return;
      }
      choices[nextIndex >= choices.length ? 0 : nextIndex].focus();
    }

    function selectLocaleFromInput(menu, input) {
      const query = input ? input.value.trim() : '';
      if (!query) {
        return false;
      }
      const normalized = normalizeLocaleValue(query);
      const exactOption = Array.from(menu.querySelectorAll('[data-locale-options] [data-select-value]'))
        .find(option => option.dataset.value === normalized);
      if (exactOption) {
        exactOption.click();
        return true;
      }
      const apply = menu.querySelector('[data-locale-apply]');
      if (apply && !apply.hidden) {
        apply.click();
        return true;
      }
      const firstOption = menu.querySelector('[data-locale-options] [data-select-value]');
      if (firstOption) {
        firstOption.click();
        return true;
      }
      return false;
    }

    function compactModelText(value) {
      return String(value || '').trim().toLowerCase().replace(/[\s_./:-]+/g, '');
    }

    function modelMatchesOption(option, query) {
      const rawQuery = String(query || '').trim().toLowerCase();
      if (!rawQuery) {
        return true;
      }
      const haystack = `${option.id || ''} ${option.label || ''}`.toLowerCase();
      return haystack.includes(rawQuery) || compactModelText(haystack).includes(compactModelText(rawQuery));
    }

    function normalizeModelOptions(items) {
      const seen = new Set();
      return (Array.isArray(items) ? items : [])
        .map(item => {
          const id = String(item?.id || item?.value || item || '').trim();
          const label = String(item?.label || item?.display_name || id).trim();
          return id ? { id, label: label || id } : null;
        })
        .filter(item => {
          if (!item || seen.has(item.id)) {
            return false;
          }
          seen.add(item.id);
          return true;
        });
    }

    function setModelValue(value) {
      const normalized = String(value || '').trim();
      if (!normalized) {
        return;
      }
      model.value = normalized;
      syncModelDisplay();
    }

    function syncModelDisplay() {
      const value = String(model.value || '').trim();
      const option = modelOptions.find(item => item.id === value);
      modelDisplay.textContent = option ? option.id : (value || '选择模型');
      updateModelMenuActive();
    }

    function setModelStatus(message, isError = false) {
      modelStatus.textContent = message || '';
      modelStatus.classList.toggle('error', Boolean(isError));
    }

    function buildModelMenuOptions(query = '') {
      const filtered = modelOptions.filter(option => modelMatchesOption(option, query));
      const rows = filtered.map(option => {
        const active = option.id === model.value;
        const meta = option.label && option.label !== option.id ? `<span>${escapeHtml(option.label)}</span>` : '';
        return `
          <button type="button" class="ghost-option ${active ? 'active' : ''}" data-model-value="${escapeHtml(option.id)}" role="option" aria-selected="${active ? 'true' : 'false'}">
            <strong>${escapeHtml(option.id)}</strong>${meta}
          </button>
        `;
      }).join('');
      const queryValue = String(query || '').trim();
      const customHidden = !queryValue || modelOptions.some(option => option.id === queryValue) ? ' hidden' : '';
      return `
        <button type="button" class="ghost-option" data-model-value="${escapeHtml(queryValue)}" data-model-custom="true" role="option" aria-selected="false"${customHidden}>
          <strong>${escapeHtml(formatUi('advanced.use_model', '使用 {model}', { model: queryValue }))}</strong><span>${escapeHtml(ui('advanced.custom_model', '自定义模型'))}</span>
        </button>
        <div class="ghost-options" data-model-options>
          ${rows}
        </div>
        <div class="ghost-empty" data-model-empty${rows.trim() ? ' hidden' : ''}>${escapeHtml(ui('advanced.no_model_match', '没有匹配的模型。可刷新模型列表，或输入自定义模型名。'))}</div>
      `;
    }

    function updateModelMenu(query = '') {
      modelMenu.innerHTML = buildModelMenuOptions(query);
      updateModelMenuActive();
    }

    function updateModelMenuActive() {
      if (!modelMenu) {
        return;
      }
      modelMenu.querySelectorAll('[data-model-value]').forEach(item => {
        const isActive = item.dataset.modelValue === model.value;
        item.classList.toggle('active', isActive);
        item.setAttribute('aria-selected', isActive ? 'true' : 'false');
      });
    }

    function openModelMenu(query = '') {
      updateModelMenu(query);
      modelSelectShell.classList.add('open');
      modelMenu.hidden = false;
      modelTrigger.setAttribute('aria-expanded', 'true');
      window.setTimeout(() => modelSearch.focus(), 0);
    }

    function closeModelMenu() {
      modelSelectShell.classList.remove('open');
      modelMenu.hidden = true;
      modelTrigger.setAttribute('aria-expanded', 'false');
      modelSearch.value = '';
    }

    function modelChoiceNodes() {
      return Array.from(modelMenu.querySelectorAll('[data-model-value]:not([hidden])'));
    }

    function focusModelChoice(current, direction) {
      const choices = modelChoiceNodes();
      if (!choices.length) {
        return;
      }
      if (current === modelSearch) {
        choices[direction < 0 ? choices.length - 1 : 0].focus();
        return;
      }
      const option = current.closest ? current.closest('[data-model-value]') : null;
      const currentIndex = choices.indexOf(option);
      const nextIndex = currentIndex + direction;
      if (nextIndex < 0) {
        modelSearch.focus();
        return;
      }
      choices[nextIndex >= choices.length ? 0 : nextIndex].focus();
    }

    function selectModelFromInput() {
      const query = modelSearch.value.trim();
      if (!query) {
        return false;
      }
      const exactOption = modelOptions.find(option => option.id === query);
      if (exactOption) {
        setModelValue(exactOption.id);
        closeModelMenu();
        return true;
      }
      const firstOption = modelMenu.querySelector('[data-model-options] [data-model-value]');
      if (firstOption) {
        firstOption.click();
        return true;
      }
      setModelValue(query);
      closeModelMenu();
      return true;
    }

    function syncModelPreset(value) {
      const presetModel = String(value || '').trim();
      modelOptions = normalizeModelOptions(presetModel ? [{ id: presetModel, label: '默认模型' }] : []);
      setModelValue(presetModel);
      updateModelMenu();
      setModelStatus('');
    }

    function scheduleModelFetch(delay = 450) {
      window.clearTimeout(modelFetchDebounce);
      if (!providerPresets[provider.value]) {
        return;
      }
      modelFetchDebounce = window.setTimeout(() => refreshModelList(true), delay);
    }

    async function refreshModelList(silent = false) {
      const preset = providerPresets[provider.value];
      if (!preset) {
        return;
      }
      const sequence = ++modelFetchSequence;
      modelRefresh.disabled = true;
      modelRefresh.setAttribute('aria-busy', 'true');
      if (!silent) {
        setModelStatus('正在获取模型列表...');
      }
      try {
        const response = await fetch('/api/models', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: provider.value,
            base_url: apiBaseUrl.value,
            api_key: apiKey.value,
            api_key_env: apiKeyEnv.value,
            api_timeout: document.getElementById('api_timeout')?.value || '10'
          })
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.error || '获取模型列表失败');
        }
        if (sequence !== modelFetchSequence) {
          return;
        }
        const options = normalizeModelOptions(payload.models);
        if (!options.length) {
          throw new Error('接口没有返回可用模型');
        }
        modelOptions = options;
        if (!modelOptions.some(option => option.id === model.value)) {
          setModelValue(modelOptions[0].id);
        } else {
          syncModelDisplay();
        }
        updateModelMenu(modelSearch.value);
        setModelStatus(formatUi('advanced.models_loaded', '已获取 {count} 个模型', { count: modelOptions.length }));
      } catch (error) {
        if (sequence === modelFetchSequence) {
          setModelStatus(error.message || ui('advanced.models_load_failed', '获取模型列表失败'), true);
        }
      } finally {
        if (sequence === modelFetchSequence) {
          modelRefresh.disabled = false;
          modelRefresh.removeAttribute('aria-busy');
        }
      }
    }

    function syncProvider(resetPreset = true) {
      const preset = providerPresets[provider.value];
      const keyLink = document.getElementById('api-key-link');
      apiBox.hidden = !preset;
      const apiPanel = apiBox.closest('details');
      if (apiPanel && preset) {
        apiPanel.open = true;
      }
      providerDisplay.textContent = ui(`provider.${provider.value}`, provider.options[provider.selectedIndex]?.textContent || ui('translator.provider', '翻译器'));
      updateSelectMenuActive(providerMenu, provider.value);
      if (!preset) {
        keyLink.hidden = true;
        setModelStatus('');
        return;
      }
      providerBadge.textContent = ui(`provider.${provider.value}`, preset.label);
      providerHelp.textContent = ui(`provider.${provider.value}.help`, preset.help);
      if (resetPreset) {
        apiBaseUrl.value = preset.url;
        apiKeyEnv.value = preset.env;
        syncModelPreset(preset.model);
        scheduleModelFetch(250);
      }
      if (preset.keyUrl) {
        keyLink.href = preset.keyUrl;
        keyLink.hidden = false;
      } else {
        keyLink.hidden = true;
      }
    }
    function syncPackFormat() {
      packFormatDisplay.textContent = packFormat.options[packFormat.selectedIndex]?.textContent || ui('translator.pack_format', '资源包格式');
      updateSelectMenuActive(packFormatMenu, packFormat.value);
    }
    function syncSourceLocale() {
      sourceLocale.value = normalizeLocaleValue(sourceLocale.value || 'en_us');
      ensureSelectOption(sourceLocale, sourceLocale.value, labelForLocale(sourceLocale.value));
      sourceLocaleDisplay.textContent = sourceLocale.options[sourceLocale.selectedIndex]?.textContent || ui('language.source', '源语言');
      updateSelectMenuActive(sourceLocaleMenu, sourceLocale.value);
    }
    function syncTargetLocale() {
      targetLocale.value = normalizeLocaleValue(targetLocale.value || 'zh_cn');
      ensureSelectOption(targetLocale, targetLocale.value, labelForLocale(targetLocale.value));
      targetLocaleDisplay.textContent = targetLocale.options[targetLocale.selectedIndex]?.textContent || ui('language.target', '目标语言');
      updateSelectMenuActive(targetLocaleMenu, targetLocale.value);
    }
    function syncFiles() {
      jarsDisplay.textContent = jarsInput.files.length ? formatUi('file.jar.count', '{count} 个 JAR', { count: jarsInput.files.length }) : ui('file.jar.placeholder', '选择一个或多个 JAR');
      ftbquestsDisplay.textContent = ftbquestsInput.files.length ? formatUi('file.ftbquests.count', '{count} 个 FTB Quests 输入', { count: ftbquestsInput.files.length }) : ui('file.ftbquests.placeholder', '选择整合包 ZIP、quests ZIP 或 en_us.snbt');
      jsonDisplay.textContent = jsonInput.files.length ? formatUi('file.json.count', '{count} 个语言 JSON', { count: jsonInput.files.length }) : ui('file.json.placeholder', '选择 en_us.json 或界面语言包 JSON');
      const directoryFiles = Array.from(ftbquestsDirectoryInput.files || []);
      const directoryRoots = [...new Set(directoryFiles.map(file => String(file.webkitRelativePath || file.name).split('/')[0]).filter(Boolean))];
      ftbquestsDirectoryDisplay.textContent = directoryFiles.length
        ? formatUi('file.directory.count', '{root}（{count} 个文件）', { root: directoryRoots[0] || ui('file.directory', '目录'), count: directoryFiles.length })
        : ui('file.ftbquests_dir.placeholder', '选择 quests、lang 或 en_us 目录');
      glossaryDisplay.textContent = glossaryInput.files.length ? glossaryInput.files[0].name : ui('translator.glossary.placeholder', '可选 .json 术语表');
    }
    function syncInputKind() {
      const mode = inputKind.value === 'ftbquests' ? 'ftbquests' : (inputKind.value === 'json' ? 'json' : 'jar');
      const isFtbquests = mode === 'ftbquests';
      const isJson = mode === 'json';
      document.querySelectorAll('[data-input-kind]').forEach(button => {
        const active = button.dataset.inputKind === mode;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      document.getElementById('jar-file-wrap').hidden = isFtbquests || isJson;
      document.getElementById('ftbquests-file-wrap').hidden = !isFtbquests;
      document.getElementById('ftbquests-directory-wrap').hidden = !isFtbquests;
      document.getElementById('json-file-wrap').hidden = !isJson;
      jarsInput.required = !isFtbquests && !isJson;
      ftbquestsInput.required = false;
      ftbquestsDirectoryInput.required = false;
      jsonInput.required = false;
      const packFormatShell = document.getElementById('pack-format-select');
      if (packFormatShell) {
        packFormatShell.hidden = isFtbquests || isJson;
      }
      const hardcodedLine = document.querySelector('input[name="scan_hardcoded"]')?.closest('.checkline');
      if (hardcodedLine) {
        hardcodedLine.hidden = isFtbquests || isJson;
      }
      statusBox.textContent = isFtbquests ? t('status.waiting_ftbquests') : (isJson ? t('status.waiting_json') : t('status.waiting_jar'));
    }
    function syncApiKeyVisibility() {
      if (!apiKey || !apiKeyToggle) {
        return;
      }
      const visible = apiKey.type === 'text';
      apiKeyToggle.setAttribute('aria-pressed', visible ? 'true' : 'false');
      apiKeyToggle.setAttribute('aria-label', visible ? '隐藏 API Key' : '查看 API Key');
      apiKeyToggle.title = visible ? '隐藏 API Key' : '查看 API Key';
      const icon = apiKeyToggle.querySelector('i');
      if (icon) {
        icon.className = visible ? 'ri-eye-off-line' : 'ri-eye-line';
      }
    }
    if (apiKeyToggle && apiKey) {
      apiKeyToggle.addEventListener('click', () => {
        const selectionStart = apiKey.selectionStart;
        const selectionEnd = apiKey.selectionEnd;
        apiKey.type = apiKey.type === 'password' ? 'text' : 'password';
        syncApiKeyVisibility();
        apiKey.focus();
        if (selectionStart !== null && selectionEnd !== null) {
          apiKey.setSelectionRange(selectionStart, selectionEnd);
        }
      });
      syncApiKeyVisibility();
    }
    function bindModelSelect() {
      modelTrigger.addEventListener('click', (event) => {
        if (event.target === modelSearch && modelSelectShell.classList.contains('open')) {
          event.stopPropagation();
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (modelSelectShell.classList.contains('open')) {
          closeModelMenu();
        } else {
          modelSearch.value = '';
          openModelMenu();
        }
      });
      modelTrigger.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'ArrowDown') {
          return;
        }
        event.preventDefault();
        if (!modelSelectShell.classList.contains('open')) {
          openModelMenu();
        }
      });
      modelSearch.addEventListener('input', () => {
        if (!modelSelectShell.classList.contains('open')) {
          openModelMenu(modelSearch.value);
        } else {
          updateModelMenu(modelSearch.value);
        }
      });
      modelSearch.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          event.stopPropagation();
          focusModelChoice(modelSearch, event.key === 'ArrowDown' ? 1 : -1);
          return;
        }
        if (event.key === 'Enter') {
          event.preventDefault();
          event.stopPropagation();
          selectModelFromInput();
          return;
        }
        if (event.key === 'Escape') {
          event.preventDefault();
          event.stopPropagation();
          closeModelMenu();
          modelTrigger.focus();
        }
      });
      modelMenu.addEventListener('click', (event) => {
        const option = event.target.closest('[data-model-value]');
        if (!option) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        setModelValue(option.dataset.modelValue || '');
        closeModelMenu();
      });
      modelMenu.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          focusModelChoice(event.target, event.key === 'ArrowDown' ? 1 : -1);
          return;
        }
        if (event.key === 'Escape') {
          event.preventDefault();
          closeModelMenu();
          modelTrigger.focus();
        }
      });
      document.addEventListener('click', (event) => {
        if (!modelSelectShell.contains(event.target)) {
          closeModelMenu();
        }
      });
      modelRefresh.addEventListener('click', () => refreshModelList(false));
      [apiBaseUrl, apiKey, apiKeyEnv].forEach(input => {
        input.addEventListener('input', () => scheduleModelFetch(650));
      });
    }
    bindModelSelect();
    sourceLocale.addEventListener('change', syncSourceLocale);
    targetLocale.addEventListener('change', syncTargetLocale);
    uiLocale.addEventListener('change', () => applyUiLocale(uiLocale.value, true));
    provider.addEventListener('change', syncProvider);
    packFormat.addEventListener('change', syncPackFormat);
    jarsInput.addEventListener('change', syncFiles);
    function handleFtbquestsInputChange() {
      syncFiles();
      syncFtbquestsSourceLocaleFromInput();
    }
    ftbquestsInput.addEventListener('change', handleFtbquestsInputChange);
    ftbquestsDirectoryInput.addEventListener('change', handleFtbquestsInputChange);
    jsonInput.addEventListener('change', syncFiles);
    glossaryInput.addEventListener('change', syncFiles);
    document.querySelectorAll('[data-input-kind]').forEach(button => {
      button.addEventListener('click', () => {
        inputKind.value = button.dataset.inputKind || 'jar';
        syncInputKind();
        syncFiles();
        syncFtbquestsSourceLocaleFromInput();
      });
    });
    populateLocaleSelect(sourceLocale, 'en_us');
    populateLocaleSelect(targetLocale, 'zh_cn');
    const initialUiLocale = preferredUiLocaleSetting();
    applyUiLocale(initialUiLocale);
    refreshUiLocales(true).then(() => applyUiLocale(initialUiLocale || uiLocale.value || 'zh_cn'));
    syncSourceLocale();
    syncTargetLocale();
    syncProvider();
    syncPackFormat();
    syncInputKind();
    syncFiles();
    syncConcurrencyHint();
    buildSelectMenus();
    closeAllSelectMenus();

    function syncConcurrencyHint() {
      const cpu = navigator.hardwareConcurrency || 4;
      const recommended = Math.max(1, Math.min(12, Math.ceil(cpu / 2)));
      if (apiConcurrency) {
        apiConcurrency.placeholder = formatUi('advanced.concurrency_placeholder', '推荐 {recommended}，当前 CPU 线程 {cpu}', { recommended, cpu });
      }
      if (apiConcurrencyHelp) {
        apiConcurrencyHelp.textContent = formatUi('advanced.concurrency_dynamic_help', '根据当前浏览器可见 CPU 线程 {cpu}，推荐并发 {recommended}。服务商限流或 503 较多时调低。', { cpu, recommended });
      }
    }

    function switchView(view) {
      resultState.activeView = view;
      closeAllSelectMenus();
      const isSettingsView = view === 'settings';
      const settingsPage = document.getElementById('settings-page');
      document.querySelector('.config-panel')?.toggleAttribute('hidden', isSettingsView);
      document.querySelector('.results-panel')?.toggleAttribute('hidden', isSettingsView);
      if (settingsPage) {
        settingsPage.hidden = !isSettingsView;
      }
      document.querySelectorAll('.side-nav button[data-view], .top-tabs button[data-view]').forEach(button => {
        const isActive = button.dataset.view === view;
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-current', isActive ? 'page' : 'false');
      });
      if (isSettingsView) {
        return;
      }
      document.querySelectorAll('.view-shell').forEach(shell => {
        shell.classList.toggle('active', shell.dataset.view === view);
      });
      const resultShells = results.querySelectorAll('[data-result-view]');
      if (resultShells.length) {
        resultShells.forEach(shell => {
          shell.classList.toggle('active', shell.dataset.resultView === view);
        });
      } else if (resultState.payload) {
        renderResultShell();
      }
    }
    document.querySelectorAll('[data-view]').forEach(button => {
      button.addEventListener('click', () => switchView(button.dataset.view));
    });

    function refreshSelectMenusForCurrentLocale() {
      buildUiLocaleMenu();
      sourceLocaleMenu.dataset.localeName = 'source_locale';
      targetLocaleMenu.dataset.localeName = 'target_locale';
      sourceLocaleMenu.innerHTML = buildLocaleSelectMenuOptions(sourceLocale, 'source_locale');
      targetLocaleMenu.innerHTML = buildLocaleSelectMenuOptions(targetLocale, 'target_locale');
      providerMenu.innerHTML = Array.from(provider.options).map(option => `
        <button type="button" class="ghost-option ${option.selected ? 'active' : ''}" data-select-value="provider" data-value="${escapeHtml(option.value)}">
          <strong>${escapeHtml(ui(`provider.${option.value}`, option.textContent))}</strong>
        </button>
      `).join('');
      packFormatMenu.innerHTML = Array.from(packFormat.options).map(option => `
        <button type="button" class="ghost-option ${option.selected ? 'active' : ''}" data-select-value="pack_format" data-value="${escapeHtml(option.value)}">
          <strong>${escapeHtml(option.textContent)}</strong>
        </button>
      `).join('');
      updateSelectMenuActive(uiLocaleMenu, uiLocale.value);
      updateSelectMenuActive(sourceLocaleMenu, sourceLocale.value);
      updateSelectMenuActive(targetLocaleMenu, targetLocale.value);
      updateSelectMenuActive(providerMenu, provider.value);
      updateSelectMenuActive(packFormatMenu, packFormat.value);
      syncUiLocaleDisplay();
      if (modelMenu && !modelMenu.hidden) {
        updateModelMenu(modelSearch.value);
      }
    }

    function buildSelectMenus() {
      refreshSelectMenusForCurrentLocale();
      bindSelectMenu(uiLocaleSelectShell, uiLocaleMenu, uiLocale, () => applyUiLocale(uiLocale.value, true));
      bindSelectMenu(sourceLocaleSelectShell, sourceLocaleMenu, sourceLocale, syncSourceLocale);
      bindSelectMenu(targetLocaleSelectShell, targetLocaleMenu, targetLocale, syncTargetLocale);
      bindSelectMenu(providerSelectShell, providerMenu, provider, syncProvider);
      bindSelectMenu(packFormatSelectShell, packFormatMenu, packFormat, syncPackFormat);
    }

    function buildSelectMenuOptions(select, name) {
      return Array.from(select.options).map(option => `
        <button type="button" class="ghost-option ${option.selected ? 'active' : ''}" data-select-value="${escapeHtml(name)}" data-value="${escapeHtml(option.value)}">
          <strong>${escapeHtml(option.textContent)}</strong>
        </button>
      `).join('');
    }

    function closeAllSelectMenus() {
      document.querySelectorAll('.ghost-select.open').forEach(shell => {
        shell.classList.remove('open');
        const trigger = shell.querySelector('[data-select-trigger]');
        if (trigger) {
          trigger.setAttribute('aria-expanded', 'false');
        }
        const modelTriggerNode = shell.querySelector('[data-model-trigger]');
        if (modelTriggerNode) {
          modelTriggerNode.setAttribute('aria-expanded', 'false');
        }
        const localeSearchInput = shell.querySelector('[data-locale-control-search]');
        if (localeSearchInput) {
          localeSearchInput.value = '';
        }
        const modelSearchInput = shell.querySelector('.model-control-input');
        if (modelSearchInput) {
          modelSearchInput.value = '';
        }
        const menu = shell.querySelector('.ghost-menu');
        if (menu) {
          menu.hidden = true;
        }
      });
    }

    function updateSelectMenuActive(menu, value) {
      if (!menu) {
        return;
      }
      menu.querySelectorAll('.ghost-option').forEach(item => {
        const isActive = item.dataset.value === value;
        item.classList.toggle('active', isActive);
        if (item.hasAttribute('role')) {
          item.setAttribute('aria-selected', isActive ? 'true' : 'false');
        }
      });
    }

    function bindSelectMenu(shell, menu, select, onChange) {
      const trigger = shell.querySelector('[data-select-trigger]');
      const localeSearchInput = shell.querySelector('[data-locale-control-search]');
      const closeMenu = () => {
        shell.classList.remove('open');
        menu.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
        if (localeSearchInput) {
          localeSearchInput.value = '';
        }
      };
      const openMenu = () => {
        const query = localeSearchInput ? localeSearchInput.value : '';
        if (menu.dataset.localeName) {
          menu.innerHTML = buildLocaleSelectMenuOptions(select, menu.dataset.localeName, query);
        }
        shell.classList.add('open');
        menu.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        if (localeSearchInput) {
          window.setTimeout(() => localeSearchInput.focus(), 0);
        }
      };
      trigger.addEventListener('click', (event) => {
        if (localeSearchInput && event.target === localeSearchInput && shell.classList.contains('open')) {
          event.stopPropagation();
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        const isOpen = shell.classList.contains('open');
        document.querySelectorAll('.ghost-select.open').forEach(item => {
          if (item !== shell) {
            item.classList.remove('open');
            const otherTrigger = item.querySelector('[data-select-trigger]');
            if (otherTrigger) {
              otherTrigger.setAttribute('aria-expanded', 'false');
            }
            const otherLocaleSearchInput = item.querySelector('[data-locale-control-search]');
            if (otherLocaleSearchInput) {
              otherLocaleSearchInput.value = '';
            }
            const otherMenu = item.querySelector('.ghost-menu');
            if (otherMenu) {
              otherMenu.hidden = true;
            }
          }
        });
        if (isOpen) {
          closeMenu();
        } else {
          if (localeSearchInput) {
            localeSearchInput.value = '';
          }
          openMenu();
        }
      });
      trigger.addEventListener('keydown', (event) => {
        if (trigger.tagName === 'BUTTON') {
          return;
        }
        if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'ArrowDown') {
          return;
        }
        event.preventDefault();
        if (!shell.classList.contains('open')) {
          openMenu();
        }
      });
      if (localeSearchInput) {
        localeSearchInput.addEventListener('input', () => {
          if (!shell.classList.contains('open')) {
            openMenu();
          }
          refreshLocaleMenuSearch(menu, select, localeSearchInput.value);
        });
        localeSearchInput.addEventListener('keydown', (event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            event.stopPropagation();
            focusLocaleChoice(menu, localeSearchInput, event.key === 'ArrowDown' ? 1 : -1, localeSearchInput);
            return;
          }
          if (event.key === 'Enter') {
            event.preventDefault();
            event.stopPropagation();
            selectLocaleFromInput(menu, localeSearchInput);
            return;
          }
          if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
            closeMenu();
            trigger.focus();
          }
        });
      }
      menu.addEventListener('click', (event) => {
        const option = event.target.closest('[data-select-value]');
        if (!option) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        const isLocaleMenu = Boolean(menu.dataset.localeName);
        const customLocale = option.dataset.customLocale === 'true';
        const value = isLocaleMenu ? normalizeLocaleValue(option.dataset.value || '') : (option.dataset.value || '');
        if (!value) {
          return;
        }
        if (isLocaleMenu && (customLocale || !Array.from(select.options).some(item => item.value === value))) {
          ensureSelectOption(select, value, labelForLocale(value));
        }
        select.value = value;
        onChange();
        updateSelectMenuActive(menu, value);
        closeMenu();
      });
      menu.addEventListener('keydown', (event) => {
        if (!menu.dataset.localeName) {
          return;
        }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          focusLocaleChoice(menu, event.target, event.key === 'ArrowDown' ? 1 : -1, localeSearchInput);
          return;
        }
        if (event.key === 'Escape') {
          event.preventDefault();
          closeMenu();
          trigger.focus();
          return;
        }
      });
      document.addEventListener('click', (event) => {
        if (!shell.contains(event.target)) {
          closeMenu();
        }
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
          closeMenu();
        }
      });
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      statusBox.className = 'status';
      statusBox.textContent = t('status.uploading');
      submit.disabled = true;
      startLoading();
      job.textContent = '';
      activeJobId = '';
      headerJob.textContent = ui('header.uploading', '上传中');

      try {
        applyCacheDirSetting(cacheDirField ? cacheDirField.value : storedCacheDirSetting());
        applyUiLocaleDirSetting(uiLocaleDirField ? uiLocaleDirField.value : storedUiLocaleDirSetting());
        const data = new FormData(form);
        if (inputKind.value === 'ftbquests') {
          data.delete('ftbquests_files');
          data.delete('ftbquests_directory_files');
          Array.from(ftbquestsInput.files || []).forEach(file => {
            data.append('ftbquests_files', file, file.name);
          });
          Array.from(ftbquestsDirectoryInput.files || []).forEach(file => {
            data.append('ftbquests_files', file, file.webkitRelativePath || file.name);
          });
          if (!data.getAll('ftbquests_files').length) {
            throw new Error(ui('error.ftbquests_missing_input', '请上传 FTB Quests ZIP/SNBT，或选择 quests/lang/en_us 目录'));
          }
        } else if (inputKind.value === 'json') {
          data.delete('json_files');
          Array.from(jsonInput.files || []).forEach(file => {
            data.append('json_files', file, file.name);
          });
          if (!data.getAll('json_files').length) {
            throw new Error(ui('error.json_missing_input', '请上传语言 JSON 文件'));
          }
        }
        const response = await fetch('/api/translate', { method: 'POST', body: data });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.error || ui('status.process_failed', '处理失败'));
        }
        activeJobId = payload.job_id;
        job.textContent = activeJobId;
        headerJob.textContent = activeJobId;
        startProgressPolling(activeJobId);
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = error.message;
        results.innerHTML = `<div class="empty">${escapeHtml(t('status.failed'))}</div>`;
        submit.disabled = false;
        stopLoading();
      }
    });

    function startLoading() {
      loadingStartedAt = Date.now();
      loadingProgress = {
        completed: 0,
        total: 0,
        stage: 'idle',
        filesCompleted: 0,
        filesTotal: 0,
        cacheHits: 0,
        cacheMisses: 0,
        currentFile: '',
        retryAttempt: 0,
        retryMax: 0,
        retryDelay: 0,
        retryReason: '',
        requestTimeout: Number(new FormData(form).get('api_timeout') || '10'),
        batchSize: Number(new FormData(form).get('api_batch_size') || '40')
      };
      cancelBtn.hidden = false;
      renderLoading();
      loadingTimer = window.setInterval(renderLoading, 1000);
    }

    function stopLoading() {
      if (loadingTimer) {
        window.clearInterval(loadingTimer);
        loadingTimer = null;
      }
      if (progressTimer) {
        window.clearInterval(progressTimer);
        progressTimer = null;
      }
      cancelBtn.hidden = true;
    }

    cancelBtn.addEventListener('click', async () => {
      if (!activeJobId) return;
      cancelBtn.disabled = true;
      try {
        await fetch(`/api/cancel/${activeJobId}`, { method: 'POST' });
        stopLoading();
        submit.disabled = false;
        statusBox.className = 'status error';
        statusBox.textContent = ui('status.cancelled_short', '已中断。');
        results.innerHTML = `<div class="empty">${escapeHtml(ui('status.cancelled_task', '任务已中断。'))}</div>`;
      } catch (e) {
        statusBox.textContent = formatUi('status.cancel_failed', '中断请求失败：{message}', { message: e.message });
      } finally {
        cancelBtn.disabled = false;
      }
    });

    function startProgressPolling(jobId) {
      const poll = async () => {
        try {
          const response = await fetch(`/api/progress/${jobId}`);
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            throw new Error(payload.error || ui('status.progress_read_failed', '进度读取失败'));
          }
          loadingProgress = {
            completed: payload.completed || 0,
            total: payload.total || 0,
            stage: payload.stage || 'running',
            filesCompleted: payload.files_completed || 0,
            filesTotal: payload.files_total || 0,
            cacheHits: payload.cache_hits || 0,
            cacheMisses: payload.cache_misses || 0,
            currentFile: payload.current_file || '',
            retryAttempt: payload.retry_attempt || 0,
            retryMax: payload.retry_max || 0,
            retryDelay: payload.retry_delay || 0,
            retryReason: payload.retry_reason || '',
            requestTimeout: payload.request_timeout || loadingProgress.requestTimeout || 10,
            batchSize: payload.batch_size || loadingProgress.batchSize || 40
          };
          renderLoading();
          if (payload.status === 'done') {
            stopLoading();
            submit.disabled = false;
            renderResult(payload.result);
            const providerNote = payload.result.provider === 'glossary' ? formatUi('status.provider_glossary', ' 离线术语表适合快速预览，完整整句汉化请使用 AI 翻译器。', {}) : '';
            const failureNote = payload.result.api_failure_count ? formatUi('status.api_failure_note', ' 汉化翻译存在异常缺失 {count} 条，可在结果区查看并重试。', { count: payload.result.api_failure_count }) : '';
            const cacheNote = payload.result.cache_hits ? formatUi('status.cache_note', ' 其中复用了 {count} 个缓存。', { count: payload.result.cache_hits }) : '';
            statusBox.className = payload.result.api_failure_count ? 'status error' : 'status success';
            if (payload.result.kind === 'ftbquests') {
              statusBox.textContent = formatUi('status.done_ftbquests', '完成：处理 {sources} 个 FTB Quests 输入，生成 {files} 个任务书文件，耗时 {elapsed}。', { sources: payload.result.processed_sources || 1, files: payload.result.generated_files, elapsed: formatSeconds(payload.result.elapsed_seconds) }) + cacheNote + providerNote + failureNote;
            } else if (payload.result.kind === 'json') {
              statusBox.textContent = formatUi('status.done_json', '完成：处理 {sources} 个语言 JSON，生成 {files} 个 JSON 文件，耗时 {elapsed}。', { sources: payload.result.processed_sources || 1, files: payload.result.generated_files, elapsed: formatSeconds(payload.result.elapsed_seconds) }) + providerNote + failureNote;
            } else {
              statusBox.textContent = formatUi('status.done_jar', '完成：处理 {jars} 个 JAR，生成 {files} 个语言文件，耗时 {elapsed}。', { jars: payload.result.processed_jars, files: payload.result.generated_files, elapsed: formatSeconds(payload.result.elapsed_seconds) }) + cacheNote + providerNote + failureNote;
            }
            switchView('language');
          } else if (payload.status === 'error') {
            stopLoading();
            submit.disabled = false;
            statusBox.className = 'status error';
            statusBox.textContent = payload.error || ui('status.process_failed', '处理失败');
          } else if (payload.status === 'cancelled') {
            stopLoading();
            submit.disabled = false;
            statusBox.className = 'status error';
            statusBox.textContent = ui('status.cancelled_short', '已中断。');
            results.innerHTML = `<div class="empty">${escapeHtml(ui('status.cancelled_task', '任务已中断。'))}</div>`;
          }
        } catch (error) {
          stopLoading();
          submit.disabled = false;
          statusBox.className = 'status error';
          statusBox.textContent = error.message;
        }
      };
      poll();
      progressTimer = window.setInterval(poll, 900);
    }

    function renderLoading() {
      const elapsed = Math.max(0, Math.floor((Date.now() - loadingStartedAt) / 1000));
      const data = new FormData(form);
      const providerName = ui(`provider.${provider.value}`, provider.options[provider.selectedIndex]?.textContent || ui('translator.provider', '翻译器'));
      const isFtbquests = inputKind.value === 'ftbquests';
      const isJson = inputKind.value === 'json';
      const sourceCount = isFtbquests ? (ftbquestsInput.files.length || ftbquestsDirectoryInput.files.length) : (isJson ? jsonInput.files.length : jarsInput.files.length);
      const sourceLabel = isFtbquests ? ui('file.ftbquests', 'FTB Quests 输入') : (isJson ? ui('file.json', '语言 JSON') : ui('file.jar', 'JAR'));
      const concurrency = Math.max(1, Number(data.get('api_concurrency') || '1'));
      const isAi = Boolean(providerPresets[provider.value]);
      const completed = loadingProgress.completed || 0;
      const total = loadingProgress.total || 0;
      const percent = total ? Math.round((completed / total) * 100) : 0;
      const filesCompleted = loadingProgress.filesCompleted || 0;
      const filesTotal = loadingProgress.filesTotal || sourceCount || 0;
      const filePercent = filesTotal ? Math.round((filesCompleted / filesTotal) * 100) : 0;
      const cacheHits = loadingProgress.cacheHits || 0;
      const cacheMisses = loadingProgress.cacheMisses || 0;
      const currentFile = loadingProgress.currentFile || '';
      const stageMap = {
        idle: ui('loading.stage.idle', '准备开始'),
        queued: isFtbquests ? ui('loading.stage.queued_ftbquests', '正在上传并解析 FTB Quests') : ui('loading.stage.queued_jar', '正在上传并解析 JAR'),
        processing_file: isFtbquests ? ui('loading.stage.processing_ftbquests', '正在分析任务书语言文件') : ui('loading.stage.processing_language', '正在分析语言文件'),
        reusing_cache: ui('loading.stage.reusing_cache', '正在复用缓存结果'),
        translating: isAi ? ui('loading.stage.translating_ai', '正在分批调用 AI 翻译接口') : ui('loading.stage.translating', '正在生成语言文件'),
        retrying: ui('loading.stage.retrying', '正在等待重试'),
        writing: ui('loading.stage.writing', '正在写入资源包和报告'),
        done: ui('loading.stage.done', '处理完成'),
        cancelled: ui('loading.stage.cancelled', '任务已中断'),
        error: ui('loading.stage.error', '处理失败')
      };
      const stage = stageMap[loadingProgress.stage] || (isAi ? ui('loading.stage.processing_ai', '正在处理翻译任务') : ui('loading.stage.processing', '正在处理任务'));
      const progressText = total ? `${completed}/${total}` : ui('loading.request_counting', '正在统计请求总量');
      const fileText = filesTotal ? `${filesCompleted}/${filesTotal}` : ui('loading.file_counting', '正在统计文件数量');
      const retryText = loadingProgress.retryAttempt
        ? formatUi('loading.retrying', '当前重试 {attempt}/{max}，原因：{reason}，等待 {delay}s，连接/读取超时 {timeout}s。', {
          attempt: loadingProgress.retryAttempt,
          max: loadingProgress.retryMax,
          reason: loadingProgress.retryReason || ui('loading.request_failed', '请求失败'),
          delay: Number(loadingProgress.retryDelay || 0).toFixed(1),
          timeout: loadingProgress.requestTimeout
        })
        : '';
      const statusText = retryText
        || (loadingProgress.stage === 'reusing_cache'
          ? formatUi('loading.cache_reuse', '缓存命中 {hits}/{total}{current}', { hits: cacheHits, total: filesTotal || sourceCount || cacheHits || 0, current: currentFile ? formatUi('loading.current_file', '，当前：{file}', { file: currentFile }) : '' })
          : (loadingProgress.stage === 'processing_file'
            ? (currentFile ? formatUi('loading.processing_current', '正在处理：{file}', { file: currentFile }) : (isFtbquests ? ui('loading.stage.processing_ftbquests', '正在分析任务书语言文件') : ui('loading.stage.processing_language', '正在分析语言文件')))
            : (loadingProgress.stage === 'writing'
              ? ui('loading.writing', '正在写入资源包、报告和缓存')
              : (isAi ? formatUi('loading.request_progress', '翻译请求 {progress}', { progress: progressText }) : ui('loading.running', '任务运行中')))));
      const cacheText = filesTotal || cacheHits || cacheMisses
        ? formatUi('loading.cache_stats', '缓存命中 {hits} 个，实际翻译 {misses} 个。', { hits: cacheHits, misses: Math.max(0, cacheMisses) })
        : '';
      const detail = isAi
        ? formatUi('loading.detail_ai', '翻译器：{provider}，并发上限：{concurrency}，每次请求 {batch} 条，{sourceLabel}：{sourceCount} 个。{cacheText}耗时 {elapsed}s。', { provider: providerName, concurrency, batch: loadingProgress.batchSize || 40, sourceLabel, sourceCount, cacheText, elapsed })
        : formatUi('loading.detail', '翻译器：{provider}，{sourceLabel}：{sourceCount} 个。{cacheText}耗时 {elapsed}s。', { provider: providerName, sourceLabel, sourceCount, cacheText, elapsed });
      const card = document.getElementById('loading-card');
      if (!card) {
        results.innerHTML = `
        <div id="loading-card" class="loading-card">
          <div class="spinner" aria-hidden="true"></div>
          <div>
            <p id="loading-title" class="loading-title"></p>
            <div class="loading-status"><i class="ri-loader-4-line"></i><span id="loading-status-text"></span></div>
            <div id="loading-meta" class="loading-meta"></div>
          </div>
          <div class="loading-lanes">
            <div class="loading-lane"><span>${escapeHtml(ui('loading.file_progress', '文件进度'))}</span><div class="loading-lane-bar"><span id="loading-file-progress-bar"></span></div><b id="loading-file-progress-text"></b></div>
            <div class="loading-lane"><span>${escapeHtml(ui('loading.request_lane', '翻译请求'))}</span><div class="loading-lane-bar"><span id="loading-progress-bar"></span></div><b id="loading-progress-text"></b></div>
          </div>
        </div>
      `;
      }
      const titleNode = document.getElementById('loading-title');
      const statusNode = document.getElementById('loading-status-text');
      const metaNode = document.getElementById('loading-meta');
      const progressNode = document.getElementById('loading-progress-bar');
      const progressTextNode = document.getElementById('loading-progress-text');
      const fileProgressNode = document.getElementById('loading-file-progress-bar');
      const fileProgressTextNode = document.getElementById('loading-file-progress-text');
      if (titleNode) {
        titleNode.textContent = stage;
      }
      if (statusNode) {
        statusNode.textContent = statusText;
      }
      if (metaNode) {
        metaNode.innerHTML = `${escapeHtml(detail)}<br>${escapeHtml(ui('loading.meta_tail', '文件进度和翻译请求进度分开统计；请求总数会随着解析到新的语言文件逐步增加。'))}`;
      }
      if (progressNode) {
        progressNode.style.width = total ? `${Math.max(6, percent)}%` : '';
        progressNode.classList.toggle('indeterminate', !total);
      }
      if (progressTextNode) {
        progressTextNode.textContent = progressText;
      }
      if (fileProgressNode) {
        fileProgressNode.style.width = filesTotal ? `${Math.max(6, filePercent)}%` : '';
        fileProgressNode.classList.toggle('indeterminate', !filesTotal);
      }
      if (fileProgressTextNode) {
        fileProgressTextNode.textContent = fileText;
      }
    }

    function renderResult(payload) {
      resultState.payload = payload;
      resultState.activeTab = 'language';
      resultState.languageSearch = '';
      resultState.languageJarFilter = '全部';
      resultState.languageFilteredCacheKey = '';
      resultState.languageFilteredEntries = [];
      resultState.languageEdits = {};
      resultState.languagePage = 1;
      resultState.reportSearch = '';
      resultState.hardcodedSearch = '';
      resultState.apiLogSearch = '';
      resultState.reportPage = 1;
      resultState.hardcodedPage = 1;
      resultState.apiLogPage = 1;
      apiLogLines = Array.isArray(payload.api_debug_log_lines) ? payload.api_debug_log_lines : [];
      loadHardcodedMap(payload.hardcoded_map || {});
      renderResultShell();
    }

    function renderResultShell() {
      const payload = resultState.payload;
      if (!payload) {
        return;
      }
      job.textContent = payload.job_id;
      const summary = payload.summary || {};
      const hardcodedCount = hardcodedState.entries.length;
      const apiFailureCount = payload.api_failure_count || summary.api_failed || 0;
      const candidateCount = payload.hardcoded_count || 0;
      const reportEntryCount = summary ? Object.values(summary).reduce((a, b) => a + b, 0) : (Array.isArray(payload.entries) ? payload.entries.length : 0);
      const isFtbquestsResult = payload.kind === 'ftbquests';
      const isJsonResult = payload.kind === 'json';
      headerJob.textContent = payload.job_id || ui('header.not_started', '未开始');
      const languageHeadTitle = resultState.activeTab === 'hardcoded'
        ? ui('result.hardcoded', '硬编码映射')
        : (isFtbquestsResult ? ui('result.ftbquests', '任务书结果') : (isJsonResult ? ui('result.json', 'JSON 结果') : ui('result.language', '语言结果')));
      const languageHeadDesc = resultState.activeTab === 'hardcoded'
        ? ui('result.hardcoded_desc', '选择候选、AI 翻译或导出映射')
        : (isFtbquestsResult ? ui('result.ftbquests_desc', '可搜索 FTB Quests 翻译条目并下载补丁') : (isJsonResult ? ui('result.json_desc', '可搜索 JSON 语言文件翻译条目并下载结果') : ui('result.language_desc', '可搜索并导出人工修改')));
      results.innerHTML = `
        <div class="actions">
          <button type="button" data-view="language"><i class="ri-folder-open-line"></i><span>${escapeHtml(ui('result.workspace', '工作区'))}</span></button>
          ${payload.pack_url ? `<button type="button" id="download-pack" data-pack-url="${escapeHtml(payload.pack_url)}" data-pack-name="${escapeHtml(payload.pack_filename || defaultPackFilename(payload.pack_url))}"><i class="ri-download-2-line"></i><span>${escapeHtml(ui('result.download_pack', '下载资源包'))}</span></button>` : ''}
          ${payload.ftbquests_patch_url ? `<button type="button" id="download-ftbquests" data-download-url="${escapeHtml(payload.ftbquests_patch_url)}"><i class="ri-download-2-line"></i><span>${escapeHtml(ui('result.download_ftbquests', '下载任务书补丁'))}</span></button>` : ''}
          ${payload.json_url ? `<button type="button" id="download-json" data-download-url="${escapeHtml(payload.json_url)}"><i class="ri-download-2-line"></i><span>${escapeHtml(ui('result.download_json', '下载 JSON'))}</span></button>` : ''}
          <button type="button" data-view="report"><i class="ri-file-list-3-line"></i><span>${escapeHtml(ui('result.open_report', '打开报告'))}</span></button>
          ${isFtbquestsResult || isJsonResult ? '' : `<button type="button" data-view="hardcoded"><i class="ri-file-search-line"></i><span>${escapeHtml(ui('result.hardcoded_report', '硬编码报告'))}</span></button>`}
          <button type="button" data-view="api-log"><i class="ri-bug-line"></i><span>${escapeHtml(ui('result.api_log', 'API 调试日志'))}</span></button>
          ${apiFailureCount && !isFtbquestsResult && !isJsonResult ? `<button type="button" id="retry-api-failures"><i class="ri-refresh-line"></i><span>${escapeHtml(ui('result.retry_failed', '重试失败项'))}</span></button>` : ''}
        </div>
        ${apiFailureCount ? `
          <div class="status error">
            ${escapeHtml(formatUi('result.api_failure_notice', '汉化翻译存在异常缺失 {count} 条。可打开 API 调试日志查看报错记录，或手动重试失败项。', { count: apiFailureCount }))}
          </div>
        ` : ''}
        <div class="summary">
          <section class="summary-group">
            <h3>${escapeHtml(ui('result.outputs', '输出产物'))}</h3>
            <div class="summary-group-grid">
              <div class="metric"><strong>${isFtbquestsResult || isJsonResult ? (payload.processed_sources || 1) : payload.processed_jars}</strong><span>${escapeHtml(isFtbquestsResult ? ui('result.ftbquests_input', '任务书输入') : (isJsonResult ? ui('result.json_input', 'JSON 输入') : ui('result.jar_input', 'JAR')))}</span></div>
              <div class="metric"><strong>${payload.generated_files}</strong><span>${escapeHtml(isFtbquestsResult ? ui('result.tasks', '任务书文件') : (isJsonResult ? ui('result.json_files', 'JSON 文件') : ui('result.language_files', '语言文件')))}</span></div>
              <div class="metric"><strong>${isFtbquestsResult ? (payload.legacy_files || 0) : (isJsonResult ? (summary.skipped || 0) : hardcodedCount)}</strong><span>${escapeHtml(isFtbquestsResult ? ui('result.legacy_snbt', '旧版 SNBT') : (isJsonResult ? ui('result.skipped_items', '跳过项') : ui('result.hardcoded_mapping', '硬编码映射')))}</span></div>
            </div>
          </section>
          <section class="summary-group">
            <h3>${escapeHtml(ui('result.quality', '质量概览'))}</h3>
            <div class="summary-group-grid">
              <div class="metric"><strong>${summary.translated || 0}</strong><span>${escapeHtml(ui('result.new_translation', '新增翻译'))}</span></div>
              <div class="metric"><strong>${summary.existing || 0}</strong><span>${escapeHtml(ui('result.existing_translation', '已有译文'))}</span></div>
              <div class="metric"><strong>${apiFailureCount + (summary.failed || 0) + (summary.incomplete || 0)}</strong><span>${escapeHtml(ui('result.to_process', '需处理'))}</span></div>
              <div class="metric"><strong>${reportEntryCount}</strong><span>${escapeHtml(ui('result.report_entries', '报告条目'))}</span></div>
            </div>
          </section>
          <section class="summary-group">
            <h3>${escapeHtml(ui('result.performance', '性能概览'))}</h3>
            <div class="summary-group-grid">
              <div class="metric"><strong>${formatSeconds(payload.elapsed_seconds)}</strong><span>${escapeHtml(ui('result.elapsed', '耗时'))}</span></div>
              <div class="metric"><strong>${payload.cache_hits || 0}</strong><span>${escapeHtml(ui('result.cache_hits', '缓存命中'))}</span></div>
              <div class="metric"><strong>${payload.cache_misses || 0}</strong><span>${escapeHtml(ui('result.actual_translation', '实际翻译'))}</span></div>
              <div class="metric"><strong>${candidateCount}</strong><span>${escapeHtml(ui('result.candidate_text', '候选文本'))}</span></div>
            </div>
          </section>
        </div>
        <div class="system-views">
          <div class="view-shell ${resultState.activeView === 'language' ? 'active' : ''}" data-result-view="language">
            <div class="view-frame">
              <div class="view-head"><strong>${languageHeadTitle}</strong><span class="muted">${languageHeadDesc}</span></div>
              <div class="view-body">
                <div class="tabs">
                  <button type="button" data-result-tab="language" class="${resultState.activeTab === 'language' ? 'active' : ''}"><i class="ri-language-line"></i><span>${escapeHtml(isFtbquestsResult ? ui('result.ftbquests', '任务书结果') : (isJsonResult ? ui('result.json', 'JSON 结果') : ui('result.language', '语言结果')))}</span></button>
                  ${isFtbquestsResult || isJsonResult ? '' : `<button type="button" data-result-tab="hardcoded" class="${resultState.activeTab === 'hardcoded' ? 'active' : ''}" ${hardcodedCount ? '' : 'disabled'}><i class="ri-draft-line"></i><span>${escapeHtml(ui('result.hardcoded', '硬编码映射'))}</span></button>`}
                </div>
                <div id="result-tab-panel" class="tab-panel">
                  ${resultState.activeTab === 'hardcoded' ? renderHardcodedWorkbench() : renderLanguageResults(payload)}
                </div>
              </div>
            </div>
          </div>
          <div class="view-shell ${resultState.activeView === 'report' ? 'active' : ''}" data-result-view="report">
            ${renderReportView()}
          </div>
          <div class="view-shell ${resultState.activeView === 'hardcoded' ? 'active' : ''}" data-result-view="hardcoded">
            ${renderHardcodedReportView()}
          </div>
          <div class="view-shell ${resultState.activeView === 'api-log' ? 'active' : ''}" data-result-view="api-log">
            ${renderApiLogView()}
          </div>
        </div>
      `;
      bindResultTabs();
      bindViewButtons();
      if (resultState.activeView === 'language') {
        if (resultState.activeTab === 'hardcoded') {
          bindHardcodedWorkbench();
        } else {
          bindLanguageResults();
        }
      }
    }

    function splitJarPath(value) {
      return String(value || '').split('::').map(part => part.trim()).filter(Boolean);
    }

    function jarSegmentLabel(value) {
      const pieces = String(value || '').replace(/\\/g, '/').split('/').filter(Boolean);
      return pieces[pieces.length - 1] || String(value || '');
    }

    function jarFilterDisplayLabel(value) {
      if (!value || value === '全部') {
        return ui('result.all', '全部');
      }
      return splitJarPath(value).map(jarSegmentLabel).join(' / ');
    }

    function buildJarFilterTree(jarNames) {
      const roots = [];
      const nodes = new Map();
      jarNames.forEach(name => {
        const parts = splitJarPath(name);
        let siblings = roots;
        let prefix = [];
        parts.forEach(part => {
          prefix.push(part);
          const value = prefix.join('::');
          let node = nodes.get(value);
          if (!node) {
            const label = jarSegmentLabel(part);
            node = {
              value,
              label,
              detail: label === part ? '' : part,
              children: []
            };
            nodes.set(value, node);
            siblings.push(node);
          }
          siblings = node.children;
        });
      });
      return roots;
    }

    function renderJarTreeOptions(nodes, activeValue, depth = 0) {
      return nodes.map(node => {
        const active = activeValue === node.value;
        const icon = node.children.length ? 'ri-folder-3-line' : 'ri-archive-line';
        const branch = depth > 0 ? '<i class="ri-corner-down-right-line" aria-hidden="true"></i>' : '';
        const option = `
          <button type="button" class="ghost-option jar-tree-option ${active ? 'active' : ''}" data-select-value="${escapeHtml(node.value)}" data-jar-depth="${depth}" role="option" aria-selected="${active ? 'true' : 'false'}" title="${escapeHtml(node.value)}" style="padding-left: ${10 + depth * 18}px">
            <span class="jar-tree-label">${branch}<i class="${icon}" aria-hidden="true"></i><strong>${escapeHtml(node.label)}</strong></span>
            ${node.detail ? `<span class="jar-tree-path">${escapeHtml(node.detail)}</span>` : ''}
          </button>
        `;
        return option + renderJarTreeOptions(node.children, activeValue, depth + 1);
      }).join('');
    }

    function renderJarFilterOptions(jarNames, activeValue) {
      const allActive = activeValue === '全部';
      const roots = buildJarFilterTree(jarNames);
      return `
        <button type="button" class="ghost-option jar-tree-option ${allActive ? 'active' : ''}" data-select-value="全部" data-jar-depth="0" role="option" aria-selected="${allActive ? 'true' : 'false'}" title="${escapeHtml(ui('result.all', '全部'))}">
          <span class="jar-tree-label"><i class="ri-stack-line" aria-hidden="true"></i><strong>${escapeHtml(ui('result.all', '全部'))}</strong></span>
        </button>
        ${renderJarTreeOptions(roots, activeValue)}
      `;
    }

    function jarFilterMatchesEntry(entryJar, jarFilter) {
      if (!jarFilter || jarFilter === '全部') {
        return true;
      }
      const jar = String(entryJar || '');
      return jar === jarFilter || jar.startsWith(`${jarFilter}::`);
    }

    function renderLanguageResults(payload) {
      const jarNames = [...new Set((payload.entries || []).map(e => e.jar).filter(Boolean))];
      const activeLabel = resultState.languageJarFilter || '全部';
      const activeDisplay = jarFilterDisplayLabel(activeLabel);
      const jarMenuOptions = renderJarFilterOptions(jarNames, activeLabel);
      const isJsonResult = payload.kind === 'json';
      return `
        <div class="toolbar">
          <div class="ghost-select jar-filter" id="language-jar-filter-shell"${isJsonResult ? ' hidden' : ''}>
            <button type="button" class="control" data-select-trigger="jar-filter" aria-haspopup="listbox" aria-expanded="false" aria-controls="language-jar-filter-menu"><span class="value" id="language-jar-filter-display" title="${escapeHtml(activeLabel)}">${escapeHtml(activeDisplay)}</span><i class="ri-arrow-down-s-line chevron"></i></button>
            <div class="ghost-menu" id="language-jar-filter-menu" role="listbox" hidden>${jarMenuOptions}</div>
          </div>
          <input id="language-search" value="${escapeHtml(resultState.languageSearch)}" placeholder="${escapeHtml(ui('result.search_language', '搜索状态、Mod ID、Key、原文或译文'))}">
          ${isJsonResult ? '' : `<button type="button" id="export-language-edits"><i class="ri-download-2-line"></i><span>${escapeHtml(ui('result.export_edits', '导出已修改译文'))}</span></button>`}
        </div>
        <div id="language-result-content" class="view-content">
          ${renderLanguageResultTable(payload)}
        </div>
      `;
    }

    function renderLanguageResultTable(payload) {
      const entries = getFilteredLanguageEntries(payload);
      const pageInfo = paginate(entries, resultState.languagePage, 50);
      resultState.languagePage = pageInfo.page;
      const rows = pageInfo.rows.map(entry => {
        const editId = languageEditId(entry);
        const target = Object.prototype.hasOwnProperty.call(resultState.languageEdits, editId)
          ? resultState.languageEdits[editId]
          : entry.target;
        return `
        <tr class="result-row">
          <td>${escapeHtml(statusLabel(entry.status))}</td>
          <td>${escapeHtml(entry.jar)}</td>
          <td>${escapeHtml(entry.mod_id)}</td>
          <td>${escapeHtml(entry.key)}</td>
          <td>${escapeHtml(entry.source)}</td>
          <td><textarea data-language-edit="${escapeHtml(editId)}" placeholder="${escapeHtml(ui('result.target', '译文'))}">${escapeHtml(target)}</textarea></td>
        </tr>
      `;
      }).join('');
      return `
        <table>
          <thead><tr><th>${escapeHtml(ui('result.status', '状态'))}</th><th>${escapeHtml(ui('result.jar', 'JAR'))}</th><th>${escapeHtml(ui('result.mod_id', 'Mod ID'))}</th><th>${escapeHtml(ui('result.key', 'Key'))}</th><th>${escapeHtml(ui('result.source', '原文'))}</th><th>${escapeHtml(ui('result.target', '译文'))}</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="6">${escapeHtml(ui('result.no_rows', '无条目'))}</td></tr>`}</tbody>
        </table>
        ${renderPager('language', pageInfo)}
      `;
    }

    function getFilteredLanguageEntries(payload) {
      if (!payload) {
        return [];
      }
      const jarFilter = resultState.languageJarFilter || '全部';
      const query = resultState.languageSearch.trim().toLowerCase();
      const cacheKey = `${payload.job_id || ''}${jarFilter}${query}${(payload.entries || []).length}`;
      if (resultState.languageFilteredCacheKey === cacheKey) {
        return resultState.languageFilteredEntries;
      }
      const entries = (payload.entries || []).filter(entry => {
        if (!jarFilterMatchesEntry(entry.jar, jarFilter)) {
          return false;
        }
        if (!query) {
          return true;
        }
        const haystack = `${statusLabel(entry.status)} ${entry.status} ${entry.mod_id} ${entry.key} ${entry.source} ${entry.target} ${entry.message}`.toLowerCase();
        return haystack.includes(query);
      });
      resultState.languageFilteredCacheKey = cacheKey;
      resultState.languageFilteredEntries = entries;
      return entries;
    }

    function renderLanguageResultContent() {
      const target = document.getElementById('language-result-content');
      if (!target) {
        renderResultShell();
        return;
      }
      target.innerHTML = renderLanguageResultTable(resultState.payload);
      bindLanguageContentControls();
      bindLanguageTextareas();
    }

    function bindResultTabs() {
      document.querySelectorAll('[data-result-tab]').forEach(button => {
        button.addEventListener('click', () => {
          resultState.activeTab = button.dataset.resultTab;
          renderResultShell();
        });
      });
    }

    function bindViewButtons() {
      results.querySelectorAll('button[data-view]').forEach(button => {
        button.addEventListener('click', () => switchView(button.dataset.view));
      });
      const reportSearch = document.getElementById('report-search');
      if (reportSearch) {
        reportSearch.addEventListener('input', () => {
          clearTimeout(reportSearchDebounce);
          reportSearchDebounce = window.setTimeout(() => {
            resultState.reportSearch = reportSearch.value;
            resultState.reportPage = 1;
            renderReportContent();
          }, 200);
        });
      }
      const hardcodedReportSearch = document.getElementById('hardcoded-report-search');
      if (hardcodedReportSearch) {
        hardcodedReportSearch.addEventListener('input', () => {
          clearTimeout(hardcodedReportSearchDebounce);
          hardcodedReportSearchDebounce = window.setTimeout(() => {
            resultState.hardcodedSearch = hardcodedReportSearch.value;
            resultState.hardcodedPage = 1;
            renderHardcodedReportContent();
          }, 200);
        });
      }
      const apiLogSearch = document.getElementById('api-log-search');
      if (apiLogSearch) {
        apiLogSearch.addEventListener('input', () => {
          clearTimeout(apiLogSearchDebounce);
          apiLogSearchDebounce = window.setTimeout(() => {
            resultState.apiLogSearch = apiLogSearch.value;
            resultState.apiLogPage = 1;
            renderApiLogContent();
          }, 200);
        });
      }
      document.querySelectorAll('[data-page-view]:not([data-page-view="language"])').forEach(button => {
        button.addEventListener('click', () => {
          const page = Number(button.dataset.page || '1');
          if (button.dataset.pageView === 'report') {
            resultState.reportPage = page;
            renderReportContent();
          } else if (button.dataset.pageView === 'hardcoded') {
            resultState.hardcodedPage = page;
            renderHardcodedReportContent();
          } else if (button.dataset.pageView === 'api-log') {
            resultState.apiLogPage = page;
            renderApiLogContent();
          } else {
            renderResultShell();
          }
        });
      });
      const exportLog = document.getElementById('export-api-log');
      if (exportLog) {
        exportLog.addEventListener('click', () => downloadJson('api-debug-log.json', apiLogLines));
      }
      const retryFailures = document.getElementById('retry-api-failures');
      if (retryFailures) {
        retryFailures.addEventListener('click', retryApiFailures);
      }
      const downloadPack = document.getElementById('download-pack');
      if (downloadPack) {
        downloadPack.addEventListener('click', () => downloadPackWithCustomName(downloadPack));
      }
      const downloadFtbquests = document.getElementById('download-ftbquests');
      if (downloadFtbquests) {
        downloadFtbquests.addEventListener('click', () => {
          const url = downloadFtbquests.dataset.downloadUrl || '';
          if (url) {
            window.location.href = url;
          }
        });
      }
      const downloadJsonButton = document.getElementById('download-json');
      if (downloadJsonButton) {
        downloadJsonButton.addEventListener('click', () => {
          const url = downloadJsonButton.dataset.downloadUrl || '';
          if (url) {
            window.location.href = url;
          }
        });
      }
    }

    function renderReportContent() {
      const target = document.getElementById('report-view-content');
      if (!target) {
        renderResultShell();
        return;
      }
      target.innerHTML = renderReportTable();
      bindPagedContentControls();
    }

    function renderHardcodedReportContent() {
      const target = document.getElementById('hardcoded-report-content');
      if (!target) {
        renderResultShell();
        return;
      }
      target.innerHTML = renderHardcodedReportTable();
      bindPagedContentControls();
    }

    function renderApiLogContent() {
      const target = document.getElementById('api-log-content');
      if (!target) {
        renderResultShell();
        return;
      }
      target.innerHTML = renderApiLogTable();
      bindPagedContentControls();
    }

    function bindPagedContentControls() {
      document.querySelectorAll('[data-page-view="report"], [data-page-view="hardcoded"], [data-page-view="api-log"]').forEach(button => {
        button.addEventListener('click', () => {
          const page = Number(button.dataset.page || '1');
          if (button.dataset.pageView === 'report') {
            resultState.reportPage = page;
            renderReportContent();
          } else if (button.dataset.pageView === 'hardcoded') {
            resultState.hardcodedPage = page;
            renderHardcodedReportContent();
          } else if (button.dataset.pageView === 'api-log') {
            resultState.apiLogPage = page;
            renderApiLogContent();
          }
        });
      });
    }

    async function downloadPackWithCustomName(button) {
      const packUrl = button.dataset.packUrl || '';
      const defaultName = normalizeZipName(button.dataset.packName || defaultPackFilename(packUrl));
      const filename = await openPackNameDialog(defaultName);
      if (!filename) {
        return;
      }
      button.disabled = true;
      try {
        const response = await fetch(packUrl);
        if (!response.ok) {
          throw new Error('资源包下载失败');
        }
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(objectUrl);
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = error.message || '资源包下载失败';
      } finally {
        button.disabled = false;
      }
    }

    function openPackNameDialog(defaultName) {
      return new Promise(resolve => {
        const dialog = document.createElement('div');
        dialog.className = 'pack-name-dialog';
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');

        const card = document.createElement('div');
        card.className = 'pack-name-card';

        const head = document.createElement('div');
        head.className = 'pack-name-head';
        const titleWrap = document.createElement('div');
        const title = document.createElement('strong');
        title.textContent = ui('pack_dialog.title', '下载资源包');
        const desc = document.createElement('span');
        desc.textContent = ui('pack_dialog.desc', '输入本次下载的资源包名称，文件后缀固定为 .zip。');
        titleWrap.append(title, desc);
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'pack-name-close';
        close.innerHTML = '<i class="ri-close-line"></i>';
        head.append(titleWrap, close);

        const label = document.createElement('label');
        label.className = 'pack-name-field';
        label.textContent = ui('pack_dialog.name', '资源包名称');
        const inputWrap = document.createElement('div');
        inputWrap.className = 'pack-name-input-wrap';
        const input = document.createElement('input');
        input.className = 'ghost-input';
        input.value = packNameStem(defaultName);
        input.placeholder = ui('pack_dialog.placeholder', '例如：my-mod-zh_cn');
        const suffix = document.createElement('span');
        suffix.className = 'pack-name-suffix';
        suffix.textContent = '.zip';
        inputWrap.append(input, suffix);
        const error = document.createElement('div');
        error.className = 'pack-name-error';
        label.append(inputWrap, error);

        const actions = document.createElement('div');
        actions.className = 'pack-name-actions';
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'secondary';
        cancel.textContent = ui('pack_dialog.cancel', '取消');
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.textContent = ui('pack_dialog.download', '下载');
        actions.append(cancel, confirm);
        card.append(head, label, actions);
        dialog.append(card);
        document.body.appendChild(dialog);

        const finish = value => {
          document.removeEventListener('keydown', onKeyDown);
          dialog.remove();
          resolve(value);
        };
        const submitName = () => {
          const filename = normalizeZipName(input.value);
          if (!filename) {
            error.textContent = ui('pack_dialog.required', '请输入资源包名称');
            input.focus();
            return;
          }
          finish(filename);
        };
        const onKeyDown = event => {
          if (event.key === 'Escape') {
            finish('');
          } else if (event.key === 'Enter') {
            event.preventDefault();
            submitName();
          }
        };
        dialog.addEventListener('click', event => {
          if (event.target === dialog) {
            finish('');
          }
        });
        close.addEventListener('click', () => finish(''));
        cancel.addEventListener('click', () => finish(''));
        confirm.addEventListener('click', submitName);
        input.addEventListener('input', () => {
          const stem = packNameStem(input.value);
          if (stem !== input.value) {
            input.value = stem;
          }
          error.textContent = '';
        });
        document.addEventListener('keydown', onKeyDown);
        requestAnimationFrame(() => {
          input.focus();
          input.select();
        });
      });
    }

    function defaultPackFilename(url) {
      const raw = String(url || '').split('/').pop() || 'auto-i18n-resourcepack.zip';
      try {
        return decodeURIComponent(raw);
      } catch {
        return raw;
      }
    }

    function normalizeZipName(value) {
      const cleaned = packNameStem(value)
        .trim()
        .replace(/[<>:"/\\|?*\x00-\x1f]+/g, '_')
        .replace(/^[ .]+|[ .]+$/g, '');
      if (!cleaned) {
        return '';
      }
      return `${cleaned}.zip`;
    }

    function packNameStem(value) {
      return String(value || '').trim().replace(/\.zip$/i, '');
    }

    async function retryApiFailures() {
      const payload = resultState.payload;
      if (!payload || !payload.job_id) {
        return;
      }
      const button = document.getElementById('retry-api-failures');
      if (button) {
        button.disabled = true;
        button.classList.add('is-loading');
        button.innerHTML = `<i class="ri-loader-4-line"></i><span>${escapeHtml(ui('result.retrying', '正在重试...'))}</span>`;
        button.setAttribute('aria-busy', 'true');
      }
      statusBox.className = 'status';
      statusBox.textContent = ui('result.retrying_failed', '正在重试失败的翻译项...');
      try {
        const response = await fetch(`/api/retry/${payload.job_id}`, { method: 'POST' });
        const retryPayload = await response.json();
        if (!response.ok || !retryPayload.ok) {
          throw new Error(retryPayload.error || ui('result.retry_failed_error', '重试失败'));
        }
        resultState.payload = retryPayload.result;
        apiLogLines = Array.isArray(retryPayload.result.api_debug_log_lines) ? retryPayload.result.api_debug_log_lines : apiLogLines;
        renderResultShell();
        if (retryPayload.remaining) {
          statusBox.className = 'status error';
          statusBox.textContent = formatUi('result.retry_remaining', '已重试 {retried} 条，仍有 {remaining} 条异常。耗时 {elapsed}。', { retried: retryPayload.retried, remaining: retryPayload.remaining, elapsed: formatSeconds(retryPayload.elapsed_seconds) });
        } else {
          statusBox.className = 'status success';
          statusBox.textContent = formatUi('result.retry_success', '失败项已重试成功，更新 {retried} 条。耗时 {elapsed}。', { retried: retryPayload.retried, elapsed: formatSeconds(retryPayload.elapsed_seconds) });
        }
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = error.message;
        renderResultShell();
      } finally {
        if (button) {
          button.disabled = false;
          button.classList.remove('is-loading');
          button.innerHTML = `<i class="ri-refresh-line"></i><span>${escapeHtml(ui('result.retry_failed', '重试失败项'))}</span>`;
          button.removeAttribute('aria-busy');
        }
      }
    }

    function paginate(items, page, pageSize) {
      const totalItems = items.length;
      const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
      const currentPage = Math.min(Math.max(1, Number(page) || 1), totalPages);
      const start = (currentPage - 1) * pageSize;
      const end = Math.min(start + pageSize, totalItems);
      return {
        rows: items.slice(start, end),
        page: currentPage,
        totalPages,
        start,
        end,
        totalItems
      };
    }

    function pagerPages(currentPage, totalPages) {
      const pages = new Set([1, totalPages]);
      for (let page = currentPage - 2; page <= currentPage + 2; page += 1) {
        if (page >= 1 && page <= totalPages) {
          pages.add(page);
        }
      }
      return Array.from(pages).sort((a, b) => a - b);
    }

    function renderPager(view, pageInfo) {
      if (pageInfo.totalItems <= pageInfo.rows.length && pageInfo.totalPages <= 1) {
        return `<div class="pager"><span class="pager-info">${escapeHtml(formatUi('result.pager_range', '显示 {range} / {total} 条', { range: pageInfo.totalItems ? `${pageInfo.start + 1}-${pageInfo.end}` : '0', total: pageInfo.totalItems }))}</span></div>`;
      }
      let previous = 0;
      const pageButtons = pagerPages(pageInfo.page, pageInfo.totalPages).map(page => {
        const gap = previous && page - previous > 1 ? '<span class="muted">...</span>' : '';
        previous = page;
        return `${gap}<button type="button" class="${page === pageInfo.page ? 'active' : ''}" data-page-view="${view}" data-page="${page}" ${page === pageInfo.page ? 'disabled' : ''}>${page}</button>`;
      }).join('');
      return `
        <div class="pager">
          <span class="pager-info">${escapeHtml(formatUi('result.pager_info', '显示 {range} / {total} 条，每页 {pageSize} 条', { range: pageInfo.totalItems ? `${pageInfo.start + 1}-${pageInfo.end}` : '0', total: pageInfo.totalItems, pageSize: pageInfo.rows.length || 0 }))}</span>
          <div class="pager-controls">
            <button type="button" data-page-view="${view}" data-page="1" ${pageInfo.page === 1 ? 'disabled' : ''}>${escapeHtml(ui('result.first_page', '首页'))}</button>
            <button type="button" data-page-view="${view}" data-page="${Math.max(1, pageInfo.page - 1)}" ${pageInfo.page === 1 ? 'disabled' : ''}>${escapeHtml(ui('result.prev_page', '上一页'))}</button>
            ${pageButtons}
            <button type="button" data-page-view="${view}" data-page="${Math.min(pageInfo.totalPages, pageInfo.page + 1)}" ${pageInfo.page === pageInfo.totalPages ? 'disabled' : ''}>${escapeHtml(ui('result.next_page', '下一页'))}</button>
            <button type="button" data-page-view="${view}" data-page="${pageInfo.totalPages}" ${pageInfo.page === pageInfo.totalPages ? 'disabled' : ''}>${escapeHtml(ui('result.last_page', '末页'))}</button>
          </div>
        </div>
      `;
    }

    function renderReportView() {
      const payload = resultState.payload;
      if (!payload) {
        return `<div class="empty">${escapeHtml(ui('result.no_report', '还没有生成报告。'))}</div>`;
      }
      return `
        <div class="view-frame">
          <div class="view-head">
            <div><strong>${escapeHtml(ui('result.report', '翻译报告'))}</strong><div class="muted">${escapeHtml(ui('result.report_subtitle', '当前任务内嵌报告视图'))}</div></div>
          </div>
          <div class="view-body">
            <div class="toolbar">
              <input id="report-search" value="${escapeHtml(resultState.reportSearch)}" placeholder="${escapeHtml(ui('result.search_report', '搜索状态、JAR、Mod ID、文件、Key、原文或译文'))}">
            </div>
            <div id="report-view-content" class="view-content">
              ${renderReportTable()}
            </div>
          </div>
        </div>
      `;
    }

    function renderReportTable() {
      const payload = resultState.payload;
      if (!payload) {
        return `<div class="empty">${escapeHtml(ui('result.no_report', '还没有生成报告。'))}</div>`;
      }
      const query = resultState.reportSearch.trim().toLowerCase();
      const entries = (payload.entries || []).filter(entry => {
        if (!query) {
          return true;
        }
        const haystack = `${entry.status} ${entry.jar} ${entry.mod_id} ${entry.file} ${entry.key} ${entry.source} ${entry.target} ${entry.message}`.toLowerCase();
        return haystack.includes(query);
      });
      const pageInfo = paginate(entries, resultState.reportPage, 50);
      resultState.reportPage = pageInfo.page;
      const rows = pageInfo.rows.map(entry => `
        <tr>
          <td>${escapeHtml(statusLabel(entry.status))}</td>
          <td>${escapeHtml(entry.jar)}</td>
          <td>${escapeHtml(entry.mod_id)}</td>
          <td>${escapeHtml(entry.file)}</td>
          <td>${escapeHtml(entry.key)}</td>
          <td>${escapeHtml(entry.source)}</td>
          <td>${escapeHtml(entry.target)}</td>
          <td>${escapeHtml(entry.message)}</td>
        </tr>
      `).join('');
      return `
        <table>
          <thead><tr><th>${escapeHtml(ui('result.status', '状态'))}</th><th>${escapeHtml(ui('result.jar', 'JAR'))}</th><th>${escapeHtml(ui('result.mod_id', 'Mod ID'))}</th><th>${escapeHtml(ui('result.file', '文件'))}</th><th>${escapeHtml(ui('result.key', 'Key'))}</th><th>${escapeHtml(ui('result.source', '原文'))}</th><th>${escapeHtml(ui('result.target', '译文'))}</th><th>${escapeHtml(ui('result.message', '信息'))}</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="8">${escapeHtml(ui('result.no_rows', '无条目'))}</td></tr>`}</tbody>
        </table>
        ${renderPager('report', pageInfo)}
      `;
    }

    function renderHardcodedReportView() {
      const payload = resultState.payload || {};
      const reportEntries = Array.isArray(payload.hardcoded_entries) && payload.hardcoded_entries.length
        ? payload.hardcoded_entries
        : hardcodedState.entries;
      if (!reportEntries.length) {
        return `<div class="view-frame"><div class="empty">${escapeHtml(ui('result.no_hardcoded_report', '没有硬编码扫描结果。'))}</div></div>`;
      }
      return `
        <div class="view-frame">
          <div class="view-head">
            <div><strong>${escapeHtml(ui('result.hardcoded_report', '硬编码报告'))}</strong><div class="muted">${escapeHtml(ui('result.hardcoded_report_subtitle', '扫描候选与映射状态'))}</div></div>
          </div>
          <div class="view-body">
            <div class="toolbar">
              <input id="hardcoded-report-search" value="${escapeHtml(resultState.hardcodedSearch)}" placeholder="${escapeHtml(ui('result.search_hardcoded', '搜索分类、风险、JAR、Class 或英文文本'))}">
            </div>
            <div id="hardcoded-report-content" class="view-content">
              ${renderHardcodedReportTable()}
            </div>
          </div>
        </div>
      `;
    }

    function renderHardcodedReportTable() {
      const payload = resultState.payload || {};
      const reportEntries = Array.isArray(payload.hardcoded_entries) && payload.hardcoded_entries.length
        ? payload.hardcoded_entries
        : hardcodedState.entries;
      const query = resultState.hardcodedSearch.trim().toLowerCase();
      const entries = reportEntries.filter(entry => {
        if (!query) {
          return true;
        }
        const categoryLabel = entry.category_label || entry.categoryLabel || entry.category;
        const haystack = `${entry.category} ${categoryLabel} ${entry.risk} ${entry.jar} ${entry.class} ${entry.source} ${entry.suggestion || ''}`.toLowerCase();
        return haystack.includes(query);
      });
      const pageInfo = paginate(entries, resultState.hardcodedPage, 50);
      resultState.hardcodedPage = pageInfo.page;
      const rows = pageInfo.rows.map(entry => {
        const categoryLabel = entry.category_label || entry.categoryLabel || entry.category;
        return `
          <tr>
            <td>${escapeHtml(categoryLabel)}</td>
            <td>${escapeHtml(entry.risk)}</td>
            <td>${escapeHtml(entry.jar)}</td>
            <td>${escapeHtml(entry.class)}</td>
            <td>${escapeHtml(entry.source)}</td>
            <td>${escapeHtml(entry.suggestion || entry.translation || '')}</td>
          </tr>
        `;
      }).join('');
      return `
        <table>
          <thead><tr><th>${escapeHtml(ui('result.category', '分类'))}</th><th>${escapeHtml(ui('result.risk', '风险'))}</th><th>${escapeHtml(ui('result.jar', 'JAR'))}</th><th>${escapeHtml(ui('result.class', 'Class'))}</th><th>${escapeHtml(ui('result.english_text', '英文文本'))}</th><th>${escapeHtml(ui('result.suggestion_translation', '建议 / 译文'))}</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="6">${escapeHtml(ui('result.no_matching_candidates', '没有匹配的候选。'))}</td></tr>`}</tbody>
        </table>
        ${renderPager('hardcoded', pageInfo)}
      `;
    }

    function renderApiLogView() {
      if (!apiLogLines.length) {
        const payload = resultState.payload || {};
        const emptyMessage = payload.cache_hits && !payload.cache_misses
          ? ui('result.api_log_cached', '本次结果全部来自缓存，未实际发起 API 请求，所以这里没有调试日志。')
          : ui('result.api_log_empty', '没有 API 调试日志。勾选“记录 API 调试日志”后，实际发起 API 请求时会在这里显示。');
        return `<div class="view-frame"><div class="empty">${escapeHtml(emptyMessage)}</div></div>`;
      }
      return `
        <div class="view-frame">
          <div class="view-head">
            <div><strong>${escapeHtml(ui('result.api_log', 'API 调试日志'))}</strong><div class="muted">${escapeHtml(ui('result.api_log_subtitle', '请求、响应和重试记录，密钥已脱敏'))}</div></div>
            <div class="toolbar">
              <button type="button" id="export-api-log"><i class="ri-download-2-line"></i><span>${escapeHtml(ui('result.export_json', '导出 JSON'))}</span></button>
            </div>
          </div>
          <div class="view-body">
            <div class="toolbar">
              <input id="api-log-search" value="${escapeHtml(resultState.apiLogSearch)}" placeholder="${escapeHtml(ui('result.search_api_log', '搜索 provider、状态码、错误、请求或响应内容'))}">
            </div>
            <div id="api-log-content" class="view-content">
              ${renderApiLogTable()}
            </div>
          </div>
        </div>
      `;
    }

    function renderApiLogTable() {
      const query = resultState.apiLogSearch.trim().toLowerCase();
      const entries = apiLogLines.filter(line => {
        if (!query) {
          return true;
        }
        return JSON.stringify(line).toLowerCase().includes(query);
      });
      const pageInfo = paginate(entries, resultState.apiLogPage, 20);
      resultState.apiLogPage = pageInfo.page;
      const rows = pageInfo.rows.map(line => `
        <tr>
          <td>${escapeHtml(line.time || '')}</td>
          <td>${formatElapsed(line.elapsed_ms)}</td>
          <td>${escapeHtml(line.provider || '')}</td>
          <td>${escapeHtml(line.status ?? '')}</td>
          <td><textarea readonly>${escapeHtml(JSON.stringify(apiLogInput(line), null, 2))}</textarea></td>
          <td><textarea readonly>${escapeHtml(JSON.stringify(apiLogOutput(line), null, 2))}</textarea></td>
        </tr>
      `).join('');
      return `
        <table class="api-log-table">
          <thead><tr><th>${escapeHtml(ui('result.time', '时间'))}</th><th>${escapeHtml(ui('result.elapsed', '耗时'))}</th><th>${escapeHtml(ui('result.provider', 'Provider'))}</th><th>${escapeHtml(ui('result.status', '状态'))}</th><th>${escapeHtml(ui('result.input', '入参'))}</th><th>${escapeHtml(ui('result.output_response', '出参 / 响应'))}</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="6">${escapeHtml(ui('result.no_matching_logs', '没有匹配的日志。'))}</td></tr>`}</tbody>
        </table>
        ${renderPager('api-log', pageInfo)}
      `;
    }

    function apiLogInput(line) {
      if (line.type === 'api_call') {
        return {
          api_url: line.api_url,
          model: line.model,
          api_key_env: line.api_key_env,
          has_inline_api_key: line.has_inline_api_key,
          headers: line.request_headers,
          body: line.request_body
        };
      }
      if (line.type === 'retry_error') {
        return { attempt: line.attempt, retryable: line.retryable };
      }
      if (line.type === 'batch_failed') {
        return { batch_size: line.batch_size, item_ids: line.item_ids };
      }
      if (line.type === 'retry') {
        return { attempt: line.attempt, batch_size: line.batch_size };
      }
      return { batch_size: line.batch_size, attempt: line.attempt };
    }

    function apiLogOutput(line) {
      if (line.type === 'api_call') {
        return {
          status: line.status,
          response_headers: line.response_headers,
          body_preview: line.body_preview
        };
      }
      if (line.type === 'retry_error') {
        return { status: line.status, error: line.error, body_preview: line.body_preview };
      }
      if (line.type === 'retry') {
        return { delay_seconds: line.delay_seconds, reason: line.reason };
      }
      if (line.type === 'batch_failed') {
        return { error: line.error };
      }
      return {};
    }

    function bindJarFilterMenu(shell) {
      const trigger = shell.querySelector('[data-select-trigger]');
      const menu = shell.querySelector('.ghost-menu');
      const display = shell.querySelector('#language-jar-filter-display');
      if (!trigger || !menu) {
        return;
      }
      const closeMenu = () => {
        shell.classList.remove('open');
        menu.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
      };
      const openMenu = () => {
        shell.classList.add('open');
        menu.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
      };
      trigger.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (shell.classList.contains('open')) {
          closeMenu();
        } else {
          document.querySelectorAll('.ghost-select.open').forEach(item => {
            if (item !== shell) {
              item.classList.remove('open');
              const otherMenu = item.querySelector('.ghost-menu');
              if (otherMenu) {
                otherMenu.hidden = true;
              }
            }
          });
          openMenu();
        }
      });
      menu.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        const option = event.target.closest('[data-select-value]');
        if (!option) {
          return;
        }
        const value = option.dataset.selectValue;
        resultState.languageJarFilter = value;
        resultState.languageFilteredCacheKey = '';
        resultState.languagePage = 1;
        if (display) {
          display.textContent = jarFilterDisplayLabel(value);
          display.title = value;
        }
        menu.querySelectorAll('.ghost-option').forEach(item => {
          const isActive = item.dataset.selectValue === value;
          item.classList.toggle('active', isActive);
          if (item.hasAttribute('aria-selected')) {
            item.setAttribute('aria-selected', isActive ? 'true' : 'false');
          }
        });
        closeMenu();
        renderLanguageResultContent();
      });
      document.addEventListener('click', (event) => {
        if (!shell.contains(event.target)) {
          closeMenu();
        }
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
          closeMenu();
        }
      });
    }

    function bindLanguageResults() {
      const search = document.getElementById('language-search');
      if (!search) {
        return;
      }
      const jarShell = document.getElementById('language-jar-filter-shell');
      if (jarShell) {
        bindJarFilterMenu(jarShell);
      }
      search.addEventListener('input', () => {
        clearTimeout(languageSearchDebounce);
        languageSearchDebounce = window.setTimeout(() => {
          resultState.languageSearch = search.value;
          resultState.languageFilteredCacheKey = '';
          resultState.languagePage = 1;
          renderLanguageResultContent();
        }, 200);
      });
      const exportButton = document.getElementById('export-language-edits');
      if (exportButton) {
        exportButton.addEventListener('click', exportLanguageEdits);
      }
      bindLanguageContentControls();
      bindLanguageTextareas();
    }

    function bindLanguageContentControls() {
      document.querySelectorAll('[data-page-view="language"]').forEach(button => {
        button.addEventListener('click', () => {
          resultState.languagePage = Number(button.dataset.page || '1');
          renderLanguageResultContent();
        });
      });
    }

    function bindLanguageTextareas() {
      document.querySelectorAll('[data-language-edit]').forEach(textarea => {
        textarea.addEventListener('input', () => {
          resultState.languageEdits[textarea.dataset.languageEdit] = textarea.value;
        });
      });
    }

    function languageEditId(entry) {
      return [entry.jar, entry.file, entry.mod_id, entry.key].map(value => String(value ?? '').replace(/\u001f/g, '')).join('\u001f');
    }

    function exportLanguageEdits() {
      const payload = resultState.payload;
      const changed = {};
      for (const entry of payload.entries || []) {
        const editId = languageEditId(entry);
        if (!Object.prototype.hasOwnProperty.call(resultState.languageEdits, editId)) {
          continue;
        }
        const edited = resultState.languageEdits[editId];
        if (edited === entry.target) {
          continue;
        }
        const file = entry.file || `${entry.mod_id || 'unknown'}.json`;
        if (!changed[file]) {
          changed[file] = {};
        }
        changed[file][entry.key] = edited;
      }
      const total = Object.values(changed).reduce((count, fileEntries) => count + Object.keys(fileEntries).length, 0);
      if (!total) {
        statusBox.className = 'status';
        statusBox.textContent = ui('result.no_manual_edits', '没有需要导出的人工修改。');
        return;
      }
      downloadJson('language-edits.json', changed);
      statusBox.className = 'status';
      statusBox.textContent = formatUi('result.exported_manual_edits', '已导出 {total} 条人工修改译文。', { total });
    }

    function loadHardcodedMap(map) {
      hardcodedState.entries = Object.entries(map).map(([source, meta]) => ({
        source,
        translation: meta.translation || '',
        category: meta.category || 'unknown_literal',
        categoryLabel: meta.category_label || meta.categoryLabel || meta.category || 'unknown_literal',
        categoryOrder: Number(meta.category_order || meta.categoryOrder || 999),
        risk: meta.risk || '',
        class: meta.class || '',
        jar: meta.jar || ''
      }));
      hardcodedState.filter = 'all';
      hardcodedState.search = '';
      hardcodedState.page = 1;
      hardcodedState.selected = new Set();
    }

    function hardcodedCategoryFilters() {
      const categories = new Map();
      hardcodedState.entries.forEach(entry => {
        const category = entry.category || 'unknown_literal';
        const current = categories.get(category) || {
          category,
          label: entry.categoryLabel || category,
          order: Number.isFinite(entry.categoryOrder) ? entry.categoryOrder : 999,
          count: 0
        };
        current.count += 1;
        categories.set(category, current);
      });
      return [{
        category: 'all',
        label: formatUi('result.all_count', '全部 {count}', { count: hardcodedState.entries.length })
      }].concat(Array.from(categories.values()).sort((left, right) =>
        left.order - right.order || left.category.localeCompare(right.category)
      ).map(item => ({
        category: item.category,
        label: formatUi('result.category_count', '{label} {count}', { label: item.label, count: item.count })
      })));
    }

    function hardcodedEntryCategoryLabel(entry) {
      return entry.categoryLabel || entry.category || 'unknown_literal';
    }

    function hardcodedEntryHaystack(entry) {
      return `${entry.source} ${entry.class} ${entry.jar} ${entry.category} ${hardcodedEntryCategoryLabel(entry)}`.toLowerCase();
    }

    function renderHardcodedWorkbench() {
      if (!hardcodedState.entries.length) {
        return `<div class="empty">${escapeHtml(ui('result.no_editable_hardcoded', '没有检测到可编辑的硬编码候选。'))}</div>`;
      }
      const filters = hardcodedCategoryFilters().map(option => {
        return `<button type="button" data-hardcoded-filter="${escapeHtml(option.category)}" class="${option.category === hardcodedState.filter ? 'active' : ''}">${escapeHtml(option.label)}</button>`;
      }).join('');
      return `
        <div class="hardcoded-workbench">
          <div class="hardcoded-head">
            <div>
              <h3>${escapeHtml(ui('result.hardcoded_workbench', '硬编码映射工作台'))}</h3>
              <div class="muted">${escapeHtml(ui('result.hardcoded_workbench_desc', '填写 translation 后可导出 hardcoded-map.json。'))}</div>
            </div>
            <div class="actions">
              <button type="button" id="import-hardcoded"><i class="ri-upload-2-line"></i><span>${escapeHtml(ui('result.import_map', '导入 map'))}</span></button>
              <button type="button" id="ai-translate-hardcoded"><i class="ri-sparkling-2-line"></i><span>${escapeHtml(ui('result.ai_translate_selected', 'AI 翻译所选'))}</span></button>
              <button type="button" id="export-hardcoded"><i class="ri-download-2-line"></i><span>${escapeHtml(ui('result.export_filled', '导出已填写'))}</span></button>
              <input id="hardcoded-map-file" class="hidden-file" type="file" accept=".json,application/json">
            </div>
          </div>
          <div class="toolbar">
            <button type="button" id="select-hardcoded-page"><i class="ri-checkbox-multiple-line"></i><span>${escapeHtml(ui('result.select_page', '全选当前页'))}</span></button>
            <span id="hardcoded-selected-count" class="muted">${escapeHtml(formatUi('result.selected_count', '已选 {count} 条', { count: hardcodedState.selected.size }))}</span>
            ${filters}
            <input id="hardcoded-search" value="${escapeHtml(hardcodedState.search)}" placeholder="${escapeHtml(ui('result.search_hardcoded_workbench', '搜索英文、Class 或 JAR'))}">
          </div>
          <div id="hardcoded-table-wrap">
            ${renderHardcodedRows()}
          </div>
        </div>
      `;
    }

    function renderHardcodedRows() {
      const query = hardcodedState.search.trim().toLowerCase();
      const filtered = hardcodedState.entries.filter(entry => {
        const categoryMatched = hardcodedState.filter === 'all' || entry.category === hardcodedState.filter;
        const haystack = hardcodedEntryHaystack(entry);
        return categoryMatched && (!query || haystack.includes(query));
      });
      const pageInfo = paginate(filtered, hardcodedState.page, 50);
      hardcodedState.page = pageInfo.page;
      const rows = pageInfo.rows.map(entry => {
        const index = hardcodedState.entries.indexOf(entry);
        const errors = validateHardcodedEntry(entry);
        const selected = hardcodedState.selected.has(index);
        return `
          <tr class="hardcoded-row ${selected ? 'selected' : ''}" data-hardcoded-row="${index}">
            <td class="select-cell"><input type="checkbox" data-hardcoded-select="${index}" ${selected ? 'checked' : ''} aria-label="${escapeHtml(ui('result.select_hardcoded_candidate', '选择该硬编码候选'))}"></td>
            <td>${escapeHtml(hardcodedEntryCategoryLabel(entry))}<br><span class="muted">${escapeHtml(entry.risk)}</span></td>
            <td>${escapeHtml(entry.source)}<br><span class="muted">${escapeHtml(entry.class)}</span></td>
            <td>
              <textarea data-hardcoded-index="${index}" class="${errors.length ? 'invalid' : ''}" placeholder="${escapeHtml(ui('result.target', '译文'))}">${escapeHtml(entry.translation)}</textarea>
              ${errors.length ? `<div class="hardcoded-errors">${errors.map(escapeHtml).join('<br>')}</div>` : ''}
            </td>
          </tr>
        `;
      }).join('');
      return `
        <table>
          <thead><tr><th class="select-cell">${escapeHtml(ui('result.select', '选择'))}</th><th>${escapeHtml(ui('result.category', '分类'))}</th><th>${escapeHtml(ui('result.english_text', '英文文本'))}</th><th>${escapeHtml(ui('result.target', '译文'))}</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="4">${escapeHtml(ui('result.no_matching_candidates', '没有匹配的候选。'))}</td></tr>`}</tbody>
        </table>
        ${renderPager('hardcoded-workbench', pageInfo)}
      `;
    }

    function bindHardcodedWorkbench() {
      const wrap = document.getElementById('hardcoded-table-wrap');
      if (!wrap) {
        return;
      }
      document.querySelectorAll('[data-hardcoded-filter]').forEach(button => {
        button.addEventListener('click', () => {
          hardcodedState.filter = button.dataset.hardcodedFilter;
          hardcodedState.page = 1;
          document.querySelectorAll('[data-hardcoded-filter]').forEach(item => {
            item.classList.toggle('active', item === button);
          });
          wrap.innerHTML = renderHardcodedRows();
          bindHardcodedPager();
          bindHardcodedSelection();
          bindHardcodedTextareas();
          updateHardcodedSelectedCount();
        });
      });
      const search = document.getElementById('hardcoded-search');
      search.addEventListener('input', () => {
        clearTimeout(hardcodedWorkbenchSearchDebounce);
        hardcodedWorkbenchSearchDebounce = window.setTimeout(() => {
          hardcodedState.search = search.value;
          hardcodedState.page = 1;
          wrap.innerHTML = renderHardcodedRows();
          bindHardcodedPager();
          bindHardcodedSelection();
          bindHardcodedTextareas();
          updateHardcodedSelectedCount();
        }, 200);
      });
      document.getElementById('import-hardcoded').addEventListener('click', () => {
        document.getElementById('hardcoded-map-file').click();
      });
      document.getElementById('select-hardcoded-page').addEventListener('click', selectHardcodedPage);
      document.getElementById('ai-translate-hardcoded').addEventListener('click', translateSelectedHardcoded);
      document.getElementById('hardcoded-map-file').addEventListener('change', importHardcodedMap);
      document.getElementById('export-hardcoded').addEventListener('click', exportHardcodedMap);
      bindHardcodedPager();
      bindHardcodedSelection();
      bindHardcodedTextareas();
      updateHardcodedSelectedCount();
    }

    function bindHardcodedPager() {
      document.querySelectorAll('[data-page-view="hardcoded-workbench"]').forEach(button => {
        button.addEventListener('click', () => {
          hardcodedState.page = Number(button.dataset.page || '1');
          document.getElementById('hardcoded-table-wrap').innerHTML = renderHardcodedRows();
          bindHardcodedPager();
          bindHardcodedSelection();
          bindHardcodedTextareas();
          updateHardcodedSelectedCount();
        });
      });
    }

    function bindHardcodedSelection() {
      document.querySelectorAll('[data-hardcoded-select]').forEach(checkbox => {
        checkbox.addEventListener('click', event => {
          event.stopPropagation();
          setHardcodedSelected(Number(checkbox.dataset.hardcodedSelect), checkbox.checked);
        });
      });
      document.querySelectorAll('[data-hardcoded-row]').forEach(row => {
        row.addEventListener('click', event => {
          if (event.target.closest('textarea, input, button, a')) {
            return;
          }
          const index = Number(row.dataset.hardcodedRow);
          setHardcodedSelected(index, !hardcodedState.selected.has(index));
        });
      });
    }

    function setHardcodedSelected(index, selected) {
      if (selected) {
        hardcodedState.selected.add(index);
      } else {
        hardcodedState.selected.delete(index);
      }
      const checkbox = document.querySelector(`[data-hardcoded-select="${index}"]`);
      const row = document.querySelector(`[data-hardcoded-row="${index}"]`);
      if (checkbox) {
        checkbox.checked = selected;
      }
      if (row) {
        row.classList.toggle('selected', selected);
      }
      updateHardcodedSelectedCount();
    }

    function currentHardcodedPageIndexes() {
      const query = hardcodedState.search.trim().toLowerCase();
      const filtered = hardcodedState.entries.filter(entry => {
        const categoryMatched = hardcodedState.filter === 'all' || entry.category === hardcodedState.filter;
        const haystack = hardcodedEntryHaystack(entry);
        return categoryMatched && (!query || haystack.includes(query));
      });
      const pageInfo = paginate(filtered, hardcodedState.page, 50);
      return pageInfo.rows.map(entry => hardcodedState.entries.indexOf(entry));
    }

    function selectHardcodedPage() {
      const indexes = currentHardcodedPageIndexes();
      const allSelected = indexes.length > 0 && indexes.every(index => hardcodedState.selected.has(index));
      indexes.forEach(index => {
        if (allSelected) {
          hardcodedState.selected.delete(index);
        } else {
          hardcodedState.selected.add(index);
        }
      });
      document.getElementById('hardcoded-table-wrap').innerHTML = renderHardcodedRows();
      bindHardcodedPager();
      bindHardcodedSelection();
      bindHardcodedTextareas();
      updateHardcodedSelectedCount();
    }

    function updateHardcodedSelectedCount() {
      const count = document.getElementById('hardcoded-selected-count');
      if (count) {
        count.textContent = formatUi('result.selected_count', '已选 {count} 条', { count: hardcodedState.selected.size });
      }
    }

    function bindHardcodedTextareas() {
      document.querySelectorAll('[data-hardcoded-index]').forEach(textarea => {
        textarea.addEventListener('input', () => {
          const entry = hardcodedState.entries[Number(textarea.dataset.hardcodedIndex)];
          entry.translation = textarea.value;
        });
      });
    }

    async function translateSelectedHardcoded() {
      if (!providerPresets[provider.value]) {
        statusBox.className = 'status error';
        statusBox.textContent = ui('result.need_ai_provider', '请选择 AI 翻译器后再翻译硬编码映射。');
        return;
      }
      const selectedIndexes = Array.from(hardcodedState.selected).filter(index => hardcodedState.entries[index]);
      if (!selectedIndexes.length) {
        statusBox.className = 'status error';
        statusBox.textContent = ui('result.need_hardcoded_selection', '请先选择需要 AI 翻译的硬编码候选。');
        return;
      }
      const button = document.getElementById('ai-translate-hardcoded');
      if (button) {
        button.disabled = true;
        button.classList.add('is-loading');
        button.innerHTML = `<i class="ri-loader-4-line"></i><span>${escapeHtml(ui('result.translating', '正在翻译...'))}</span>`;
        button.setAttribute('aria-busy', 'true');
      }
      statusBox.className = 'status';
      statusBox.textContent = formatUi('result.translating_hardcoded', '正在用当前 API 配置翻译 {count} 条硬编码候选...', { count: selectedIndexes.length });
      try {
        const config = Object.fromEntries(new FormData(form).entries());
        const response = await fetch('/api/translate-hardcoded', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_id: resultState.payload?.job_id || '',
            config,
            entries: selectedIndexes.map(index => ({
              index,
              source: hardcodedState.entries[index].source,
              category: hardcodedState.entries[index].category,
              risk: hardcodedState.entries[index].risk,
              class: hardcodedState.entries[index].class,
              jar: hardcodedState.entries[index].jar
            }))
          })
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.error || ui('result.hardcoded_ai_failed', '硬编码 AI 翻译失败'));
        }
        let updated = 0;
        for (const [indexText, translation] of Object.entries(payload.translations || {})) {
          const index = Number(indexText);
          if (!hardcodedState.entries[index]) {
            continue;
          }
          hardcodedState.entries[index].translation = translation;
          hardcodedState.selected.delete(index);
          updated += 1;
        }
        if (Array.isArray(payload.api_debug_log_lines)) {
          apiLogLines = payload.api_debug_log_lines;
        }
        document.getElementById('hardcoded-table-wrap').innerHTML = renderHardcodedRows();
        bindHardcodedPager();
        bindHardcodedSelection();
        bindHardcodedTextareas();
        updateHardcodedSelectedCount();
        statusBox.className = payload.failed_count ? 'status error' : 'status success';
        statusBox.textContent = payload.failed_count
          ? formatUi('result.hardcoded_translated_partial', '已翻译 {updated} 条，{failed} 条失败，可查看 API 日志。', { updated, failed: payload.failed_count })
          : formatUi('result.hardcoded_translated', '已翻译 {updated} 条硬编码候选。', { updated });
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = error.message;
      } finally {
        if (button) {
          button.disabled = false;
          button.classList.remove('is-loading');
          button.innerHTML = `<i class="ri-sparkling-2-line"></i><span>${escapeHtml(ui('result.ai_translate_selected', 'AI 翻译所选'))}</span>`;
          button.removeAttribute('aria-busy');
        }
      }
    }

    async function importHardcodedMap(event) {
      const file = event.target.files[0];
      if (!file) {
        return;
      }
      try {
        const imported = JSON.parse(await file.text());
        const bySource = new Map(hardcodedState.entries.map(entry => [entry.source, entry]));
        for (const [source, value] of Object.entries(imported)) {
          const entry = bySource.get(source);
          if (!entry) {
            continue;
          }
          entry.translation = typeof value === 'string' ? value : (value.translation || '');
        }
        hardcodedState.page = 1;
        document.getElementById('hardcoded-table-wrap').innerHTML = renderHardcodedRows();
        bindHardcodedPager();
        bindHardcodedSelection();
        bindHardcodedTextareas();
        updateHardcodedSelectedCount();
        statusBox.className = 'status';
        statusBox.textContent = formatUi('result.imported_file', '已导入 {file}。', { file: file.name });
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = formatUi('result.import_failed', '导入失败：{message}', { message: error.message });
      } finally {
        event.target.value = '';
      }
    }

    function exportHardcodedMap() {
      const filled = hardcodedState.entries.filter(entry => entry.translation.trim());
      const errors = filled.flatMap(entry => validateHardcodedEntry(entry).map(error => `${entry.source}: ${error}`));
      if (errors.length) {
        statusBox.className = 'status error';
        statusBox.textContent = formatUi('result.hardcoded_validation_failed', '硬编码映射未通过校验：{errors}', { errors: errors.slice(0, 3).join('；') });
        document.getElementById('hardcoded-table-wrap').innerHTML = renderHardcodedRows();
        bindHardcodedPager();
        bindHardcodedSelection();
        bindHardcodedTextareas();
        updateHardcodedSelectedCount();
        return;
      }
      const output = {};
      filled.forEach(entry => {
        output[entry.source] = {
          translation: entry.translation.trim(),
          category: entry.category,
          risk: entry.risk,
          class: entry.class,
          jar: entry.jar
        };
      });
      downloadJson('hardcoded-map.json', output);
      statusBox.className = 'status';
      statusBox.textContent = formatUi('result.exported_hardcoded', '已导出 {count} 条硬编码译文。', { count: filled.length });
    }

    function validateHardcodedEntry(entry) {
      if (!entry.translation.trim()) {
        return [];
      }
      const errors = [];
      for (const [label, regex] of [
        ['printf placeholder', /%(?!%)(?:\d+\$)?[+#\-0,( ]*(?:\d+)?(?:\.\d+)?[bcdeEfgGaAosxXhHsd]/g],
        ['brace placeholder', /\{[A-Za-z0-9_.:-]+\}/g],
        ['minecraft format code', /§[0-9A-FK-ORa-fk-or]/g],
        ['newline', /\n/g]
      ]) {
        const missing = missingTokens(entry.source.match(regex) || [], entry.translation.match(regex) || []);
        if (missing.length) {
          errors.push(formatUi('result.missing_token', '缺少 {label}: {tokens}', { label, tokens: missing.join(', ') }));
        }
      }
      return errors;
    }

    function missingTokens(sourceTokens, targetTokens) {
      const counts = new Map();
      targetTokens.forEach(token => counts.set(token, (counts.get(token) || 0) + 1));
      const missing = [];
      sourceTokens.forEach(token => {
        const count = counts.get(token) || 0;
        if (count > 0) {
          counts.set(token, count - 1);
        } else {
          missing.push(token);
        }
      });
      return missing;
    }

    function downloadJson(filename, value) {
      const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    function formatSeconds(value) {
      const seconds = Number(value || 0);
      if (!Number.isFinite(seconds) || seconds <= 0) {
        return '0s';
      }
      if (seconds < 60) {
        return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
      }
      const minutes = Math.floor(seconds / 60);
      const rest = Math.round(seconds % 60);
      return `${minutes}m ${rest}s`;
    }

    function formatElapsed(ms) {
      if (ms == null) return '-';
      if (ms < 1000) return ms + 'ms';
      const s = ms / 1000;
      if (s < 60) return s.toFixed(1) + 's';
      const m = Math.floor(s / 60);
      const rs = Math.round(s % 60);
      return m + 'm ' + rs + 's';
    }

    const STATUS_LABEL_KEYS = {
      translated: ['result.status_translated', '已翻译'],
      existing: ['result.status_existing', '已有翻译'],
      skipped: ['result.status_skipped', '已跳过'],
      failed: ['result.status_failed', '校验失败'],
      api_failed: ['result.status_api_failed', 'API 失败'],
      jar_failed: ['result.status_jar_failed', 'JAR 错误'],
      incomplete: ['result.status_incomplete', '不完整'],
    };
    function statusLabel(status) {
      const pair = STATUS_LABEL_KEYS[status];
      return pair ? ui(pair[0], pair[1]) : status;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }
  </script>
</body>
</html>
"""


@dataclass(frozen=True)
class MultipartPart:
    name: str
    filename: str | None
    content_type: str
    data: bytes


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


def make_handler(workdir: Path):
    jobs: dict[str, dict[str, Any]] = {}
    cancel_events: dict[str, Event] = {}
    jobs_lock = Lock()

    def update_job(job_id: str, **values: Any) -> None:
        with jobs_lock:
            job = jobs.setdefault(job_id, {})
            job.update(values)

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
            if parsed.path == "/assets/logo/minecraft.svg":
                if not SIDEBAR_LOGO_PATH.is_file():
                    self.send_error(404)
                    return
                self._send_bytes(SIDEBAR_LOGO_PATH.read_bytes(), "image/svg+xml; charset=utf-8")
                return
            if parsed.path == "/favicon.ico":
                if not SIDEBAR_LOGO_PATH.is_file():
                    self.send_error(404)
                    return
                self._send_bytes(SIDEBAR_LOGO_PATH.read_bytes(), "image/svg+xml; charset=utf-8")
                return
            if parsed.path.startswith("/api/progress/"):
                self._send_progress(parsed.path.removeprefix("/api/progress/"))
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
            if parsed.path.startswith("/download/"):
                self._serve_run_file(parsed.path.removeprefix("/download/"), download=True)
                return
            if parsed.path.startswith("/report/"):
                self._serve_run_file(parsed.path.removeprefix("/report/"), download=False)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/models":
                try:
                    payload = self._handle_models()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/cache/clear":
                try:
                    payload = self._handle_clear_cache()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            if parsed.path == "/api/ui-locales/import":
                try:
                    payload = self._handle_ui_locale_import()
                    self._send_json(payload)
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)
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

        def _handle_clear_cache(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8") or "{}")
            cache_root = resolve_cache_root(workdir, str(payload.get("cache_dir", "") or ""))
            removed = clear_cache_directory(cache_root, workdir)
            return {"ok": True, "cache_dir": str(cache_root), "removed": removed}

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
            package = export_ui_locale_package(normalized, root)
            data = json.dumps(package, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            filename = f"mc-mod-i18n-ui-{package['locale']}.json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def _handle_ui_locale_import(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            parts = parse_multipart(self.headers.get("Content-Type", ""), body)
            fields = collect_fields(parts)
            root = resolve_ui_locale_root(workdir, fields.get("ui_locale_dir", ""))
            part = next((item for item in parts if item.filename and item.name in {"ui_locale_file", "ui_locale_pack"} and item.data), None)
            if part is None:
                raise ValueError("请上传界面语言包 JSON")
            try:
                payload = json.loads(part.data.decode("utf-8-sig"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"语言包 JSON 无法解析：{exc}") from exc
            package = parse_ui_locale_package(payload, part.filename or "")
            result = write_extension_package(root, package)
            return {"ok": True, "ui_locale_dir": str(root), **result}

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

            glossary_path = None
            for part in parts:
                if part.name == "glossary" and part.filename and part.data:
                    glossary_path = upload_dir / sanitize_filename(part.filename)
                    glossary_path.write_bytes(part.data)
                    break

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
                progress_callback=progress_callback,
            )
            cache_root = resolve_cache_root(workdir, fields.get("cache_dir", ""))
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
                    "cache_dir": str(cache_root),
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
            for index, part in enumerate(uploaded, start=1):
                filename = sanitize_filename(part.filename or f"language-{index}.json")
                if not filename.lower().endswith(".json"):
                    continue
                path = upload_dir / filename
                path.write_bytes(part.data)
                json_paths.append(path)

            if not json_paths:
                raise ValueError(translate_ui("error.json_no_file", ui_locale, ui_locale_root))

            glossary_path = None
            for part in parts:
                if part.name == "glossary" and part.filename and part.data:
                    glossary_path = upload_dir / sanitize_filename(part.filename)
                    glossary_path.write_bytes(part.data)
                    break

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
                api_concurrency=progress_total,
                api_retries=max(1, min(10, int(fields.get("api_retries", "5") or "5"))),
                api_batch_size=api_batch_size,
                api_timeout=api_timeout,
                model=fields.get("model", "gpt-4o-mini") or "gpt-4o-mini",
                progress_callback=progress_callback,
            )
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
                    "cache_dir": "",
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
                args=None,
                api_debug_log_path=str(api_debug_log_path),
            )

            glossary_path = None
            for part in parts:
                if part.name == "glossary" and part.filename and part.data:
                    glossary_path = upload_dir / sanitize_filename(part.filename)
                    glossary_path.write_bytes(part.data)
                    break

            args = argparse.Namespace(
                source_locale=source_locale,
                target_locale=fields.get("target_locale", "zh_cn") or "zh_cn",
                provider=fields.get("provider", "glossary") or "glossary",
                glossary=str(glossary_path) if glossary_path else None,
                overwrite_existing=fields.get("overwrite_existing") == "on",
                ignore_cache=fields.get("ignore_cache") == "on",
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
                    "cache_dir": str(cache_root),
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
            updated = 0
            still_failed = 0
            remaining_failed_entries: list[dict[str, Any]] = []
            visible_entries = result.get("entries", [])
            visible_by_id = {entry_id(entry): entry for entry in visible_entries}
            for failed_entry in failed_entries:
                item_id = entry_id(failed_entry)
                entry = visible_by_id.get(item_id, failed_entry)
                if item_id in failed_map or item_id not in translations:
                    entry["message"] = str(failed_map.get(item_id, "retry did not return translation"))
                    still_failed += 1
                    remaining_failed_entries.append(dict(entry))
                    continue
                translated = translations[item_id]
                errors = validate_translation(entry.get("source", ""), translated)
                if errors:
                    entry["message"] = "; ".join(errors)
                    still_failed += 1
                    remaining_failed_entries.append(dict(entry))
                    continue
                entry["target"] = translated
                entry["status"] = "translated"
                entry["message"] = "手动重试成功"
                updated += 1

            summary: dict[str, int] = {}
            base_summary = result.get("summary", {})
            if isinstance(base_summary, dict):
                summary.update({str(key): int(value) for key, value in base_summary.items()})
                summary["api_failed"] = still_failed
                summary["translated"] = max(0, summary.get("translated", 0)) + updated
            else:
                summary = {}
            if "api_failed" in summary:
                summary["api_failed"] = still_failed
            result["summary"] = summary
            result["api_failure_count"] = still_failed
            result["api_failed_entries"] = remaining_failed_entries
            result["retry_elapsed_seconds"] = round(elapsed_seconds, 2)
            pack_url = str(result.get("pack_url") or "")
            if updated and pack_url.startswith(f"/download/{job_id}/"):
                relative = pack_url.removeprefix(f"/download/{job_id}/")
                pack_path = safe_run_path(workdir / job_id, relative)
                update_resource_pack_entries(pack_path, successful_retry_updates(failed_entries, translations, failed_map))
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


def normalize_models_url(base_url: str, provider: str) -> str:
    preset = get_provider_preset(provider)
    raw = str(base_url or preset.api_url).strip() or preset.api_url
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("BaseURL 必须是 http 或 https URL")
    path = parsed.path.rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/messages"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    if path.endswith("/models"):
        models_path = path
    elif path in ("", "/"):
        models_path = "/v1/models"
    else:
        models_path = f"{path}/models"
    return parsed._replace(path=models_path, params="", query="", fragment="").geturl()


def fetch_provider_models(provider: str, base_url: str, api_key: str, api_key_env: str, timeout: float) -> list[dict[str, str]]:
    key = api_key or os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"API Key 未填写，且环境变量 {api_key_env} 未设置")
    models_url = normalize_models_url(base_url, provider)
    headers = {"Content-Type": "application/json"}
    if provider == "anthropic-compatible":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(models_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"模型列表请求失败：HTTP {exc.code}: {body[:300]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"模型列表连接失败：{reason}") from exc
    return parse_models_response(response_text)


def parse_models_response(response_text: str) -> list[dict[str, str]]:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        preview = response_text[:180].replace("\n", "\\n")
        raise RuntimeError(f"模型列表返回格式无法识别：{preview}") from exc
    raw_models: Any
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        raw_models = data["data"]
    elif isinstance(data, dict) and isinstance(data.get("models"), list):
        raw_models = data["models"]
    elif isinstance(data, list):
        raw_models = data
    else:
        raise RuntimeError("模型列表返回格式无法识别")
    models: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_models:
        if isinstance(item, str):
            model_id = item
            label = item
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("name") or "").strip()
            label = str(item.get("display_name") or item.get("label") or model_id).strip()
        else:
            continue
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        models.append({"id": model_id, "label": label or model_id})
    return models


def parse_multipart(content_type: str, body: bytes) -> list[MultipartPart]:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("请求不是 multipart/form-data")
    boundary = match.group("boundary").strip('"')
    delimiter = b"--" + boundary.encode("utf-8")
    parts: list[MultipartPart] = []

    for raw_part in body.split(delimiter):
        raw_part = raw_part.strip(b"\r\n")
        if not raw_part or raw_part == b"--":
            continue
        if raw_part.endswith(b"--"):
            raw_part = raw_part[:-2].rstrip(b"\r\n")
        if b"\r\n\r\n" not in raw_part:
            continue
        raw_headers, data = raw_part.split(b"\r\n\r\n", 1)
        headers = parse_part_headers(raw_headers)
        disposition = headers.get("content-disposition", "")
        params = parse_header_params(disposition)
        name = params.get("name")
        if not name:
            continue
        parts.append(
            MultipartPart(
                name=name,
                filename=params.get("filename"),
                content_type=headers.get("content-type", "application/octet-stream"),
                data=data,
            )
        )
    return parts


def parse_part_headers(raw_headers: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in raw_headers.decode("utf-8", errors="replace").split("\r\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def parse_header_params(value: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for piece in value.split(";"):
        piece = piece.strip()
        if "=" not in piece:
            continue
        key, raw_value = piece.split("=", 1)
        params[key.strip().lower()] = raw_value.strip().strip('"')
    return params


def collect_fields(parts: list[MultipartPart]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in parts:
        if part.filename is None:
            fields[part.name] = part.data.decode("utf-8", errors="replace")
    return fields


def resolve_cache_root(workdir: Path, raw_cache_dir: str | None) -> Path:
    raw = (raw_cache_dir or "").strip()
    if not raw:
        return (workdir / ".shared-cache").resolve()
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


def shared_cache_scope_dir(cache_root: Path, args: argparse.Namespace) -> Path:
    digest = compute_translation_config_hash(args)[:16]
    scope_dir = cache_root / digest
    scope_dir.mkdir(parents=True, exist_ok=True)
    return scope_dir


def shared_cache_key(jar_path: Path) -> str:
    name_hash = hashlib.sha1(jar_path.name.encode("utf-8")).hexdigest()[:10]
    return f"{jar_path.stem}-{name_hash}"


def json_target_filename(source_name: str, source_locale: str, target_locale: str, schema: str) -> str:
    name = sanitize_filename(source_name)
    stem = Path(name).stem
    source = str(source_locale or "en_us").lower()
    target = str(target_locale or "zh_cn").lower()
    if schema == "ui_locale":
        return f"mc-mod-i18n-ui-{target}.json"
    pattern = re.compile(re.escape(source), flags=re.IGNORECASE)
    if pattern.search(stem):
        stem = pattern.sub(target, stem, count=1)
    elif re.fullmatch(r"[a-z]{2,3}_[a-z0-9]{2,8}", stem.lower()):
        stem = target
    else:
        stem = f"{stem}.{target}"
    return f"{stem}.json"


def minecraft_locale_display_names() -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r'\["([a-z0-9_]+)", "([^"]+)"\]', INDEX_HTML)
    }


UI_LOCALE_NAME_MAP: dict[str, str] = {**LOCALE_DISPLAY_NAMES, **minecraft_locale_display_names()}


def ui_locale_name_pair(locale: str) -> tuple[str, str]:
    normalized = str(locale or "").strip().lower().replace("-", "_")
    display = UI_LOCALE_NAME_MAP.get(normalized) or normalized or "Custom"
    return display, display


def parse_json_translation_payload(data: Any, filename: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError("语言 JSON 必须是对象")
    if isinstance(data.get("messages"), dict):
        package = parse_ui_locale_package(data, filename)
        root = {
            key: value
            for key, value in data.items()
            if key != "messages"
        }
        root.update(
            {
                "schema_version": package["schema_version"],
                "locale": package["locale"],
                "name": package["name"],
                "native_name": package["native_name"],
                "source_locale": package["source_locale"],
                "source_version": package["source_version"],
                "messages": dict(package["messages"]),
            }
        )
        return "ui_locale", root, root["messages"]
    return "flat", dict(data), data


def process_json_language_file(
    path: Path,
    args: argparse.Namespace,
    translator,
) -> tuple[str, dict[str, Any], list[ReportEntry], int, int, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} 不是有效 JSON：{exc}") from exc
    schema, root, entries = parse_json_translation_payload(data, path.name)
    output_name = json_target_filename(path.name, args.source_locale, args.target_locale, schema)
    report: list[ReportEntry] = []
    items: list[TranslationItem] = []
    item_sources: dict[str, tuple[str, str]] = {}
    skipped = 0
    for key, value in entries.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, str):
            skipped += 1
            report.append(
                ReportEntry(
                    jar=path.name,
                    mod_id="json",
                    file=output_name,
                    key=key,
                    source="",
                    target="",
                    status="skipped",
                    message="non-string JSON value skipped",
                )
            )
            continue
        if value == "":
            entries[key] = value
            continue
        item_id = f"{path.name}\u001f{key}"
        item_sources[item_id] = (key, value)
        items.append(TranslationItem(id=item_id, key=key, text=value, mod_id="json"))

    translations, failed_items = translate_batch_with_failures(translator, items)
    translated_count = 0
    failed_count = 0
    for item_id, (key, source_text) in item_sources.items():
        if item_id in failed_items:
            failed_count += 1
            entries[key] = source_text
            report.append(
                ReportEntry(
                    jar=path.name,
                    mod_id="json",
                    file=output_name,
                    key=key,
                    source=source_text,
                    target=source_text,
                    status="api_failed",
                    message=str(failed_items[item_id]),
                )
            )
            continue
        translated = translations.get(item_id, source_text)
        errors = validate_translation(source_text, translated)
        if errors:
            failed_count += 1
            entries[key] = source_text
            report.append(
                ReportEntry(
                    jar=path.name,
                    mod_id="json",
                    file=output_name,
                    key=key,
                    source=source_text,
                    target=source_text,
                    status="failed",
                    message="; ".join(errors),
                )
            )
            continue
        entries[key] = translated
        translated_count += 1
        report.append(
            ReportEntry(
                jar=path.name,
                mod_id="json",
                file=output_name,
                key=key,
                source=source_text,
                target=translated,
                status="translated",
                message="",
            )
        )

    if schema == "ui_locale":
        target_name, target_native_name = ui_locale_name_pair(args.target_locale)
        root["locale"] = args.target_locale
        root["name"] = target_name
        root["native_name"] = target_native_name
        root["source_locale"] = args.source_locale
        root["messages"] = entries
    else:
        root = entries
    return output_name, root, report, translated_count, failed_count, skipped


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
        report_entries: list[ReportEntry] = []
        output_paths: list[Path] = []
        translated_total = 0
        failed_total = 0
        skipped_total = 0
        for index, path in enumerate(json_paths, start=1):
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("cancelled")
            update_job(job_id, stage="processing_file", files_completed=index - 1, files_total=len(json_paths), current_file=path.name)
            output_name, output_data, entries, translated_count, failed_count, skipped_count = process_json_language_file(path, args, translator)
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
        result = {
            "kind": "json",
            "job_id": job_id,
            "provider": args.provider,
            "processed_sources": len(json_paths),
            "generated_files": len(output_paths),
            "json_url": f"/download/{job_id}/out/{download_path.name}",
            "json_filename": download_path.name,
            "report_url": "",
            "api_debug_log_url": f"/report/{job_id}/out/api-debug.jsonl" if api_debug_log_path.is_file() else "",
            "api_debug_log_lines": read_jsonl(api_debug_log_path, limit=300),
            "elapsed_seconds": round(elapsed_seconds, 2),
            "cache_hits": 0,
            "cache_misses": translated_total,
            "summary": summary,
            "api_failure_count": summary.get("api_failed", 0),
            "api_failed_entries": [entry.__dict__ for entry in report_entries if entry.status == "api_failed"],
            "entries": [entry.__dict__ for entry in report_entries],
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
        patch_url = f"/download/{job_id}/out/{patch_path.name}" if patch_path and patch_path.is_file() else ""
        result_payload = {
            "ok": True,
            "kind": "ftbquests",
            "job_id": job_id,
            "processed_jars": 0,
            "processed_sources": 1,
            "generated_files": len(result.output_files),
            "mode": result.mode,
            "legacy_files": len(result.legacy_files),
            "ftbquests_patch_url": patch_url,
            "ftbquests_directory": str(directory_path) if directory_path else "",
            "report_url": f"/report/{job_id}/out/ftbquests-report.html",
            "ftbquests_json_report_url": f"/download/{job_id}/out/ftbquests-report.json",
            "api_debug_log_url": f"/report/{job_id}/out/api-debug.jsonl" if api_debug_log_path.is_file() else "",
            "hardcoded_count": 0,
            "hardcoded_map": {},
            "hardcoded_entries": [],
            "summary": summary,
            "provider": args.provider,
            "elapsed_seconds": round(elapsed_seconds, 2),
            "cache_hits": 1 if cache_hit else 0,
            "cache_misses": 0 if cache_hit else 1,
            "api_failure_count": summary.get("api_failed", 0),
            "api_failed_entries": [entry.__dict__ for entry in result.report_entries if entry.status == "api_failed"],
            "entries": [entry.__dict__ for entry in result.report_entries],
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
        def process_single(jar_path: Path) -> tuple[Path, list[OutputLangDocument], list[ReportEntry], list, str, bool]:
            jar_docs: list[OutputLangDocument] = []
            jar_entries: list[ReportEntry] = []
            jar_hardcoded: list = []
            source_hash = ""
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
                jar_docs, jar_entries, source_hash = process_jar(jar_path, args, translator)
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
                read_co1dsand_pack_icon(),
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

        result = {
            "ok": True,
            "job_id": job_id,
            "processed_jars": len(jar_paths),
            "generated_files": len(output_documents),
            "hardcoded_count": len(hardcoded_entries),
            "pack_url": f"/download/{job_id}/out/{pack_filename}" if output_documents else "",
            "pack_filename": pack_filename,
            "report_url": f"/report/{job_id}/out/report.html",
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


def sanitize_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or "upload.bin"


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


def entry_id(entry: dict[str, Any]) -> str:
    return f"{entry.get('jar', '')}{entry.get('file', '')}{entry.get('key', '')}"


def successful_retry_updates(
    failed_entries: list[dict[str, Any]],
    translations: dict[str, str],
    failed_map: dict[str, str],
) -> dict[str, dict[str, str]]:
    updates: dict[str, dict[str, str]] = {}
    for entry in failed_entries:
        item_id = entry_id(entry)
        if item_id in failed_map or item_id not in translations:
            continue
        translated = translations[item_id]
        if validate_translation(entry.get("source", ""), translated):
            continue
        file_path = entry.get("file", "")
        key = entry.get("key", "")
        if not file_path or not key:
            continue
        updates.setdefault(file_path, {})[key] = translated
    return updates


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


def read_co1dsand_pack_icon() -> bytes | None:
    for path in CO1DSAND_PACK_LOGO_PATHS:
        icon = read_pack_icon(path)
        if icon:
            return icon
    return None


def read_jsonl(path: Path, limit: int = 300) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
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


def safe_run_path(workdir: Path, relative: str) -> Path:
    decoded = unquote(relative).replace("\\", "/")
    target = (workdir / decoded).resolve()
    if target != workdir and workdir not in target.parents:
        raise ValueError("invalid path")
    return target
