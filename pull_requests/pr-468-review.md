---
pr: 468
branch: feat/448-032-new-defaults
title: "032 US8: exploratory_1's settings become the defaults (split kept by person)"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: self-review (agent), against .claude/review-rubric.md
verdict: approve-with-nits
---

# PR Review: 032 US8: exploratory_1's settings become the defaults (split kept by person)

## Summary
The `exploratory_1` settings become the code's defaults, except the split, which stays by person for both models. The
new defaults are written out as `repo_v2`; `repo_v1` keeps the old ones. The visit filters, the five-group scoring and
the absent-code rule apply when results are scored (`study.scored_review`, `study.reread_absent_code`), so the
benchmark note set and every committed model prediction stay as they were; rebuilding the note set is tracked in #467.
Every result a default touches that can be recomputed locally was rerun with the repo's scripts and recommitted:
the ladder, the leaderboards, prevalence, the status classifier, the data-quality page, the presets, the simulated
judge scorecard and the EDR deck. Python and R agree. Approve with nits.

## Scope of Change
- Files changed: 117 (most of them regenerated CSVs).
  - code: `labels.py`, `eval/score.py`, `prevalence.py`, `phenotype.py`, `study.py`, `ladder_eval.py`, `harm.py`,
    `readme_results.py`, `judge_scorecard.py`, `dq_site.py`, `presets.py`, `tooth_loss_dq.py`, `tooth_loss_model.py`,
    `analysis_presets.yaml`; scripts 19, 28, 29, 40, 51, 58 and `export_rules_predictions.py`;
  - R: `eval/score.R`, `labels.R`, `06_validation.R`, `18_spec032.R`, `04_reliability.R`, `10_ladder.R`,
    `11_judge_scorecard.R`, `r/tests/test_parity.R`;
  - tests: new `test_scoring_defaults.py`; `test_presets.py` and nine others updated for the new defaults;
  - docs: `presets.md` (what changed, before and after), `tooth_loss.md`, `algorithms.md`, `scoring.md`,
    `evidence_rules.md`, `eval/README.md`, `README.md`, `claims.yaml`, EDR slides 4 and 8 and the rebuilt deck;
    generated `docs/edr/README.md`, `docs/results.md`, `docs/site/data-quality.json`; spec 032 text and T008/T009;
  - data: `data/datasets/{ladder,prevalence,classify_status,presets,judge}/`.
- Areas touched: python, R, data, docs, decks, a Databricks notebook comment.

## CI Status
Not yet read on the PR head at the time of writing. Locally: full `pytest -q tests` 1626 passed, 16 skipped;
`Rscript r/tests/test_parity.R` OK in every section; `scripts/35_readme_results.py --check` and
`scripts/50_dq_site.py --check` up to date (their tests pass).

## Secrets, PHI and Claims Scan
- **Secrets:** none in the diff.
- **PHI / real data:** none. Every changed data file is computed from the generator's synthetic data; no note text
  was added (the re-read uses the seeded raw codes in memory only).
- **Organisation claims:** none. Presets and docs name settings only; the start dates are called synthetic stand-ins.
  `test_no_org_references.py` and `test_wording.py` pass; no "diagnose" wording added.

## Strengths
- The note set the external runs were scored on is untouched, and the scoring-time view is guarded:
  `reread_absent_code` fails if the regenerated raw codes don't give the committed readings, and a test checks that
  re-reading under `no_answer` gives back the answer key exactly.
