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
| tooth loss: minimum age | 18 | none (since 029 US10, #529) | 18 |
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
| rules phenotype (`algorithm_design`): macro F1 at the main grouping | 0.747 (six) | 0.759 (five); 0.846 (three) | 0.759 (five); 0.846 (three) |
| rules phenotype: periodontitis sensitivity / specificity | 0.980 / 0.903 | 0.933 / 0.917 | 0.933 / 0.917 |
| the note's stated status: macro F1 at the main grouping | 0.760 (six) | 0.769 (five) | 0.769 (five) |
| tooth loss, held-out teeth (completed label set, shared features) | 223 | 89 | 87 |
| tooth loss: AUC, logistic / XGBoost | 0.808 / 0.799 | 0.719 / 0.749 | 0.878 / 0.834 |
| tooth loss: patients in both the training and the test part | 0 | 0 | 12 |
| status classifier, 5level: accuracy / macro F1 | 0.815 / 0.763 | 0.791 / 0.767 | 0.781 / 0.661 |
| status classifier, 3level: accuracy / macro F1 | 0.882 / 0.850 | 0.857 / 0.832 | 0.875 / 0.853 |
| status classifier: people in both the training and the test part | 0 | 0 | 413 |
| stage IV, all patients at stage III-IV: every missing tooth / fewer than 20 teeth / fewer than 10 pairs / truth | 261 / 49 / 171 / 98 | 261 / 49 / 171 / 98 | 261 / 49 / 171 / 98 |
| stage IV by the expected count, completed + planned, logistic / XGBoost | 94 / 89 | 92 / 80 | 86 / 84 |
| CAL reliability: ICC for the same site charted again (SEM) | not run | 0.683 (0.82 mm) | 0.683 (0.82 mm) |

How to read it:

- `repo_v2` reproduces the committed status-classifier results (`data/datasets/classify_status/`, 0.791 and 0.857
  accuracy), as it should. The visit rows are on the study visits as drawn since #467 (spec 033 US3's smoking and
  diabetes shares), so `repo_v1` keeps the old settings but no longer the old numbers (0.797 and 0.881 before).
- **A split by visit overstates accuracy.** It puts some people (413 here) or patients on both sides, so the model is
  partly tested on people it trained on. Script 58 prints that count next to every such score, with a warning. A
  higher number under `exploratory_1` is not a better model: the test set is smaller (the start date leaves out more
  than half the teeth) and the split leaks.
- Reading a plan with no gum-disease code as healthy or gingivitis turns some "no answer" readings into answers. The
  rules phenotype then finds periodontitis less often (sensitivity 0.980 to 0.933): a plan with no code says nothing
  about gum health, so on this synthetic data the rule costs sensitivity.
- Grouping changes the macro F1 most (fewer, larger groups are easier to tell apart); periodontitis yes/no is the same
  at every grouping.
- The ICC numbers come from placeholder variance components (spec 013, `reliability_cal`), not from any estimate.

## What changed in the defaults (spec 032 US8)

Spec 032 US8 (#448) made the `exploratory_1` settings the code's defaults, with one exception, and wrote them out as
`repo_v2`; the defaults before it stay available as `repo_v1`.

**The split stays by person.** A random split by visit lets one person's visits (or one patient's teeth) sit in both
the training and the test part, so the model is partly tested on people it learned from, and the score overstates
how well it would do on new people (413 people on both sides for the status classifier above). It stays an option
(`split_unit=visit`, `--split-unit visit`), which reports that count beside every score, and is never a default.

