---
pr: 459
branch: feat/441-032-visit-filters
title: "032 US2: which visits count: a minimum age and a start date, as settings"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: implementing agent self-review against .claude/review-rubric.md and AGENTS.md (coordinator to verify)
verdict: approve-with-nits
---

# PR Review: which visits count: a minimum age and a start date, as settings

## Summary
Spec 032 US2. The visit-level study set (`study.build_study`, script 10) takes `min_age` and `start_date`, both
None by default, and reports the visits left out by reason when either is set. The tooth-loss model gains
`ModelParams.start_date` beside `min_age`, filtering on the loss date or, when that isn't recorded, the patient's
first exam date; `exclusions` counts `before_start_date_count` and `unknown_date_count`. Defaults are unchanged, and
rerunning script 10 leaves `data/` clean, so SC-001 holds. Approve with nits.

## Scope of Change
- Files changed: 8 (+168 / -12), plus this review
- Areas touched: python, docs, specs (T002 ticked)
- Commits:
  - e4fb32f Add a start date to the tooth-loss model; failing tests for visit filters
  - 9d85f2a Let the visit-level study set take a minimum age and a start date
  - 03f6fb9 Sort the study test's imports
  - cd4447c Describe the tooth-loss start date; tick T002
- Range reviewed: `origin/main (a36e316)..cd4447c`

## CI Status
| Check | Status |
|---|---|
| Local `pytest -q tests` | 1545 passed, 16 skipped |
| `ruff check` on touched files | clean (one C408 in `study.py` predates this PR) |
| R parity | not affected (no label, scoring or stage-rule change) |
| GitHub CI | pending at time of writing |

## Secrets, PHI and Claims Scan
Clean: no credentials, no real records, no organisation named; test data are hand-made frames and the seeded
synthetic extract. Wording: no "diagnose" phrasing added.

## Strengths
- Each visit and tooth is counted once, under the first reason, in the order the filters apply; the counts add up
  to the input (tested).
- The build summary gains `visits_left_out` only when a filter is set, so `build_summary.json` stays byte-identical.
- The first-exam date mirrors the fallback `tooth_loss` already uses for the age at first exam.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None found.
### 🔵 Nits / suggestions (Minor)
- `tooth_loss_model.py`, `with_first_exam_date`: its docstring says the column is added only when a start date is
  set; that's true in `run`, but script 51 adds it every time it prints the exclusions. Harmless, since only
  `exclusions` reads it there. Left as is.
- `study.py`: the filter applies right after the visits are generated, so the medical record (spec 023) and the
  review pick come from the kept visits only. That's intended (who is in the study is decided first) and only
  matters when a filter is set.
- The tooth-loss tests came from an interrupted earlier attempt and were applied together with their code, so this
  session didn't see them fail first. The visit-level tests were seen failing (ImportError) before the code.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | |
| Synthetic only, no PHI | yes | |
| No organization claims | yes | settings are generic |
| Test first | yes | see the nit about the tooth-loss tests |
| Python and R in parity | n/a | filters only; plan.md lists no R twin for US2 |
| Simulated labelled | n/a | no new results |
| Seeds fixed | yes | no new sampler |
| Paths | yes | no hard-coded `data/` |
| Spec for big changes | yes | spec 032 US2, T002 ticked |
| Commits | yes | imperative, body says why, trailer |
| Docs | yes | `docs/tooth_loss.md`; script 10 docstring |
| Configuration | yes | function arguments and script flags; no environment changes |
| Telemetry | yes | `visits_in_study`, `visit_exclusions`, `with_first_exam_date` are `@traced` |

## Test Coverage
`test_study.py`: default keeps every visit; both filters, a visit under both reasons counted once; the build
reports `visits_left_out` only with a filter and writes only kept visits. `test_tooth_loss_model.py`: start date on
loss date and first exam date, an undated tooth counted, the start date after the age cut, the first exam date
read from the extract. Ran the full suite and script 10 with defaults (`data/` unchanged).

## Verdict
Approve with nits; nothing must change first.