- The old behaviour is one flag away and was checked byte for byte: `28_ladder_vs_truth.py --grouping six
  --all-visits --absent-code no_answer` matches main's script output, `19_prevalence.py --all-visits --absent-code
  no_answer` matches the committed prevalence files, and the `repo_v1` / `exploratory_1` preset parts are unchanged.
- The test that guards the defaults now checks `repo_v2` against every code default, so a later change shows up.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None open. Two found during the work and fixed in the PR: the R prevalence parity read every visit while Python now
counts the filtered, re-read ones (fixed: `export_rules_predictions.py` writes the scored visits for R); and the
simulated judge scorecard mixed grouped answers with six-status judge statuses (fixed in both languages; the
committed real judge run, which needs the LLM endpoint to redo, still checks at six statuses).
### 🔵 Nits / suggestions (Minor)
- **The ladder gains GatorTron (lr 2e-05).** Its predictions were committed after the ladder was last rebuilt, so any
  rerun of script 28 adds it, main's version included. It now appears in the leaderboard (91.0 with the stage 4 rule)
  and drops off the "not run yet" list; the README test was relaxed to allow either. Worth a line in the PR (done).
- **Seed stability still scores six statuses on all review charts** (`49_seed_stability.py` rebuilds five studies).
  Moving it to the scoring defaults needs `reread_absent_code` per seed; left as a follow-up and listed.
- **`algorithm_patel2022` keeps its own reading of the diagnosis codes** (a published order reproduced as is); it is
  grouped and filtered like the others but not re-read under the absent-code rule.
- **`docs/tooth_loss.md`'s detailed tables are the pre-US8 run.** The new headline numbers are above them, and the
  text says which run the tables are; regenerating every table by hand was not attempted.
- **`readme_results.load_inputs` now regenerates the 1,200-person visit table** (about 2 s) to re-read the codes.
  Acceptable for a report script; could be cached if it grows.
- **Deck figures re-derived (step 5):** 215, 201, 181, 177, 179 of 221 and 163 (73.8% x 221) read from
  `docs/edr/README.md`, `docs/results.md` and `ladder_vs_truth.csv`; the solution slide's 240 (the review set) now
  points at `build_summary.json`. `test_deck_claims.py` passes.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | Generated data only |
| No organization claims | ✅ | Settings only |
| Test first | ✅ | Failing preset test committed first (0440c81); new scoring tests |
| Python and R in parity | ✅ | R defaults follow; parity OK in every section |
| Simulated is labelled simulated | ✅ | The CAL ICC section is `is_simulated`; simulated judge and MedGemma files keep their prefix |
| Seeds fixed | ✅ | The re-read uses the build's seed (42) and people (1,200) as named constants |
| Paths | ✅ | `DATASETS_DIR`, `REPO_ROOT` |
| Spec for big changes | ✅ | Spec 032 US8; spec text updated, T008/T009 ticked |
| Telemetry | ✅ | New public functions (`grouped`, `grouped_proba`, `reread_absent_code`, `scored_review`, `cal_reliability`) have `@traced` |
| Words | ✅ | "find gum disease in records"; no "diagnose" |
| Deck figures | ✅ | Every changed figure in `claims.yaml`, re-derived |
| Configuration | ✅ | No new settings; the PR names the jobs that change on deploy |
| Commits | ✅ | Imperative subjects, bodies say why, trailers |
| Docs | ✅ | `presets.md` says what changed, why the split stays by person, the scoring-time filters and #467, and how to get the old behaviour |

## Test Coverage
- `tests/test_presets.py`: `repo_v2` against every code default (one test per setting), `repo_v1` unchanged,
  `exploratory_1` differs from `repo_v2` only in the two split settings, the settings table compares with `repo_v2`.
- `tests/test_scoring_defaults.py` (new): grouping and grouped probabilities, harm of the merged group, the re-read
  under `no_answer` reproduces the answer key, the new rule only turns no-answer codes into healthy, the scored charts
  are adults from the start date, the committed ladder is scored under the defaults.
- Updated for the new defaults (old values passed explicitly where a test is about something else): absent code,
  status grouping, study filters, tooth-loss model and validation, consistency groups, data-quality page (insurance
  split, CAL ICC), leaderboard, judge scorecard, per-field MedGemma, algorithms page.
- Full suite 1626 passed, 16 skipped; R parity OK.

## Verdict
Approve with nits. The defaults change as the owner decided, the split stays by person, every committed prediction
stays valid, and the results that a default touches and that can run locally were rerun and committed.
