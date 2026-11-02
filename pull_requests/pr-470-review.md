---
pr: 470
branch: fix/469-nhanes-edentulous-exam-status
title: "Count only examined adults with no teeth as edentulous in NHANES"
author: johncbowyer
reviewed_at: 2026-11-02
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: Count only examined adults with no teeth as edentulous in NHANES

## Summary
Closes #469. The first run against the real cdc.gov NHANES 2009–2014 files counted ~1,580 adults 30+ whose dentition
exam was not done (`OHDDESTS` 3, every tooth code blank) as edentulous, giving 16.3% against Tay 2025's 6.7%.
`classify_people` now requires a completed dentition exam with every natural tooth coded and none present, and fails
on a missing `OHDDESTS` column. The reviewer re-ran the pipeline on the real files: the committed CSV reproduces
exactly (n_domain 11,796, edentulous 6.9%), and the new tests fail on the base commit and pass on HEAD. Two minor
wording nits were found and fixed on the branch. Verdict: approve-with-nits.

## Scope of Change
- Files changed: 4 code/docs files (+~40 / -~8), plus 2 generated aggregate CSVs (`data/datasets/nhanes/`, 50 lines)
- Areas touched: python, docs, data
- Commits:
  - 24ce427 Count only examined adults with no teeth as edentulous in NHANES
  - (this review) Match the edentulous comment and domain docstring to the code; record the review of PR #470
- Range reviewed: `merge-base(origin/main)..24ce427`

## CI Status
| Check | Status |
|---|---|
| check (PR conventions) | success |
| changes | success |
| postgres | success |
| bundle | success |
| azure-infra | success |
| python | in progress at review time |
| r-parity | in progress at review time |

## Secrets, PHI and Claims Scan
- Secrets: clean (grep for keys, tokens, credentialed URLs over the full diff).
- PHI / real data: clean. The CSVs are survey-weighted aggregates of public-domain CDC/NCHS data, with no person-level
  rows; the raw XPT files are not committed.
- Organization claims: clean. The published comparison figures cite Eke 2018 (PMC8094373) and Tay 2025 (PMC12176459).

## Strengths
- The fix was found by checking against published figures, and the result now lands inside Tay 2025's CIs for
  edentulous, every CDC/AAP category and ACES stages 1–4; dentate CDC/AAP any/severe 42.1%/7.8% vs Eke's 42.2%/7.8%.
- A missing `OHDDESTS` fails loudly, matching the existing `OHDPDSTS` check.
- The remaining gap (ACES non-classified 0.5% vs 0.1%) is recorded on action item B9 rather than hidden.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. `python/health_transformation_lab_nlp/nhanes.py:188` — the comment said every natural tooth was "recorded absent";
   the code checks every code is non-null and none is 2 or 5. Verified by reading the code; codes 1 and 9 never occur
   among adults 30+ in 2009–2014, so outputs are unaffected. **Fixed:** comment reworded to match the code.
2. `python/health_transformation_lab_nlp/nhanes.py:13` (existed before this PR) — the module docstring gave the domain
   as "adults 30+, complete exam", but `adults30_all` also includes the edentulous. **Fixed:** docstring now says
   "adults 30+ with a complete periodontal exam, or edentulous".

Checked and not findings: duplicate `SEQN` (none in any cycle; would raise, not mislead); people in DEMO but not OHXDEN
(not edentulous); `OHDDESTS` 2 (none counted edentulous); implants (code 3) on edentulous people (correctly edentulous);
pandas 3 dtype of `map`/`fillna`/`astype` (no FutureWarning); `adults30_all` and `adults30_dentate` domains in
`scripts/38_nhanes_perio.py` (still right, no NaN categories in either).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | public-domain aggregates only, raw files not committed |
| No organization claims; vendors cited | ✅ | published figures cited |
| Test first | ✅ | new tests fail on the base commit, pass on HEAD |
| Python and R in parity | ✅ | NHANES has no R twin; no label, scoring, reliability or cost change |
| Simulated is labelled simulated | ✅ | results are real public data and labelled REAL |
| Seeds fixed | n/a | no generators |
| Paths | ✅ | output via `DATASETS_DIR` |
| Spec for big changes | ✅ | bug fix with regression test under spec 013 G4 |
| Prices | n/a | |
| Deck figures | n/a | no decks touched |
| Commits | ✅ | imperative, body says why, co-author trailer |
| Docs | ✅ | action item B9 updated |
| Configuration | n/a | no settings change |
| Secrets register | n/a | no credentials |
| Idempotent writes | ✅ | CSVs overwritten |
| Alerts | n/a | |

## Test Coverage
New: a skipped dentition exam, an exam with teeth not all recorded, and a missing `OHDDESTS` column. Run locally:
`pytest -q tests` 1606 passed, 32 skipped; `tests/test_nhanes.py` 10 passed (8 passed, 2 failed on the base commit);
`ruff check` clean; full pipeline re-run on the real cdc.gov files reproduces the committed CSV. R not available here;
CI `r-parity` covers it.

## Verdict
approve-with-nits. Both nits are fixed on the branch. Merge once CI `python` and `r-parity` are green.
