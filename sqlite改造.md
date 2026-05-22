# SQLite 改造评估与实施方案

## 背景

当前项目的长期状态数据主要通过 JSON/JSONL 文件保存：

- 任务历史：`jobs/index.jsonl` 和 `jobs/settings.json`
- 用户术语表：`glossaries/user-glossary.json`
- 翻译记忆：`cache/translation-memory.jsonl`
- 配置预设：`presets/*.json`

这些文件结构简单，适合早期实现。但随着任务历史、翻译记忆和术语表规模增长，JSON/JSONL 会逐渐暴露出全量读写、重复记录、统计和筛选成本高的问题。SQLite 是 Python 标准库内置能力，不需要额外依赖，适合作为本地桌面/Web 工具的结构化状态存储。

## 改造目标

1. 提升翻译记忆、任务历史等长期数据在大规模场景下的读写和管理性能。
2. 减少 JSONL 追加写导致的重复记录和定期 compact 成本。
3. 保持现有 API 和前端契约尽量不变，降低改造风险。
4. 保留资源包、报告、日志、失败项 JSON 等文件制品，不把大文件塞进数据库。
5. 支持从旧 JSON/JSONL 数据自动迁移，避免用户已有数据丢失。

## 建议数据库位置

推荐使用一个统一数据库文件：

```text
<workdir>/data/mc-mod-i18n.sqlite3
```

也可以放在根目录：

```text
<workdir>/app.db
```

推荐 `data/mc-mod-i18n.sqlite3`，语义更清晰，也方便未来把其他本地状态集中管理。

## 适合迁移的范围

### 第一优先级：翻译记忆

当前实现位于 `src/mc_mod_i18n/core.py` 的 `TranslationMemory`，使用 `translation-memory.jsonl` 追加写入。

问题：

- 首次加载需要读取整个 JSONL 文件。
- 同一个 `(scope, source)` 可以重复出现，需要 compact。
- 按 scope 统计、清理、预览都需要遍历完整文件。

SQLite 收益：

- 用唯一索引保证 `(scope, source)` 唯一。
- `get()` 可以按索引查询。
- `put_many()` 可以批量 upsert。
- 清理指定 scope 和统计 scope 数量更直接。

### 第二优先级：任务历史

当前实现位于 `src/mc_mod_i18n/job_history.py`，使用 `jobs/index.jsonl`。

问题：

- 追加、删除、裁剪都会读写整个历史文件。
- 历史数量变大后，筛选、分页、删除会变慢。
- JSONL 中坏行只能跳过，数据结构缺少约束。

SQLite 收益：

- 按 `created_at`、`status`、`input_kind` 建索引。
- 删除指定 job、裁剪保留数量不需要重写整个文件。
- 前端历史列表可以逐步支持分页和条件查询。

### 第三优先级：用户术语表和配置预设

术语表当前是一个小 JSON 对象，配置预设是多个 JSON 文件。它们也可以迁移，但收益相对较小。

适合迁移的理由：

- 未来支持多术语表、多命名空间、导入记录、搜索分页时更自然。
- 避免整文件覆盖。

不急于迁移的理由：

- 当前数据量通常较小，JSON 足够快。
- 迁移后需要增加导入导出兼容逻辑。

## 不建议迁移的范围

以下内容继续保留为文件更合适：

- 生成的资源包 zip
- JSON/FTB Quests 输出文件
- 报告 JSON/CSV
- `failed-items.json`
- API 调试日志
- 临时上传文件
- JAR 处理缓存制品

这些内容本身就是用户可下载、可查看、可复制的文件。放入 SQLite 会降低可调试性，也不利于直接下载。

## 建议表结构

### 元数据与设置

```sql
CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

可用于保存任务历史保留数量、数据库迁移状态等小型设置。

### 翻译记忆

```sql
CREATE TABLE IF NOT EXISTS translation_memory (
  scope TEXT NOT NULL,
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (scope, source)
);

CREATE INDEX IF NOT EXISTS idx_translation_memory_updated_at
  ON translation_memory(updated_at);
