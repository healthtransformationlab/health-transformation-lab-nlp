---
pr: 461
branch: feat/443-032-stage4-teeth-pairs
title: "032 US4: stage III vs IV also by fewer than 20 teeth and fewer than 10 occluding pairs"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: author's self-review against .claude/review-rubric.md and AGENTS.md (coordinator verification)
verdict: approve-with-nits
---

# PR Review: stage III vs IV also by fewer than 20 teeth and fewer than 10 occluding pairs

## Summary
Adds two stage IV rules that read the teeth left rather than the teeth lost: `teeth_lt_20` and `pairs_lt_10`
(`labels.STAGE4_COUNT_RULES`), with third molars left out as in `aces.py` and the pair count shared with aces
through `aces.opposing_pair_count`. `stage4_rule` takes the teeth present as a keyword-only argument, so existing
callers are unchanged. The tooth-loss patient stage table and recount report the two rules, the R twins and the
parity test cover them, and the docs and the analysis plan's change log say so. The four existing rules and every
other tooth-loss output are identical to `main` on the full synthetic run. Approve with two nits.

## Scope of Change
- Files changed: 11 before this review (+179 / -25), no generated data committed
- Areas touched: python, r, docs, specs
- Commits:
  - f31d989 Stage IV also by fewer than 20 teeth or fewer than 10 occluding pairs (032 US4)
  - 8386a17 R twins of the teeth-left stage IV rules, and their parity checks (032 US4)
  - 7f682f2 Report the teeth-left stage rules in the tooth-loss results (032 US4)
- Range reviewed: `a36e316..7f682f2`

## CI Status
| Check | Status |
|---|---|
| changes, check | success |
| python, r-parity, postgres, bundle, azure-infra | running when this review was written; the same checks were run locally (below) |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean; synthetic results only, labelled SYNTHETIC in `docs/tooth_loss.md`.
- Organization claims: clean; "published record studies" names no study or organisation.

## Strengths
- Backward compatible: `teeth_present` is keyword-only, the four counting rules ignore it, and a test pins that.
- One definition of an opposing pair: `aces.occluding_pairs` now calls the set-based `opposing_pair_count` that
  `labels.stage4_tooth_counts` also uses.
- The teeth left are read from the whole tooth table (`patient_stage(..., chart=teeth)`), so the model's own
  exclusions (third molars, minimum age) can't make a patient look toothless; a test covers it.
- Results shown unchanged, not assumed: script 51 run on `origin/main` and on the branch (6,000 patients, 5 seeds)
  and compared file by file.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `labels.py` now imports `aces` and `periodx` (for `THIRD_MOLARS`, `opposing_pair_count`, `OCCLUDING_PAIRS_MIN`),
  which pull in pandas on `import labels`. Verified there is no import cycle (both import only `.telemetry`) and
  pandas is a core dependency, so it is left as is.
- `present_tooth_text` lists the teeth as charted, third molars included, while the counts leave them out. This is
  deliberate (the R parity test re-derives the counts from it, exercising the molar exclusion) and documented in the
  `patient_stage` docstring.
- Running `make_parity_inputs.sh` in this container rewrites some committed files outside the tooth-loss outputs
  (float-level differences in TF-IDF predictions and simulated judge files), from library versions, not this change;
  they were restored and are not in the PR.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | |
| Synthetic only, no PHI | yes | |
| No organization claims | yes | |
| Test first | yes | the new tests in `test_tooth_loss_model.py` failed before the code |
| Python and R in parity | yes | `stage4_tooth_counts_029`, `stage4_rule_029(..., teeth_present=)`; parity OK |
| Simulated is labelled simulated | yes | results text says SYNTHETIC |
| Seeds fixed | n/a | no new generator |
| Paths | yes | |
| Spec for big changes | yes | spec 032 US4; T004 ticked; analysis plan change log row |
| Commits | yes | imperative subject, why in the body, co-author trailer |
| Docs | yes | `docs/tooth_loss.md` results text |
| Configuration, secrets register, writes, alerts | n/a | none touched |
| Telemetry | yes | new public functions `@traced`; levels in `telemetry_levels.yaml` (detail, manual) |
| Words | yes | `test_wording.py`, `test_no_org_references.py` pass |

## Test Coverage
- New: tooth and pair counts (third molars aside, one arch), both rules at the 20 / 10 edges, `teeth_present`
  required, existing callers unchanged, the patient table's new columns, counting from the whole chart.
- Run locally: `pytest -q tests` 1542 passed, 16 skipped; `ruff check` clean on changed Python files;
  `make_parity_inputs.sh` then `Rscript r/tests/test_parity.R`: every section OK, the stage rule over 8,000 patient
  rows with 0 differences, and the hand-worked cases.
- Full script 51 run: scores, calibration, predictions, missing and eval rows identical to `main`; patient stage
  identical on every existing column; stage recount identical apart from the 10 new rows.

## Verdict
Approve with nits; nothing must change first.
