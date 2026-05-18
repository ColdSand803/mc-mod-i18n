# Output Strategy

## Overwrite existing target-language entries

Enable this when the target JAR already contains target-language entries and you want the new output to replace them.

## Skip JARs that already contain the target language

This is useful in batch jobs where you want to avoid repeating work for files that already contain the target language.

## Ignore cache and translate again

This skips checkpoint and result cache data, forcing the current batch to be processed again.

## Ignore translation memory hits

This skips only translation memory reuse. Normal checkpoint or result cache behavior is not changed. Use it when you suspect an old translation is being reused from memory.

## Scan hardcoded English text

This also produces a hardcoded text report and mapping template. Use it when English text may exist outside resource-pack language files.

Related documents:

- [Translation Memory and Cache](#/docs/translation-memory)
- [Hardcoded Text Scan and Workbench](#/docs/hardcoded)
- [Preflight Checks](#/docs/preflight)
