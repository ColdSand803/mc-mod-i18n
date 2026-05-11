# FTB Quests 支持方案

## 背景

当前工具的主流程面向 Minecraft Mod JAR 的语言文件翻译：扫描 `assets/<modid>/lang/<locale>.json|lang`，翻译后生成资源包 ZIP，并在报告中按 JAR、mod id、语言文件和 key 展示结果。

FTB Quests 的内容不属于普通 Mod JAR 语言文件。它主要是整合包配置内容，任务书、章节、任务、奖励、说明文本通常位于整合包目录的 `config/ftbquests/quests` 下。1.21 起 FTB Quests 引入新的翻译系统，文本会集中存储到 `lang/<locale>.snbt`；旧版本或旧整合包仍可能把文本直接写在章节、任务等 SNBT 文件里。

因此本功能应作为独立输入类型接入：支持 FTB Quests 任务书配置翻译，输出翻译后的任务书配置目录或补丁 ZIP，而不是默认写入 Minecraft 资源包。

## 依据

- FTB Quests 2100.1.0 变更说明提到，1.21 起翻译文本从任务数据中拆分到任务书目录下的 `lang/` 文件夹，文件名按 locale 命名，例如 `lang/en_us.snbt`。
- FTB Quests 2100.1.1 变更说明提到，旧任务书数据加载后会迁移到新翻译系统，并在 `config/ftbquests/quests` 下自动创建 `lang/en_us.snbt`。
- CurseForge 上 FTB Quests 仍同时覆盖 1.20.1、1.20.4、1.21.x 等版本，所以工具需要兼容“旧版直接 SNBT 文本”和“新版 lang SNBT 文本”两类整合包。

## 目标

1. 支持上传或选择 FTB Quests 任务书目录、整合包目录、整合包 ZIP。
2. 自动识别 `config/ftbquests/quests`。
3. 优先处理新版 `lang/<source_locale>.snbt`。
4. 当不存在 lang 文件时，回退到旧版章节/任务 SNBT 文本提取。
5. 复用现有翻译器配置、批量翻译、失败报告、缓存目录设置。
6. 输出可直接覆盖到整合包的翻译结果，并保留原文件结构。
7. 提供人工校对报告，标出文本来源、字段路径、原文、译文和风险状态。

## 非目标

1. 不修改 FTB Quests 本体 JAR。
2. 不默认把 FTB Quests 结果写进资源包 ZIP。
3. 不翻译 item id、entity id、recipe id、command、NBT 结构、文件名、UUID、颜色代码本身。
4. 第一阶段不做任务书可视化编辑器，只做提取、翻译、生成和报告。
5. 第一阶段不尝试理解每一种第三方 FTB Quests 扩展字段，只提供可扩展字段规则。

## 输入识别

### 支持的输入

- 任务书目录：`.../config/ftbquests/quests`
- 整合包根目录：包含 `config/ftbquests/quests`
- 整合包 ZIP：ZIP 内包含 `config/ftbquests/quests/**`
- 独立导出的 quests ZIP：根目录或子目录中包含 `chapters/`、`lang/`、`reward_tables/` 等 FTB Quests 文件

### 识别规则

1. 如果输入路径本身包含 `lang/`、`chapters/` 或 `chapter_groups.snbt` 等任务书特征，视为 quests 根目录。
2. 如果输入路径下存在 `config/ftbquests/quests`，以该目录为 quests 根目录。
3. 如果是 ZIP，扫描 ZIP 条目并定位 `config/ftbquests/quests/` 或等价的 quests 根。
4. 如果同时发现多个 quests 根目录，报告为多个任务书，UI 允许用户选择或全部处理。

## 版本与文件布局

### 新版布局

典型路径：

```text
config/ftbquests/quests/
  chapters/*.snbt
  lang/en_us.snbt
  lang/zh_cn.snbt
  reward_tables/*.snbt
```

处理策略：

- 如果存在 `lang/<source_locale>.snbt`，优先从该文件提取待翻译文本。
- 如果目标 `lang/<target_locale>.snbt` 已存在，默认做增量补全，已有目标译文不覆盖。
- 提供“覆盖已有目标译文”选项，用于用户明确要求重翻。

### 旧版布局

典型路径：

```text
config/ftbquests/quests/
  chapters/*.snbt
  reward_tables/*.snbt
  chapter_groups.snbt
  data.snbt
```

处理策略：

- 在 SNBT 结构里按字段白名单提取文本。
- 翻译后生成同结构的目标 quests 目录。
- 尽量保留原文件顺序、缩进和注释；如果无法无损保留，生成格式化 SNBT，并在报告中标记。

