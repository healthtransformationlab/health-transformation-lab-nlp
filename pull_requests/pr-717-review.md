---
pr: 717
branch: fix/677-r-parity-timeout-retry
title: "Stop the R parity job hanging, and retry installing R"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator
verdict: approve
---

# PR Review: Stop the R parity job hanging, and retry installing R

## Summary

On November 11 the `r-parity` job hung for up to six hours, and then failed, because the runner couldn't install R.
This PR gives the job a 30-minute limit and refreshes the package lists with retries before installing R. It gives
`setup-r` its own 10-minute limit and one retry. A new test reads the workflow and checks all three. The issue's open
question for the owner moves to #715. Closes #677. Approve once `r-parity` itself passes on this PR, which also
confirms the runner has recovered.

## Scope of Change

- Files changed: 2: `.github/workflows/ci.yml` (job `r-parity`) and new `python/tests/test_ci_r_parity.py`.
- Areas touched: CI and tests. No Python package code, no data, no settings.

## CI Status

To be read on the PR's latest commit before merging. `r-parity` must run and pass: `ci.yml` is a parity input, so
it runs.

## Findings

None blocking, none to fix. One note: the retry repeats `setup-r` as a second step rather than looping inside one.
That's because an action can't be retried by itself in GitHub Actions. The `if:` on the second step names the first
step's `id`, and the test checks that link.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue and branch | Yes | `fix/677-...`; `Closes #677` |
| Test first | Yes | The 3 new tests failed before the workflow change and pass after |
| Settings change by PR | Yes | CI only; no environment or runtime setting changes |
| Words and names | Yes | No banned organisation name, no phrases from the wording list |

## Verdict

Approve, and merge when every check, `r-parity` included, is green on the latest commit.
