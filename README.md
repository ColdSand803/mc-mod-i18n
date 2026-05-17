# mc-mod-i18n

Minecraft Mod JAR 自动汉化工具。当前版本实现 CLI MVP：扫描 Mod JAR 中的英文语言文件，生成 `zh_cn` 资源包 ZIP 和 HTML 报告。

## 使用

启动桌面版（单窗口应用）：

```bash
$env:PYTHONPATH="src"
python -m pip install ".[desktop]"
python -m mc_mod_i18n desktop
```

桌面模式会自动选择可用本地端口，并默认使用用户应用数据目录保存任务历史和运行数据。

桌面依赖 `pywebview`。当前 Windows 桌面打包建议使用 Python 3.10-3.12；Python 3.14 环境下 `pywebview` 的 `pythonnet` 依赖可能无法构建。

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
- `deep-free`：基于免费公共翻译源的零配置试用入口，无需 API Key，但可能受网络、限流和第三方服务变动影响
- `libretranslate`：开源翻译服务，可连接自托管或托管实例，默认 BaseURL 为 `http://127.0.0.1:5000`
- `argos`：本地离线翻译 provider，需要预先安装 `argostranslate` 和对应语言包
- `azure-translator`：Azure 官方翻译服务，需要 API Key，默认 BaseURL 为 `https://api.cognitive.microsofttranslator.com`
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

如果使用 `deep-free`：

- 无需 API Key
- 当前通过 `google + mymemory` 两个免费句子级引擎回退
- Google 与 MyMemory 分别使用各自更稳的 locale 映射
- 第三方免费源失败时会回退为原文，并在报告中标记为失败项
- Web UI 的“测试连接”会对 `deep-free` 执行短文本 smoke test，而不是检查 API key / models 接口

可选 live test：

```powershell
$env:PYTHONPATH="src"
$env:MC_MOD_I18N_LIVE_TRANSLATION_TESTS="1"
python -m unittest tests.test_deep_translator_live
```

如果使用 `libretranslate`：

- 默认按自托管实例处理，BaseURL 为 `http://127.0.0.1:5000`
- 可在 Web UI 或 CLI 中改成托管实例地址
- 可选 `api_key`
- Web UI 的“测试连接”会执行短文本 smoke test

如果使用 `argos`：

- 无需联网
- 无需 API Key
- 需要先安装 `argostranslate`
- 还需要安装源语言和目标语言对应的本地语言包
- Web UI 的“测试连接”会检查依赖和本地翻译能力

如果使用 `azure-translator`：

- 需要 `API Key`
- 默认 BaseURL 为 `https://api.cognitive.microsofttranslator.com`
- 可通过 `--api-region` 或 Web UI 的 `Region` 字段填写区域，例如 `global`、`eastasia`
- Web UI 的“测试连接”会执行 Azure 专用 smoke test，而不是走通用 `/models` 检查

CLI 示例：

```powershell
$env:AZURE_TRANSLATOR_KEY="your-key"
python -m mc_mod_i18n translate .\mods --provider azure-translator --api-region global
```

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

如需同时安装桌面窗口依赖：

```powershell
.\scripts\build_exe.ps1 -InstallDesktopDeps -Clean
```

输出：

```text
dist/
└─ mc-mod-i18n/
   ├─ mc-mod-i18n.exe
   └─ _internal/
```

双击启动桌面版：

```powershell
.\dist\mc-mod-i18n\mc-mod-i18n.exe
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

`hardcoded-map.json` 不是资源包文件，单独放进资源包不会让 Java 代码里写死的英文生效。它的用途是作为运行时补丁 Mod / Mixin / 配置模板生成器的输入：补丁在游戏显示文本的入口处按原文查表替换，或把可配置的注释/模板写成目标模组能读取的格式。

仓库内置一个最小 NeoForge 1.21.1 起步模板：`templates/neoforge-hardcoded-patch`。它会读取 `config/mc-mod-i18n/hardcoded-map.json`，并先通过 `ItemTooltipEvent` 替换物品 tooltip 中与原文完全匹配的文本。后续可以在这个模板上继续补 Screen、Ponder、配置注释等入口。
