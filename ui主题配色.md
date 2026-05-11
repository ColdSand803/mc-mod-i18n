# UI 主题配色统计

统计日期：2026-05-11  
统计范围：当前运行代码中的主题系统，不把 `stitch设计/` 历史稿、`tests/` 断言和需求文档里的旧方案混入统计。

## 来源文件

- Web 主应用主题：`public/style.css`、`public/js/ui.js`
- 浏览器扩展主题：`extension/popup.css`、`extension/content.css`、`extension/popup.js`、`extension/content.js`
- Android 客户端主题：`android-client/app/src/main/java/com/safevault/mobile/onboarding/OnboardingState.kt`、`android-client/app/src/main/java/com/safevault/mobile/ui/SafeVaultApp.kt`、`android-client/app/src/main/java/com/safevault/mobile/ui/AndroidUiContracts.kt`

## 总览

- Web：30 个主题入口，其中 `system` 是跟随系统的虚拟入口，29 个真实 CSS 主题。
- Android：30 个主题入口，其中 `system` 当前映射为一套灰蓝浅色调，不是直接读取系统明暗色。
- 浏览器扩展：21 个主题入口，其中 `system` 会按系统明暗解析为 `light` 或 `dark`，实际覆盖 20 个真实主题。
- 扩展暂未覆盖 9 个 Stitch 配色：`healing-sea-blue`、`mint-tea-green`、`neon-track`、`cream-berry-purple`、`orange-slate`、`seafoam-apricot`、`klein-gold`、`honey-sunset`、`crimson-ivory`。

## 主题覆盖

| ID | 中文名 | 分组 | Web | Android | 扩展 |
|---|---|---|---|---|---|
| `system` | 跟随系统 | 基础主题 | 是，解析为明/暗 | 是，灰蓝浅色映射 | 是，解析为明/暗 |
| `light` | 默认浅色 | 基础主题 | 是 | 是 | 是 |
| `dark` | 默认深色 | 基础主题 | 是 | 是 | 是 |
| `forest` | 森林安全 | 专注主题 | 是 | 是 | 是 |
| `midnight` | 午夜蓝 | 专注主题 | 是 | 是 | 是 |
| `dongbei-rain` | 东北雨 | 趣味主题 | 是 | 是 | 是 |
| `rainbow-rgb` | 彩虹 RGB | 趣味主题 | 是 | 是 | 是 |
| `bleach-tybw` | 死神:千年血战 | 联名主题 | 是 | 是 | 是 |
| `eva` | EVA | 联名主题 | 是 | 是 | 是 |
| `starry-night` | 梵高星空 | 艺术主题 | 是 | 是 | 是 |
| `monet` | 莫奈 | 艺术主题 | 是 | 是 | 是 |
| `qingming-scroll` | 清明上河图 | 艺术主题 | 是 | 是 | 是 |
| `cezanne` | 塞尚 | 艺术主题 | 是 | 是 | 是 |
| `sisley` | 西斯莱 | 艺术主题 | 是 | 是 | 是 |
| `pissarro` | 毕沙罗 | 艺术主题 | 是 | 是 | 是 |
| `morandi` | 莫兰迪 | 艺术主题 | 是 | 是 | 是 |
| `gauguin` | 高更 | 艺术主题 | 是 | 是 | 是 |
| `matisse` | 马蒂斯 | 艺术主题 | 是 | 是 | 是 |
| `qi-baishi` | 齐白石 | 艺术主题 | 是 | 是 | 是 |
| `p-site` | P站 | 联名主题 | 是 | 是 | 是 |
| `healing-sea-blue` | 治愈海盐蓝 | Stitch 配色 | 是 | 是 | 否 |
| `mint-tea-green` | 薄荷茶青 | Stitch 配色 | 是 | 是 | 否 |
| `neon-track` | 荧光赛道绿 | Stitch 配色 | 是 | 是 | 否 |
| `cream-berry-purple` | 奶油莓紫 | Stitch 配色 | 是 | 是 | 否 |
| `orange-slate` | 橙灰机能 | Stitch 配色 | 是 | 是 | 否 |
| `seafoam-apricot` | 海风杏桃 | Stitch 配色 | 是 | 是 | 否 |
| `klein-gold` | 克莱因金 | Stitch 配色 | 是 | 是 | 否 |
| `honey-sunset` | 蜜糖落日 | Stitch 配色 | 是 | 是 | 否 |
| `crimson-ivory` | 酒红象牙 | Stitch 配色 | 是 | 是 | 否 |
| `sakura-mist` | 樱雾灰紫 | Stitch 配色 | 是 | 是 | 是 |

## 核心主题色值

表内色值以 Web `public/style.css` 为主。Android 的 `webThemeColorScheme(...)` 使用同一组核心色，但把半透明 `surface` 简化为不透明色；扩展的 `popup.css` / `content.css` 只覆盖前 20 个真实主题，并使用 `--sv-*` 前缀。

