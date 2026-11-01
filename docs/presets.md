# Presets: named sets of analysis settings

> **Every number on this page is SYNTHETIC.** It is agreement with a synthetic answer key on generated records, not a
> finding about any practice or patient. Personal learning project; see [DISCLAIMER.md](../DISCLAIMER.md).

Published studies that find gum disease in dental records (phenotyping) make different design choices: how the
statuses are grouped, which visits count, how a missing gum-disease code is read, how stage IV is decided when the
record doesn't say why a tooth was lost, how a model is validated. Spec 032 made each of these a setting. A **preset**
names one value for every setting, so a whole study design can be run in one go and set beside this repo's defaults.
Presets name settings only, never a study, person or organisation.

The presets live in [`analysis_presets.yaml`](../python/health_transformation_lab_nlp/analysis_presets.yaml), each
setting with a one-line comment. `presets.load_preset(name)` reads one and fails at once, naming it, on an unknown
preset, an unknown or missing setting, or a value the code can't use.

| Preset | What it is |
|---|---|
| `repo_v2` | The code's defaults since spec 032 US8 (#448), every one written out: `exploratory_1` with the split kept by person. A test (`tests/test_presets.py`) checks each against the code's own default, so when a default changes the preset has to follow or the test fails. |
| `repo_v1` | The defaults before spec 032 US8, kept as they were: `--preset repo_v1` gives the old behaviour. |
| `exploratory_1` | Common choices of published record studies turned on together: five statuses (three also reported), adults only, a start date, a plan with no gum-disease code read as healthy or gingivitis, a split by visit at 20% with 5-fold tuning, insurance in the consistency split, and the reliability (ICC) of attachment loss. It differs from `repo_v2` only in the split. |

## Run one

```bash
cd python && python scripts/58_preset.py --preset exploratory_1
```

It runs every part under the preset and under the defaults (`repo_v2`), on freshly generated synthetic data with fixed seeds (1,200
people for the visit-level study set, 6,000 patients for the Open Dental extract, generator seed 42), and writes one
file per part and preset to `data/datasets/presets/synthetic_preset_<name>_<part>.csv`, every row with
`data_label = synthetic` and `preset_name`. To keep the run to about six minutes it uses one generator seed and no
bootstrap intervals, where `scripts/51_tooth_loss_model.py` uses five seeds and 1,000 resamples; so the tooth-loss
numbers here have no intervals. A preset run writes only these files; every other committed result stays as it was.
The committed files are from `--preset repo_v1` and `--preset exploratory_1` (each also writes `repo_v2`).

The start dates are synthetic stand-ins for "the date a newer classification was adopted": 2021-04-01 for the visits
(which start in late 2020) and 2018-01-01 for the extract (whose practices switch diagnosis lists from 2018).

## The settings

| Setting | `repo_v1` | `repo_v2` (the defaults) | `exploratory_1` |
|---|---|---|---|
| status grouping | six | five | five |
| also reported | none | three | three |
| visits: minimum age | none | 18 | 18 |
| visits: start date | none | 2021-04-01 | 2021-04-01 |
| plan with no gum-disease code | no answer | healthy or gingivitis | healthy or gingivitis |
| stage IV rules reported | all six | all six | all six |
| tooth loss: minimum age | 18 | 18 | 18 |
| tooth loss: start date | none | 2018-01-01 | 2018-01-01 |
| tooth loss: split | by patient, 30% | by patient, 20% | by tooth (`visit`), 20% |
| tooth loss: XGBoost tuning | none | 5-fold | 5-fold |
| status classifier: split | by person, 20% | by person, 20% | by visit, 20% |
| status classifier: tuning | 5-fold | 5-fold | 5-fold |
| consistency groups | office, provider, sex, race, exam year, age band | the same plus insurance type | the same plus insurance type |
| CAL reliability ICC | off | on | on |

## Headline comparison (SYNTHETIC)

