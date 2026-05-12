# mc-mod-i18n

Minecraft Mod JAR 自动汉化工具。当前版本实现 CLI MVP：扫描 Mod JAR 中的英文语言文件，生成 `zh_cn` 资源包 ZIP 和 HTML 报告。

## 使用

启动本地 UI：

```bash
$env:PYTHONPATH="src"
python -m mc_mod_i18n serve
```

浏览器打开：

```text
http://127.0.0.1:8765
```

浏览器级 UI 自检（需要先安装 Playwright）：

```powershell
npm install --save-dev playwright
npx playwright install chromium
$env:PYTHONPATH="src"
python -m mc_mod_i18n serve --port 8765
node scripts/ui_smoke_test.mjs http://127.0.0.1:8765
```

开发模式直接运行：

```bash
$env:PYTHONPATH="src"
python -m mc_mod_i18n translate ./mods --out ./dist --provider glossary
```

处理单个 JAR：

```bash
$env:PYTHONPATH="src"
python -m mc_mod_i18n translate ./example.jar --out ./dist
```

可选翻译器：

- `copy`：复制原文，适合测试流程
- `glossary`：使用内置术语和可选 `glossary.json` 做规则翻译
- `openai-compatible`：兼容 OpenAI Chat Completions 的接口
- `anthropic-compatible`：兼容 Anthropic Messages 的接口

使用自定义术语表：

```bash
python -m mc_mod_i18n translate ./mods --provider glossary --glossary glossary.json
```

术语表示例：

```json
{
  "Copper": "铜",
  "Crystal": "水晶",
  "Mana": "魔力"
}
```

使用 AI 接口：

```bash
$env:OPENAI_API_KEY="sk-..."
python -m mc_mod_i18n translate ./mods --provider openai-compatible --model gpt-4o-mini

$env:ANTHROPIC_API_KEY="sk-ant-..."
python -m mc_mod_i18n translate ./mods --provider anthropic-compatible --model claude-3-5-haiku-latest
```

Web UI 可以直接填写 API Key；如果留空，则读取对应环境变量，例如 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`。高级 API 设置里的 `BaseURL` 填到 `/v1` 即可，模型下拉会通过本地代理请求 `/models` 获取可选模型；完整 `/chat/completions` 或 `/messages` 地址也兼容。

默认输出：

```text
dist/
├─ auto-i18n-resourcepack.zip
└─ report.html
```

## 打包为 Windows exe

安装 PyInstaller 并构建：

```powershell
.\scripts\build_exe.ps1 -InstallPyInstaller -Clean
```

如果已经安装过 PyInstaller：

```powershell
.\scripts\build_exe.ps1 -Clean
```

输出：

```text
dist/
└─ mc-mod-i18n/
   ├─ mc-mod-i18n.exe
   └─ _internal/
```

启动 UI：

```powershell
.\dist\mc-mod-i18n\mc-mod-i18n.exe serve
```

命令行翻译：

```powershell
.\dist\mc-mod-i18n\mc-mod-i18n.exe translate .\mods --out .\dist-output
```

## JarJar 和硬编码扫描

NeoForge bundled / JarJar 类型的 Mod 会把真实 Mod 放在 `META-INF/jarjar/*.jar` 里。工具会自动递归扫描这些内层 JAR。

扫描 Ponder 教程、配置注释等硬编码英文：

```powershell
$env:PYTHONPATH="src"
python -m mc_mod_i18n translate .\测试mod --out .\dist-test --scan-hardcoded
```

额外输出：

```text
dist-test/
├─ hardcoded-report.html
└─ hardcoded-map.template.json
```

`hardcoded-report.html` 用来确认硬编码英文的实际来源分类；`hardcoded-map.template.json` 后续用于生成补丁 Mod 或汉化配置模板。

Web UI 处理完成后会显示“硬编码映射工作台”：

- 可按实际扫描到的分类筛选候选文本，例如 `Ponder 场景`、`界面硬编码`、`配置注释`、`待确认文本`
- 可直接填写每条候选的 `translation`
- 可导入已有 `hardcoded-map.json` / `hardcoded-map.template.json` 继续编辑
- 导出时只写入已填写译文的条目，文件名为 `hardcoded-map.json`
- 导出前会校验 `%s`、`%1$s`、`{0}`、`§a` 和换行等占位符

`hardcoded-map.json` 不是资源包文件，单独放进资源包不会让 Java 代码里写死的英文生效。它的用途是作为运行时补丁 Mod / Mixin / 配置模板生成器的输入：补丁在游戏显示文本的入口处按原文查表替换，或把可配置的注释/模板写成目标模组能读取的格式。当前工具负责扫描、分类、翻译和导出映射；真正运行时替换需要配套补丁读取该 JSON。