```

写入时使用 upsert：

```sql
INSERT INTO translation_memory(scope, source, target, updated_at)
VALUES (?, ?, ?, ?)
ON CONFLICT(scope, source) DO UPDATE SET
  target = excluded.target,
  updated_at = excluded.updated_at;
```

### 任务历史

```sql
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
);

CREATE INDEX IF NOT EXISTS idx_job_history_created_at
  ON job_history(created_at);

CREATE INDEX IF NOT EXISTS idx_job_history_status
  ON job_history(status);

CREATE INDEX IF NOT EXISTS idx_job_history_input_kind
  ON job_history(input_kind);
```

输入文件单独拆表：

```sql
CREATE TABLE IF NOT EXISTS job_input_files (
  job_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  path TEXT NOT NULL,
  PRIMARY KEY (job_id, position),
  FOREIGN KEY (job_id) REFERENCES job_history(job_id) ON DELETE CASCADE
);
```

`summary_json`、`downloads_json` 和 `download_files_json` 先保留 JSON 文本，可以减少前端和 API 改动。未来如果需要做复杂统计，再拆成更细的表。

### 用户术语表

```sql
CREATE TABLE IF NOT EXISTS glossary_terms (
  source TEXT PRIMARY KEY,
  target TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

后续如果要支持多个术语表，可以扩展为：

```sql
CREATE TABLE glossary_sets (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE glossary_terms (
  set_id TEXT NOT NULL,
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (set_id, source)
);
```

当前阶段不建议一开始就做多术语表，避免扩大范围。

## SQLite 连接建议

初始化连接时建议启用：

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;
```

原因：

- WAL 对本地 Web/桌面应用的读写并发更友好。
- `busy_timeout` 可以缓解 Windows 文件锁和短暂并发写冲突。
- `foreign_keys` 确保任务历史和输入文件级联删除生效。

## 兼容迁移策略

不要硬切旧文件格式。推荐启动时做一次兼容导入：

1. 初始化 SQLite schema。
2. 检查 `schema_migrations` 或 `app_settings` 中是否已有导入标记。
3. 如果没有导入过：
   - 导入 `cache/translation-memory.jsonl`
   - 导入 `jobs/index.jsonl`
   - 导入 `jobs/settings.json`
   - 导入 `glossaries/user-glossary.json`
4. 导入时跳过坏行，保持当前 JSONL 容错行为。
5. 导入后保留旧文件，不自动删除。
6. 写入新数据只写 SQLite。

建议添加迁移记录表：

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  key TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);
```

迁移 key 示例：

```text
import_translation_memory_jsonl_v1
import_job_history_jsonl_v1
import_user_glossary_json_v1
```

## 代码改造建议

新增模块：

```text
src/mc_mod_i18n/app_db.py
```

职责：

- 解析数据库路径。
- 初始化 schema。
- 提供连接上下文。
- 执行旧文件迁移。
- 封装通用 JSON 读写和时间戳。

保留现有上层函数名：

- `read_job_history()`
- `append_job_history()`
- `trim_job_history()`
- `delete_job_history_records()`
- `clear_job_history()`
- `read_user_glossary()`
- `write_user_glossary()`
- `translation_memory_stats()`
- `clear_translation_memory()`
- `compact_translation_memory()`
- `TranslationMemory.get()`
- `TranslationMemory.put_many()`

这样前端和 Web API 可以尽量不动，主要替换内部存储实现。

## 性能预期

会明显改善的场景：

- 翻译记忆达到几万到几十万条。
- 频繁按 scope 查询、统计、清理翻译记忆。
- 任务历史达到几百到几千条。
- 前端历史页后续支持分页、搜索和过滤。

提升有限的场景：

- 术语表只有几十到几百条。
- 任务历史只有几十条。
- 翻译记忆只有几千条以内。
- 单次任务主要耗时来自 API 网络和模型响应。

结论：SQLite 不会显著缩短翻译 API 本身的耗时，但会提升长期使用后的状态管理性能和稳定性。

## 风险与应对

### 并发写入

风险：任务运行、设置页操作、历史写入可能同时访问数据库。

应对：

- 启用 WAL。
- 设置 `busy_timeout`。
- 写操作使用短事务。
- `put_many()` 批量写，不逐条打开连接。

### 旧数据兼容

风险：已有 JSON/JSONL 文件可能包含坏行或旧字段。

应对：

- 迁移时跳过坏行。
- 字段缺失时使用当前代码的默认值。
- 旧文件保留，方便回滚和排查。

### 回滚

风险：SQLite 改造后用户需要回到旧版本。

应对：

- 初期不删除旧 JSON/JSONL。
- 可提供导出命令或内部函数，将 SQLite 数据导出回 JSON/JSONL。

### 文件锁

风险：Windows 下数据库文件被杀毒软件、备份软件或多个进程短暂占用。

应对：

- `busy_timeout=5000`。
- 避免长事务。
- 避免长期持有全局游标。

## 分阶段实施计划

### 阶段 1：数据库基础设施

1. 新增 `app_db.py`。
2. 创建 schema 初始化函数。
3. 添加 WAL、busy timeout、foreign key 配置。
4. 添加迁移标记表。
5. 写基础单元测试：数据库创建、重复初始化、迁移标记。

### 阶段 2：翻译记忆迁移

1. 为 `TranslationMemory` 增加 SQLite 实现。
2. 从 `translation-memory.jsonl` 自动导入旧数据。
3. `get()` 改为按 `(scope, source)` 查询。
4. `put_many()` 改为批量 upsert。
5. `translation_memory_stats()` 改为 SQL 统计。
6. `clear_translation_memory()` 改为 SQL 删除。
7. `compact_translation_memory()` 在 SQLite 模式下变成无操作或返回 0。
8. 保持现有测试通过，并新增旧 JSONL 迁移测试。

### 阶段 3：任务历史迁移

1. 从 `jobs/index.jsonl` 自动导入旧历史。
2. 从 `jobs/settings.json` 导入保留数量。
3. `append_job_history()` 改为 upsert。
4. `read_job_history()` 改为按时间倒序查询。
5. `trim_job_history()` 改为 SQL 删除超出保留数量的旧记录。
6. `delete_job_history_records()` 和 `clear_job_history()` 改为 SQL 删除。
7. 保留 `download_status` 的运行时文件存在性检查。
8. 添加迁移、删除、裁剪、缺失下载文件状态测试。

### 阶段 4：术语表迁移

1. 从 `glossaries/user-glossary.json` 导入。
2. `read_user_glossary()` 从 SQLite 读取并保持排序。
3. `write_user_glossary()` 使用事务替换当前用户术语表。
4. 保持导入导出 JSON 的前端体验不变。
5. 添加冲突检测和空术语表兼容测试。

### 阶段 5：配置预设评估

配置预设暂不建议第一批迁移。等前三阶段稳定后，再决定是否把 `presets/*.json` 移入 SQLite。

## 测试清单

必须覆盖：

- 空数据库首次启动。
- 重复初始化不报错。
- 旧 JSONL 翻译记忆迁移。
- 翻译记忆同 `(scope, source)` 更新后只保留最新值。
- 翻译记忆按 scope 清理。
- 任务历史 JSONL 迁移。
- 任务历史删除、裁剪、清空。
- 任务历史下载文件存在性检查。
- 用户术语表 JSON 迁移。
- 用户术语表空对象兼容。
- 坏 JSONL 行跳过。
- Windows 路径和中文路径。

建议运行：

```text
python -m unittest tests.test_translation_memory tests.test_translation_memory_management tests.test_job_history tests.test_glossary_management
```

同时保留 Web UI 契约测试：

```text
python -m unittest tests.test_web_ui_contract
```

## 结论

项目可以迁移到 SQLite。最值得优先改的是翻译记忆和任务历史，它们的数据会持续增长，并且当前 JSONL 方案在去重、统计、清理和筛选上会逐渐变重。

术语表也可以迁移，但当前收益小于翻译记忆和任务历史。资源包、报告、日志、失败项 JSON 等文件制品不建议迁移到 SQLite。

推荐路线：

1. 先建设 SQLite 基础设施。
2. 先迁翻译记忆。
3. 再迁任务历史。
4. 最后评估术语表和配置预设。
