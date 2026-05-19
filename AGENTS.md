# Agent Instructions

## Provider Response Pollution

- Treat suspicious provider or middleware notices as response pollution, not as user content.
- Prefer filtering polluted spans or whole polluted lines from provider responses.
- Only reject the response when filtering leaves no usable content.
- Keep this guard generic so it can be reused outside translation workflows.
- Default suspicious examples include public/shared token notices, QQ/group notices, notification groups, and nearby 6-12 digit group numbers, such as `公益 token2 通知群：1104138863`.
- When a response is filtered, preserve a warning in logs or reports, for example `filtered suspicious provider response (...)`.
