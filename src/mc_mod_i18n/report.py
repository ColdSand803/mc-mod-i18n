from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path

from .hardcoded import HardcodedEntry

HARDCODED_MAP_CATEGORIES = {"ponder", "config_comment", "ui_literal", "unknown_literal"}


@dataclass(frozen=True)
class ReportEntry:
    jar: str
    mod_id: str
    file: str
    key: str
    source: str
    target: str
    status: str
    message: str


def _group_report_entries_by_jar(entries: list[ReportEntry]) -> dict[str, list[ReportEntry]]:
    grouped: dict[str, list[ReportEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.jar or "unknown", []).append(entry)
    return grouped


def _status_counts(entries: list[ReportEntry]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for entry in entries:
        totals[entry.status] = totals.get(entry.status, 0) + 1
    return totals


def _render_status_summary(totals: dict[str, int]) -> str:
    return "".join(f"<li>{escape(status)}: {count}</li>" for status, count in sorted(totals.items()))


def _json_for_html(data: object) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _build_error_aggregation(entries: list[ReportEntry]) -> str:
    groups: dict[str, list[ReportEntry]] = {}
    for entry in entries:
        if entry.status in ("failed", "api_failed", "jar_failed", "incomplete"):
            groups.setdefault(entry.status, []).append(entry)
    if not groups:
        return ""

    parts: list[str] = []
    for status in sorted(groups.keys()):
        group = groups[status]
        parts.append(
            f'<details class="error-group">'
            f'<summary class="error-summary">{escape(status)} ({len(group)} entries)</summary>'
            f'<table class="error-table">'
            f'<thead><tr><th>JAR</th><th>Mod ID</th><th>Key</th><th>Source</th><th>Message</th></tr></thead>'
            f'<tbody>'
        )
        for entry in group:
            parts.append(
                "<tr>"
                f"<td>{escape(entry.jar)}</td>"
                f"<td>{escape(entry.mod_id)}</td>"
                f"<td>{escape(entry.key)}</td>"
                f"<td>{escape(entry.source[:80])}</td>"
                f"<td>{escape(entry.message)}</td>"
                "</tr>"
            )
        parts.append("</tbody></table></details>")
    return "\n".join(parts)


def write_report(path: Path, entries: list[ReportEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    totals = _status_counts(entries)
    summary = _render_status_summary(totals)
    jar_groups = _group_report_entries_by_jar(entries)
    jar_sections: list[str] = []
    jar_payload: dict[str, list[dict[str, str]]] = {}
    for index, jar_name in enumerate(sorted(jar_groups.keys()), start=1):
        jar_entries = jar_groups[jar_name]
        jar_totals = _status_counts(jar_entries)
        jar_status = " / ".join(f"{status}: {count}" for status, count in sorted(jar_totals.items()))
        section_id = f"jar-report-{index}"
        jar_sections.append(
            f'<details class="jar-section" data-report-section="{section_id}">'
            f'<summary><span class="jar-name">{escape(jar_name)}</span><span class="jar-meta">{len(jar_entries)} 条</span><span class="jar-status">{escape(jar_status)}</span></summary>'
            f'<div class="jar-body" id="{section_id}"><div class="jar-placeholder">展开后加载详细条目...</div></div>'
            f"</details>"
        )
        jar_payload[section_id] = [
            {
                "status": entry.status,
                "jar": entry.jar,
                "mod_id": entry.mod_id,
                "key": entry.key,
                "source": entry.source,
                "target": entry.target,
                "message": entry.message,
            }
            for entry in jar_entries
        ]

    error_agg_html = _build_error_aggregation(entries)
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>mc-mod-i18n report</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #222222;
      --muted: #64748b;
      --line: #dddddd;
      --line-strong: #e1e5ea;
      --thead: #f3f5f7;
      --alt: #fafafa;
      --danger: #ba1a1a;
      --danger-bg: #fff6f6;
      --name: #10243e;
      --meta: #4a637d;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #020617;
        --panel: #0b1220;
        --text: #e5eefb;
        --muted: #8da0ba;
        --line: #22314a;
        --line-strong: #22314a;
        --thead: #101a2d;
        --alt: #0e1626;
        --danger: #fca5a5;
        --danger-bg: #1a0f15;
        --name: #dbeafe;
        --meta: #a5b8d1;
      }}
    }}
    body {{ font-family: Segoe UI, Microsoft YaHei, sans-serif; margin: 24px; color: var(--text); background: var(--bg); }}
    h1, h2 {{ margin-bottom: 12px; }}
    ul {{ margin-top: 0; }}
    .summary-panel {{ padding: 16px 18px; border: 1px solid var(--line-strong); border-radius: 12px; background: var(--panel); margin-bottom: 18px; }}
    .report-stack {{ display: grid; gap: 12px; }}
    .jar-section {{ border: 1px solid var(--line-strong); border-radius: 12px; background: var(--panel); overflow: hidden; }}
    .jar-section summary {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 14px 16px; cursor: pointer; list-style: none; }}
    .jar-section summary::-webkit-details-marker {{ display: none; }}
    .jar-name {{ font-weight: 700; color: var(--name); }}
    .jar-meta {{ color: var(--meta); font-weight: 600; }}
    .jar-status {{ color: var(--muted); font-size: 13px; }}
    .jar-body {{ padding: 0 16px 16px; }}
    .jar-placeholder {{ padding: 10px 0 2px; color: var(--muted); }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
    th, td {{ border: 1px solid var(--line); padding: 8px; vertical-align: top; word-break: break-word; }}
    th {{ background: var(--thead); text-align: left; }}
    tr:nth-child(even) {{ background: var(--alt); }}
    details summary {{ font-size: 1.05em; }}
    .error-group {{ margin: 8px 0; }}
    .error-summary {{ cursor: pointer; font-weight: 600; color: var(--danger); }}
    .error-table {{ margin: 4px 0 12px; }}
  </style>
</head>
<body>
  <h1>mc-mod-i18n report</h1>
  <section class="summary-panel">
    <h2>摘要</h2>
    <ul>{summary}</ul>
    <div>JAR 数量: {len(jar_groups)}，总条目: {len(entries)}</div>
  </section>
  {error_agg_html}
  <h2>按 JAR 查看</h2>
  <section class="report-stack">
    {"".join(jar_sections)}
  </section>
  <script id="jar-report-data" type="application/json">{_json_for_html(jar_payload)}</script>
  <script>
    const jarReportData = JSON.parse(document.getElementById('jar-report-data').textContent || '{{}}');
    const renderReportRows = (rows) => rows.map((entry) => `
      <tr>
        <td>${{escapeHtml(entry.status)}}</td>
        <td>${{escapeHtml(entry.jar)}}</td>
        <td>${{escapeHtml(entry.mod_id)}}</td>
        <td>${{escapeHtml(entry.key)}}</td>
        <td>${{escapeHtml(entry.source)}}</td>
        <td>${{escapeHtml(entry.target)}}</td>
        <td>${{escapeHtml(entry.message)}}</td>
      </tr>
    `).join('');
    const escapeHtml = (value) => String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
    document.querySelectorAll('[data-report-section]').forEach((section) => {{
      section.addEventListener('toggle', () => {{
        if (!section.open || section.dataset.rendered === '1') {{
          return;
        }}
        const targetId = section.dataset.reportSection;
        const target = document.getElementById(targetId);
        const rows = jarReportData[targetId] || [];
        target.innerHTML = `
          <table>
            <thead>
              <tr>
                <th>状态</th>
                <th>JAR</th>
                <th>Mod ID</th>
                <th>Key</th>
                <th>原文</th>
                <th>译文</th>
                <th>信息</th>
              </tr>
            </thead>
            <tbody>${{renderReportRows(rows) || '<tr><td colspan="7">无条目</td></tr>'}}</tbody>
          </table>
        `;
        section.dataset.rendered = '1';
      }});
    }});
  </script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def write_hardcoded_report(path: Path, entries: list[HardcodedEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    totals: dict[str, int] = {}
    risks: dict[str, int] = {}
    for entry in entries:
        totals[entry.category] = totals.get(entry.category, 0) + 1
        risks[entry.risk] = risks.get(entry.risk, 0) + 1

    category_summary = "".join(f"<li>{escape(status)}: {count}</li>" for status, count in sorted(totals.items()))
    risk_summary = "".join(f"<li>{escape(status)}: {count}</li>" for status, count in sorted(risks.items()))
    filter_buttons = "\n".join(
        f'<button type="button" data-category="{escape(category)}">{escape(category)}</button>'
        for category in ("ponder", "config_comment", "ui_literal", "unknown_literal")
    )
    rows = "\n".join(
        "<tr "
        f'data-category="{escape(entry.category)}" '
        f'data-text="{escape((entry.text + " " + entry.class_path + " " + entry.jar).lower())}">'
        f"<td>{escape(entry.category)}</td>"
        f"<td>{escape(entry.risk)}</td>"
        f"<td>{escape(entry.jar)}</td>"
        f"<td>{escape(entry.class_path)}</td>"
        f"<td>{escape(entry.text)}</td>"
        f"<td>{escape(entry.suggestion)}</td>"
        "</tr>"
        for entry in entries
    )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>hardcoded text report</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #ffffff;
      --panel: #ffffff;
      --text: #222222;
      --muted: #64748b;
      --line: #dddddd;
      --line-strong: #ccd3d8;
      --thead: #f3f5f7;
      --alt: #fafafa;
      --field: #ffffff;
      --accent: #2f7d57;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #020617;
        --panel: #0b1220;
        --text: #e5eefb;
        --muted: #8da0ba;
        --line: #22314a;
        --line-strong: #22314a;
        --thead: #101a2d;
        --alt: #0e1626;
        --field: #0f172a;
        --accent: #22c55e;
      }}
    }}
    body {{ font-family: Segoe UI, Microsoft YaHei, sans-serif; margin: 24px; color: var(--text); background: var(--bg); }}
    .summary {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 16px; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 18px; }}
    button {{ border: 1px solid var(--line-strong); border-radius: 6px; background: var(--field); color: var(--text); padding: 7px 10px; cursor: pointer; }}
    button.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
    input {{ min-width: 260px; flex: 1; border: 1px solid var(--line-strong); border-radius: 6px; padding: 8px; font: inherit; background: var(--field); color: var(--text); }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; margin-top: 18px; }}
    th, td {{ border: 1px solid var(--line); padding: 8px; vertical-align: top; word-break: break-word; }}
    th {{ background: var(--thead); text-align: left; }}
    tr:nth-child(even) {{ background: var(--alt); }}
  </style>
