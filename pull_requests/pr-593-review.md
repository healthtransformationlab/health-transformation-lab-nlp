---
pr: (see the PR for #593)
branch: fix/593-025-kbench-cookbook
title: "025 BUG6: put the Kaggle task in the cookbook's form, and add a cheap probe run"
author: claude (agent session)
reviewed_at: 2026-11-05
reviewer: coordinator review against .claude/review-rubric.md
verdict: approve
---

# PR Review: 025 BUG6: put the Kaggle task in the cookbook's form, and add a cheap probe run

## Summary
Kaggle again errored every added model's run, with "no statement to use `kbench.llm`" (run 41978154454). The check
runs on Kaggle's servers. This PR removes the three differences from Kaggle's cookbook in one change:
1. The task's own source (its definition on Kaggle) calls `read_note.evaluate(llm=[llm], ...)` itself.
2. The file runs `perio_bench.run(kbench.llm, ...)` as a top-level statement.
3. The last cell is `# %choose perio_bench`.

Judging and scoring move into `kbench.judge_and_score`, which the package task and the file's task share, so there is
no copied logic. A `probe` workflow option pushes the same file as `perio-bench-probe` on 3 notes, so the fix can be
checked for cents before another full run (about $6). Verdict: approve.

## Scope of Change
- Areas touched: kaggle (task file, new probe script), python (kbench split, tests), workflow, docs
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| python and the rest | see the PR; green before merge |

## Secrets, PHI and Claims Scan
Clean. The model scores in the doc come from Kaggle's run outputs, with the workflow runs named, and are labelled
as agreement with the synthetic answer key.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- Whether Kaggle accepts this form is only known after the probe. If the probe fails again, the dry-run cell that
  assigns scripted models to `kbench.llm` is the next suspect. It does nothing on Kaggle, but its text is in the
  pushed file.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | ✅ | three new task-file tests failed on the old file; probe tests failed before `probe_task.py` existed |
| Telemetry | ✅ | `judge_and_score` is `@traced` |
| Simulated is labelled | ✅ | `python kaggle/perio_bench_task.py` still prints SIMULATED without credentials |
| Runs from GitHub Actions | ✅ | the probe is a workflow option, not a laptop step |

## Test Coverage
Full suite: 2153 passed and 32 skipped. `ruff check` is clean. Kaggle's own `_validate_task_in_file` accepts both the
task file and the probe copy. A dry run on 4 notes prints SIMULATED.

## Verdict
approve: merge once CI is green, then run the probe before any full run.