## 文本提取规则

### 字段白名单

优先提取这些语义字段：

- `title`
- `subtitle`
- `description`
- `name`
- `text`
- `tooltip`
- `hover`
- `label`
- `quest_title`
- `quest_subtitle`
- `chapter_title`
- `chapter_subtitle`
- `reward_title`
- `task_title`

新版 `lang/<locale>.snbt` 中，如果 key 对应值是字符串或字符串数组，默认视为可翻译文本。

旧版 SNBT 中，如果字段名命中白名单，且值看起来是自然语言文本，则提取。

### 字段黑名单

跳过这些内容：

- `id`、`uid`、`uuid`
- `icon`、`image`、`texture`
- `item`、`item_id`、`entity`、`entity_id`
- `recipe`、`advancement`
- `command`、`custom_reward` 中的命令字符串
- `filename`、`path`
- `x`、`y`、`size`、`color`
- 数字、布尔值、空值
- 形如 `minecraft:stone`、`modid:item_name` 的资源路径
- 形如 `#forge:ingots/iron` 的 tag
- 纯格式码、纯变量占位符、纯 URL

### 文本保护

翻译前需要保护这些片段，翻译后恢复：

- Minecraft 格式码：`§a`、`§l`、`&a`、`&l`
- FTB Quests/文本中的颜色写法：`&#RRGGBB`
- 占位符：`{player}`、`{team}`、`%s`、`%1$s`
- JSON text component 中的 click/hover 结构字段
- Markdown 风格链接或 FTB Quests 内部链接
- 换行、列表符号、缩进

## SNBT 处理策略

### 优先方案

新增模块：

```text
src/mc_mod_i18n/ftbquests.py
```

模块职责：

- 定位 quests 根目录。
- 读取目录或 ZIP 中的 SNBT 文件。
- 解析新版 lang SNBT。
- 解析旧版章节 SNBT。
- 生成 `FTBQuestTextItem`。
- 应用翻译结果并写出目标目录/ZIP。
- 生成 FTB Quests 专用报告数据。

### 解析策略

第一阶段建议采用“容错 SNBT tokenizer + 定位 patch”：

1. tokenizer 识别字符串、列表、对象、key、注释、换行和原始文本片段。
2. 对命中字段记录原始字符串范围、字段路径和文件路径。
3. 翻译后仅替换字符串内容，不重排整个文件。
4. 如果文件存在复杂语法导致无法定位 patch，回退到结构化解析和格式化输出。

这样可以最大限度保留用户原始 quests 文件的顺序、注释和排版。

### 备选方案

如果后续发现 SNBT 兼容成本过高，可以引入独立 SNBT parser 依赖。但当前项目依赖较少，优先控制新增依赖，避免打包复杂度上升。

## 翻译流程接入

### 数据模型

新增内部模型：

```python
@dataclass
class FTBQuestTextItem:
    source_root: str
    file: str
    path: str
    key: str
    source: str
    target: str = ""
    mode: str = "lang"  # lang | legacy_snbt
    status: str = "pending"
    message: str = ""
```

其中：

- `file` 是相对 quests 根目录的文件路径。
- `path` 是 SNBT 字段路径，例如 `chapters/getting_started.snbt.quest.123.description`。
- `key` 对新版 lang 文件使用原始 key。
- `mode` 用于报告区分新版 lang 文件和旧版直接 SNBT。

### 翻译复用

复用现有翻译器：

- `create_translator`
- `TranslationItem`
- `translate_batch_with_failures`
- 当前 BaseURL、API Key、模型、OpenAI/Anthropic 兼容配置

FTB Quests 的 prompt 需要额外补充：

- 保留 Minecraft 格式码和占位符。
- 不翻译物品 ID、命令、变量。
- 保留原有换行与列表结构。
- 对任务书描述使用自然中文，不要过度意译机制名词。

### 批处理

- 按文件或 key 顺序稳定排序，保证结果可复现。
- 新版 lang 模式可以直接按 key 批量。
- 旧版 SNBT 模式按文件分批，便于失败时定位。
- 与现有 JAR 翻译一样支持并发，但写文件阶段串行执行。

## 输出策略

### 默认输出

输出目录：

```text
out/
  ftbquests/
    config/ftbquests/quests/...
  ftbquests-report.html
  ftbquests-report.json
```

默认生成完整可覆盖目录，用户可以把 `config/ftbquests/quests` 覆盖到整合包。

### Patch ZIP

可选生成：

