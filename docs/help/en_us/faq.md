# FAQ

## Why does the connection test fail?

- `deep-free`
  - Public free sources may be rate-limited, unreachable, or temporarily changed by a third party.
- `libretranslate`
  - Check that the BaseURL is correct and the instance is online.
- `argos`
  - Confirm that local dependencies and the needed language packages are installed.
- `azure-translator`
  - Check the API key and `Region` first.
- `openai-compatible / anthropic-compatible`
  - Check that the BaseURL, model name, and authentication headers match the server requirements.

## Why did the result not change?

The most common cause is a cache or translation memory hit. Check:

- Whether `Ignore cache and translate again` is enabled.
- Whether `Ignore translation memory hits` is enabled.
- Whether the result page shows `cache hits` or `memory hits`.

For the full explanation, read [Translation Memory and Cache](#/docs/translation-memory).

## Why does history show a task, but the file cannot be opened?

Task history stores records. It does not guarantee that files exist forever.

Common causes:

- The workspace or cache directory changed.
- The output files were deleted.
- The record is old and the files are no longer at the original path.

## Why does the resource pack still contain English?

Separate the issue into two cases:

- The report shows failed or untranslated entries.
  - Continue checking the provider, API logs, and failed items.
- The report looks fine, but English still appears in game.
  - The text is likely hardcoded and outside resource-pack language files.

In the second case, read [Hardcoded Text Scan and Workbench](#/docs/hardcoded).

## Which provider should I choose first?

- To verify the workflow: `glossary` or `deep-free`.
- For a stable free setup: a self-hosted or fixed `libretranslate` instance.
- For fully offline translation: `argos`.
- For stable online translation: `azure-translator`.
- For higher translation quality: an OpenAI-compatible or Anthropic-compatible AI provider.
