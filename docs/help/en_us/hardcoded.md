# Hardcoded Text Scan and Workbench

## What hardcoded English means

Not all English text comes from `lang/*.json`.

Some text may be written directly in:

- Java code
- Ponder scenes
- Configuration comments
- UI hints

This text will not automatically change just because a resource pack was translated.

## What scanning hardcoded English produces

- `hardcoded-report.html`
  - Helps confirm candidate text sources and risk levels.
- `hardcoded-map.template.json`
  - Can be completed manually or imported into the workbench for editing.

After generation, the Web UI can also show the hardcoded mapping workbench.

## What the workbench can do

- Filter candidates by category and keyword.
- Fill in `translation` manually.
- Import an existing `hardcoded-map.json` and continue editing.
- Export a mapping file that contains only completed entries.

## Why exported mappings may not change the game

`hardcoded-map.json` is not a resource-pack language file.

It must be read by one of the following before text can be replaced at runtime:

- A runtime patch mod.
- A Mixin.
- A configuration template generator.

## When to use this feature

- The resource pack was generated, but scattered English text remains in game.
- The report looks complete, but tutorials, tooltips, or configuration text still show English.
- You are working with Ponder content or modpack configuration content.

Related documents:

- [Output Strategy](#/docs/output-strategy)
- [Results, Reports, and Task History](#/docs/history-and-report)
- [FAQ](#/docs/faq)