| | `repo_v1` | `repo_v2` (the defaults) | `exploratory_1` |
|---|---|---|---|
| visits in the study set (left out: before the start date) | 4,343 (0) | 3,794 (549) | 3,794 (549) |
| rules phenotype (`algorithm_design`): macro F1 at the main grouping | 0.739 (six) | 0.740 (five); 0.843 (three) | 0.740 (five); 0.843 (three) |
| rules phenotype: periodontitis sensitivity / specificity | 0.973 / 0.878 | 0.925 / 0.889 | 0.925 / 0.889 |
| the note's stated status: macro F1 at the main grouping | 0.788 (six) | 0.803 (five) | 0.803 (five) |
| tooth loss, held-out teeth (completed label set, shared features) | 242 | 91 | 88 |
| tooth loss: AUC, logistic / XGBoost | 0.836 / 0.856 | 0.811 / 0.819 | 0.895 / 0.827 |
| tooth loss: patients in both the training and the test part | 0 | 0 | 6 |
| status classifier, 5level: accuracy / macro F1 | 0.797 / 0.746 | 0.795 / 0.751 | 0.768 / 0.716 |
| status classifier, 3level: accuracy / macro F1 | 0.881 / 0.864 | 0.882 / 0.868 | 0.867 / 0.846 |
| status classifier: people in both the training and the test part | 0 | 0 | 405 |
| stage IV, all patients at stage III-IV: every missing tooth / fewer than 20 teeth / fewer than 10 pairs / truth | 273 / 46 / 181 / 97 | 273 / 46 / 181 / 97 | 273 / 46 / 181 / 97 |
| stage IV by the expected count, completed + planned, logistic / XGBoost | 85 / 84 | 83 / 94 | 84 / 100 |
| CAL reliability: ICC for the same site charted again (SEM) | not run | 0.683 (0.82 mm) | 0.683 (0.82 mm) |

How to read it:

- `repo_v2` reproduces the committed status-classifier results (`data/datasets/classify_status/`, 0.795 and 0.882
  accuracy) and `repo_v1` the ones before spec 032 US8 (0.797 and 0.881), as they should.
- **A split by visit overstates accuracy.** It puts some people (405 here) or patients on both sides, so the model is
  partly tested on people it trained on. Script 58 prints that count next to every such score, with a warning. A
  higher number under `exploratory_1` is not a better model: the test set is smaller (the start date leaves out more
  than half the teeth) and the split leaks.
- Reading a plan with no gum-disease code as healthy or gingivitis turns some "no answer" readings into answers. The
  rules phenotype then finds periodontitis less often (sensitivity 0.973 to 0.925): a plan with no code says nothing
  about gum health, so on this synthetic data the rule costs sensitivity.
- Grouping changes the macro F1 most (fewer, larger groups are easier to tell apart); periodontitis yes/no is the same
  at every grouping.
- The ICC numbers come from placeholder variance components (spec 013, `reliability_cal`), not from any estimate.

## What changed in the defaults (spec 032 US8)

Spec 032 US8 (#448) made the `exploratory_1` settings the code's defaults, with one exception, and wrote them out as
`repo_v2`; the defaults before it stay available as `repo_v1`.

**The split stays by person.** A random split by visit lets one person's visits (or one patient's teeth) sit in both
the training and the test part, so the model is partly tested on people it learned from, and the score overstates
how well it would do on new people (405 people on both sides for the status classifier above). It stays an option
(`split_unit=visit`, `--split-unit visit`), which reports that count beside every score, and is never a default.

