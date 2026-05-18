# FTB Quests 测试整合包推荐

整理时间：2026-05-18

目标：挑选明确使用或高度依赖 FTB Quests 的整合包，用于测试 FTB Quests 任务文本提取、翻译、回写和版本兼容能力。

## 推荐优先级

| 优先级 | 整合包 | MC 版本 / 加载器 | 推荐用途 | 选择理由 |
| --- | --- | --- | --- | --- |
| 1 | FTB StoneBlock 4 | 1.21.1 / NeoForge | 新版 FTB Quests 主流程测试 | 官方整合包，任务引导明确，适合验证新版 FTB Quests 数据结构、任务章节、奖励文本和进度描述。 |
| 2 | All the Mods 10 - ATM10 | 1.21.1 / NeoForge | 大型任务包压力测试 | 大型整合包，任务数量和模组覆盖面高，适合测试批量扫描、批量翻译、长耗时任务和复杂任务树。 |
| 3 | FTB Skies 2 | 1.21.1 / NeoForge | 大量任务文本测试 | 天空岛流程通常依赖任务推进，任务文本类型丰富，适合测章节标题、任务描述、奖励说明、商店文本等。 |
| 4 | FTB OceanBlock 2 | 1.21.1 / NeoForge | 流程引导和长描述测试 | 适合验证偏叙事或阶段推进类任务文本，能覆盖较多说明性文本和进度目标。 |
| 5 | All the Mods 9 - ATM9 | 1.20.1 / Forge | Forge 1.20.1 兼容对照 | 成熟稳定，任务量大，适合作为 1.20.1 Forge 与 1.21.1 NeoForge 的差异对照样本。 |
| 6 | Create: Above and Beyond | 1.16.5 / Forge | 旧版数据格式兼容测试 | 老版本经典任务整合包，适合验证旧版 FTB Quests 文件布局和 SNBT 兼容处理。 |

## 建议测试顺序

1. FTB StoneBlock 4
2. All the Mods 10 - ATM10
3. Create: Above and Beyond
4. FTB Skies 2
5. All the Mods 9 - ATM9
6. FTB OceanBlock 2

原因：

- 先用 StoneBlock 4 验证当前主流 1.21.1 NeoForge 场景。
- 再用 ATM10 做大规模压力测试。
- 中间插入 Create: Above and Beyond，尽早暴露旧版格式兼容问题。
- 最后用其他新版和稳定版包补齐覆盖面。

## 重点检查路径

常见 FTB Quests 文件位置：

```text
config/ftbquests/quests/
```

新版整合包中，语言文件可能位于：

```text
config/ftbquests/quests/lang/en_us.snbt
```

也可能存在章节、任务、奖励等分散的 SNBT 文件。测试时不要只检查 `lang` 目录，应同时扫描整个 `config/ftbquests/quests/`。

## 测试关注点

### 1. 文本提取

- 章节标题
- 任务标题
- 任务描述
- 副标题或提示文本
- 奖励说明
- 商店文本
- 队伍、阶段、依赖提示
- 多行文本

### 2. 格式保留

重点确认翻译后不会破坏：

- Minecraft 颜色码和格式码，例如 `&a`、`&l`、`§6`
- 换行符
- SNBT 引号和转义
- 变量占位符
- 物品 ID、方块 ID、标签 ID
- 任务 ID、章节 ID、依赖关系 ID

### 3. 回写验证

建议至少验证：

- 翻译后文件仍可被 SNBT 解析
- 游戏启动不报 FTB Quests 配置错误
- 任务书能正常打开
- 章节顺序不变
- 任务依赖线不丢失
- 奖励显示正常

## 推荐样本组合

### 最小测试组合

适合快速验证功能是否可用：

1. FTB StoneBlock 4
2. Create: Above and Beyond

覆盖新版 NeoForge 和旧版 Forge 两类基础场景。

### 标准测试组合

适合发布前验证：

1. FTB StoneBlock 4
2. All the Mods 10 - ATM10
3. Create: Above and Beyond
4. All the Mods 9 - ATM9

覆盖新版、旧版、大型任务包和稳定 Forge 包。

### 压力测试组合

适合验证扫描速度、翻译吞吐和异常恢复：

1. All the Mods 10 - ATM10
2. FTB Skies 2
3. All the Mods 9 - ATM9

这些包任务量较大，适合观察批量处理性能和长任务稳定性。

## 下载与来源

优先从这些页面获取整合包，避免使用二次转载包：

- FTB StoneBlock 4: <https://www.curseforge.com/minecraft/modpacks/ftb-stoneblock-4>
- All the Mods 10 - ATM10: <https://www.curseforge.com/minecraft/modpacks/all-the-mods-10>
- FTB Skies 2: <https://www.curseforge.com/minecraft/modpacks/ftb-skies-2>
- FTB OceanBlock 2: <https://www.curseforge.com/minecraft/modpacks/ftb-oceanblock-2>
- All the Mods 9 - ATM9: <https://www.curseforge.com/minecraft/modpacks/all-the-mods-9>
- Create: Above and Beyond: <https://www.curseforge.com/minecraft/modpacks/create-above-and-beyond>
- FTB Quests: <https://www.curseforge.com/minecraft/mc-mods/ftb-quests-forge>

## 结论

如果只选一个包，优先选 **FTB StoneBlock 4**。

如果要验证工具可靠性，使用 **FTB StoneBlock 4 + All the Mods 10 + Create: Above and Beyond**。这三个包能同时覆盖新版 NeoForge、大型任务数据和旧版 Forge 任务格式。
