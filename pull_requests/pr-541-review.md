---
pr: (see the PR for #541)
branch: fix/541-025-task-decorator
title: "025 BUG4: declare the perio-bench task in the file Kaggle pushes"
author: claude (agent session)
reviewed_at: 2026-11-04
reviewer: coordinator review against .claude/review-rubric.md (small diff, 3 files)
verdict: approve
---

# PR Review: 025 BUG4: declare the perio-bench task in the file Kaggle pushes

## Summary
Kaggle's CLI refused to push `kaggle/perio_bench_task.py` ("No @task decorators found"; run 41781245301): it parses the
pushed file for a function decorated `@task` named after the slug. The file now declares
`@kbench.task(name="perio-bench")`, and its body is the package's `perio_bench.func`, so tests and Kaggle run the same
code. A new test parses the file the way the CLI does. It failed before the fix and passes after. Kaggle's own
`KaggleApi._validate_task_in_file("perio-bench", ...)` also accepts the file. Verdict: approve.

## Scope of Change
- Files changed: 3 (task file, test, this review)
- Areas touched: kaggle, python tests
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| python (runs test_kbench.py since #539) | see the PR; green before merge |

## Secrets, PHI and Claims Scan
Clean.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The test mirrors the CLI's parser rather than importing it, because `import kaggle` authenticates at import time and
  CI has no Kaggle credentials. If Kaggle changes its parser, the next push will fail loudly at the same step.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | ✅ | `test_task_file_defines_the_task_the_cli_pushes` failed first |
| Simulated is labelled | ✅ | the dry run still prints SIMULATED |
| Commits | ✅ | |

## Test Coverage
`tests/test_kbench.py`: 16 passed. A dry run on 5 notes writes one `perio-bench` run file plus the per-note files.
`ruff check` is clean.

## Verdict
approve: merge once CI is green.
