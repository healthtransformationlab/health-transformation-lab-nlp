---
pr: 277
branch: docs/276-bench-order
title: "Name the benchmarks in one order everywhere: Perio, OralHealth, Access"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-29
reviewer: coordinator verification (mechanical reorder plus one test; no reviewer subagent run)
verdict: approve
---

# PR Review: Name the benchmarks in one order everywhere: Perio, OralHealth, Access

## Summary
The owner asked for one order wherever the benchmarks are named: PerioBench, OralHealthBench, AccessBench. This PR
writes that rule in AGENTS.md and enforces it with a test, as `test_wording.py` does for wording. It also fixes
the places that broke it: one pitch slide and every schema list, which put `access_bench` before
`oral_health_bench`. The Databricks bundle change only reorders YAML keys. I checked that the parsed file is
identical before and after, so no schema is created, renamed or destroyed. Approve.

## Scope of Change
- Files changed: 14, plus this review; `docs/pitch/deck.html` and its full text are rebuilt outputs
- Areas touched: AGENTS.md, python (schemas, tests), databricks (bundle order, comment), docs, specs
- Commits: 7a9b137 Name the benchmarks in one order everywhere: Perio, OralHealth, Access; this review
- Range reviewed: `origin/main..docs/276-bench-order`

## CI Status
| Check | Status |
|---|---|
| python, bundle, postgres, PR conventions | pending when written; see the PR |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean.
- Organization claims: clean. The benchmark descriptions are the owner's own words.

## Strengths
- The test reads every tracked file in every spelling, with a layer prefix allowed (`gold_access_bench`). It only
  counts names joined like a list (punctuation, "and", "or", "then"), so prose that names two benchmarks in a
  sentence passes. Both cases have parametrised examples.
- The bundle reorder is proved safe: `yaml.safe_load` gives the same mapping before and after, and
  `test_bundle.py` compares the schemas as a dict.
- The owner's quoted words in spec 022's **Input** line are kept as written, through a marked exception.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The test catches a list on one line only. A list that wraps across lines (the AGENTS.md Conventions line,
  `databricks.yml`'s comment) wasn't caught and was fixed by hand. `test_the_schemas_follow_the_order` covers
  the code path. A cross-line check would also flag wrapped prose, so it isn't worth its false positives.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | |
| Synthetic only, no PHI | Yes | |
| Test first | Yes | three of the new tests failed before the fix, listing seven spots |
| Python and R in parity | n/a | no labels or scoring |
| Configuration | Yes | no setting changes; bundle resources are the same; the PR says no environment changes |
| Docs | Yes | decks rebuilt with `docs/build_decks.py` after editing the slide |
| Commits | Yes | imperative subject, body says why, co-author trailer |
| Branch and issue | Yes | `docs/276-bench-order`, `Closes #276` |

## Test Coverage
`cd python && python -m pytest -q tests`: 1068 passed, 15 skipped. `ruff check` on the changed files: one
`re.I` warning on `test_decks.py:102`, which is already on main and not in this diff.

## Verdict
Approve. It can merge once CI is green. Still to do, outside this repo: the website's order, and the GitHub
repository description.
