---
pr: 368
branch: fix/364-025-kbench-build-dir
title: "Create build/ before kaggle b init writes its example task"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-29
reviewer: coordinator verification (a one-line workflow fix with a regression test; no reviewer subagent run)
verdict: approve
---

# PR Review: Create build/ before kaggle b init writes its example task

## Summary
The *Run PerioBench on Kaggle Benchmarks* workflow failed at its first Kaggle step. `kaggle b init` tried to write
`build/example_task.py`, but a fresh runner has no `build/` folder, because `build/` is gitignored. The fix creates
the folder first. A new test, which runs without the Kaggle Benchmarks SDK, checks that every `--example-file`
folder is created before `kaggle b init` runs. Approve.

## Scope of Change
- Files changed: 2 (+30 / -0), plus this review
- Areas touched: ci (workflow), python tests
- Commits: Create build/ before kaggle b init writes its example task; this review
- Range reviewed: `origin/main..fix/364-025-kbench-build-dir`

## CI Status
| Check | Status |
|---|---|
| python, PR conventions | pending when written; see the PR |

## Secrets, PHI and Claims Scan
- Secrets: clean. The workflow still keeps the Model Proxy credentials in the runner's gitignored `.env`.
- PHI / real data: clean.
- Organization claims: clean.

## Strengths
- The cause is traced to the log line (`[Errno 2]` on `build/example_task.py`), and the fix is the smallest one
  that addresses it.
- The test parses the workflow rather than matching a fixed string, so it also covers a later change to the
  example-file path.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Not in this diff: the `models` input defaults to `gemini-2.5-flash`, but the failed run's `kaggle b init`
  listed `google/gemini-3-flash-preview` as the default and didn't list `gemini-2.5-flash`. That list is the
  Model Proxy's, and the leaderboard's slugs may differ (`kaggle b t models`). If the run step then refuses the
  model, that default is the next thing to change.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | |
| Test first | Yes | the new test failed before the fix |
| Configuration | Yes | no settings change; the PR names the affected workflow |
| Commits | Yes | imperative subject, body says why, co-author trailer |
| Branch and issue | Yes | `fix/364-025-kbench-build-dir`, `Closes #364` |

## Test Coverage
`cd python && python -m pytest -q tests`: 1109 passed, 16 skipped. `ruff check` on the new test: clean.

## Verdict
Approve. It can merge once CI is green, then rerun the workflow.
