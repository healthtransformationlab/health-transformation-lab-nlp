---
pr: 514
branch: ci/510-000-parallel-pytest
title: "000 CHORE43: run the Python test suite in parallel in CI (pytest-xdist)"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: coordinator (CI and dev-extra change only; checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: run the Python test suite in parallel in CI

## Summary
The `python` and `python-databricks-runtime` jobs run `cd python && pytest -q -n auto tests`, and `pytest-xdist>=3.5`
joins the `dev` extra. `test_ci_databricks_runtime.py` checks that both jobs run the whole suite with `-n auto`.

## Checks
- **Whole suite, not a subset:** the command still names `tests`; nothing is skipped, xfailed or deleted.
- **Safe in parallel:** `python -m pytest -q -n 4 tests` passed three times in a row (1900 passed, 16 skipped), and
  once serially with the same counts. `git status` was clean after every run, so no test writes a committed file.
  No test needed changing.
- **Constraints file:** `python/constraints/databricks_serverless.txt` pins only runtime libraries, so it is
  unchanged; the runtime job still installs with `-c` and asserts pandas 2.
- **CI time (pytest step):** `python` 8m34s on main to 5m38s; `python-databricks-runtime` 6m05s to 4m27s.
- **Rules:** branch `ci/510-...`, `Closes #510`, no settings, secrets or environments change, no code or result
  changes, so Python/R parity is unaffected.

## Verdict
Approve. Nothing blocking.
