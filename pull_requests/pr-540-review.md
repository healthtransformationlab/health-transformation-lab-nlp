---
pr: 540
branch: feat/529-029-study-lead-answers
title: "029 US10: the tooth-loss model follows the study lead's answers on codes, labels, window and output"
author: jcbowyer
reviewed_at: 2026-11-04
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 029 US10: the tooth-loss model follows the study lead's answers on codes, labels, window and output

## Summary
Brings the tooth-loss model in line with the study lead's answers:
- **Extraction codes:** D7111, D7140, D7210 and D7250.
- **No diagnosis:** extractions without one are dropped.
- **Planned extractions:** the most recent plan gives the label, with a 548-day window.
- **Age:** no cut-off by default.
- **Output:** tooth level only; the stage recount is written only on request.

The R twin follows, spec 029 gains US10, and the outputs are regenerated on the newest main.

The review found no blocking issues, two Important findings and three Minor ones, all fixed on the branch with tests. CI and the local suite and parity pass. Verdict: approve with nits. Two answers are still open from the study lead (the end of the age sentence, and the periodontal codes); both are documented, and neither blocks this.

## Scope of Change
- Files changed: 19 (+279 / -67, excluding generated data and draw.io sources)
- Areas touched: python / r / docs / specs / diagrams / data (regenerated)
- Commits:
  - 537c9d4 029 US10: the tooth-loss model follows the study lead's answers
  - 874c320, e5b0def, dd805b1: regenerate the tooth-table inputs, ERD sources, presets, site JSON
  - 4efaed8 029 US10: results under the study lead's answers, tooth level
  - (merge of main: 033 US5, 033 DOCS1, 027 CHORE2, 025 BUG3)
  - 7acb990 029 US10: fix review findings on PR #540
  - cdfb26e 029 US10: regenerate the presets and the data-quality site JSON on the newest main
- Range reviewed: merge base with main `..cdfb26e`

## CI Status
| Check | Status |
|---|---|
| all | read on the PR before merge (latest commit) |

## Secrets, PHI and Claims Scan
Clean on the code and the data:
- no secrets;
- no real data;
- no organization or person named. The guidance is attributed to "the study lead" only.

## Strengths
- Every behaviour change has a test that fails on the old code:
  - the codes;
  - the most recent plan, including an undated plan;
  - the dropped no-diagnosis extractions and their exclusion count;
  - the defaults;
  - output on request.
- `exclusions()` stays consistent with `eligible()`. The reviewer checked 300 random hand-built tables under 4 parameter sets and found no mismatch.
- The docs lead with the confusion-matrix measures, as the study lead asked, and state the seed spread.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **Fixed in 7acb990.** `tooth_loss.py`: an undated planned extraction sorted last in pandas, so `keep="last"` chose it, while R chose the latest dated plan.
  - Reproduced on a two-row case.
  - Now an undated plan is the oldest on both sides (`na_position="first"`).
  - Tests: `test_the_most_recent_planned_extraction_gives_the_label_and_the_window` (tooth 28) and a hand-worked R block.
  - The synthetic generator never writes an undated plan, so no committed result changes.
- **Fixed in 7acb990.** The R "most recent plan" branch was never exercised: no synthetic tooth has two plans. A hand-worked R block in `r/tests/test_parity.R` now covers it, along with the undated plan and a lettered code.

### 🔵 Nits / suggestions (Minor)
- **Fixed.** Presets still write the stage recount. `docs/presets.md` now says the presets keep it as an exploratory part.
- **Fixed.** The script 51 docstring marks the stage files as `--stage-recount` only.
- **Fixed.** Acceptance scenario 5 is now tested through `tooth_loss_model.outputs_to_write`, which script 51 uses.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims | ✅ | |
| Test first | ✅ | each change has a test that fails on the old code |
| Python and R in parity | ✅ | R twin changed; parity on statuses plus the new hand-worked R block |
| Simulated is labelled simulated | ✅ | results marked SYNTHETIC; seed spread stated |
| Seeds fixed | ✅ | no new draws |
| Spec for big changes | ✅ | spec 029 US10, FR-014, SC-012, T030-T032; analysis plan and change log |
| Commits | ✅ | |
| Docs | ✅ | `docs/tooth_loss.md`, `docs/presets.md`, script docstring |
| Configuration | ✅ | model defaults change (documented); no environment settings |

## Test Coverage
New or changed tests cover:
- the four codes and a lettered code;
- the most recent plan, including an undated one;
- the dropped no-diagnosis extractions and `no_diagnosis_count`;
- the defaults: no age cut-off and the 548-day window;
- the presets (repo_v2 none, exploratory_1 18);
- output on request.

The split-by-visit test now uses a 1,500-patient extract, because few patients have two labelled teeth.

Run locally on the final code:
- `cd python && pytest -q tests`: 1,979 passed, 16 skipped.
- `ruff check` on changed files: clean.
- `python/scripts/make_parity_inputs.sh && Rscript r/tests/test_parity.R`: parity OK on every section (tooth statuses 6,400 teeth, 0 differ; the new hand-worked US10 block passes).

## Verdict
**Approve with nits.** Nothing blocking. Merge when CI is green on the latest commit.
