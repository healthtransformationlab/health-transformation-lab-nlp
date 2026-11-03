---
pr: 480
branch: ci/478-pandas2-tests
title: "000 CHORE42: run the Python tests on the Databricks runtime's pandas 2 too"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: coordinator (small CI change with its own test; checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve-with-nits
---

# PR Review: run the Python tests on the Databricks runtime's pandas 2 too

## Summary
Adds a CI job, `python-databricks-runtime`. It runs the whole Python suite on the libraries of Databricks serverless
environment 4: pandas 2.2.3, NumPy 2.1.3, PyArrow 19.0.1, scikit-learn 1.6.1, Python 3.12. They're pinned in
`python/constraints/databricks_serverless.txt`, with the release notes cited. The pandas 3 `python` job is
unchanged. The job does what it is for: on this branch before #477 it reproduces #476 (17 `ValueError: setting an
array element with a sequence` in `test_tooth_loss_dq` and `test_dq_site`). It also found a second case the
runtime breaks: a fold test that only worked with newer scikit-learn, fixed here. Approve. The new job turns green
once #477 is merged and main is merged into this branch.

## Scope of Change
- Files changed: 5 (+81 / -2, excluding this review)
- Areas touched: CI (`.github/workflows/ci.yml`), python tests, new constraints file
- Commits: `b31fecd` 000 CHORE42: run the Python tests on the Databricks runtime's pandas 2 too
- Range reviewed: `origin/main..ci/478-pandas2-tests`

## CI Status
| Check | Status |
|---|---|
| check (PR conventions) | ✅ |
| changes, postgres, azure-infra, bundle | ✅ |
| python (pandas 3) | running at review time; passes locally (below) |
| python-databricks-runtime (pandas 2) | expected ❌ until #477 merges: the #476 failures it was added to catch |
| r-parity | running at review time; no R or scoring change |

## Secrets, PHI and Claims Scan
Clean. No credentials: the only `password` match is the existing Postgres service password `ci`. No data files.
The only vendor statement is Databricks' library versions, and it cites the release-notes page.

## Strengths
- The job pins with a constraints file, not by editing `pyproject.toml`, so the package's own ranges stay as they are.
- `test_ci_databricks_runtime.py` ties the pins to `databricks.yml`'s `gpu_environment_version`. If the bundle moves
  to a new environment version, CI fails until the pins are revisited.
- It's a separate job, not a matrix, so the required `python` check keeps its name.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `python/constraints/databricks_serverless.txt:2`. The CPU notebook jobs don't name an environment version, so they
  run on the workspace's default environment, not necessarily version 4. #476 shows that default has pandas 2, but
  if a workspace moves its default, the pins could drift from it unnoticed. A later change could give the CPU jobs
  an explicit `environment_version` too. Not needed for this PR.
- The version check step asserts only `pandas 2.*`, not the exact pin. pip's `-c` already enforces the exact pin,
  and the step prints both versions in the log.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data touched |
| No organization claims; vendors cited | ✅ | Databricks versions cite the release notes |
| Test first | ✅ | `test_ci_databricks_runtime.py` failed (3 tests) before the job and pins existed |
| Python and R in parity | ✅ | no label, scoring, reliability or cost-effectiveness change |
| Simulated is labelled simulated | n/a | |
| Seeds fixed | ✅ | the fold test keeps `seed=1` |
| Paths | ✅ | `paths.REPO_ROOT` |
| Spec for big changes | n/a | CI chore with an issue (#478); no dataset, metric or label change |
| Commits | ✅ | imperative subject, body says why, co-author trailer |
| Configuration | ✅ | no setting added; no environment changes (CI only) |
| Branch and issue | ✅ | `ci/478-pandas2-tests`, `Closes #478` |

## Test Coverage
Run locally on the branch:
- pandas 3.1.0, scikit-learn 1.9.1, Python 3.13: `pytest -q tests` gave 1645 passed, 5 skipped.
- pandas 2.2.3, NumPy 2.1.3, scikit-learn 1.6.1: full suite before the fold-test fix gave 1624 passed. The failures
  were the 17 from #476 (`test_tooth_loss_dq`, `test_dq_site`) plus `test_folds_missing_a_class_are_skipped_in_tuning`.
  The fold test now passes on both versions.
- This branch merged with #477, on pandas 2.2.3: `test_tooth_loss_dq`, `test_dq_site`, `test_classify_status` and
  `test_ci_databricks_runtime` gave 42 passed.
- `ruff check` is clean on the changed Python files.

## Verdict
Approve with nits. Merge #477 first, then merge main into this branch, so `python-databricks-runtime` goes green
before this PR merges.
