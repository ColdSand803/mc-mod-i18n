# Results, Reports, and Task History

## What to check on the result page

- `Output artifacts`
  - Confirm that the resource pack, reports, failed-item exports, or other files were generated.
- `Quality overview`
  - Review successful entries, failed entries, preserved source text, and skipped items.
- `Performance overview`
  - Review duration, cache hits, and translation memory hits.

## What the translation report is for

- Search failed or risky entries.
- Filter by states such as `API failed`, `validation failed`, or `incomplete`.
- Export failed items as JSON for retries or manual work.

## What task history is for

- Recover download links for recent tasks.
- Open the matching report for further investigation.
- Check whether a task completed, failed, or was interrupted.

If history says the file no longer exists, the usual causes are:

- The task directory was cleaned or moved.
- The workspace or cache directory changed.
- The history entry is old and the original local files are gone.

## When to inspect API logs

Open API logs first when:

- Provider connection tests fail.
- The report still has obvious missing entries.
- You suspect rate limits, timeouts, or authentication failures.
- The same task gives unstable results across retries.

If the result came entirely from cache, the API log may be empty. That is expected.

## Recommended troubleshooting order

1. Read the result summary to identify failure, skip, or cache-hit behavior.
2. Open the translation report to locate specific entries.
3. Check API logs if the provider may be involved.
4. Use task history when you need to trace old output files.

Related documents:

- [Translation Memory and Cache](#/docs/translation-memory)
- [FAQ](#/docs/faq)
