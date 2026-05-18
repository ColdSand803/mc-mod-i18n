# Choosing a Provider

## No-configuration trial

- `deep-free`
  - Does not require an API key.
  - Works well for quick trials.
  - Stability depends on third-party public sources.

## Offline or local options

- `glossary`
  - Fully offline.
  - Performs rule-based replacements only.
- `argos`
  - Local offline translation.
  - Requires local dependencies and language packages.

## Controlled free option

- `libretranslate`
  - Best used with a self-hosted or fixed instance.
  - More controllable than public free web sources.

## Official stable option

- `azure-translator`
  - Requires an API key.
  - Some resource types also require a `Region`.

## Generic AI providers

- `openai-compatible`
- `anthropic-compatible`

These are useful when translation quality matters more than cost.

Related documents:

- [Quick Start](#/docs/quick-start)
- [Preflight Checks](#/docs/preflight)
- [FAQ](#/docs/faq)
