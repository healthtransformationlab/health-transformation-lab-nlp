---
pr: (see the PR for #601)
branch: chore/601-erd-dictionary-format
title: "000 CHORE44: every ERD in the data-dictionary format, with the entity view in the same layout"
author: claude (agent session)
reviewed_at: 2026-11-05
reviewer: coordinator review against .claude/review-rubric.md
verdict: approve
---

# PR Review: 000 CHORE44: every ERD in the data-dictionary format, with the entity view in the same layout

## Summary
Every ERD now has two draw.io views in the owner's data-dictionary format (`dictionary_erd.py`, #379, #403): gold,
Open Dental silver and OMOP silver. The **full** view has subject areas, row count and grain, and every column with
its type and meaning, plus a profile for silver. The **entity** view keeps that arrangement (the same subject areas in the same
page columns, tables in the same order), each table cut to its header and key columns and each area shrunk to fit (keys, and every column a relationship
joins on, so each line has a row to meet). The gold model gains subject areas (from its existing areas), kinds by its
prefixes (fact, dimension, summary) and `PROFILE = False`, since its rows live in Databricks. The separate
`_dictionary` files are gone, because `_full` is that format now. The old grid writer is removed: nothing called it.
Verdict: approve.

## Scope of Change
- Areas touched: diagrams (`_build/` writers, regenerated `.drawio`, `.mmd`, `.png`, `data_model.md`), python tests
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| python and the rest | see the PR; green before merge |

## Secrets, PHI and Claims Scan
Clean. The diagrams show synthetic data only.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- First pass kept the full views' exact positions; the owner asked for less empty space, so the entity view now keeps
  the full view's arrangement (same subject areas in the same page columns, tables in the same order) with each table
  sized to its keys and each area shrunk to fit: the Open Dental entity PNG went from 11,670 × 10,638 px to
  6,054 × 4,078, gold from 8,060 × 12,590 to 5,240 × 4,512. A test checks the arrangement is the same and the areas
  take under 60% of the full view's.
- The PNGs were rendered with draw.io's viewer script fetched from jgraph/drawio on GitHub and served locally
  (`VIEWER=`, render.md), because viewer.diagrams.net is blocked from the agent sandbox. The output is the same viewer.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | ✅ | `tests/test_erd_format.py`: 11 tests failed before the change and pass after |
| Generated files current | ✅ | `gold_erd.py` and `silver_erd.py` rerun; `.mmd` and `data_model.md` checked by tests |
| Commits | ✅ | |

## Test Coverage
Full suite: 2173 passed and 32 skipped. One local error, in `test_digests.py`: the `pipeline_doctor` package isn't
installed in this sandbox. It's unrelated, and CI installs it. `ruff check` is clean on the changed files.

## Verdict
approve: merge once CI is green.
