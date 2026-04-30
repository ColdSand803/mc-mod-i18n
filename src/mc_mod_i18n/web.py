from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import mimetypes
from pathlib import Path
import re
from secrets import token_hex
from threading import Thread
from typing import Any
from urllib.parse import unquote, urlparse
from zipfile import BadZipFile

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .cli import create_translator, process_jar
from .hardcoded import scan_jar_for_hardcoded
from .pack import OutputLangDocument, write_resource_pack
from .report import ReportEntry, write_hardcoded_map_template, write_hardcoded_report, write_report


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>mc-mod-i18n</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f2;
      --panel: #ffffff;
      --panel-2: #eef3f0;
      --text: #202522;
      --muted: #68736d;
      --line: #d9dfd8;
      --accent: #2f7d57;
      --accent-2: #1f5f82;
      --danger: #b4533c;
      --shadow: 0 8px 24px rgba(36, 48, 42, .08);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
    }
    header {
      height: 58px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfa;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      font-size: 18px;
    }
    .mark {
      width: 28px;
      height: 28px;
      display: grid;
      place-items: center;
      background: var(--accent);
      color: #fff;
      border-radius: 6px;
      font-size: 16px;
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      grid-template-columns: minmax(320px, 420px) 1fr;
      gap: 20px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .panel-head {
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    h1, h2 {
      margin: 0;
      font-size: 16px;
      line-height: 1.3;
    }
    .muted { color: var(--muted); font-size: 13px; }
    form {
      padding: 18px;
      display: grid;
      gap: 16px;
    }
    label {
      display: grid;
      gap: 7px;
      font-size: 13px;
      font-weight: 600;
    }
    input, select {
      width: 100%;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 0 10px;
      font: inherit;
    }
    input[type="file"] {
      height: auto;
      padding: 9px;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .checkline {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 500;
    }
    .checkline input {
      width: 16px;
      height: 16px;
    }
    button {
      border: 0;
      border-radius: 6px;
      height: 40px;
      padding: 0 14px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      background: var(--accent);
      color: #fff;
    }
    button.secondary {
      background: var(--accent-2);
    }
    button:disabled {
      cursor: wait;
      opacity: .65;
    }
    .status {
      min-height: 44px;
      padding: 11px 12px;
      border-radius: 6px;
      background: var(--panel-2);
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .status.error {
      background: #fff0ea;
      color: var(--danger);
      border: 1px solid #f0c6b8;
    }
    .results {
      padding: 18px;
      display: grid;
      gap: 16px;
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
      border-radius: 6px;
      background: var(--accent-2);
      color: #fff;
      text-decoration: none;
      font-weight: 700;
      font-size: 13px;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr));
      gap: 10px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fcfdfb;
    }
    .metric strong {
      display: block;
      font-size: 22px;
      line-height: 1.1;
      margin-bottom: 5px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 9px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
    }
    th {
      background: #f3f6f3;
      color: #3b443f;
      font-size: 12px;
    }
    .empty {
      padding: 36px 18px;
      color: var(--muted);
      text-align: center;
    }
    @media (max-width: 880px) {
      header { padding: 0 16px; }
      main {
        grid-template-columns: 1fr;
        padding: 16px;
      }
      .summary {
        grid-template-columns: repeat(2, minmax(120px, 1fr));
      }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand"><span class="mark">文</span><span>mc-mod-i18n</span></div>
    <div class="muted">本地 UI</div>
  </header>
  <main>
    <section>
      <div class="panel-head">
        <h1>生成汉化资源包</h1>
      </div>
      <form id="translate-form">
        <label>Mod JAR
          <input id="jars" name="jars" type="file" accept=".jar" multiple required>
        </label>
        <div class="grid-2">
          <label>源语言
            <input name="source_locale" value="en_us">
          </label>
          <label>目标语言
            <input name="target_locale" value="zh_cn">
          </label>
        </div>
        <div class="grid-2">
          <label>翻译器
            <select name="provider" id="provider">
              <option value="glossary">术语表</option>
              <option value="copy">复制原文</option>
              <option value="openai-compatible">OpenAI 兼容</option>
            </select>
          </label>
          <label>资源包格式
            <input name="pack_format" type="number" value="15" min="1">
          </label>
        </div>
        <label>术语表 JSON
          <input name="glossary" type="file" accept=".json">
        </label>
        <div class="grid-2 api-row">
          <label>模型
            <input name="model" value="gpt-4o-mini">
          </label>
          <label>API Key 环境变量
            <input name="api_key_env" value="OPENAI_API_KEY">
          </label>
        </div>
        <label class="api-row">API URL
          <input name="api_url" value="https://api.openai.com/v1/chat/completions">
        </label>
        <label class="checkline">
          <input name="overwrite_existing" type="checkbox">
          覆盖 JAR 内已有中文
        </label>
        <label class="checkline">
          <input name="scan_hardcoded" type="checkbox" checked>
          扫描 Ponder / 配置硬编码英文
        </label>
        <button id="submit" type="submit">开始生成</button>
        <div id="status" class="status">等待选择 JAR。</div>
      </form>
    </section>

    <section>
      <div class="panel-head">
        <h2>结果</h2>
        <span id="job" class="muted"></span>
      </div>
      <div id="results" class="results">
        <div class="empty">还没有生成结果。</div>
      </div>
    </section>
  </main>
  <script>
    const form = document.getElementById('translate-form');
    const submit = document.getElementById('submit');
    const statusBox = document.getElementById('status');
    const results = document.getElementById('results');
    const job = document.getElementById('job');
    const provider = document.getElementById('provider');
    const apiRows = [...document.querySelectorAll('.api-row')];

    function syncProvider() {
      const show = provider.value === 'openai-compatible';
      apiRows.forEach(row => row.style.display = show ? '' : 'none');
    }
    provider.addEventListener('change', syncProvider);
    syncProvider();

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      statusBox.className = 'status';
      statusBox.textContent = '正在上传并处理...';
      submit.disabled = true;
      results.innerHTML = '<div class="empty">处理中。</div>';
      job.textContent = '';

      try {
        const data = new FormData(form);
        const response = await fetch('/api/translate', { method: 'POST', body: data });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.error || '处理失败');
        }
        renderResult(payload);
        statusBox.textContent = `完成：处理 ${payload.processed_jars} 个 JAR，生成 ${payload.generated_files} 个语言文件。`;
      } catch (error) {
        statusBox.className = 'status error';
        statusBox.textContent = error.message;
        results.innerHTML = '<div class="empty">生成失败。</div>';
      } finally {
        submit.disabled = false;
      }
    });

    function renderResult(payload) {
      job.textContent = payload.job_id;
      const summary = payload.summary || {};
      const rows = (payload.entries || []).slice(0, 80).map(entry => `
        <tr>
          <td>${escapeHtml(entry.status)}</td>
          <td>${escapeHtml(entry.jar)}</td>
          <td>${escapeHtml(entry.mod_id)}</td>
          <td>${escapeHtml(entry.key)}</td>
          <td>${escapeHtml(entry.target)}</td>
        </tr>
      `).join('');
      results.innerHTML = `
        <div class="actions">
          ${payload.pack_url ? `<a href="${payload.pack_url}">下载资源包</a>` : ''}
          <a href="${payload.report_url}" target="_blank" rel="noreferrer">打开报告</a>
          ${payload.hardcoded_report_url ? `<a href="${payload.hardcoded_report_url}" target="_blank" rel="noreferrer">硬编码报告</a>` : ''}
          ${payload.hardcoded_map_url ? `<a href="${payload.hardcoded_map_url}">硬编码映射模板</a>` : ''}
        </div>
        <div class="summary">
          <div class="metric"><strong>${payload.processed_jars}</strong><span>JAR</span></div>
          <div class="metric"><strong>${payload.generated_files}</strong><span>语言文件</span></div>
          <div class="metric"><strong>${summary.translated || 0}</strong><span>已翻译</span></div>
          <div class="metric"><strong>${payload.hardcoded_count || 0}</strong><span>硬编码候选</span></div>
        </div>
        <table>
          <thead><tr><th>状态</th><th>JAR</th><th>Mod ID</th><th>Key</th><th>译文</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="5">无条目</td></tr>'}</tbody>
        </table>
      `;
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
    class WebHandler(BaseHTTPRequestHandler):
        server_version = "mc-mod-i18n/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            print("%s - %s" % (self.address_string(), format % args))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_bytes(INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
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
            if parsed.path != "/api/translate":
                self.send_error(404)
                return
            try:
                payload = self._handle_translate()
                self._send_json(payload)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)

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

            args = argparse.Namespace(
                source_locale=fields.get("source_locale", "en_us") or "en_us",
                target_locale=fields.get("target_locale", "zh_cn") or "zh_cn",
                provider=fields.get("provider", "glossary") or "glossary",
                glossary=str(glossary_path) if glossary_path else None,
                overwrite_existing=fields.get("overwrite_existing") == "on",
                scan_hardcoded=fields.get("scan_hardcoded") == "on",
                hardcoded_limit=5000,
                pack_format=int(fields.get("pack_format", "15") or "15"),
                api_url=fields.get("api_url", "https://api.openai.com/v1/chat/completions"),
                api_key_env=fields.get("api_key_env", "OPENAI_API_KEY") or "OPENAI_API_KEY",
                model=fields.get("model", "gpt-4o-mini") or "gpt-4o-mini",
            )
            translator = create_translator(args)

            output_documents: list[OutputLangDocument] = []
            report_entries: list[ReportEntry] = []
            hardcoded_entries = []
            for jar_path in jar_paths:
                try:
                    docs, entries = process_jar(jar_path, args, translator)
                    output_documents.extend(docs)
                    report_entries.extend(entries)
                    if args.scan_hardcoded:
                        hardcoded_entries.extend(scan_jar_for_hardcoded(str(jar_path), max_entries=args.hardcoded_limit))
                except (BadZipFile, RuntimeError, ValueError) as exc:
                    report_entries.append(
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

            pack_path = out_dir / "auto-i18n-resourcepack.zip"
            report_path = out_dir / "report.html"
            hardcoded_report_path = out_dir / "hardcoded-report.html"
            hardcoded_map_path = out_dir / "hardcoded-map.template.json"
            if output_documents:
                write_resource_pack(
                    pack_path,
                    output_documents,
                    args.pack_format,
                    f"Auto generated {args.target_locale} translations",
                )
            write_report(report_path, report_entries)
            if args.scan_hardcoded:
                write_hardcoded_report(hardcoded_report_path, hardcoded_entries)
                write_hardcoded_map_template(hardcoded_map_path, hardcoded_entries)

            summary: dict[str, int] = {}
            for entry in report_entries:
                summary[entry.status] = summary.get(entry.status, 0) + 1

            return {
                "ok": True,
                "job_id": job_id,
                "processed_jars": len(jar_paths),
                "generated_files": len(output_documents),
                "hardcoded_count": len(hardcoded_entries),
                "pack_url": f"/download/{job_id}/out/auto-i18n-resourcepack.zip" if output_documents else "",
                "report_url": f"/report/{job_id}/out/report.html",
                "hardcoded_report_url": f"/report/{job_id}/out/hardcoded-report.html" if args.scan_hardcoded else "",
                "hardcoded_map_url": f"/download/{job_id}/out/hardcoded-map.template.json" if args.scan_hardcoded else "",
                "summary": summary,
                "entries": [entry.__dict__ for entry in report_entries[:200]],
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


def sanitize_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or "upload.bin"


def safe_run_path(workdir: Path, relative: str) -> Path:
    decoded = unquote(relative).replace("\\", "/")
    target = (workdir / decoded).resolve()
    if target != workdir and workdir not in target.parents:
        raise ValueError("invalid path")
    return target