```text
ftbquests-zh_cn-patch.zip
```

ZIP 内保持整合包路径：

```text
config/ftbquests/quests/lang/zh_cn.snbt
config/ftbquests/quests/chapters/...
```

这样用户可以直接解压到实例根目录。

### 新版 lang 输出

当源文件是 `lang/en_us.snbt`：

- 生成或更新 `lang/zh_cn.snbt`。
- 不修改 `lang/en_us.snbt`。
- 不修改章节结构文件。
- 已存在 `zh_cn.snbt` 时默认只补齐缺失 key。

### 旧版 SNBT 输出

当没有 lang 源文件：

- 生成翻译后的 quests 目录副本。
- 原目录不原地修改。
- 对无法安全 patch 的文件，报告中标记 `format_rewritten`。

## 缓存设计

### 缓存 key

FTB Quests 缓存维度：

- quests 根目录或 ZIP 的内容 hash。
- 源语言。
- 目标语言。
- 翻译器 provider。
- BaseURL。
- 模型。
- prompt 版本。
- 文本保护规则版本。
- 提取规则版本。

### 缓存内容

缓存文件保存：

- 提取出的 `FTBQuestTextItem` 列表。
- 每条文本的 source hash。
- 翻译结果。
- 报告状态。
- 输出模式。

### 命中策略

- 单条文本级别缓存优先于整任务书缓存。
- 如果只改了一个章节，只重新翻译变化文本。
- 如果 provider/model/prompt 变化，默认失效。
- 设置菜单的“清空缓存”和“设置缓存目录”直接复用现有实现。

## UI 改动

### 输入区

新增处理类型：

- `Mod JAR 语言文件`
- `FTB Quests 任务书`

选择 FTB Quests 后：

- 上传支持目录、ZIP 或多个 SNBT 文件。
- 显示识别到的 quests 根目录。
- 显示检测模式：`新版 lang` / `旧版 SNBT` / `混合`。
- 源语言默认 `en_us`。
- 目标语言沿用现有目标语言下拉框。

### 选项

新增选项：

- 目标 locale：默认 `zh_cn`。
- 已有目标译文：`保留已有` / `覆盖重翻`。
- 输出类型：`目录` / `Patch ZIP` / `目录 + Patch ZIP`。
- 旧版 SNBT：是否允许格式化重写无法无损 patch 的文件。
- 文本保护：默认开启，不建议关闭。

### 结果区

新增 FTB Quests 结果 tab：

- 概览：文件数、文本数、缓存命中数、失败数。
- 文件筛选：按 `lang`、`chapters`、`reward_tables` 等目录树显示。
- 表格列：文件、字段路径/key、原文、译文、状态、消息。
- 下载：翻译目录、Patch ZIP、HTML 报告、JSON 报告。

## CLI 改动

建议新增子命令或参数组：

```bash
mc-mod-i18n ftbquests <input> \
  --source-locale en_us \
  --target-locale zh_cn \
  --output out \
  --output-mode both \
  --existing-target keep \
  --cache-dir .shared-cache
```

可选参数：

```text
--ftbquests-root <path>       手动指定 quests 根目录
--overwrite-existing          覆盖已有目标 locale 译文
--allow-format-rewrite        允许无法无损 patch 时格式化重写 SNBT
--no-patch-zip                不生成 patch ZIP
--only-missing                只补全缺失 key
```

也可以在现有 `translate` 子命令上增加 `--mode jar|ftbquests|auto`，但从维护角度看，独立 `ftbquests` 子命令更清晰。

## 报告设计

新增 HTML/JSON 报告：

```text
ftbquests-report.html
ftbquests-report.json
```

报告字段：

- `source_root`
- `mode`
- `file`
- `path`
- `key`
- `source`
- `target`
- `status`
- `message`
- `cache_hit`

状态建议：

- `translated`
- `cached`
- `skipped_existing`
- `skipped_non_text`
- `failed`
- `format_rewritten`
- `unsafe`

报告需要突出这些风险：

- 命令字段疑似被跳过。
- JSON text component 未完全解析。
- 文件无法无损 patch，已格式化重写。
- 译文占位符缺失。
- 译文格式码数量不匹配。

## 测试计划

### 单元测试

- quests 根目录识别。
- ZIP 内路径识别。
- 新版 `lang/en_us.snbt` 提取。
- 已存在 `lang/zh_cn.snbt` 时只补缺失。
- 旧版章节 SNBT 字段白名单提取。
- 黑名单字段跳过。
- 格式码、占位符、资源路径保护。
- 翻译结果 patch 后 SNBT 字符串转义正确。