</head>
<body>
  <h1>硬编码英文扫描报告</h1>
  <div class="summary">
    <section>
      <h2>分类</h2>
      <ul>{category_summary}</ul>
    </section>
    <section>
      <h2>风险</h2>
      <ul>{risk_summary}</ul>
    </section>
  </div>
  <div class="toolbar">
    <button type="button" class="active" data-category="all">全部</button>
    {filter_buttons}
    <input id="search" placeholder="搜索英文、Class 或 JAR">
  </div>
  <table>
    <thead>
      <tr>
        <th>分类</th>
        <th>风险</th>
        <th>JAR</th>
        <th>Class</th>
        <th>英文文本</th>
        <th>建议</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  <script>
    const buttons = [...document.querySelectorAll('[data-category]')];
    const search = document.getElementById('search');
    const rows = [...document.querySelectorAll('tbody tr')];
    let category = 'all';

    function applyFilter() {{
      const query = search.value.trim().toLowerCase();
      rows.forEach(row => {{
        const categoryMatched = category === 'all' || row.dataset.category === category;
        const textMatched = !query || row.dataset.text.includes(query);
        row.style.display = categoryMatched && textMatched ? '' : 'none';
      }});
    }}

    buttons.forEach(button => {{
      button.addEventListener('click', () => {{
        category = button.dataset.category;
        buttons.forEach(item => item.classList.toggle('active', item === button));
        applyFilter();
      }});
    }});
    search.addEventListener('input', applyFilter);
  </script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def build_hardcoded_map_template(entries: list[HardcodedEntry]) -> dict[str, dict[str, str]]:
    template: dict[str, dict[str, str]] = {}
    for entry in entries:
        if entry.category not in HARDCODED_MAP_CATEGORIES:
            continue
        template.setdefault(
            entry.text,
            {
                "translation": "",
                "category": entry.category,
                "risk": entry.risk,
                "class": entry.class_path,
                "jar": entry.jar,
            },
        )
    return template


def write_hardcoded_map_template(path: Path, entries: list[HardcodedEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    template = build_hardcoded_map_template(entries)
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