| ID | Accent | Accent Strong | Signal | Danger | BG | BG Deep | Ink | Muted | Surface | Surface Dark |
|---|---|---|---|---|---|---|---|---|---|---|
| `light` | `#2563eb` | `#1d4ed8` | `#059669` | `#dc2626` | `#f8fafc` | `#e2e8f0` | `#0f172a` | `#475569` | `rgba(255, 255, 255, 0.86)` | `#f1f5f9` |
| `dark` | `#38bdf8` | `#7dd3fc` | `#34d399` | `#f87171` | `#020617` | `#0f172a` | `#f8fafc` | `#cbd5e1` | `rgba(15, 23, 42, 0.86)` | `#1e293b` |
| `forest` | `#2f6b3f` | `#1f4d2b` | `#0f766e` | `#b54432` | `#f3f7f0` | `#e6efe2` | `#172313` | `#53624d` | `rgba(255, 255, 255, 0.88)` | `#e6efe2` |
| `midnight` | `#4f8cff` | `#7aa7ff` | `#4fd1c5` | `#fb7185` | `#07111f` | `#020617` | `#eaf2ff` | `#9fb1c8` | `rgba(14, 27, 46, 0.88)` | `#14243a` |
| `dongbei-rain` | `#c9162f` | `#f2f0e9` | `#3f7f35` | `#e34f86` | `#4d2f1f` | `#2f1c14` | `#fffaf0` | `#e2cfc0` | `rgba(99, 45, 39, 0.86)` | `#5b3022` |
| `rainbow-rgb` | `#00d4ff` | `#ffffff` | `#00ff85` | `#ff3366` | `#070711` | `#02040d` | `#f8fbff` | `#b9c7da` | `rgba(10, 14, 28, 0.88)` | `#101427` |
| `bleach-tybw` | `#e6397c` | `#ff78ad` | `#f8f4f7` | `#ff477e` | `#1a1a1d` | `#0d0d10` | `#fff7fb` | `#c9b8c1` | `rgba(31, 31, 36, 0.88)` | `#141418` |
| `eva` | `#b7ff2a` | `#8b5cf6` | `#ff9f1c` | `#ff4fb3` | `#090812` | `#030208` | `#f6ffe8` | `#d3c6ff` | `rgba(18, 14, 34, 0.9)` | `#0c0918` |
| `starry-night` | `#f6c945` | `#ffe27a` | `#5eead4` | `#fb7185` | `#07142e` | `#030817` | `#f8efcb` | `#b8c7e6` | `rgba(13, 31, 63, 0.88)` | `#162d58` |
| `monet` | `#6b9f8a` | `#4e806f` | `#5d927d` | `#b85f73` | `#eef4f2` | `#dcebe8` | `#243a3a` | `#60706b` | `rgba(255, 255, 250, 0.86)` | `#e4efeb` |
| `qingming-scroll` | `#2f6673` | `#1e4c57` | `#5f7f4f` | `#b34a32` | `#f3e8d2` | `#e4d2ad` | `#2a241b` | `#6d6253` | `rgba(255, 249, 235, 0.9)` | `#eadbbb` |
| `cezanne` | `#8f4f2f` | `#6f3a22` | `#5e7a4d` | `#a64735` | `#efe6d8` | `#d7c4aa` | `#2f241d` | `#685b4f` | `rgba(255, 249, 238, 0.9)` | `#e0cfb6` |
| `sisley` | `#5f8fa8` | `#3f718a` | `#6b946d` | `#a85d55` | `#eef4ef` | `#d7e5dc` | `#24343a` | `#5d6d70` | `rgba(250, 254, 251, 0.88)` | `#dcebe3` |
| `pissarro` | `#7f8f4e` | `#5f6f35` | `#607e4a` | `#a05742` | `#f1eddf` | `#ded5ba` | `#2d2a1e` | `#675f4c` | `rgba(255, 252, 239, 0.9)` | `#e5ddc4` |
| `morandi` | `#8d8580` | `#6f6662` | `#748375` | `#a06b68` | `#eeece8` | `#d9d5cf` | `#2f2d2b` | `#66615c` | `rgba(250, 248, 244, 0.9)` | `#dfdbd4` |
| `gauguin` | `#b65f2a` | `#8f431f` | `#247a72` | `#b33b4b` | `#f1e0c2` | `#d6ad73` | `#2c2117` | `#6e5944` | `rgba(255, 246, 224, 0.9)` | `#e8c790` |
| `matisse` | `#2468c9` | `#174d9b` | `#1f8f78` | `#d33732` | `#f4efe5` | `#d8e0e8` | `#18243a` | `#536176` | `rgba(255, 252, 244, 0.9)` | `#e2e8ef` |
| `qi-baishi` | `#b7352d` | `#8d251f` | `#386a55` | `#9f2f2a` | `#f6f0e3` | `#e3d7c1` | `#211f1b` | `#635c52` | `rgba(255, 252, 243, 0.92)` | `#e8dec9` |
| `p-site` | `#ff9900` | `#f2b400` | `#f2b400` | `#ff4d4d` | `#050505` | `#000000` | `#f7f7f7` | `#b8b8b8` | `rgba(22, 22, 22, 0.92)` | `#101010` |
| `healing-sea-blue` | `#0081ff` | `#005ec4` | `#a79f00` | `#d34f4f` | `#eef7ff` | `#d8ecff` | `#08204a` | `#4d6280` | `rgba(255, 255, 255, 0.88)` | `#dbefff` |
| `mint-tea-green` | `#178b85` | `#0f6d68` | `#4f8f4f` | `#b85f73` | `#eefaf7` | `#d0efea` | `#173a36` | `#55706b` | `rgba(255, 255, 250, 0.88)` | `#dff3ee` |
| `neon-track` | `#00fd00` | `#0947fe` | `#2cff5a` | `#ff3d7a` | `#07180b` | `#020a04` | `#efffee` | `#b7d7c1` | `rgba(9, 24, 15, 0.9)` | `#0d2316` |
| `cream-berry-purple` | `#652c97` | `#4c1f74` | `#c85c8b` | `#b63f65` | `#fff0f2` | `#f3d7df` | `#2d183a` | `#745d7e` | `rgba(255, 250, 251, 0.9)` | `#f7dfe7` |
| `orange-slate` | `#ff7400` | `#ff9a3d` | `#7ad0b1` | `#ff5f55` | `#172728` | `#0d1718` | `#fff2e5` | `#c8d0cc` | `rgba(43, 60, 61, 0.9)` | `#213132` |
| `seafoam-apricot` | `#01847f` | `#006b67` | `#d9775f` | `#c74d5a` | `#effaf7` | `#d3eee9` | `#123936` | `#5c706d` | `rgba(255, 251, 247, 0.9)` | `#f4ded6` |
| `klein-gold` | `#002fa7` | `#ffcf14` | `#e6b800` | `#e05252` | `#f5f8ff` | `#d9e5ff` | `#061a4d` | `#52617b` | `rgba(255, 255, 255, 0.9)` | `#e8efff` |
| `honey-sunset` | `#ff6067` | `#d9434a` | `#d89d00` | `#d9434a` | `#fff7d6` | `#ffeaa0` | `#3b2b19` | `#76694d` | `rgba(255, 252, 238, 0.9)` | `#ffe8a3` |
| `crimson-ivory` | `#990033` | `#740026` | `#7f6a4f` | `#b52a3f` | `#f4eee5` | `#ddcdb7` | `#341019` | `#6f5b57` | `rgba(255, 250, 242, 0.9)` | `#e8dac8` |
| `sakura-mist` | `#535369` | `#3d3d52` | `#b7b7cc` | `#c9617d` | `#ffe3ee` | `#f6d7e4` | `#272333` | `#6f6474` | `rgba(255, 250, 253, 0.9)` | `#eadae3` |

