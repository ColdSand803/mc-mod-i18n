# SQLite 改造补充完善方案

基于 `sqlite改造.md` 的 5 阶段计划，前 4 阶段已全部完成。本文档梳理需要补充完善的遗留项。

---

## 一、测试补全（P1）

`test_app_db.py` 当前只验证了 `schema_comments` 一致性，缺少基础设施层的核心测试。

### 1.1 空库首次启动不报错

**目的**：验证全新环境（无旧 JSON/JSONL 文件）下 `connect_app_db` + `initialize_app_db` 能正常建表。

**测试要点**：
- 传入一个不存在目录下的新路径
- 确认 7 张表全部创建成功
- 确认 `schema_migrations` 表为空
- 确认 `schema_comments` 行数与 `SCHEMA_COMMENTS` 常量一致

### 1.2 重复初始化幂等性

**目的**：验证多次调用 `initialize_app_db` 不会报错或丢失数据。

**测试要点**：
- 打开同一个 db_path 两次
- 第一次写入数据（如 `translation_memory`）
- 第二次打开后确认数据仍在
- 确认 `CREATE TABLE IF NOT EXISTS` 和 `CREATE INDEX IF NOT EXISTS` 不会冲突

### 1.3 `connect_app_db` 自动建目录

**目的**：验证 `path.parent.mkdir(parents=True, exist_ok=True)` 在深层嵌套路径下生效。

**测试要点**：
- 传入 `tmp/a/b/c/mc-mod-i18n.sqlite3`
- 确认目录自动创建
- 确认数据库文件正常生成

### 1.4 `clear_job_history` 单独测试

**目的**：当前测试只覆盖了删除和裁剪，`clear_job_history` 未被单独断言。

**测试要点**：
- 写入多条记录
- 调用 `clear_job_history`
- 确认返回 `{"ok": True, "before": N, "after": 0, "removed": N}`
- 确认 `read_job_history` 返回空列表

### 1.5 并发写入安全（可选）

**目的**：验证 WAL + `busy_timeout=5000` 在多线程同时写入时不丢数据。

**测试要点**：
- 用 `threading.Thread` 启动 2-3 个线程同时 `put_many`
- 确认所有数据最终写入且无异常
- 此测试依赖 SQLite 的线程安全性，主要用于验证配置正确

### 1.6 Windows 中文路径（可选）

**目的**：验证中文目录名和长路径在 Windows 下不报错。

**测试要点**：
- 使用包含中文字符的临时目录路径
- 确认 `connect_app_db` 正常工作

---

## 二、代码健壮性改进（P2）

### 2.1 `delete_job_history_records` 的 IN 子句写法

**现状**（`job_history.py:410-412`）：

```python
f"SELECT job_id FROM job_history WHERE job_id IN ({','.join('?' for _ in normalized_ids)})"
```

虽然输入经过 `sanitize_job_id` 过滤且使用参数化绑定，实际无注入风险，但 f-string 拼接 SQL 的模式不够直观，review 时容易引起疑虑。

**建议改为**：

```python
placeholders = ",".join("?" for _ in normalized_ids)
query = f"SELECT job_id FROM job_history WHERE job_id IN ({placeholders})"
connection.execute(query, tuple(normalized_ids))
```

或直接用 `executemany` + 单条 DELETE（当前代码第 416 行已经是这种写法），将 SELECT 查询也统一风格。

**优先级**：低，功能正确，仅改善可读性。

### 2.2 `compact_translation_memory` 加注释

**现状**（`web_state.py:447-449`）：

```python
def compact_translation_memory(cache_root: Path) -> int:
    ensure_translation_memory_migrated(cache_root)
    return 0
```

**建议**：加一行注释说明 SQLite 模式下 compact 无意义（`ON CONFLICT DO UPDATE` 保证唯一性，无重复记录需要清理）。

```python
def compact_translation_memory(cache_root: Path) -> int:
    # SQLite 模式下 upsert 天然去重，无需 compact
    ensure_translation_memory_migrated(cache_root)
    return 0
```

---

## 三、可选增强（P3）

### 3.1 SQLite → JSONL 导出函数

**现状**：设计文档提到"可提供导出命令或内部函数，将 SQLite 数据导出回 JSON/JSONL"，目前未实现。

**建议实现**：

```python
def export_translation_memory_to_jsonl(db_path: Path, output_path: Path) -> int:
    """将 translation_memory 表导出为 JSONL 文件，返回导出行数。"""

def export_job_history_to_jsonl(db_path: Path, output_path: Path) -> int:
    """将 job_history 表导出为 JSONL 文件，返回导出行数。"""

def export_glossary_to_json(db_path: Path, output_path: Path) -> int:
    """将 glossary_terms 表导出为 JSON 文件，返回导出行数。"""
```

放在 `app_db.py` 中，供命令行或调试使用。

**优先级**：低。旧文件保留策略已覆盖手动回滚，此功能仅在需要跨工具迁移时有用。

### 3.2 JSONL 模式标记 deprecated

**现状**：`TranslationMemory` 类在 `core.py` 中支持双模式——路径后缀为 `.sqlite3` 走 SQLite，否则走 JSONL。所有 web 层调用方已切到 `.sqlite3` 路径。

**建议**：在 JSONL 代码路径的 `__init__` 中加 `warnings.warn("JSONL mode is deprecated", DeprecationWarning)`，提醒外部直接调用 `TranslationMemory` 的用户迁移。

**前提**：确认没有其他调用方仍在传 JSONL 路径。

---

## 四、不在范围内

| 项目 | 原因 |
|------|------|
| 配置预设迁移 | `sqlite改造.md` 阶段 5，计划暂缓 |
| 系统设置 `system.json` | 品牌配置，数据量极小，不值得迁移 |
| 大文件制品（zip/报告/日志） | 设计文档明确排除 |

---

## 五、实施建议

| 顺序 | 项 | 工作量 | 改动文件 |
|------|------|--------|----------|
| 1 | 测试补全 1.1 ~ 1.4 | 小 | `tests/test_app_db.py` |
| 2 | `compact_translation_memory` 加注释 | 极小 | `web_state.py` |
| 3 | `delete_job_history_records` 写法优化 | 小 | `job_history.py` |
| 4 | 并发/中文路径测试（可选） | 中 | `tests/test_app_db.py` |
| 5 | 导出函数（可选） | 中 | `app_db.py` |
| 6 | JSONL deprecated 标记（可选） | 小 | `core.py` |

建议优先完成 1~3，其余按需安排。