**The visit filters apply when results are scored, not to the note set.** The age and start-date defaults, the
five-group scoring and the absent-code rule are applied at scoring time (`study.scored_review`,
`study.reread_absent_code`): the ladder, the leaderboards, prevalence and the status classifier count only adults'
visits from 2021-04-01, and re-read the diagnosis codes from the seeded raw codes. The benchmark note set itself is
built as before: `scripts/10_build_study.py` keeps every visit and reads an absent code as no answer (its `--min-age`
and `--start-date` flags remain for a filtered build), and the review set, the answer key and the Kaggle and Hugging
Face task data are unchanged, because the external model runs (MedGemma on Kaggle and Databricks, the encoders on
GPU) were scored on those exact notes. Every committed prediction stays valid; scores are recomputed on the visits
that count. Rebuilding the note set for adults from the start date, then rerunning the external model runs, is
tracked in #467. No synthetic visit is under 18, so today the age filter leaves nothing out; the start date leaves
out 19 of the 240 review charts and 549 of the 4,343 visits.

Headline numbers before and after (SYNTHETIC: agreement with the generator's answer key, not clinical performance):

| | Before (`repo_v1`) | After (`repo_v2`) |
|---|---|---|
| review charts scored | 240 | 221 (19 visits before 2021-04-01 left out) |
| status scored as | six statuses | five groups (healthy and gingivitis together) |
| rules, gum measurements first (whole record) | 234 of 240 | 215 of 221 |
| rules, exam form first (the study design's order) | 173 of 240 (72.1%) | 163 of 221 (73.8%) |
| note only: ModernBERT + stage 4 rule | 219 of 240 | 201 of 221 |
| note only: MedGemma 4B + stage 4 rule / MedGemma 1.5 4B + stage 4 rule | 196 / 185 of 240 | 181 / 177 of 221 |
| keyword rules / gum measurements alone | 189 / 193 of 240 | 179 / 177 of 221 |
| prevalence of periodontitis, rules exam form first (people) | 56.3% of 1,200 | 53.8% of 1,119 |
| prevalence from the done-treatment diagnosis codes alone | 46.4% of 1,131 answered | 32.0% of 1,119 answered |
| status classifier, 5level / 3level accuracy | 0.797 / 0.881 | 0.795 / 0.882 |
| tooth loss, held-out extractions: AUC logistic / XGBoost (shared, completed) | 0.84 / 0.86 (242 teeth) | 0.81 / 0.82 (91 teeth) |
| tooth loss: stage IV by every missing tooth / fewer than 20 teeth / fewer than 10 pairs / truth | 273 / 46 / 181 / 97 | 273 / 46 / 181 / 97 (the start date chooses the model's teeth, not the teeth counted) |
| tooth loss: stage IV by the expected count, completed + planned, logistic / XGBoost | 85 / 84 | 83 / 94 |
| data-quality page: chart consistency split by | six group types | the same plus insurance type (and the four insurance tables are checked) |
| data-quality page: CAL reliability | not reported | ICC per probing error (SIMULATED variance components) |

The ladder also gains the committed GPU GatorTron run (learning rate 2e-05), which the old ladder file predated. The
plan with no gum-disease code read as healthy or gingivitis turns many "no answer" readings of the diagnosis codes
into answers, so the codes alone now answer for every person and find periodontitis less often. Kept as they were:
the LLM judge scorecard (`data/datasets/judge/`; recomputing it needs the LLM endpoint), the Kaggle and Hugging Face
task data and cards (the note set, #467), the per-field MedGemma accuracy (it scores the reader's fields, not a
status), and the seed-stability check (`scripts/49_seed_stability.py` rebuilds the study for five seeds and still
scores six statuses on every review chart; moving it to the scoring defaults is a follow-up).

To get the old behaviour: `--preset repo_v1` for script 58; `scripts/28_ladder_vs_truth.py --grouping six
--all-visits --absent-code no_answer` and `scripts/19_prevalence.py --all-visits --absent-code no_answer` give
byte for byte what the scripts wrote before spec 032 US8; `scripts/51_tooth_loss_model.py --start-date "" --test-share 0.3
--cv-folds 0`; in code, pass `grouping="six"`, `min_age=None, start_date=None`, `absent_code="no_answer"`, or
`tooth_loss_dq.GROUP_TYPES[:-1]`. See also [tooth loss](tooth_loss.md).
