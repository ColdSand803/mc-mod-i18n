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


def write_report(path: Path, entries: list[ReportEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    totals: dict[str, int] = {}
    for entry in entries:
        totals[entry.status] = totals.get(entry.status, 0) + 1

    summary = "".join(f"<li>{escape(status)}: {count}</li>" for status, count in sorted(totals.items()))
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(entry.status)}</td>"
        f"<td>{escape(entry.jar)}</td>"
        f"<td>{escape(entry.mod_id)}</td>"
        f"<td>{escape(entry.key)}</td>"
        f"<td>{escape(entry.source)}</td>"
        f"<td>{escape(entry.target)}</td>"
        f"<td>{escape(entry.message)}</td>"
        "</tr>"
        for entry in entries
    )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>mc-mod-i18n report</title>
  <style>
    body {{ font-family: Segoe UI, Microsoft YaHei, sans-serif; margin: 24px; color: #222; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; word-break: break-word; }}
    th {{ background: #f3f5f7; text-align: left; }}
    tr:nth-child(even) {{ background: #fafafa; }}
  </style>
</head>
<body>
  <h1>mc-mod-i18n report</h1>
  <ul>{summary}</ul>
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
    <tbody>
      {rows}
    </tbody>
  </table>
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
    body {{ font-family: Segoe UI, Microsoft YaHei, sans-serif; margin: 24px; color: #222; }}
    .summary {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 16px; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 18px; }}
    button {{ border: 1px solid #ccd3d8; border-radius: 6px; background: #fff; padding: 7px 10px; cursor: pointer; }}
    button.active {{ background: #2f7d57; border-color: #2f7d57; color: #fff; }}
    input {{ min-width: 260px; flex: 1; border: 1px solid #ccd3d8; border-radius: 6px; padding: 8px; font: inherit; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; margin-top: 18px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; word-break: break-word; }}
    th {{ background: #f3f5f7; text-align: left; }}
    tr:nth-child(even) {{ background: #fafafa; }}
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