## 特殊主题和固定配色

- `system`：Web / 扩展不是独立配色，按系统明暗解析为 `light` 或 `dark`。Android 当前使用 `#64748b` / `#475569` / `#059669` / `#dc2626` / `#f8fafc` / `#0f172a` / `#475569` / `#ffffff` / `#f1f5f9`。
- `rainbow-rgb`：Web 和扩展额外定义跑马灯渐变，主要色带为 `#ff004c`、`#ff8a00`、`#fff000`、`#00ff85`、`#00c2ff`、`#3b82f6`、`#8b5cf6`、`#ff00d4`。Web 主题菜单预览额外用了 `#ffb800`。
- Android fallback：`SandVeilColorScheme` 是未知主题 fallback，核心色为 `primary #bac3ff`、`primaryContainer #3f51b5`、`tertiary #4edea3`、`background/surface #0b1326`、`surfaceVariant #2d3449`、`outline #8f909e`。
- Android UI 合同色：`AndroidStitchThemeTokens` 固定公开 `darkSurface #0b1326`、`darkSurfaceContainer #171f33`、`darkSurfaceContainerHigh #222a3d`、`primary #bac3ff`、`tertiary #4edea3`。
- 代码块/状态框存在固定色：扩展和 Web 状态输出使用 `#111827`、`#d9e7ff` 一类非主题色，用于日志/状态显示，不属于可切换主题 token。

## Token 口径

Web 主题完整变量包括：`--accent`、`--accent-strong`、`--accent-soft`、`--accent-glow`、`--signal`、`--signal-soft`、`--danger`、`--danger-soft`、`--bg`、`--bg-deep`、`--ink`、`--muted`、`--surface`、`--surface-strong`、`--surface-dark`、`--line`、`--line-strong`、`--shadow`、`--shadow-tight`，部分主题还覆盖 `--workspace-shell-bg`、`--workspace-chrome-bg`、`--workspace-chrome-card-bg`。

扩展主题变量使用同源色值但前缀为 `--sv-*`，例如 `--sv-accent`、`--sv-accent-strong`、`--sv-signal`、`--sv-danger`、`--sv-ink`、`--sv-muted`、`--sv-surface`、`--sv-surface-muted`、`--sv-line`、`--sv-shadow`。Android 主题则通过 `webThemeColorScheme(accent, accentStrong, signal, danger, bg, ink, muted, surface, surfaceDark)` 映射到 Material 3 `ColorScheme`。