**The visit filters applied when results were scored, not to the note set** (until #467, below). The age and
start-date defaults, the
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

Headline numbers before and after spec 032 US8, on the notes as they were then (SYNTHETIC: agreement with the
generator's answer key, not clinical performance; the visit rows have moved again since #467, below):

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
| tooth loss, held-out extractions: AUC logistic / XGBoost (shared, completed) | 0.81 / 0.80 (223 teeth) | 0.72 / 0.75 (89 teeth) |
| tooth loss: stage IV by every missing tooth / fewer than 20 teeth / fewer than 10 pairs / truth | 261 / 49 / 171 / 98 | 261 / 49 / 171 / 98 (the start date chooses the model's teeth, not the teeth counted) |
| tooth loss: stage IV by the expected count, completed + planned, logistic / XGBoost | 94 / 89 | 92 / 80 |
| data-quality page: chart consistency split by | six group types | the same plus insurance type (and the four insurance tables are checked) |
| data-quality page: CAL reliability | not reported | ICC per probing error (SIMULATED variance components) |

The tooth-loss rows of both tables are from the extract with the published smoking and diabetes shares (spec 033
US2, #485) and, since spec 033 US4 (#500), patients with no natural teeth, whom the model and the stage recount leave
out: a fresh synthetic sample each time, so they moved within the seed-to-seed spread
([tooth loss](tooth_loss.md), "Before and after spec 033 US2" and "... US4"); the visit rows did not change.

The ladder also gains the committed GPU GatorTron run (learning rate 2e-05), which the old ladder file predated. The
plan with no gum-disease code read as healthy or gingivitis turns many "no answer" readings of the diagnosis codes
into answers, so the codes alone now answer for every person and find periodontitis less often. Kept as they were:
the LLM judge scorecard (`data/datasets/judge/`; recomputing it needs the LLM endpoint), the Kaggle and Hugging Face
task data and cards (the note set, #467), the per-field MedGemma accuracy (it scores the reader's fields, not a
status), and the seed-stability check (`scripts/49_seed_stability.py` rebuilds the study for five seeds and still
scores six statuses on every review chart; moving it to the scoring defaults is a follow-up).

## The note set rebuilt for adults from the start date (#467, spec 033 US3)

Since #467 the benchmark note set itself holds only the visits the defaults count: `study.build_study` and
`scripts/10_build_study.py` default to adults (18+) and visits from 2021-04-01 (`--all-visits` keeps every one), so the
review set, the answer key, `train.csv`, `visits_structured.csv` and the Kaggle and Hugging Face task data are built
from those visits alone. In the same rebuild the study draws smoking and diabetes at spec 033 US2's published US shares
(11.6% smoke, 15.8% have diabetes; `study.STUDY_RISK_KWARGS`, [synthetic data card](synthetic_data.md)), so the
external model runs are redone once. The diagnosis codes are still written as read, and re-read under the default
absent-code rule at scoring time.

**The scoring-time filter is now a check.** `study.scored_review` still applies the age and start-date filter; on the
rebuilt notes it leaves nothing out (223 of 223 review charts; `tests/test_scoring_defaults.py` fails if it ever leaves
one out), so a build made with other filters can't be scored under the defaults by mistake.

**The review set is 223 charts, not 240.** The review set takes one visit per person, stratified by status. With the
new risk draw only 12 people's latest visit is stage IV, under the 29 the stratum asks for, so the set is 223 (stage
IV 12; the other strata as before). The sampling rule is unchanged.

**Runs made on the old notes are kept, not rescored.** The committed predictions of the GPU encoders (ModernBERT,
GatorTron and the others), MedGemma on Kaggle and Databricks, Llama 3.3 70B on Databricks and the real LLM judge
were made on the 240 notes before the rebuild. `note_set.py` fingerprints the review notes (SHA-256 of each visit id
and note text) and `data/datasets/prediction_note_sets.csv` records the note set each result file was made on; the
ladder (`scripts/28_ladder_vs_truth.py`) scores only files made on the current notes and lists the rest in
`data/datasets/ladder/ladder_pending.csv`, and the leaderboards ([results](results.md)) show them as "rerun pending on
the new notes". The Kaggle and Hugging Face results datasets leave them out. A collected run (`kaggle/record_results.py`)
is stamped with the current notes, and refused if it holds visits that aren't review notes.

Headline numbers before and after the rebuild (SYNTHETIC: agreement with the generator's answer key, not clinical
performance; both columns at the `repo_v2` defaults):

| | Before (#467) | After |
|---|---|---|
| visits in the note set | 4,343 (549 before 2021-04-01 left out when scored) | 3,794 |
| training notes / people | 3,484 / 960 | 3,016 / 896 |
| review charts / scored | 240 / 221 | 223 / 223 |
| review charts at stage IV | 29 | 12 |
| rules, gum measurements first (whole record) | 215 of 221 | 207 of 223 |
| rules, exam form first (the study design's order) | 163 of 221 (73.8%) | 176 of 223 (78.9%) |
| keyword rules / gum measurements alone | 179 / 177 of 221 | 183 / 166 of 223 |
| word counts (TF-IDF) / plus the stage 4 rule | 175 / 196 of 221 | 185 / 191 of 223 |
| word counts plus the X-ray reading / plus the stage 4 rule | 182 / 195 of 221 | 187 / 193 of 223 |
| GPU encoders, MedGemma, Llama 3.3 70B, the LLM judge | scored (ModernBERT + stage 4 rule 201, MedGemma 4B + rule 181 of 221) | rerun pending on the new notes |
| prevalence of periodontitis, rules exam form first (people) | 53.8% of 1,119 | 52.6% of 1,119 |
| prevalence from the done-treatment diagnosis codes alone | 32.0% of 1,119 | 31.0% of 1,119 |
| status classifier (outcome: rules exam form first), 5level / 3level accuracy | 0.795 / 0.882 | 0.791 / 0.857 |
| tooth loss (Open Dental extract) | | unchanged: a separate generator |

The TF-IDF rungs were retrained on the new training notes; this container's scikit-learn also gives slightly
different TF-IDF predictions on the old notes, so their before and after are not a clean comparison of notes alone.
The simulated reviewers, judge and reader (all `simulated_*`), prevalence, the data-quality tables and page, case
profiles, the PerioDx scores, site-level charts, progression, the medical feature sets, seed stability, the presets'
visit parts, the dashboards, the standards page, the leaderboards and the decks were rerun on the new notes.

To get the old behaviour: `--preset repo_v1` for script 58; `scripts/28_ladder_vs_truth.py --grouping six
--all-visits --absent-code no_answer` and `scripts/19_prevalence.py --all-visits --absent-code no_answer` gave
byte for byte what the scripts wrote before spec 032 US8 on the notes before #467 (the old notes need
`scripts/10_build_study.py --all-visits` and the old risk shares, `generate_visits(..., risk_kwargs={})`); `scripts/51_tooth_loss_model.py --start-date "" --test-share 0.3
--cv-folds 0`; in code, pass `grouping="six"`, `min_age=None, start_date=None`, `absent_code="no_answer"`, or
`tooth_loss_dq.GROUP_TYPES[:-1]`. See also [tooth loss](tooth_loss.md).
