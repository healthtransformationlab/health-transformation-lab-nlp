---
pr: 574
branch: feat/567-029-perio-codes-f1
title: "029 US11: perio by the study lead's codes, adult teeth only, and F1"
author: jcbowyer
reviewed_at: 2026-11-04
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 029 US11: perio by the study lead's codes, adult teeth only, and F1

## Summary
The tooth-loss label now reads the diagnosis item's code: PE1-PE4 and P1-P4 are periodontal (`open_dental.PERIO_CODES`,
`open_dental.diagnosis_classes`). Any other recorded diagnosis is another reason, and no diagnosis is none. The
synthetic lists carry those codes. F1 joins the classification measures, and a test pins that only permanent teeth 1-32
reach the tooth table. The R twin and a hand-worked parity block follow. The full synthetic run gives unchanged
numbers, as expected, plus F1. The reviewer found nothing blocking. Of six minor points, three were fixed on the branch
(one with a regression test), one was traced to a stale diagram on `main`, and two were left. Verdict: approve with nits.

## Scope of Change
- Files changed: 22 (excluding generated data)
- Areas touched: python / r / docs / specs / diagrams / data (regenerated)
- Commits:
  - c600bd5 029 US11: perio by the study lead's codes, adult teeth only, and F1
  - d0a1c29 029 US11: regenerate the tooth-table inputs and ERD source; results with F1
  - (this review) 029 US11: fix review findings on PR #574
- Range reviewed: `0b9abe1..d0a1c29`, plus the review-fix commit

## CI Status
| Check | Status |
|---|---|
| all | read on the PR before merge (latest commit) |

## Secrets, PHI and Claims Scan
Clean on the code and the data:
- no secrets;
- no real data: every row comes from `open_dental.py`, and `data/raw/` is untouched;
- no organization or person named: the codes are attributed to "the study lead" only.

## Strengths
- Each change has a test that fails on the old code:
  - each of the eight codes, matched in any case;
  - a perio-sounding name with another code;
  - no diagnosis;
  - F1, including its zero and NaN cases;
  - F1 in the run's scores.
- Python and R were traced to agree on:
  - a missing or empty code ("other");
  - a key in another category, or none at all ("none");
  - float against integer keys.
- The docs say plainly that the results don't move, and why. They also say what a real run still needs (#572).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- **Fixed.** `open_dental.extractions` mapped `dx` without converting it to a number, so a text `dx` (read from CSV)
  fell to "none". It now uses `pd.to_numeric`. Test `test_extractions_read_the_diagnosis_key_as_a_number_even_from_text`
  fails without the fix.
- **Fixed (documented).** A recorded diagnosis outside the practice's lists is now "other" (by name it was "none"),
  while `tooth_loss_dq`'s `diagnosis_not_in_lists` still checks the lists by name. Spec FR-015 and
  `docs/tooth_loss.md` now say so, and the `DIAGNOSIS_LOOKUP` comment says what it still serves. The injected
  unlisted item lands only on scaling rows, never on extractions, so no result changes.
- **Fixed.** The silver model described `itemvalue` as "extra information". It now names it as the diagnosis code
  the label reads. The ERD sources and the two Open Dental silver PNGs were regenerated and re-rendered.
- **Not this PR.** The silver dictionary's `patplan` figures changed (1,740 to 1,579 rows). Regenerating on `main`
  alone gives the same figures, so `main`'s diagram was stale; this PR brings it up to date.
- **Left.** Python keeps the last duplicate defnum in category 16 and R keeps the first. defnum is Open Dental's
  primary key, so only a malformed extract shows the difference.
- **Left.** Two prose lines in `docs/tooth_loss.md` and `analysis_plan.md` run past the wrap width (cosmetic).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims | ✅ | |
| Test first | ✅ | the new tests failed before the code (seen in the session); the lettered-teeth test pins existing behaviour |
| Python and R in parity | ✅ | R twin changed; the US11 hand-worked block and the F1 metric parity pass |
| Simulated is labelled simulated | ✅ | results marked SYNTHETIC |
| Seeds fixed | ✅ | no new draws |
| Spec for big changes | ✅ | spec 029 US11, FR-015, SC-013, T033-T035, analysis-plan change log |
| Commits | ✅ | |
| Docs | ✅ | `docs/tooth_loss.md` |
| Configuration | n/a | no settings |

## Test Coverage
Run locally:
- `cd python && pytest -q tests`: 2,067 passed, 17 skipped (before the review fixes). The touched modules gave
  120 passed after them.
- `ruff check` on changed files: clean.
- `python/scripts/make_parity_inputs.sh && Rscript r/tests/test_parity.R`: parity OK on every section:
  - tooth statuses: 6,400 teeth, 0 differ;
  - the US11 block passes;
  - tooth-loss metrics, F1 included: 292 values, 0 differ.

## Verdict
**Approve with nits.** Nothing blocking. Merge when CI is green on the latest commit.
