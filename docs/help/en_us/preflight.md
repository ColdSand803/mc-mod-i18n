# Preflight Checks

## What preflight checks do

- Verify that the input can be read.
- Count source files.
- Check for existing target-language files.
- Estimate the expected output.

## Blocking issues

A blocking issue means the task should not be started as-is. Common causes include:

- Invalid input.
- No translatable source files.
- A file structure that does not match the expected layout.

## Warnings

A warning means the task can continue, but the output may be incomplete or may need manual review.

## Recommended workflow

Read the summary first, then inspect the message list. Fix blocking issues before warnings.

Related documents:

- [Quick Start](#/docs/quick-start)
- [Output Strategy](#/docs/output-strategy)
- [FAQ](#/docs/faq)
