# 常见问题

## 为什么测试连接失败

- `deep-free`
  - 免费公共源可能被限流、网络不可达，或第三方策略临时变化。
- `libretranslate`
  - 先确认 BaseURL 是否正确，实例是否在线。
- `argos`
  - 先确认本机已安装依赖和对应语言包。
- `azure-translator`
  - 优先检查 API Key 和 `Region`。
- `openai-compatible / anthropic-compatible`
  - 优先检查 BaseURL、模型名和认证头是否匹配服务端要求。

## 为什么结果没变化

最常见的是命中了缓存或翻译记忆。先看：

- 是否勾选了 `忽略缓存并重新翻译`
- 是否勾选了 `忽略翻译记忆命中`
- 结果页里有没有 `cache hits` / `memory hits`

需要完整说明时，先看 [翻译记忆与缓存](#/docs/translation-memory)。

## 为什么历史里有任务，但文件打不开

任务历史只保存记录，不保证文件永远存在。

常见原因：

- 工作目录或缓存目录变了。
- 对应产物已被删除。
- 这是旧任务记录，文件已经不在原路径。

## 为什么资源包里还有英文

先区分两类情况：

- 报告里就是失败或未翻译
  - 继续看 provider、API 日志、失败项。
- 报告没问题，但游戏里仍显示英文
  - 很可能是硬编码文本，不属于资源包语言文件。

这时先看 [硬编码扫描与工作台](#/docs/hardcoded)。

## 第一次使用建议选哪个 provider

- 只想跑通流程：`glossary` 或 `deep-free`
- 想稳定免费：`libretranslate` 自托管或固定实例
- 想完全离线：`argos`
- 想要更稳的在线翻译：`azure-translator`
- 想追求更高质量：兼容 OpenAI / Anthropic 的 AI provider
