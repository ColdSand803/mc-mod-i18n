# Translation Memory and Cache

## Separate the three layers

- `checkpoint / result cache`
  - Avoids processing the same batch repeatedly.
  - The `Ignore cache and translate again` option skips this layer.
- `translation memory`
  - Reuses previously accepted short phrases or entries.
  - The `Ignore translation memory hits` option skips only this layer.
- `current configuration scope`
  - Translation memory is not reused globally without conditions.
  - Provider, language direction, and important output-policy changes can affect the hit scope.

## Why results may not change

Common reasons include:

- The task hit normal cache, so no new provider request was made.
- The task hit translation memory, so an older translation was reused.
- The changed setting does not affect that specific entry.

## When to ignore translation memory

- You changed glossary terms and want to confirm the new terms are used.
- You suspect an old low-quality translation keeps being reused.
- You switched from `deep-free` to a higher-quality provider and do not want to reuse early trial output.

## What the settings page can do

- `Refresh memory`
  - Reload translation memory statistics and preview from the current cache directory.
- `Export JSONL`
  - Export all translation memory records for review or external cleanup.
- `Compact and deduplicate`
  - Remove duplicate records to reduce maintenance cost.
- `Clean current configuration`
  - Remove only records in the current scope.
- `Clear memory`
  - Empty the full translation memory file before a broad rerun.

## Recommended troubleshooting order

1. Check whether the result page or report shows `cache hits` or `memory hits`.
2. To retest the current provider, start with `Ignore translation memory hits`.
3. To rerun the full batch, also enable `Ignore cache and translate again`.
4. If the result still looks wrong, inspect the memory preview for the current configuration on the settings page.

Related documents:

- [Output Strategy](#/docs/output-strategy)
- [Results, Reports, and Task History](#/docs/history-and-report)
- [FAQ](#/docs/faq)
