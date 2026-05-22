from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DB_FILENAME = "mc-mod-i18n.sqlite3"


SCHEMA_COMMENTS: dict[str, dict[str, str]] = {
    "schema_migrations": {
        "key": "迁移或旧文件导入任务的唯一标识。",
        "applied_at": "迁移或导入完成的 UTC 时间。",
    },
    "schema_comments": {
        "table_name": "被注释的表名。",
        "column_name": "被注释的字段名。",
        "comment": "字段用途说明。",
        "updated_at": "注释写入或更新的 UTC 时间。",
    },
    "translation_memory": {
        "scope": "翻译配置 scope 哈希，用于隔离不同语言、模型和输出策略。",
        "source": "原文文本。",
        "target": "译文文本。",
        "updated_at": "该记忆条目最后写入或更新的 UTC 时间。",
    },
    "app_settings": {
        "key": "设置项唯一键。",
        "value_json": "设置值 JSON 文本。",
        "updated_at": "设置最后写入或更新的 UTC 时间。",
    },
    "job_history": {
        "job_id": "任务唯一 ID。",
        "created_at": "任务创建时间。",
        "updated_at": "任务历史记录更新时间。",
        "status": "任务状态，例如 done、error 或 cancelled。",
        "input_kind": "输入类型，例如 jar、json 或 ftbquests。",
        "primary_input": "任务主要输入文件或展示名称。",
        "target_locale": "目标 Minecraft 语言代码。",
        "provider": "任务使用的翻译器 Provider。",
        "model": "任务使用的模型名称。",
        "processed_sources": "已处理的输入源数量。",
        "generated_files": "生成的输出文件数量。",
        "success_count": "成功或复用的翻译条目数量。",
        "failure_count": "失败、不完整或 JAR 错误条目数量。",
        "summary_json": "任务报告 summary 字段的 JSON 文本。",
        "downloads_json": "任务可下载资源 URL 映射的 JSON 文本。",
        "download_files_json": "任务下载资源相对文件路径映射的 JSON 文本。",
        "error": "任务失败时的错误消息。",
    },
    "job_input_files": {
        "job_id": "所属任务 ID。",
        "position": "输入文件在任务中的顺序，从 1 开始。",
        "path": "输入文件路径或显示名称。",
    },
    "glossary_terms": {
        "source": "术语原文。",
        "target": "术语译文。",
        "updated_at": "术语最后写入或更新的 UTC 时间。",
    },
    "config_presets": {
        "slug": "预设唯一标识，由名称规范化生成。",
        "name": "预设显示名称。",
        "config_json": "预设配置 JSON 文本。",
        "created_at": "预设创建时间。",
        "updated_at": "预设最后更新时间。",
    },
}


def app_db_path(root: Path) -> Path:
    return root / DB_FILENAME


@contextmanager
def connect_app_db(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        initialize_app_db(connection)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_app_db(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          key TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_comments (
          table_name TEXT NOT NULL,
          column_name TEXT NOT NULL,
          comment TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (table_name, column_name)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS translation_memory (
          scope TEXT NOT NULL,
          source TEXT NOT NULL,
          target TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (scope, source)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_translation_memory_updated_at
        ON translation_memory(updated_at)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS job_history (
          job_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          status TEXT NOT NULL,
          input_kind TEXT NOT NULL,
          primary_input TEXT NOT NULL,
          target_locale TEXT NOT NULL,
          provider TEXT NOT NULL,
          model TEXT NOT NULL,
          processed_sources INTEGER NOT NULL DEFAULT 0,
          generated_files INTEGER NOT NULL DEFAULT 0,
          success_count INTEGER NOT NULL DEFAULT 0,
          failure_count INTEGER NOT NULL DEFAULT 0,
          summary_json TEXT NOT NULL DEFAULT '{}',
          downloads_json TEXT NOT NULL DEFAULT '{}',
          download_files_json TEXT NOT NULL DEFAULT '{}',
          error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_job_history_created_at ON job_history(created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_job_history_status ON job_history(status)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_job_history_input_kind ON job_history(input_kind)")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS job_input_files (
          job_id TEXT NOT NULL,
          position INTEGER NOT NULL,
          path TEXT NOT NULL,
          PRIMARY KEY (job_id, position),
          FOREIGN KEY (job_id) REFERENCES job_history(job_id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS glossary_terms (
          source TEXT PRIMARY KEY,
          target TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS config_presets (
          slug TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          config_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    write_schema_comments(connection)


def write_schema_comments(connection: sqlite3.Connection) -> None:
    from .web_utils import utc_timestamp

    now = utc_timestamp()
    rows = [
        (table_name, column_name, comment, now)
        for table_name, columns in SCHEMA_COMMENTS.items()
        for column_name, comment in columns.items()
    ]
    connection.executemany(
        """
        INSERT INTO schema_comments(table_name, column_name, comment, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(table_name, column_name) DO UPDATE SET
          comment = excluded.comment,
          updated_at = excluded.updated_at
        """,
        rows,
    )


def export_translation_memory_to_jsonl(db_path: Path, output_path: Path) -> int:
    """将 translation_memory 表导出为 JSONL 文件，返回导出行数。"""
    with connect_app_db(db_path) as connection:
        rows = connection.execute(
            "SELECT scope, source, target, updated_at FROM translation_memory ORDER BY scope, source"
        ).fetchall()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({"scope": row["scope"], "source": row["source"], "target": row["target"], "updated_at": row["updated_at"]}, ensure_ascii=False) + "\n")
    return len(rows)


def import_translation_memory_from_jsonl(db_path: Path, jsonl_path: Path) -> int:
    """从 JSONL 文件导入翻译记忆到 SQLite，返回导入行数（upsert）。"""
    if not jsonl_path.is_file():
        raise ValueError(f"导入文件不存在: {jsonl_path}")
    count = 0
    with connect_app_db(db_path) as connection:
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                scope = str(row.get("scope", ""))
                source = str(row.get("source", ""))
                target = str(row.get("target", ""))
                updated_at = str(row.get("updated_at", ""))
                if not scope or not source or not target:
                    continue
                if not updated_at:
                    from .web_utils import utc_timestamp
                    updated_at = utc_timestamp()
                connection.execute(
                    "INSERT INTO translation_memory(scope, source, target, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(scope, source) DO UPDATE SET target = excluded.target, updated_at = excluded.updated_at",
                    (scope, source, target, updated_at),
                )
                count += 1
    return count


def export_job_history_to_jsonl(db_path: Path, output_path: Path) -> int:
    """将 job_history 表导出为 JSONL 文件，返回导出行数。"""
    with connect_app_db(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM job_history ORDER BY created_at DESC"
        ).fetchall()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            record = dict(row)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(rows)


def export_glossary_to_json(db_path: Path, output_path: Path) -> int:
    """将 glossary_terms 表导出为 JSON 文件，返回导出行数。"""
    with connect_app_db(db_path) as connection:
        rows = connection.execute(
            "SELECT source, target FROM glossary_terms ORDER BY source"
        ).fetchall()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    glossary = {row["source"]: row["target"] for row in rows}
    output_path.write_text(json.dumps(glossary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(glossary)
