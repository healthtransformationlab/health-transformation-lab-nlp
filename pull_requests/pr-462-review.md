---
pr: 462
branch: feat/442-032-absent-code-rule
title: "032 US3: the diagnosis-code source can read a treatment plan with no gum-disease code as healthy or gingivitis"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: implementing agent self-review against .claude/review-rubric.md and AGENTS.md (coordinator to verify)
verdict: approve-with-nits
---

# PR Review: the diagnosis-code source can read a treatment plan with no gum-disease code as healthy or gingivitis

## Summary
Spec 032 US3 adds the setting `absent_code` to the diagnosis-code source (`proc_dx_completed`, `proc_dx_planned`).
- `no_answer`, the default, is unchanged.
- With `healthy_or_gingivitis`, a visit with a treatment plan but no gum-disease code (K05) reads as `healthy`,
  which stands for healthy or gingivitis. A visit with no plan stays no answer.
- `study.read_methods` takes the setting.
- The base-R twin agrees with Python on all 140 cases.
- With the default, the study files are byte-identical.

Verdict: approve with nits.

## Scope of Change
- Files changed: 8 (+192 / -4), plus this review.
- Areas touched: python, r, docs, specs (T003 ticked).
- Commits:
  - 3e8f184 Test the diagnosis-code source's absent-code rule first
  - 4d81ef3 Add the absent-code rule to the diagnosis-code source, in Python and R
  - b9a9132 Describe the absent-code setting in the evidence rules; tick T003
- Range reviewed: `origin/main (47c6272)..b9a9132`

## CI Status
| Check | Status |
|---|---|
| Local `pytest -q tests` | 1544 passed, 16 skipped |
| Local `Rscript r/tests/test_parity.R` | every section OK; `absent code: 140 / 140 cases agree` |
| `ruff check` | clean on new and changed lines (older SIM102 and C408 untouched) |
| GitHub CI | pending at time of writing |

## Secrets, PHI and Claims Scan
Clean. No credentials or real records; the cases are made-up code and plan strings. The setting is generic and no
organisation is named. The wording is "reads as", "counts as" and "status", never a clinical judgement.

## Strengths
- The status stays within the six labels, so the scoring, labels and R contracts are untouched.
  - "healthy" standing for healthy or gingivitis follows the existing reading of a prophy alone in `read_proc_codes`.
  - The five-level grouping merges the two anyway.
- An unknown rule fails at once, and so do missing raw columns; the default returns the very same frame.
- The parity grid covers empty, non-K05 and unreadable K05 codes, and blank and `(none)` plans.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None found.
### 🔵 Nits / suggestions (Minor)
- `sources.read_proc_dx` (unchanged) raises `KeyError` on a K05.3 code whose last digit isn't 1-3 (e.g. `K05.324`),
  so `read_dx_code` inherits that. The R twin returns `unknown` instead. Synthetic codes never take that form, so
  it isn't in the parity grid. Worth a separate fix in `sources.py` if real-shaped codes ever come in.
- At six levels, a gingivitis visit read by this rule counts as a miss. That's a property of the rule, documented in
  `docs/evidence_rules.md` and the PR. The five-level grouping (US1) is where the rule is fair.
- Merge order with the sibling spec 032 PRs: `r/tests/test_parity.R` (end-of-file sections),
  `export_rules_predictions.py` and `tasks.md` (adjacent task lines) are also edited by US1, US2 and US4. Expect
  trivial textual conflicts, keeping both sides.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | |
| Synthetic only, no PHI | yes | |
| No organization claims | yes | |
| Test first | yes | 5 tests committed and seen failing (3e8f184) before the code |
| Python and R in parity | yes | `r/R/18_spec032.R`, 140 / 140 |
| Simulated labelled | n/a | no new results |
| Seeds fixed | n/a | no sampler |
| Paths | yes | `LABELS_DIR` |
| Spec for big changes | yes | spec 032 US3, T003 ticked |
| Commits | yes | imperative, body says why, trailer |
| Docs | yes | `docs/evidence_rules.md` |
| Configuration | yes | a function argument; no environment changes |
| Telemetry | yes | `read_dx_code`, `with_absent_code` are `@traced` |

## Test Coverage
`tests/test_absent_code.py` covers:
- the default;
- each branch of the rule;
- an unknown rule;
- the frame helper;
- `read_methods` on seeded synthetic visits.

Locally I ran the full suite, `make_parity_inputs.sh` (against this checkout) and the R parity test. The study
files were unchanged after the rerun.

## Verdict
Approve with nits. Nothing must change first.
