---
pr: 398
branch: feat/397-030-subgroups-stability
title: "030 US2: scores by subgroup, and whether they hold on other test sets"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve-with-nits
---

# PR Review: 030 US2: scores by subgroup, and whether they hold on other test sets

## Summary
Closes checklist items 6 (stability) and 10 (subgroups) for PerioBench on synthetic data. The spec came first, then
tests before code. Seed 42 reproduces the committed leaderboard exactly, which shows the rebuild is faithful. R
recomputes every new number. The full suite passes (1171 passed, 16 skipped). Approve, with nits.

## Secrets, PHI and Claims Scan
Clean. The rebuilds go to a temporary folder; the raw notes with fake identifiers never reach `data/`. Everything is
labelled synthetic.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- **Stability covers only the methods that need no GPU.** The BERT and MedGemma runs aren't repeated across seeds;
  the scoring page says so and points to their bootstrap intervals. A GPU run per seed is a follow-up, if it's wanted.
### 🟢 Nits / Suggestions
- **Five seeds is a small sample for an SD.** The page reports ranges, which read better at this size.
- **Sex isn't generated**, so the subgroup split has no sex row. The checklist says so.

## Rubric
- Spec first (US2, SC-003); tests first; Python/R parity for every new number: yes.
- `@traced` on the new public functions; paths via `paths.py`; seeds fixed.
- `Closes #397`, and the branch is `feat/397-…`.
