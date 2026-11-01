---
pr: 245
branch: ci/244-required-checks-docs-prs
title: "Report every CI check on docs-only pull requests"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator (3 files; no subagent needed)
verdict: approve
---

# PR Review: Report every CI check on docs-only pull requests

## Summary
Docs-only PRs never started `ci.yml` (`paths-ignore`), so its checks couldn't be required on `main`. The workflow
now always runs on PRs. `python` always runs (it also tests the docs, which docs-only PRs used to skip), and
`postgres`, `azure-infra` and `bundle` skip when only Markdown or images changed. Docs-only pushes to `main` still
skip CI. Verdict: approve.

## Scope of Change
- Files: `.github/workflows/ci.yml`, `.github/scripts/parity_needed.py`, `python/tests/test_parity_needed.py`
- Range reviewed: `origin/main..HEAD`

## Secrets, PHI and Claims Scan
Clean.

## Repo Rules
| Rule | Status |
|---|---|
| Test first | ✅ the 11 new cases failed before the change |
| Configuration | ✅ no settings; the PR names the ruleset to add after merge |
| Wording | ✅ |

## Findings
🔵 Docs-only PRs now take about 2.5 minutes longer (the Python tests). That's the point: those tests read the docs.

## Checks run
- `cd python && pytest -q tests`: 982 passed, 15 skipped; `ruff check` clean.
- `parity_needed.py` on `9ec926c`, `2533942`, `81444d1`: false/false, true/true, false/true as expected.
