---
pr: 275
branch: docs/274-no-overstated-absolutes
title: "Replace overstated absolutes such as \"Nobody can count it\""
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator (wording in decks and README, one test, cover image)
verdict: approve
---

# PR Review: Replace overstated absolutes

## Summary
This PR replaces absolute claims about the world ("Nobody can count it", "can't be linked", "Nobody publishes") with
accurate, scoped wording. It rebuilds both decks and re-renders the landing cover. Verdict: approve.

## Scope of Change
- Commits: e186638
- Range reviewed: `origin/main..e186638`

## Rubric
- **Claims scoped and supportable:** "hard to count" matches the evidence (Patel 2020: 47% agreement between
  sources). "We found no ..." states a search, not a fact about the world.
- **Wording rule** (`test_wording.py`): passes. No "diagnose" phrasing added.
- **Built files match their sources:** `test_decks.py` passes after `build_decks.py`.
- **Tests first:** the new test failed before the edits.

## CI Status
| Check | Status |
|---|---|
| python | 1055 passed, 15 skipped locally |