### 集成测试

准备 fixtures：

```text
tests/fixtures/ftbquests/new_lang/
tests/fixtures/ftbquests/legacy_snbt/
tests/fixtures/ftbquests/modpack_zip/
```

验证：

- 输出目录结构正确。
- Patch ZIP 路径正确。
- 报告条目数量正确。
- 缓存二次运行命中。
- 失败项不会破坏输出文件。

### 人工验证

- 用一个真实 1.20.1 整合包任务书验证旧版 SNBT。
- 用一个真实 1.21.x 整合包任务书验证 lang SNBT。
- 把 Patch ZIP 解压进测试实例，进入游戏确认任务书能加载。

## 分阶段实施

### 第一阶段：可用闭环

1. 新增 `ftbquests.py`。
2. 支持目录和 ZIP 输入识别。
3. 支持新版 `lang/<source_locale>.snbt` 提取与生成目标 locale。
4. 复用现有翻译器和缓存目录。
5. 输出目录和 Patch ZIP。
6. 生成 JSON/HTML 报告。
7. 增加 CLI 子命令。

验收标准：

- 对存在 `lang/en_us.snbt` 的任务书，可以生成 `lang/zh_cn.snbt`。
- 已有目标文件时默认不覆盖已有 key。
- 失败项在报告中可追踪。

### 第二阶段：旧版 SNBT 兼容

1. 增加旧版章节/奖励 SNBT 提取。
2. 增加无损 patch。
3. 增加无法无损 patch 时的格式化重写 fallback。
4. 增加格式码、占位符一致性校验。

验收标准：

- 对没有 `lang/` 的旧任务书，可以生成翻译后的 quests 目录。
- 不翻译 item id、command、recipe、advancement 等结构字段。

### 第三阶段：Web UI 接入

1. UI 新增处理类型。
2. 上传/选择 FTB Quests 输入。
3. 展示检测结果和输出选项。
4. 结果页新增 FTB Quests tab。
5. 下载 Patch ZIP 和报告。

验收标准：

- 用户无需 CLI 即可完成 FTB Quests 翻译。
- 结果列表能按目录树筛选文件。

### 第四阶段：高级能力

1. 支持 split lang 结构，例如 `lang/en_us/chapters/*.snbt` 这类社区拆分方案。
2. 增加术语表对 FTB Quests 任务文本的优先级控制。
3. 增加“只检查不翻译”模式，用于报告可翻译文本。
4. 增加人工修改回写功能。
5. 支持多目标语言批量生成。

## 风险与处理

### SNBT 方言差异

风险：不同版本或工具生成的 SNBT 细节不完全一致。

处理：第一阶段优先支持新版 lang 文件；旧版 SNBT 采用 tokenizer + patch，并保留 fallback。

### 误翻译结构字段

风险：翻译了 ID、命令或资源路径会导致任务书加载失败。

处理：默认字段白名单提取，同时用黑名单和内容模式二次过滤。

### 格式码/占位符丢失

风险：译文丢失 `§`、`&`、`{team}` 等导致显示异常。

处理：翻译前占位保护，翻译后校验，不一致则标记失败或要求人工处理。

### 新旧版本混合

风险：某些任务书同时存在 lang 文件和章节内直接文本。

处理：检测为 `混合`，默认优先 lang，同时报告章节内疑似直写文本，提供“同时处理旧版字段”的高级选项。

### 输出覆盖风险

风险：用户把结果覆盖到整合包后难以回退。

处理：工具不原地修改输入；默认输出到 `out/ftbquests`，并生成 Patch ZIP。

## 待确认问题

1. 用户更常见的输入是整合包 ZIP、实例目录，还是单独的 `config/ftbquests/quests` 目录。
2. 第一版是否只接 Web UI，还是 CLI 也同步开放。
3. 目标 locale 是否固定默认 `zh_cn`，或跟随当前工具目标语言。
4. 已存在目标语言时，默认“保留已有”是否符合使用习惯。
5. 是否需要把 FTB Quests 翻译结果纳入当前“语言结果”列表，还是单独做“任务书结果”列表。

## 推荐落地顺序

推荐先做新版 `lang/en_us.snbt -> lang/zh_cn.snbt` 闭环。这个路径最贴合 FTB Quests 1.21+ 的官方设计，风险低、输出稳定，也能复用当前翻译器、缓存和报告机制。

旧版章节 SNBT 直接 patch 放在第二阶段，因为它涉及 SNBT 方言兼容、无损写回和误翻译风险，应该在新版闭环稳定后再推进。
