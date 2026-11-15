---
pr: 802
branch: fix/801-014-azure-flush
title: "014 BUG2: flush Azure spans and say whether each export succeeded"
author: claude
reviewed_at: 2026-11-15
reviewer: coordinator verification against .claude/review-rubric.md
verdict: approve
---

# PR Review: flush Azure spans and say whether each export succeeded

## Checks
| Check | Result |
|---|---|
| Issue #801 with its four parts first; names as its Contract | yes |
| Test first: `test_telemetry_flush.py`, 7 tests, all failed before the change, pass after; telemetry and watcher suites 81 passed, 1 skipped | yes |
| The bug: the `azure` branch of `setup()` never recorded its providers, so neither `_shutdown_providers()` nor anything else flushed them | fixed |
| Global providers are flushed, never shut down here, so a second `setup()` in the same process still sends (the SDK shuts them down at exit) | yes, tested |
| A failed export is visible: `flush()` returns False, the exporter's warnings go to stderr, the watcher prints `telemetry export: FAILED` and a `::warning::` annotation | yes, tested |
| The push trigger can't loop: an unchanged ledger opens no PR | yes |
| No secret printed; telemetry stays optional (flush never raises) | yes |
| `ruff`: no new findings (S110 in `_shutdown_providers` was there before) | yes |

## Findings
### Blocking
None.
### Minor
1. The proof is the next watcher run's log line plus a query of the workspace; the PR can't show Azure receiving data
   from CI. Run the watcher after merging and re-query.

## Verdict
Approve. Merge when CI is green.
