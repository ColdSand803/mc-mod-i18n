from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
import re
from secrets import token_hex
from threading import Event, Lock, Thread
import time
from typing import Any
from urllib.parse import unquote, urlparse
from zipfile import BadZipFile, ZipFile

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import compute_translation_config_hash, compute_zip_source_hash, create_translator, process_jar, report_has_uncacheable_failures, translate_batch_with_failures
from .hardcoded import HardcodedEntry
from .hardcoded import scan_jar_for_hardcoded
from .pack import OutputLangDocument, load_checkpoint, load_checkpoint_config_hash, load_checkpoint_source_hash, read_pack_icon, resolve_pack_format, resource_pack_filename, save_checkpoint, update_resource_pack_entries, write_resource_pack
from .report import (
    ReportEntry,
    build_hardcoded_map_template,
    write_hardcoded_map_template,
    write_hardcoded_report,
    write_report,
)
from .translator import TranslationItem, is_ai_provider
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
        const mode = localStorage.getItem(key) || 'auto';
        const resolved = mode === 'auto'
          ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
          : mode;
        document.documentElement.dataset.themeMode = mode;
        document.documentElement.dataset.theme = resolved;
        document.documentElement.style.colorScheme = resolved;
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
      --danger: #ba1a1a;
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
      --danger: #fca5a5;
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
    .ghost-menu-input {
      position: sticky;
      top: 0;
      z-index: 1;
      min-height: 38px;
      margin-bottom: 4px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: var(--field-bg);
      color: var(--text);
      padding: 0 10px;
      font: inherit;
      outline: none;
      box-shadow: var(--field-shadow);
    }
    .ghost-menu-input:focus {
      border-color: var(--accent);
      box-shadow: var(--focus-ring);
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
      background: #fff;
      color: var(--text);
      cursor: pointer;
      font: inherit;
      text-align: left;
      transition: background-color var(--motion-fast) ease, border-color var(--motion-fast) ease, color var(--motion-fast) ease, transform var(--motion-fast) ease;
    }
    .ghost-option:hover {
      background: var(--accent-soft-hover);
      border-color: var(--accent-soft-line);
      color: var(--accent);
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
      content: "展开";
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }
    details.form-card[open] summary::after {
      content: "收起";
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
      color: #fff;
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
      color: #fff;
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
    .pack-name-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
    }
    .pack-name-head strong {
      display: block;
      font-size: 16px;
      line-height: 1.35;
    }
    .pack-name-head span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .pack-name-close {
      width: 34px;
      height: 34px;
      min-height: 34px;
      padding: 0;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--field-bg);
      color: var(--muted);
    }
    .pack-name-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
    .pack-name-actions button {
      border-radius: 10px;
    }
    .pack-name-actions .secondary {
      border: 1px solid var(--line);
      background: var(--field-bg);
      color: var(--text);
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
    .theme-toggle {
      min-width: 122px;
      padding: 0 12px;
      border: 1px solid var(--line);
      background: var(--field-bg);
      color: var(--text);
      box-shadow: none;
    }
    .theme-toggle span {
      font-size: 12px;
      font-weight: 700;
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
    .metric:nth-child(5)::before { background: #7c3aed; }
    .metric:nth-child(6)::before { background: #0891b2; }
    .metric:nth-child(7)::before { background: #ea580c; }
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
      background: #f8fbff;
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
      color: #fff;
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
      background: #eff6ff;
      color: #1d4ed8;
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
      background: #dbe7f4;
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
    .results-panel::-webkit-scrollbar {
      width: 12px;
      height: 12px;
    }
    .results::-webkit-scrollbar-thumb,
    .config-panel::-webkit-scrollbar-thumb,
    .results-panel::-webkit-scrollbar-thumb {
      border: 3px solid transparent;
      background-clip: padding-box;
      background-color: var(--scroll-thumb);
      border-radius: 999px;
    }
    .results::-webkit-scrollbar-track,
    .config-panel::-webkit-scrollbar-track,
    .results-panel::-webkit-scrollbar-track {
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
    :root[data-theme="dark"] .ghost-menu-input,
    :root[data-theme="dark"] .ghost-option,
    :root[data-theme="dark"] input,
    :root[data-theme="dark"] select,
    :root[data-theme="dark"] textarea,
    :root[data-theme="dark"] .toolbar button,
    :root[data-theme="dark"] .pack-name-close,
    :root[data-theme="dark"] .pack-name-actions .secondary {
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
    :root[data-theme="dark"] .loading-meta {
      color: var(--muted);
    }
    :root[data-theme="dark"] input[type="file"],
    :root[data-theme="dark"] .loading-progress {
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
      .results-panel {
        max-height: none;
      }
      .panel-head,
      .form-card,
      .view-head,
      .view-body {
        padding-left: 16px;
        padding-right: 16px;
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
      .tabs {
        width: 100%;
      }
      .actions a,
      .actions button,
      .toolbar button,
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
      .view-body {
        padding-left: 14px;
        padding-right: 14px;
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
        <div class="mark"><img src="/assets/logo/minecraft.svg" alt="汉化工作台"></div>
        <div><strong>汉化工作台</strong><span>mc-mod-i18n 本地版</span></div>
      </div>
      <nav class="nav-list">
        <button type="button" class="nav-item active" data-view="language"><i class="ri-folder-open-line"></i><span>工作区</span></button>
        <button type="button" class="nav-item" data-view="report"><i class="ri-history-line"></i><span>翻译报告</span></button>
        <button type="button" class="nav-item" data-view="hardcoded"><i class="ri-tools-line"></i><span>硬编码</span></button>
        <button type="button" class="nav-item" data-view="api-log"><i class="ri-bug-line"></i><span>API 日志</span></button>
      </nav>
      <div class="nav-footer">
        <div class="nav-item"><i class="ri-file-list-3-line"></i><span>文档</span></div>
        <div class="nav-item"><i class="ri-question-line"></i><span>帮助</span></div>
      </div>
    </aside>
    <div class="content-shell">
      <header>
        <div class="top-left">
          <div class="brand">MC-LocaliZ</div>
          <div class="header-task"><span>当前任务</span><strong id="header-job">未开始</strong></div>
        </div>
        <div class="header-meta">
          <button type="button" id="theme-toggle" class="theme-toggle" title="主题"><i class="ri-computer-line" data-theme-icon></i><span data-theme-label>跟随系统</span></button>
          <span class="pill">本地处理</span>
          <span class="pill provider-badge">多 AI 翻译器</span>
        </div>
      </header>
      <main>
    <section class="config-panel">
      <div class="panel-head">
        <div>
          <h1>生成汉化资源包</h1>
          <div class="panel-copy">上传 JAR，配置翻译器和资源包版本，直接生成资源包、报告和硬编码映射。</div>
        </div>
      </div>
      <form id="translate-form">
        <div class="form-card">
          <h3><i class="ri-archive-2-line"></i>Mod JAR Selection</h3>
        <label class="ghost-file">Mod JAR
          <span class="control"><span class="value" id="jars-display">选择一个或多个 JAR</span><i class="ri-folder-upload-line icon"></i></span>
          <input id="jars" name="jars" type="file" accept=".jar" multiple required>
        </label>
        </div>
        <div class="form-card">
          <h3><i class="ri-translate-2"></i>Language Settings</h3>
        <div class="grid-2">
          <label class="ghost-select" id="source-locale-select">源语言
            <button type="button" class="control" data-select-trigger="source_locale"><span class="value" id="source-locale-display"></span><i class="ri-arrow-down-s-line chevron"></i></button>
            <div class="ghost-menu" id="source-locale-menu" hidden></div>
            <select name="source_locale" id="source_locale" tabindex="-1" aria-hidden="true">
              <option value="en_us" selected>en_us - English (US)</option>
              <option value="en_gb">en_gb - English (UK)</option>
              <option value="zh_cn">zh_cn - 简体中文</option>
              <option value="zh_tw">zh_tw - 繁体中文</option>
              <option value="ja_jp">ja_jp - 日本語</option>
              <option value="ko_kr">ko_kr - 한국어</option>
            </select>
          </label>
          <label class="ghost-select" id="target-locale-select">目标语言
            <button type="button" class="control" data-select-trigger="target_locale"><span class="value" id="target-locale-display"></span><i class="ri-arrow-down-s-line chevron"></i></button>
            <div class="ghost-menu" id="target-locale-menu" hidden></div>
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
          <h3><i class="ri-cpu-line"></i>Translator & Resource Pack</h3>
        <div class="grid-2">
        <label class="ghost-select" id="provider-select">翻译器
            <button type="button" class="control" data-select-trigger="provider"><span class="value" id="provider-display"></span><i class="ri-arrow-down-s-line chevron"></i></button>
            <div class="ghost-menu" id="provider-menu" hidden></div>
            <select name="provider" id="provider" tabindex="-1" aria-hidden="true">
              <option value="glossary">离线术语表（有限）</option>
              <option value="copy">复制原文</option>
              <option value="openai">OpenAI</option>
              <option value="deepseek">DeepSeek</option>
              <option value="moonshot">Moonshot</option>
              <option value="dashscope">通义千问 / 百炼</option>
              <option value="zhipu">智谱 AI</option>
              <option value="siliconflow">硅基流动</option>
              <option value="gemini">Google Gemini (免费)</option>
              <option value="groq">Groq (免费)</option>
              <option value="mimo">小米 MiMo (免费)</option>
              <option value="openai-compatible">自定义 OpenAI 兼容</option>
            </select>
          </label>
          <label class="ghost-select" id="pack-format-select">资源包格式
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
        <label class="ghost-file">术语表 JSON
          <span class="control"><span class="value" id="glossary-display">可选 .json 术语表</span><i class="ri-file-list-3-line icon"></i></span>
          <input name="glossary" type="file" accept=".json">
        </label>
        </div>
        <details class="form-card" data-advanced-panel>
          <summary><span><i class="ri-flashlight-line"></i>高级 API 设置</span></summary>
        <div id="api-box" class="api-box" hidden>
          <div class="api-box-head api-box-title">
            <div>
              <strong>AI 接口配置</strong>
              <span id="provider-badge" class="pill provider-badge">AI</span>
              <a id="api-key-link" href="#" target="_blank" rel="noopener" class="btn-key-apply" hidden>申请 Key <i class="ri-external-link-line"></i></a>
            </div>
            <div id="provider-help" class="field-help">选择翻译器后会自动填入推荐 URL 和模型。</div>
          </div>
          <div class="grid-2">
            <label>模型
              <input name="model" id="model" value="gpt-4o-mini">
            </label>
            <label>API Key
              <input name="api_key" id="api_key" type="password" autocomplete="off" placeholder="可直接粘贴 Key">
            </label>
          </div>
          <label>API URL
            <input name="api_url" id="api_url" value="https://api.openai.com/v1/chat/completions">
            <span class="field-help">可填 base URL，例如 https://aiapi.hhnto.top/v1；也可填完整 /chat/completions 地址。</span>
          </label>
          <label>API Key 环境变量
            <input name="api_key_env" id="api_key_env" value="OPENAI_API_KEY">
            <span class="field-help">API Key 留空时使用该环境变量；直接填写 Key 可避免本地 UI 读不到环境变量导致报错。</span>
          </label>
          <label>并发请求数
            <input name="api_concurrency" id="api_concurrency" type="number" value="2" min="1" placeholder="正在计算推荐并发...">
            <span class="field-help" id="api-concurrency-help">内容很多时可并发翻译多个批次；中转站限流时调低到 1。</span>
          </label>
          <label>断线重试次数
            <input name="api_retries" id="api_retries" type="number" value="5" min="1" max="10">
            <span class="field-help">单个批次遇到断线、超时、429 或 5xx 时自动重试。</span>
          </label>
          <div class="grid-2">
            <label>每次请求条数
              <input name="api_batch_size" id="api_batch_size" type="number" value="40" min="5" max="200">
              <span class="field-help">控制一个 API 请求包含多少条文本；不稳定中转站建议 20。</span>
            </label>
            <label>请求超时秒数
              <input name="api_timeout" id="api_timeout" type="number" value="10" min="1" max="300">
              <span class="field-help">连接或读取响应超过该秒数，会进入下一次重试。</span>
            </label>
          </div>
          <label class="checkline">
            <input name="api_debug_log" type="checkbox">
            <span>记录 API 调试日志</span>
          </label>
          <div class="field-help">会记录请求体、响应头和原始响应到本次任务目录；Authorization/API Key 会被隐藏。</div>
        </div>
        </details>
        <details class="form-card" data-advanced-panel open>
          <summary><span><i class="ri-equalizer-line"></i>输出策略</span></summary>
        <label class="checkline">
          <input name="overwrite_existing" type="checkbox">
          <span>覆盖 JAR 内已有中文</span>
        </label>
        <label class="checkline">
          <input name="skip_translated" type="checkbox">
          <span>跳过已包含目标语言的 JAR</span>
        </label>
        <label class="checkline">
          <input name="ignore_cache" type="checkbox">
          <span>忽略缓存并重新翻译</span>
        </label>
        <label class="checkline">
          <input name="scan_hardcoded" type="checkbox" checked>
          <span>扫描 Ponder / 配置硬编码英文</span>
        </label>
        <button id="submit" type="submit"><i class="ri-rocket-2-line"></i><span>开始生成</span></button>
        <button id="cancel-btn" type="button" hidden><i class="ri-stop-circle-line"></i><span>中断</span></button>
        <div id="status" class="status">等待选择 JAR。</div>
        </details>
      </form>
    </section>

    <section class="results-panel">
      <div class="panel-head">
        <div>
          <h2>结果</h2>
          <div class="panel-copy">处理完成后可直接下载资源包，或切换到硬编码映射继续补全译文。</div>
        </div>
        <span id="job" class="job-pill"></span>
      </div>
      <div id="results" class="results">
        <div class="empty">还没有生成结果。</div>
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
    const jarsInput = document.getElementById('jars');
    const glossaryInput = document.querySelector('input[name="glossary"]');
    const sourceLocaleDisplay = document.getElementById('source-locale-display');
    const targetLocaleDisplay = document.getElementById('target-locale-display');
    const providerDisplay = document.getElementById('provider-display');
    const packFormatDisplay = document.getElementById('pack-format-display');
    const jarsDisplay = document.getElementById('jars-display');
    const glossaryDisplay = document.getElementById('glossary-display');
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
    const themeToggle = document.getElementById('theme-toggle');
    const THEME_STORAGE_KEY = 'mc-mod-i18n-theme';
    const themeModes = ['auto', 'dark', 'light'];
    const themeMeta = {
      auto: { label: '跟随系统', icon: 'ri-computer-line' },
      dark: { label: '暗色', icon: 'ri-moon-clear-line' },
      light: { label: '亮色', icon: 'ri-sun-line' }
    };
    const systemThemeQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const apiBox = document.getElementById('api-box');
    const providerHelp = document.getElementById('provider-help');
    const providerBadge = document.getElementById('provider-badge');
    const apiUrl = document.getElementById('api_url');
    const apiKeyEnv = document.getElementById('api_key_env');
    const model = document.getElementById('model');
    const apiConcurrency = document.getElementById('api_concurrency');
    const apiConcurrencyHelp = document.getElementById('api-concurrency-help');
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
        label: '自定义兼容',
        url: 'https://api.openai.com/v1/chat/completions',
        model: 'gpt-4o-mini',
        env: 'OPENAI_API_KEY',
        help: '适用于任何兼容 OpenAI Chat Completions 的服务。',
        keyUrl: ''
      },
      openai: {
        label: 'OpenAI',
        url: 'https://api.openai.com/v1/chat/completions',
        model: 'gpt-4o-mini',
        env: 'OPENAI_API_KEY',
        help: '使用 OpenAI 官方 Chat Completions 接口。',
        keyUrl: 'https://platform.openai.com/api-keys'
      },
      deepseek: {
        label: 'DeepSeek',
        url: 'https://api.deepseek.com/chat/completions',
        model: 'deepseek-chat',
        env: 'DEEPSEEK_API_KEY',
        help: 'DeepSeek 官方 OpenAI 兼容接口。',
        keyUrl: 'https://platform.deepseek.com/api_keys'
      },
      moonshot: {
        label: 'Moonshot',
        url: 'https://api.moonshot.cn/v1/chat/completions',
        model: 'moonshot-v1-8k',
        env: 'MOONSHOT_API_KEY',
        help: 'Moonshot / Kimi OpenAI 兼容接口。',
        keyUrl: 'https://platform.moonshot.cn/console/api-keys'
      },
      dashscope: {
        label: '通义千问',
        url: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        model: 'qwen-plus',
        env: 'DASHSCOPE_API_KEY',
        help: '阿里云百炼 DashScope 兼容模式接口。',
        keyUrl: 'https://bailian.console.aliyun.com/?apiKey=1'
      },
      zhipu: {
        label: '智谱 AI',
        url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        model: 'glm-4-flash',
        env: 'ZHIPUAI_API_KEY',
        help: '智谱 AI OpenAI 兼容接口。glm-4-flash 完全免费。',
        keyUrl: 'https://open.bigmodel.cn/usercenter/apikeys'
      },
      siliconflow: {
        label: '硅基流动',
        url: 'https://api.siliconflow.cn/v1/chat/completions',
        model: 'deepseek-ai/DeepSeek-V3',
        env: 'SILICONFLOW_API_KEY',
        help: '硅基流动 OpenAI 兼容接口，可按需替换模型。',
        keyUrl: 'https://cloud.siliconflow.cn/account/ak'
      },
      gemini: {
        label: 'Gemini',
        url: 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        model: 'gemini-2.0-flash',
        env: 'GEMINI_API_KEY',
        help: 'Google Gemini OpenAI 兼容接口，免费层每分钟 15 次请求。',
        keyUrl: 'https://aistudio.google.com/apikey'
      },
      groq: {
        label: 'Groq',
        url: 'https://api.groq.com/openai/v1/chat/completions',
        model: 'llama-3.3-70b-versatile',
        env: 'GROQ_API_KEY',
        help: 'Groq OpenAI 兼容接口，免费层每天 14400 次请求，速度极快。',
        keyUrl: 'https://console.groq.com/keys'
      },
      mimo: {
        label: '小米 MiMo',
        url: 'https://token-plan-sgp.xiaomimimo.com/v1/chat/completions',
        model: 'mimo-v2.5-pro',
        env: 'MIMO_API_KEY',
        help: '小米 MiMo OpenAI 兼容接口。',
        keyUrl: 'https://platform.xiaomimimo.com/token-plan'
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
        return localStorage.getItem(THEME_STORAGE_KEY) || document.documentElement.dataset.themeMode || 'auto';
      } catch (error) {
        return document.documentElement.dataset.themeMode || 'auto';
      }
    }

    function resolveThemeMode(mode) {
      if (mode === 'auto') {
        return systemThemeQuery.matches ? 'dark' : 'light';
      }
      return mode === 'dark' ? 'dark' : 'light';
    }

    function applyThemeMode(mode) {
      const resolved = resolveThemeMode(mode);
      document.documentElement.dataset.themeMode = mode;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = resolved;
      if (!themeToggle) {
        return;
      }
      const meta = themeMeta[mode] || themeMeta.auto;
      const icon = themeToggle.querySelector('[data-theme-icon]');
      const label = themeToggle.querySelector('[data-theme-label]');
      if (icon) {
        icon.className = meta.icon;
      }
      if (label) {
        label.textContent = meta.label;
      }
      themeToggle.dataset.themeMode = mode;
      themeToggle.title = `主题：${meta.label}，点击切换`;
    }

    function cycleThemeMode() {
      const current = document.documentElement.dataset.themeMode || 'auto';
      const currentIndex = themeModes.indexOf(current);
      const next = themeModes[(currentIndex + 1) % themeModes.length];
      try {
        localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch (error) {}
      applyThemeMode(next);
    }

    applyThemeMode(storedThemeMode());
    if (themeToggle) {
      themeToggle.addEventListener('click', cycleThemeMode);
    }
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

    function normalizeLocaleValue(value) {
      return String(value || '').trim().toLowerCase().replace(/-/g, '_');
    }

    function isValidLocaleValue(value) {
      return /^[a-z0-9_]{2,24}$/.test(normalizeLocaleValue(value));
    }

    function labelForLocale(value) {
      const normalized = normalizeLocaleValue(value);
      const found = minecraftLocales.find(([code]) => code === normalized);
      return found ? found[1] : '自定义语言';
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

    function buildLocaleSelectMenuOptions(select, name) {
      return `
        <input type="text" class="ghost-menu-input" data-locale-search="${escapeHtml(name)}" placeholder="输入语言代码，如 zh_tw">
        <button type="button" class="ghost-option" data-select-value="${escapeHtml(name)}" data-value="" data-custom-locale="true" data-locale-apply hidden>
          <strong>使用输入值</strong><span>自定义</span>
        </button>
        ${buildSelectMenuOptions(select, name)}
      `;
    }

    function updateLocaleApply(menu, value) {
      const apply = menu.querySelector('[data-locale-apply]');
      if (!apply) {
        return;
      }
      const normalized = normalizeLocaleValue(value);
      apply.hidden = !isValidLocaleValue(normalized);
      apply.dataset.value = normalized;
      const label = apply.querySelector('strong');
      if (label) {
        label.textContent = normalized ? `使用 ${normalized}` : '使用输入值';
      }
    }

    function syncProvider() {
      const preset = providerPresets[provider.value];
      const keyLink = document.getElementById('api-key-link');
      apiBox.hidden = !preset;
      const apiPanel = apiBox.closest('details');
      if (apiPanel && preset) {
        apiPanel.open = true;
      }
      providerDisplay.textContent = provider.options[provider.selectedIndex]?.textContent || '翻译器';
      updateSelectMenuActive(providerMenu, provider.value);
      if (!preset) {
        keyLink.hidden = true;
        return;
      }
      providerBadge.textContent = preset.label;
      providerHelp.textContent = preset.help;
      apiUrl.value = preset.url;
      apiKeyEnv.value = preset.env;
      model.value = preset.model;
      if (preset.keyUrl) {
        keyLink.href = preset.keyUrl;
        keyLink.hidden = false;
      } else {
        keyLink.hidden = true;
      }
    }
    function syncPackFormat() {
      packFormatDisplay.textContent = packFormat.options[packFormat.selectedIndex]?.textContent || '资源包格式';
      updateSelectMenuActive(packFormatMenu, packFormat.value);
    }
    function syncSourceLocale() {
      sourceLocale.value = normalizeLocaleValue(sourceLocale.value || 'en_us');
      ensureSelectOption(sourceLocale, sourceLocale.value, labelForLocale(sourceLocale.value));
      sourceLocaleDisplay.textContent = sourceLocale.options[sourceLocale.selectedIndex]?.textContent || '源语言';
      updateSelectMenuActive(sourceLocaleMenu, sourceLocale.value);
    }
    function syncTargetLocale() {
      targetLocale.value = normalizeLocaleValue(targetLocale.value || 'zh_cn');
      ensureSelectOption(targetLocale, targetLocale.value, labelForLocale(targetLocale.value));
      targetLocaleDisplay.textContent = targetLocale.options[targetLocale.selectedIndex]?.textContent || '目标语言';
      updateSelectMenuActive(targetLocaleMenu, targetLocale.value);
    }
    function syncFiles() {
      jarsDisplay.textContent = jarsInput.files.length ? `${jarsInput.files.length} 个 JAR` : '选择一个或多个 JAR';
      glossaryDisplay.textContent = glossaryInput.files.length ? glossaryInput.files[0].name : '可选 .json 术语表';
    }
    sourceLocale.addEventListener('change', syncSourceLocale);
    targetLocale.addEventListener('change', syncTargetLocale);
    provider.addEventListener('change', syncProvider);
    packFormat.addEventListener('change', syncPackFormat);
    jarsInput.addEventListener('change', syncFiles);
    glossaryInput.addEventListener('change', syncFiles);
    populateLocaleSelect(sourceLocale, 'en_us');
    populateLocaleSelect(targetLocale, 'zh_cn');
    syncSourceLocale();
    syncTargetLocale();
    syncProvider();
    syncPackFormat();
    syncFiles();
    syncConcurrencyHint();
    buildSelectMenus();
    closeAllSelectMenus();

    function syncConcurrencyHint() {
      const cpu = navigator.hardwareConcurrency || 4;
      const recommended = Math.max(1, Math.min(12, Math.ceil(cpu / 2)));
      if (apiConcurrency) {
        apiConcurrency.placeholder = `推荐 ${recommended}，当前 CPU 线程 ${cpu}`;
      }
      if (apiConcurrencyHelp) {
        apiConcurrencyHelp.textContent = `根据当前浏览器可见 CPU 线程 ${cpu}，推荐并发 ${recommended}。服务商限流或 503 较多时调低。`;
      }
    }

    function switchView(view) {
      resultState.activeView = view;
      closeAllSelectMenus();
      document.querySelectorAll('.side-nav button[data-view], .top-tabs button[data-view]').forEach(button => {
        const isActive = button.dataset.view === view;
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-current', isActive ? 'page' : 'false');
      });
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

    function buildSelectMenus() {
      sourceLocaleMenu.dataset.localeName = 'source_locale';
      targetLocaleMenu.dataset.localeName = 'target_locale';
      sourceLocaleMenu.innerHTML = buildLocaleSelectMenuOptions(sourceLocale, 'source_locale');
      targetLocaleMenu.innerHTML = buildLocaleSelectMenuOptions(targetLocale, 'target_locale');
      providerMenu.innerHTML = Array.from(provider.options).map(option => `
        <button type="button" class="ghost-option ${option.selected ? 'active' : ''}" data-select-value="provider" data-value="${escapeHtml(option.value)}">
          <strong>${escapeHtml(option.textContent)}</strong>
        </button>
      `).join('');
      packFormatMenu.innerHTML = Array.from(packFormat.options).map(option => `
        <button type="button" class="ghost-option ${option.selected ? 'active' : ''}" data-select-value="pack_format" data-value="${escapeHtml(option.value)}">
          <strong>${escapeHtml(option.textContent)}</strong>
        </button>
      `).join('');
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
        item.classList.toggle('active', item.dataset.value === value);
      });
    }

    function bindSelectMenu(shell, menu, select, onChange) {
      const trigger = shell.querySelector('[data-select-trigger]');
      const closeMenu = () => {
        shell.classList.remove('open');
        menu.hidden = true;
      };
      const openMenu = () => {
        if (menu.dataset.localeName) {
          menu.innerHTML = buildLocaleSelectMenuOptions(select, menu.dataset.localeName);
        }
        shell.classList.add('open');
        menu.hidden = false;
        const localeInput = menu.querySelector('[data-locale-search]');
        if (localeInput) {
          window.setTimeout(() => localeInput.focus(), 0);
        }
      };
      trigger.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        const isOpen = shell.classList.contains('open');
        document.querySelectorAll('.ghost-select.open').forEach(item => {
          if (item !== shell) {
            item.classList.remove('open');
            const otherMenu = item.querySelector('.ghost-menu');
            if (otherMenu) {
              otherMenu.hidden = true;
            }
          }
        });
        if (isOpen) {
          closeMenu();
        } else {
          openMenu();
        }
      });
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
        menu.querySelectorAll('.ghost-option').forEach(item => {
          item.classList.toggle('active', item.dataset.value === value);
        });
        closeMenu();
      });
      menu.addEventListener('input', (event) => {
        const input = event.target.closest('[data-locale-search]');
        if (!input) {
          return;
        }
        updateLocaleApply(menu, input.value);
      });
      menu.addEventListener('keydown', (event) => {
        const input = event.target.closest('[data-locale-search]');
        if (!input || event.key !== 'Enter') {
          return;
        }
        event.preventDefault();
        const apply = menu.querySelector('[data-locale-apply]');
        if (apply && !apply.hidden) {
          apply.click();
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
      statusBox.textContent = '正在上传并处理...';
      submit.disabled = true;
      startLoading();
      job.textContent = '';
      headerJob.textContent = '上传中';

      try {
        const data = new FormData(form);
        const response = await fetch('/api/translate', { method: 'POST', body: data });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.error || '处理失败');
        }
        activeJobId = payload.job_id;
        job.textContent = activeJobId;
        headerJob.textContent = activeJobId;
        startProgressPolling(activeJobId);
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = error.message;
        results.innerHTML = '<div class="empty">生成失败。</div>';
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
        statusBox.textContent = '已中断。';
        results.innerHTML = '<div class="empty">任务已中断。</div>';
      } catch (e) {
        statusBox.textContent = '中断请求失败：' + e.message;
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
            throw new Error(payload.error || '进度读取失败');
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
            const providerNote = payload.result.provider === 'glossary' ? ' 离线术语表适合快速预览，完整整句汉化请使用 AI 翻译器。' : '';
            const failureNote = payload.result.api_failure_count ? ` 汉化翻译存在异常缺失 ${payload.result.api_failure_count} 条，可在结果区查看并重试。` : '';
            const cacheNote = payload.result.cache_hits ? ` 其中复用了 ${payload.result.cache_hits} 个缓存 JAR。` : '';
            statusBox.className = payload.result.api_failure_count ? 'status error' : 'status success';
            statusBox.textContent = `完成：处理 ${payload.result.processed_jars} 个 JAR，生成 ${payload.result.generated_files} 个语言文件，耗时 ${formatSeconds(payload.result.elapsed_seconds)}。${cacheNote}${providerNote}${failureNote}`;
            switchView('language');
          } else if (payload.status === 'error') {
            stopLoading();
            submit.disabled = false;
            statusBox.className = 'status error';
            statusBox.textContent = payload.error || '处理失败';
          } else if (payload.status === 'cancelled') {
            stopLoading();
            submit.disabled = false;
            statusBox.className = 'status error';
            statusBox.textContent = '已中断。';
            results.innerHTML = '<div class="empty">任务已中断。</div>';
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
      const providerName = provider.options[provider.selectedIndex]?.textContent || '当前翻译器';
      const jarCount = document.getElementById('jars').files.length;
      const concurrency = Math.max(1, Number(data.get('api_concurrency') || '1'));
      const isAi = Boolean(providerPresets[provider.value]);
      const completed = loadingProgress.completed || 0;
      const total = loadingProgress.total || 0;
      const percent = total ? Math.round((completed / total) * 100) : 0;
      const filesCompleted = loadingProgress.filesCompleted || 0;
      const filesTotal = loadingProgress.filesTotal || jarCount || 0;
      const filePercent = filesTotal ? Math.round((filesCompleted / filesTotal) * 100) : 0;
      const cacheHits = loadingProgress.cacheHits || 0;
      const cacheMisses = loadingProgress.cacheMisses || 0;
      const currentFile = loadingProgress.currentFile || '';
      const stageMap = {
        idle: '准备开始',
        queued: '正在上传并解析 JAR',
        processing_file: '正在分析语言文件',
        reusing_cache: '正在复用缓存结果',
        translating: isAi ? '正在分批调用 AI 翻译接口' : '正在生成语言文件',
        retrying: '正在等待重试',
        writing: '正在写入资源包和报告',
        done: '处理完成',
        cancelled: '任务已中断',
        error: '处理失败'
      };
      const stage = stageMap[loadingProgress.stage] || (isAi ? '正在处理翻译任务' : '正在处理任务');
      const progressText = total ? `${completed}/${total}` : '正在统计请求总量';
      const fileText = filesTotal ? `${filesCompleted}/${filesTotal}` : '正在统计文件数量';
      const retryText = loadingProgress.retryAttempt
        ? `当前重试 ${loadingProgress.retryAttempt}/${loadingProgress.retryMax}，原因：${loadingProgress.retryReason || '请求失败'}，等待 ${Number(loadingProgress.retryDelay || 0).toFixed(1)}s，连接/读取超时 ${loadingProgress.requestTimeout}s。`
        : '';
      const statusText = retryText
        || (loadingProgress.stage === 'reusing_cache'
          ? `缓存命中 ${cacheHits}/${filesTotal || jarCount || cacheHits || 0}${currentFile ? `，当前：${currentFile}` : ''}`
          : (loadingProgress.stage === 'processing_file'
            ? (currentFile ? `正在处理：${currentFile}` : '正在分析语言文件')
            : (loadingProgress.stage === 'writing'
              ? '正在写入资源包、报告和缓存'
              : (isAi ? `翻译请求 ${progressText}` : '任务运行中'))));
      const cacheText = filesTotal || cacheHits || cacheMisses
        ? `缓存命中 ${cacheHits} 个，实际翻译 ${Math.max(0, cacheMisses)} 个。`
        : '';
      const detail = isAi
        ? `翻译器：${providerName}，并发上限：${concurrency}，每次请求 ${loadingProgress.batchSize || 40} 条，JAR：${jarCount} 个。${cacheText}耗时 ${elapsed}s。`
        : `翻译器：${providerName}，JAR：${jarCount} 个。${cacheText}耗时 ${elapsed}s。`;
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
            <div class="loading-lane"><span>文件进度</span><div class="loading-lane-bar"><span id="loading-file-progress-bar"></span></div><b id="loading-file-progress-text"></b></div>
            <div class="loading-lane"><span>翻译请求</span><div class="loading-lane-bar"><span id="loading-progress-bar"></span></div><b id="loading-progress-text"></b></div>
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
        metaNode.innerHTML = `${escapeHtml(detail)}<br>文件进度和翻译请求进度分开统计；请求总数会随着解析到新的语言文件逐步增加。`;
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
      headerJob.textContent = payload.job_id || '未开始';
      const languageHeadTitle = resultState.activeTab === 'hardcoded' ? '硬编码映射' : '语言结果';
      const languageHeadDesc = resultState.activeTab === 'hardcoded' ? '选择候选、AI 翻译或导出映射' : '可搜索并导出人工修改';
      results.innerHTML = `
        <div class="actions">
          <button type="button" data-view="language"><i class="ri-folder-open-line"></i><span>工作区</span></button>
          ${payload.pack_url ? `<button type="button" id="download-pack" data-pack-url="${escapeHtml(payload.pack_url)}" data-pack-name="${escapeHtml(payload.pack_filename || defaultPackFilename(payload.pack_url))}"><i class="ri-download-2-line"></i><span>下载资源包</span></button>` : ''}
          <button type="button" data-view="report"><i class="ri-file-list-3-line"></i><span>打开报告</span></button>
          <button type="button" data-view="hardcoded"><i class="ri-file-search-line"></i><span>硬编码报告</span></button>
          <button type="button" data-view="api-log"><i class="ri-bug-line"></i><span>API 调试日志</span></button>
          ${apiFailureCount ? `<button type="button" id="retry-api-failures"><i class="ri-refresh-line"></i><span>重试失败项</span></button>` : ''}
        </div>
        ${apiFailureCount ? `
          <div class="status error">
            汉化翻译存在异常缺失 ${apiFailureCount} 条。可打开 API 调试日志查看报错记录，或手动重试失败项。
          </div>
        ` : ''}
        <div class="summary">
          <section class="summary-group">
            <h3>输出产物</h3>
            <div class="summary-group-grid">
              <div class="metric"><strong>${payload.processed_jars}</strong><span>JAR</span></div>
              <div class="metric"><strong>${payload.generated_files}</strong><span>语言文件</span></div>
              <div class="metric"><strong>${hardcodedCount}</strong><span>硬编码映射</span></div>
            </div>
          </section>
          <section class="summary-group">
            <h3>质量概览</h3>
            <div class="summary-group-grid">
              <div class="metric"><strong>${summary.translated || 0}</strong><span>新增翻译</span></div>
              <div class="metric"><strong>${summary.existing || 0}</strong><span>已有译文</span></div>
              <div class="metric"><strong>${apiFailureCount + (summary.failed || 0) + (summary.incomplete || 0)}</strong><span>需处理</span></div>
              <div class="metric"><strong>${reportEntryCount}</strong><span>报告条目</span></div>
            </div>
          </section>
          <section class="summary-group">
            <h3>性能概览</h3>
            <div class="summary-group-grid">
              <div class="metric"><strong>${formatSeconds(payload.elapsed_seconds)}</strong><span>耗时</span></div>
              <div class="metric"><strong>${payload.cache_hits || 0}</strong><span>缓存命中</span></div>
              <div class="metric"><strong>${payload.cache_misses || 0}</strong><span>实际翻译</span></div>
              <div class="metric"><strong>${candidateCount}</strong><span>候选文本</span></div>
            </div>
          </section>
        </div>
        <div class="system-views">
          <div class="view-shell ${resultState.activeView === 'language' ? 'active' : ''}" data-result-view="language">
            <div class="view-frame">
              <div class="view-head"><strong>${languageHeadTitle}</strong><span class="muted">${languageHeadDesc}</span></div>
              <div class="view-body">
                <div class="tabs">
                  <button type="button" data-result-tab="language" class="${resultState.activeTab === 'language' ? 'active' : ''}"><i class="ri-language-line"></i><span>语言结果</span></button>
                  <button type="button" data-result-tab="hardcoded" class="${resultState.activeTab === 'hardcoded' ? 'active' : ''}" ${hardcodedCount ? '' : 'disabled'}><i class="ri-draft-line"></i><span>硬编码映射</span></button>
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

    function renderLanguageResults(payload) {
      const jarNames = [...new Set((payload.entries || []).map(e => e.jar).filter(Boolean))];
      const activeLabel = resultState.languageJarFilter || '全部';
      const jarMenuOptions = ['<div class="ghost-option' + (activeLabel === '全部' ? ' active' : '') + '" data-select-value="全部" title="全部"><strong>全部</strong></div>']
        .concat(jarNames.map(name => '<div class="ghost-option' + (activeLabel === name ? ' active' : '') + '" data-select-value="' + escapeHtml(name) + '" title="' + escapeHtml(name) + '"><strong>' + escapeHtml(name) + '</strong></div>'))
        .join('');
      return `
        <div class="toolbar">
          <div class="ghost-select jar-filter" id="language-jar-filter-shell">
            <button type="button" class="control" data-select-trigger="jar-filter"><span class="value" id="language-jar-filter-display" title="${escapeHtml(activeLabel)}">${escapeHtml(activeLabel)}</span><i class="ri-arrow-down-s-line chevron"></i></button>
            <div class="ghost-menu" id="language-jar-filter-menu" hidden>${jarMenuOptions}</div>
          </div>
          <input id="language-search" value="${escapeHtml(resultState.languageSearch)}" placeholder="搜索状态、Mod ID、Key、原文或译文">
          <button type="button" id="export-language-edits"><i class="ri-download-2-line"></i><span>导出已修改译文</span></button>
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
          <td><textarea data-language-edit="${escapeHtml(editId)}" placeholder="译文">${escapeHtml(target)}</textarea></td>
        </tr>
      `;
      }).join('');
      return `
        <table>
          <thead><tr><th>状态</th><th>JAR</th><th>Mod ID</th><th>Key</th><th>原文</th><th>译文</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="6">无条目</td></tr>'}</tbody>
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
        if (jarFilter !== '全部' && entry.jar !== jarFilter) {
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
        title.textContent = '下载资源包';
        const desc = document.createElement('span');
        desc.textContent = '输入本次下载的资源包文件名，未填写扩展名时会自动补全 .zip。';
        titleWrap.append(title, desc);
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'pack-name-close';
        close.innerHTML = '<i class="ri-close-line"></i>';
        head.append(titleWrap, close);

        const label = document.createElement('label');
        label.textContent = '资源包名称';
        const input = document.createElement('input');
        input.className = 'ghost-input';
        input.value = defaultName;
        input.placeholder = '例如：my-mod-zh_cn.zip';
        const error = document.createElement('div');
        error.className = 'field-help';
        label.append(input, error);

        const actions = document.createElement('div');
        actions.className = 'pack-name-actions';
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'secondary';
        cancel.textContent = '取消';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.textContent = '下载';
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
            error.textContent = '请输入资源包名称';
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
      const cleaned = String(value || '')
        .trim()
        .replace(/[<>:"/\\|?*\x00-\x1f]+/g, '_')
        .replace(/^[ .]+|[ .]+$/g, '');
      if (!cleaned) {
        return '';
      }
      return cleaned.toLowerCase().endsWith('.zip') ? cleaned : `${cleaned}.zip`;
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
        button.innerHTML = '<i class="ri-loader-4-line"></i><span>正在重试...</span>';
        button.setAttribute('aria-busy', 'true');
      }
      statusBox.className = 'status';
      statusBox.textContent = '正在重试失败的翻译项...';
      try {
        const response = await fetch(`/api/retry/${payload.job_id}`, { method: 'POST' });
        const retryPayload = await response.json();
        if (!response.ok || !retryPayload.ok) {
          throw new Error(retryPayload.error || '重试失败');
        }
        resultState.payload = retryPayload.result;
        apiLogLines = Array.isArray(retryPayload.result.api_debug_log_lines) ? retryPayload.result.api_debug_log_lines : apiLogLines;
        renderResultShell();
        if (retryPayload.remaining) {
          statusBox.className = 'status error';
          statusBox.textContent = `已重试 ${retryPayload.retried} 条，仍有 ${retryPayload.remaining} 条异常。耗时 ${formatSeconds(retryPayload.elapsed_seconds)}。`;
        } else {
          statusBox.className = 'status success';
          statusBox.textContent = `失败项已重试成功，更新 ${retryPayload.retried} 条。耗时 ${formatSeconds(retryPayload.elapsed_seconds)}。`;
        }
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = error.message;
        renderResultShell();
      } finally {
        if (button) {
          button.disabled = false;
          button.classList.remove('is-loading');
          button.innerHTML = '<i class="ri-refresh-line"></i><span>重试失败项</span>';
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
        return `<div class="pager"><span class="pager-info">显示 ${pageInfo.totalItems ? `${pageInfo.start + 1}-${pageInfo.end}` : '0'} / ${pageInfo.totalItems} 条</span></div>`;
      }
      let previous = 0;
      const pageButtons = pagerPages(pageInfo.page, pageInfo.totalPages).map(page => {
        const gap = previous && page - previous > 1 ? '<span class="muted">...</span>' : '';
        previous = page;
        return `${gap}<button type="button" class="${page === pageInfo.page ? 'active' : ''}" data-page-view="${view}" data-page="${page}" ${page === pageInfo.page ? 'disabled' : ''}>${page}</button>`;
      }).join('');
      return `
        <div class="pager">
          <span class="pager-info">显示 ${pageInfo.totalItems ? `${pageInfo.start + 1}-${pageInfo.end}` : '0'} / ${pageInfo.totalItems} 条，每页 ${pageInfo.rows.length || 0} 条</span>
          <div class="pager-controls">
            <button type="button" data-page-view="${view}" data-page="1" ${pageInfo.page === 1 ? 'disabled' : ''}>首页</button>
            <button type="button" data-page-view="${view}" data-page="${Math.max(1, pageInfo.page - 1)}" ${pageInfo.page === 1 ? 'disabled' : ''}>上一页</button>
            ${pageButtons}
            <button type="button" data-page-view="${view}" data-page="${Math.min(pageInfo.totalPages, pageInfo.page + 1)}" ${pageInfo.page === pageInfo.totalPages ? 'disabled' : ''}>下一页</button>
            <button type="button" data-page-view="${view}" data-page="${pageInfo.totalPages}" ${pageInfo.page === pageInfo.totalPages ? 'disabled' : ''}>末页</button>
          </div>
        </div>
      `;
    }

    function renderReportView() {
      const payload = resultState.payload;
      if (!payload) {
        return '<div class="empty">还没有生成报告。</div>';
      }
      return `
        <div class="view-frame">
          <div class="view-head">
            <div><strong>翻译报告</strong><div class="muted">当前任务内嵌报告视图</div></div>
          </div>
          <div class="view-body">
            <div class="toolbar">
              <input id="report-search" value="${escapeHtml(resultState.reportSearch)}" placeholder="搜索状态、JAR、Mod ID、文件、Key、原文或译文">
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
        return '<div class="empty">还没有生成报告。</div>';
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
          <thead><tr><th>状态</th><th>JAR</th><th>Mod ID</th><th>文件</th><th>Key</th><th>原文</th><th>译文</th><th>信息</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="8">无条目</td></tr>'}</tbody>
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
        return '<div class="view-frame"><div class="empty">没有硬编码扫描结果。</div></div>';
      }
      return `
        <div class="view-frame">
          <div class="view-head">
            <div><strong>硬编码报告</strong><div class="muted">扫描候选与映射状态</div></div>
          </div>
          <div class="view-body">
            <div class="toolbar">
              <input id="hardcoded-report-search" value="${escapeHtml(resultState.hardcodedSearch)}" placeholder="搜索分类、风险、JAR、Class 或英文文本">
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
        const haystack = `${entry.category} ${entry.risk} ${entry.jar} ${entry.class} ${entry.source} ${entry.suggestion || ''}`.toLowerCase();
        return haystack.includes(query);
      });
      const pageInfo = paginate(entries, resultState.hardcodedPage, 50);
      resultState.hardcodedPage = pageInfo.page;
      const rows = pageInfo.rows.map(entry => `
        <tr>
          <td>${escapeHtml(entry.category)}</td>
          <td>${escapeHtml(entry.risk)}</td>
          <td>${escapeHtml(entry.jar)}</td>
          <td>${escapeHtml(entry.class)}</td>
          <td>${escapeHtml(entry.source)}</td>
          <td>${escapeHtml(entry.suggestion || entry.translation || '')}</td>
        </tr>
      `).join('');
      return `
        <table>
          <thead><tr><th>分类</th><th>风险</th><th>JAR</th><th>Class</th><th>英文文本</th><th>建议 / 译文</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="6">没有匹配的候选。</td></tr>'}</tbody>
        </table>
        ${renderPager('hardcoded', pageInfo)}
      `;
    }

    function renderApiLogView() {
      if (!apiLogLines.length) {
        const payload = resultState.payload || {};
        const emptyMessage = payload.cache_hits && !payload.cache_misses
          ? '本次结果全部来自缓存，未实际发起 API 请求，所以这里没有调试日志。'
          : '没有 API 调试日志。勾选“记录 API 调试日志”后，实际发起 API 请求时会在这里显示。';
        return `<div class="view-frame"><div class="empty">${emptyMessage}</div></div>`;
      }
      return `
        <div class="view-frame">
          <div class="view-head">
            <div><strong>API 调试日志</strong><div class="muted">请求、响应和重试记录，密钥已脱敏</div></div>
            <div class="toolbar">
              <button type="button" id="export-api-log"><i class="ri-download-2-line"></i><span>导出 JSON</span></button>
            </div>
          </div>
          <div class="view-body">
            <div class="toolbar">
              <input id="api-log-search" value="${escapeHtml(resultState.apiLogSearch)}" placeholder="搜索 provider、状态码、错误、请求或响应内容">
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
          <thead><tr><th>时间</th><th>耗时</th><th>Provider</th><th>状态</th><th>入参</th><th>出参 / 响应</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="6">没有匹配的日志。</td></tr>'}</tbody>
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
      };
      const openMenu = () => {
        shell.classList.add('open');
        menu.hidden = false;
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
          display.textContent = value;
          display.title = value;
        }
        menu.querySelectorAll('.ghost-option').forEach(item => {
          item.classList.toggle('active', item.dataset.selectValue === value);
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
        statusBox.textContent = '没有需要导出的人工修改。';
        return;
      }
      downloadJson('language-edits.json', changed);
      statusBox.className = 'status';
      statusBox.textContent = `已导出 ${total} 条人工修改译文。`;
    }

    function loadHardcodedMap(map) {
      hardcodedState.entries = Object.entries(map).map(([source, meta]) => ({
        source,
        translation: meta.translation || '',
        category: meta.category || 'unknown_literal',
        risk: meta.risk || '',
        class: meta.class || '',
        jar: meta.jar || ''
      }));
      hardcodedState.filter = 'all';
      hardcodedState.search = '';
      hardcodedState.page = 1;
      hardcodedState.selected = new Set();
    }

    function renderHardcodedWorkbench() {
      if (!hardcodedState.entries.length) {
        return '<div class="empty">没有检测到可编辑的硬编码候选。</div>';
      }
      const counts = hardcodedState.entries.reduce((acc, entry) => {
        acc[entry.category] = (acc[entry.category] || 0) + 1;
        return acc;
      }, {});
      const filters = ['all', 'ponder', 'config_comment', 'ui_literal', 'unknown_literal'].map(category => {
        const label = category === 'all' ? `全部 ${hardcodedState.entries.length}` : `${category} ${counts[category] || 0}`;
        return `<button type="button" data-hardcoded-filter="${category}" class="${category === hardcodedState.filter ? 'active' : ''}">${escapeHtml(label)}</button>`;
      }).join('');
      return `
        <div class="hardcoded-workbench">
          <div class="hardcoded-head">
            <div>
              <h3>硬编码映射工作台</h3>
              <div class="muted">填写 translation 后可导出 hardcoded-map.json。</div>
            </div>
            <div class="actions">
              <button type="button" id="import-hardcoded"><i class="ri-upload-2-line"></i><span>导入 map</span></button>
              <button type="button" id="ai-translate-hardcoded"><i class="ri-sparkling-2-line"></i><span>AI 翻译所选</span></button>
              <button type="button" id="export-hardcoded"><i class="ri-download-2-line"></i><span>导出已填写</span></button>
              <input id="hardcoded-map-file" class="hidden-file" type="file" accept=".json,application/json">
            </div>
          </div>
          <div class="toolbar">
            <button type="button" id="select-hardcoded-page"><i class="ri-checkbox-multiple-line"></i><span>全选当前页</span></button>
            <span id="hardcoded-selected-count" class="muted">已选 ${hardcodedState.selected.size} 条</span>
            ${filters}
            <input id="hardcoded-search" value="${escapeHtml(hardcodedState.search)}" placeholder="搜索英文、Class 或 JAR">
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
        const haystack = `${entry.source} ${entry.class} ${entry.jar}`.toLowerCase();
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
            <td class="select-cell"><input type="checkbox" data-hardcoded-select="${index}" ${selected ? 'checked' : ''} aria-label="选择该硬编码候选"></td>
            <td>${escapeHtml(entry.category)}<br><span class="muted">${escapeHtml(entry.risk)}</span></td>
            <td>${escapeHtml(entry.source)}<br><span class="muted">${escapeHtml(entry.class)}</span></td>
            <td>
              <textarea data-hardcoded-index="${index}" class="${errors.length ? 'invalid' : ''}" placeholder="译文">${escapeHtml(entry.translation)}</textarea>
              ${errors.length ? `<div class="hardcoded-errors">${errors.map(escapeHtml).join('<br>')}</div>` : ''}
            </td>
          </tr>
        `;
      }).join('');
      return `
        <table>
          <thead><tr><th class="select-cell">选择</th><th>分类</th><th>英文文本</th><th>译文</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="4">没有匹配的候选。</td></tr>'}</tbody>
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
        const haystack = `${entry.source} ${entry.class} ${entry.jar}`.toLowerCase();
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
        count.textContent = `已选 ${hardcodedState.selected.size} 条`;
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
        statusBox.textContent = '请选择 AI 翻译器后再翻译硬编码映射。';
        return;
      }
      const selectedIndexes = Array.from(hardcodedState.selected).filter(index => hardcodedState.entries[index]);
      if (!selectedIndexes.length) {
        statusBox.className = 'status error';
        statusBox.textContent = '请先选择需要 AI 翻译的硬编码候选。';
        return;
      }
      const button = document.getElementById('ai-translate-hardcoded');
      if (button) {
        button.disabled = true;
        button.classList.add('is-loading');
        button.innerHTML = '<i class="ri-loader-4-line"></i><span>正在翻译...</span>';
        button.setAttribute('aria-busy', 'true');
      }
      statusBox.className = 'status';
      statusBox.textContent = `正在用当前 API 配置翻译 ${selectedIndexes.length} 条硬编码候选...`;
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
          throw new Error(payload.error || '硬编码 AI 翻译失败');
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
          ? `已翻译 ${updated} 条，${payload.failed_count} 条失败，可查看 API 日志。`
          : `已翻译 ${updated} 条硬编码候选。`;
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = error.message;
      } finally {
        if (button) {
          button.disabled = false;
          button.classList.remove('is-loading');
          button.innerHTML = '<i class="ri-sparkling-2-line"></i><span>AI 翻译所选</span>';
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
        statusBox.textContent = `已导入 ${file.name}。`;
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = `导入失败：${error.message}`;
      } finally {
        event.target.value = '';
      }
    }

    function exportHardcodedMap() {
      const filled = hardcodedState.entries.filter(entry => entry.translation.trim());
      const errors = filled.flatMap(entry => validateHardcodedEntry(entry).map(error => `${entry.source}: ${error}`));
      if (errors.length) {
        statusBox.className = 'status error';
        statusBox.textContent = `硬编码映射未通过校验：${errors.slice(0, 3).join('；')}`;
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
      statusBox.textContent = `已导出 ${filled.length} 条硬编码译文。`;
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
          errors.push(`缺少 ${label}: ${missing.join(', ')}`);
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

    const STATUS_LABELS = {
      translated: '已翻译',
      existing: '已有翻译',
      skipped: '已跳过',
      failed: '校验失败',
      api_failed: 'API 失败',
      jar_failed: 'JAR 错误',
    };
    function statusLabel(status) {
      return STATUS_LABELS[status] || status;
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
            if parsed.path.startswith("/download/"):
                self._serve_run_file(parsed.path.removeprefix("/download/"), download=True)
                return
            if parsed.path.startswith("/report/"):
                self._serve_run_file(parsed.path.removeprefix("/report/"), download=False)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
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

        def _handle_translate(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            parts = parse_multipart(self.headers.get("Content-Type", ""), body)
            fields = collect_fields(parts)

            uploaded_jars = [part for part in parts if part.name == "jars" and part.filename and part.data]
            if not uploaded_jars:
                raise ValueError("请至少选择一个 JAR 文件")

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
                raise ValueError("上传内容里没有 .jar 文件")

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
                api_url=fields.get("api_url", "https://api.openai.com/v1/chat/completions"),
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
                    "ignore_cache": args.ignore_cache,
                },
            )

            cancel_evt = Event()
            cancel_events[job_id] = cancel_evt

            Thread(
                target=run_translate_job,
                args=(job_id, jar_paths, out_dir, workdir / ".shared-cache", api_debug_log_path, args, update_job, cancel_evt),
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
                api_url=config.get("api_url", "https://api.openai.com/v1/chat/completions"),
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


def shared_cache_scope_dir(cache_root: Path, args: argparse.Namespace) -> Path:
    digest = compute_translation_config_hash(args)[:16]
    scope_dir = cache_root / digest
    scope_dir.mkdir(parents=True, exist_ok=True)
    return scope_dir


def shared_cache_key(jar_path: Path) -> str:
    name_hash = hashlib.sha1(jar_path.name.encode("utf-8")).hexdigest()[:10]
    return f"{jar_path.stem}-{name_hash}"


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
