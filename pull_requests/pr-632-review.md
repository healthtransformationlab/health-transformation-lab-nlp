---
pr: 632
branch: fix/631-029-plan-date-undated-status3
title: "029 BUG1: fix four tooth-table rules (plan date, undated extraction, status 3, blanked measures)"
author: jcbowyer
reviewed_at: 2026-11-07
reviewer: read-only reviewer subagent + coordinator verification
verdict: approve
---

# PR Review: 029 BUG1: fix four tooth-table rules

## Summary
Fixes four defects in `tooth_loss.py` found by a line-by-line review against the study lead's rules: the plan date
was the first plan not the latest copy, an undated completed extraction read exams after the loss, ProcStatus 3 was
ignored, and the missing-at-entry mask was applied after re-sorting merges and blanked a quarter of charted present
teeth. Each has a test that fails on `main` and passes here (verified by loading main's module). The R twin applies
the same rules; the reviewer's one Critical finding (R crashed on zero planned rows, the US11 parity case) is fixed in
the second commit. Approve once CI is green on the head commit.

## Scope of Change
- Files changed: 10 (+~190 / -~60 excluding generated data)
- Areas touched: python / r / specs / data (parity inputs regenerated, treatplan.csv added)

## Findings
| Severity | Where | Finding | Status |
|---|---|---|---|
| Critical | `r/R/16_spec029.R` plan dates | `mapply` over zero planned rows returns a list; `as.Date` errors; `r-parity` red on the first commit | fixed (guarded; `as.Date(character(0))`) |
| Minor | `tooth_loss._plan_copy_dates` | annotated `pd.Series`, returns a DataFrame | fixed |
| Minor | `specs/029-tooth-loss/spec.md` | window default still read 365 | fixed |

## Compliance
| Rule | Result |
|---|---|
| No secrets | none in the diff, CSVs scanned |
| Synthetic only, no PHI | seeded synthetic ids and dates only; `data/raw/` untouched |
| No organization claims | none; wording and org-reference tests pass |
| Test first | four new tests, each fails on `main` |
| Python and R in parity | both twins changed; parity inputs regenerated; CI `r-parity` on the head commit |
| Spec | FR-013 updated with the three label-rule changes |
| Commits | imperative, body says why, co-author trailer |

## Checks
- `pytest -q tests/test_tooth_loss.py tests/test_tooth_loss_model.py tests/test_tooth_loss_dq.py`: pass
- `ruff check` on the changed Python: clean
- Full suite: CI (`test_digests.py` needs `pipeline-doctor`, not installed locally)

## Notes
- The committed synthetic model results were produced with the blanked-measures defect; they are not regenerated
  here. The next model run will show the difference.
- Merge: an agent may merge its own PR when green (AGENTS.md rule 6); nothing here runs on limited compute or
  publishes outside the repo.
