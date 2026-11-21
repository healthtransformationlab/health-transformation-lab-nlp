---
pr: 903
branch: fix/875-042-deid-extra
title: "042 AI1: declare the de-identification rerun's dependencies as a pyproject extra"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator (rubric scan + local pytest + pip install)
verdict: approve
---

# PR Review: 042 AI1 deid pyproject extra

## Summary
Declares a `deid` optional-extra so `76_deid_drivers.py --rerun` is installable without
hand-picked packages; updates the script docstring and the Databricks de-id notebook to use
it. Approve — no blocking findings. Full CPU `--rerun` is optional verification, not a merge gate.

## Scope of Change
- Files changed: 5 (+47) plus this review
- Areas touched: python/pyproject, scripts, deid module note, databricks notebook, tests
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| check / python / others | pending at review write; re-check before merge |

## Secrets, PHI and Claims Scan
- Secrets: clean
- PHI / real data: clean (deps only; synthetic challenge set unchanged)
- Organization claims: clean

## Strengths
- Wheel URL matches `06_deid_benchmark.py`
- `--check` path still needs no extra
- Local `pip install -e ".[deid]"` succeeded

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- Full `--rerun` (~25 min) was started to confirm scores.csv reproduction; declaration is still correct if that run is deferred.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | yes | `test_deid_extra.py` failed before the extra existed |
| Spec for big changes | n/a | dependency declaration chore |
| Config declared once | yes | one extra name |

## Test Coverage
`pytest tests/test_deid_extra.py` passed; `pip install -e ".[deid]"` succeeded.

## Verdict
**approve** — merge when CI is green on the latest commit.
