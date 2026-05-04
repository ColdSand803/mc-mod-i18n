# 多 JAR 性能优化方案

> 目标：当 Mod 数量大（10+ JAR）或单 JAR 条目多（2000+）时，翻译和 UI 保持可用速度。

## 1. 当前瓶颈

| 瓶颈 | 位置 | 影响 | 50 JAR 估算 |
|---|---|---|---|
| AI 翻译 JAR 间串行 | `cli.py:156` — AI provider 强制 `worker_count=1` | 所有 JAR 排队等翻译 | 50×2min = 100min |
| 单 JAR 内批次串行 | `translator.py:475` — `workers<=1` 走顺序分支 | 2000条/batch40 = 50次串行调用 | 单大JAR 2min+ |
| 搜索每击全量过滤 | `web.py:2433` — `entries.filter()` 无防抖 | 每次击键遍历全量 5000+ 条目 | UI 明显卡顿 |
| 过滤无提前终止 | `web.py:2433` — 找到 50 条后仍遍历剩余 | 翻页浪费 99% 过滤开销 | 翻页慢 |
| 多 JAR 无增量判断 | `cli.py` — 每次跑都全量处理 | 重复跑不改的 JAR 也要重新翻译 | 浪费时间+API 费用 |

## 2. 优化方案

### P0：不优化基本没法用

#### 2.1 搜索防抖 + 过滤提前终止

**文件：** `web.py`

- 搜索 `input` 事件加 200ms debounce（`setTimeout` + `clearTimeout`），停止连续击键后再触发过滤
- `renderLanguageResultTable` 的 filter 循环内：当收集到当前页需要的条目数后 `break`，不再遍历剩余条目

**改动量：** ~10 行 JS  
**效果：** 5000 条目列表翻页时过滤开销降低 95%+，输入不卡顿

#### 2.2 API 翻译并发度放开

**文件：** `cli.py`, `translator.py`

- `cli.py:156`：对 AI provider 不再强制 `worker_count=1`。`RateLimiter` 已经协调 429，可以安全并发
- `translator.py:475`：去掉 `workers <= 1` 的顺序分支，统一走 `ThreadPoolExecutor`
- `--api-concurrency` 同时控制 JAR 级别和批次级别并发

**改动量：** ~5 行  
**效果：** 单 JAR 翻译耗时减少 50-70%；多 JAR 场景可并行处理

#### 2.3 Hash 增量跳过

**文件：** `cli.py`, `pack.py`

- 每次 `process_jar` 前，对 `collect_lang_documents(zf, source_locale)` 的条目内容计算 SHA-256
- 写入 checkpoint JSON：`"source_hash": "<sha256>"`
- 下次运行时比对：hash 未变 → 直接加载上次翻译结果，跳过整个 JAR
- 复用已有的 `save_checkpoint` / `load_checkpoint` 机制

**改动量：** ~30 行  
**效果：** 重复跑同一批 JAR → 未变更的 JAR 0 耗时（配合 `--resume`）

### P1：Mod 量很大时进一步优化

#### 2.4 多 JAR 共享翻译 Worker 池

**文件：** `cli.py`

- 多 JAR 场景不各自独立开线程池，而是所有 JAR 的翻译 item 汇入同一个 chunk queue
- 共享同一个 `RateLimiter` 实例（已是线程安全）
- 减少线程创建/销毁开销，提高 API 利用率

#### 2.5 Lang 文件读取并行化

**文件：** `cli.py:process_zip`

- `collect_lang_documents` 是纯 I/O（ZipFile 读取），可与其他操作并行
- 同一 JAR 内多个 lang 文件的翻译 batch 可并行提交到 worker pool

#### 2.6 报告 HTML 按 JAR 折叠

**文件：** `report.py`

- `write_report` 当前一次性生成包含全部条目的巨大 HTML
- 改为按 JAR 分组，使用 `<details>` 折叠，首屏只渲染摘要统计
- 减少 DOM 节点数，报告页打开速度提升

## 3. 实施顺序

```
第1步: 搜索防抖 + 过滤提前终止     (1h, 立竿见影, UI 不再卡)
第2步: API 并发度放开               (1h, 翻译耗时减少 50-70%)
第3步: hash 增量跳过                (2h, 重复跑 0 耗时 + 0 API 费用)
第4步: 多JAR并行 + lang并行         (按需, 超大场景进一步优化)
第5步: 报告折叠                     (按需, 报告加载优化)
```

## 4. 预期效果

| 场景 | 优化前 | 优化后（第1-3步） |
|---|---|---|
| 10 个 JAR 首次翻译 | ~20min | ~6-8min |
| 10 个 JAR 重复翻译（1 个变更） | ~20min | ~40s（只翻变更的 1 个） |
| 5000 条目结果页搜索 | 每次击键卡顿 | 流畅 |
| 5000 条目结果页翻页 | 遍历全量 | 只遍历当前页所需条目 |

## 5. 注意

- API 并发度受 provider 限流影响，`RateLimiter` 已有 429 协调，放开后需验证各 provider 的实际限流阈值
- Hash 增量跳过依赖源文件不变，用户修改 lang 文件后需重新计算 hash
- 改动集中在 `web.py`、`cli.py`、`translator.py`、`pack.py`，不引入新依赖
