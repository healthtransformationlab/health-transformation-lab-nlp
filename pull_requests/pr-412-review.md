---
pr: 412
branch: fix/131-mlflow-none-and-warning
title: "004 BUG1: treat None-like MLflow settings as unset, keep the cause in warnings"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve
---

# PR Review: 004 BUG1: treat None-like MLflow settings as unset, keep the cause in warnings

## Summary
This fixes #131 and the code part of #143, and approves it.
- **#131:** `tracking.setting()` treats `None`, `""`, `"None"` and `"null"` as unset. These all go through it:
  - the experiment and the tracking URI;
  - params, so an unset one is left out instead of being sent as `"None"`;
  - metrics, where anything that isn't a number (including NaN) is dropped.

  MLflow's own `MLFLOW_EXPERIMENT_ID`, `MLFLOW_EXPERIMENT_NAME` and `MLFLOW_RUN_ID`, when set to `"None"`, are cleared
  with a warning. Both notebooks that read the `experiment_name` widget now go through `setting()`. Tracking stays
  optional: if it's misconfigured, it warns and the step carries on.
- **#143:** the "tracking off" warning now keeps both the start and the end of a long error, like the logging-call
  warnings already did, so urllib3's `Caused by ...` survives.

## Tests
- 17 regression tests were written first and failed before the change.
- `tests/test_tracking.py`: 29 passed.
- `-k "tracking or mlflow or telemetry"`: 64 passed, 7 skipped.
- Full suite: 1217 passed, 16 skipped.
- `ruff check` is clean on the changed Python module and its test. The notebooks have lint findings, but none on the
  lines this PR changed.

## Secrets, PHI and Claims Scan
Clean: no credentials, no data and no claims about any organization. The test host names are generic placeholders.

## Findings
None blocking.
- 🔵 **Root cause not confirmed:** the fix is defensive. No traceback named which value carried `"None"`, so every
  path where it could reach MLflow is now guarded. A dev run of the MedGemma reader job will confirm that params and
  metrics log.
- 🔵 **#143 not finished:** its second "Done when" point needs a serverless GPU run, either to make the artifact
  upload or to skip it on purpose once the cause shows in the log. That's why the PR uses `Refs #143`. The same
  predictions are already in `ai_predictions`.

## Rubric
- `@traced` is on the new public `setting`. The helpers are private.
- Test first.
- No new settings and no environment changes.
- No secrets register change.
- The commit is imperative, its body says why, and it has the co-author trailer.
- `Closes #131`, `Refs #143`.
