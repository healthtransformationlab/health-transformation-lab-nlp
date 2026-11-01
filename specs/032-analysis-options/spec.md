# Feature Specification: analysis options

**Feature Branch**: `spec/446-032-analysis-options`

**Created**: 2026-11-01

**Status**: specified

**Input**: the owner asked that the common design choices of published dental-record studies be settings here, so
a study laid out differently from this repo's defaults can be reproduced on the synthetic data and the effect of
each choice seen. These are standard parameters, not anyone's method: a status grouping, which visits count, how an
absent diagnosis code is read, how stage IV is decided without a recorded reason for tooth loss, how a model is
validated, and a consistency split by insurance.

> Personal learning project; synthetic data only. Every default stays as it is, so no committed result changes;
> each option is reported beside the default, never in its place.

## User stories

### US1 - Scores and prevalence at a chosen status grouping (P1) #440

- `labels.GROUPINGS`: `six` (the six statuses, default), `five` (healthy and gingivitis merged as
  `healthy_or_gingivitis`), `three` (`healthy_or_gingivitis`, `mild` = stage I-II, `severe` = stage III-IV).
- `labels.group_status(status, grouping)` maps a status (and "no answer") to its group; scoring and prevalence take
  a `grouping` argument and score at that level.
- Base-R twin and the parity test (AGENTS.md: labels and scoring stay in parity).

### US2 - Which visits count: a minimum age and a start date (P1) #441

- The visit-level study set takes `min_age` (default none) and `start_date` (default none: all years).
- The tooth-loss model gains `start_date` beside `min_age` (default 18, spec 029).
- Both report the visits or teeth left out, by reason (as `tooth_loss_model.exclusions`).

### US3 - The diagnosis-code source can read a plan with no gum-disease code as healthy or gingivitis (P2) #442

- Setting `absent_code`: `no_answer` (default, today's behaviour) or `healthy_or_gingivitis` (a visit with a
  treatment plan but no gum-disease code counts as healthy or gingivitis; a visit with no plan stays no answer).
- Python and R.

### US4 - Stage III vs IV also by fewer than 20 teeth and fewer than 10 occluding pairs (P1) #443

- `labels.STAGE4_COUNT_RULES` gains `teeth_lt_20` and `pairs_lt_10` (counts from `aces.py` and `periodx.py`); the
  tooth-loss stage recount reports them beside the four rules it has. R twins in `r/R/16_spec029.R`; parity.

### US5 - How a model is validated (P2) #444

- `split_unit`: `person` (default) or `visit` (a random split of rows; the output reports how many people fall in
  both parts, since that usually flatters a score); `test_share`; optional k-fold cross-validated tuning for
  XGBoost (`cv_folds`, default none).
- Applies to the tooth-loss model and the visit-level status classifier.

### US6 - Insurance in the synthetic extract and the consistency split (P2) #445

- The synthetic Open Dental extract gains `carrier`, `insplan`, `inssub` and `patplan`, seeded, with each patient's
  insurance type: `private`, `public` or `none`.
- `tooth_loss_dq.group_consistency` adds `insurance_type`; the silver model and ERDs follow.

### US7 - A named preset runs the options together (P2) #446

- `python/health_transformation_lab_nlp/analysis_presets.yaml` names sets of settings; `exploratory_1` turns on:
  five and three-level groupings, adults (18+), a start date, the healthy-or-gingivitis code rule, the 20-teeth and
  10-pairs rules, a split by visit at 20%, 5-fold tuning, insurance in the consistency split, and the CAL
  reliability ICC (spec 013, `reliability_cal`).
- `scripts/56_exploratory_preset.py --preset exploratory_1` runs it on synthetic data and writes
  `data/results/synthetic_exploratory_1_*.csv`, each row labelled synthetic, with a table of every setting, its
  default, the preset's value and the headline numbers under each.

## Out of scope

- A probabilistic answer key (PheValuator-style); a later spec if wanted.
- Real records. Presets name settings only, never a study, person or organisation.

## Success criteria

- SC-001: with every setting at its default, every committed result is byte-identical.
- SC-002: each option has a failing test written first, and Python and R agree to 1e-9 where a twin exists.
- SC-003: `exploratory_1` runs end to end on the synthetic extract and its output names every setting it changed.
