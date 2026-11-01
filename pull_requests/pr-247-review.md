---
pr: 247
branch: feat/235-026-mismatch-rules
title: "Flag records whose recorded code doesn't fit the chart (026 US2)"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: Flag records whose recorded code doesn't fit the chart (026 US2)

## Summary
The PR adds six record-mismatch rules (`case_profile.check_rules`) and their scores against the generator's
truth over the visits each rule can check (`score_rules`). The results are written by `scripts/45_case_profiles.py`,
twinned in R (`r/R/15_spec026.R`), and loaded to two gold tables, which the DQ Genie space now uses. The review
found nothing critical or important. The R parity block was run here with base R: 1,275 flags identical and 63
score rows exact. The reviewer also broke the R side five different ways, and the parity test failed each time.
The six minor findings are fixed. Verdict: approve with nits.

## Scope of Change
- Areas touched: python (`case_profile`, `grader_tables`, `gold_names`, `dashboards`, script 45, tests), r (twin, parity block), data (two small CSVs), diagrams (model, ERD sources), docs, specs (tasks ticked)
- Commits: a0f6406 (rules, scores, gold, Genie, R twin), then the review fixes
- Range reviewed: `origin/main..feat/235-026-mismatch-rules`

## CI Status
| Check | Status |
|---|---|
| python, r-parity, postgres, bundle, check | pending on push |
| local | `pytest -q tests` and the spec 026 R parity block (base R): pass |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. Synthetic statuses and measures only; the evidence text quotes codes and measures, never notes.
- **Organization claims:** clean.

## Strengths
- **R parity is exact and sensitive.** Each of these changes to the R side makes the parity test fail: `CHART_STEPS` 1 to 2, disabling stage drops, a wrong injected-error definition, a wrong `only_rule_count`, and an empty precision returned as 0.
- **The rules match the spec table.** Stage drops equal `plausibility.check_history` on the whole study, and a test checks it.
- **The docs and PR numbers match a rerun.** That includes the claim that `code_below_chart` adds nothing `code_vs_chart` doesn't already flag: all 141 of its flags are also chart flags.
- **The names agree everywhere.** Gold, the model and Genie use the same column names, and all of them have legal suffixes.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
All fixed:
- **No per-visit count of failed rules.** The spec has visits failing the most rules sort first, but nothing stored that count. `record_mismatches()` now adds `failed_rule_count` (gold `failed_rule_count`), and a test checks it.
- **Task T014 (the R twin) was left unticked.** It is now ticked.
- **The `HIGH_CODE_MAX_PD_MM` comment contradicted its value.** It said "PD 4 mm or less", but the rule uses PD < 6. The comment now says PD under 6 mm is below stage III's depth.
- **No tests at the thresholds.** No study visit sits on a boundary, so the data can't pin them. Tests now cover CAL 2.9 and 3.0, bone loss 14.9 and 15.0, PD 5.9 and 6.0, a tooth lost, and chart steps of one and two.
- **The R constants lacked the `_026` suffix** the rest of the file uses. They now have it.
- **The mismatch-to-score relationship reads as joining on `rule_name` alone**, but the scores are per rule and clinic. Its label now says to join on `clinic_code` too.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | |
| Synthetic only, no PHI | Yes | |
| No organization claims; vendors cited | Yes | Thresholds cite the 2017 AAP/EFP classification |
| Test first | Yes | Every behaviour and fix had a failing test first |
| Python and R in parity | Yes | R 15_spec026.R; parity block run locally, exact |
| Simulated is labelled simulated | Yes | Every score is labelled synthetic, against the generator's truth |
| Seeds fixed | Yes | Deterministic over the seeded study |
| Paths | Yes | `DATASETS_DIR` |
| SQL and data names | Yes | `test_sql_conventions.py` |
| Idempotent writes | Yes | Load results overwrites; `DQ_PROV` on every row |
| Telemetry | Yes | `check_rules`, `score_rules`, `record_mismatches` are `@traced` |
| Words | Yes | "record mismatch", "coding or charting gap"; `test_wording.py` |

## Test Coverage
`test_case_profile.py` covers each rule firing alone, the threshold edges, not-checkable and no-code outcomes,
agreement with `check_history`, a hand-worked scoring case, the per-visit count, and every rule on the study.
`test_grader_tables`, `test_gold_model`, `test_dashboards` and `test_sql_conventions` cover gold and Genie. The R
parity block passes locally with base R.

## Verdict
Approve with nits. It can merge once CI is green. Rendering the gold ERD PNGs is still outstanding.
