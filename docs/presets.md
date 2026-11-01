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
| `repo_v1` | Today's defaults, every one written out. A test (`tests/test_presets.py`) checks each against the code's own default, so when a default changes (spec 032 US8) the preset has to follow or the test fails. |
| `exploratory_1` | Common choices of published record studies turned on together: five statuses (three also reported), adults only, a start date, a plan with no gum-disease code read as healthy or gingivitis, a split by visit at 20% with 5-fold tuning, insurance in the consistency split, and the reliability (ICC) of attachment loss. |

## Run one

```bash
cd python && python scripts/58_preset.py --preset exploratory_1
```

It runs every part under the preset and under `repo_v1`, on freshly generated synthetic data with fixed seeds (1,200
people for the visit-level study set, 6,000 patients for the Open Dental extract, generator seed 42), and writes one
file per part and preset to `data/datasets/presets/synthetic_preset_<name>_<part>.csv`, every row with
`data_label = synthetic` and `preset_name`. To keep the run to about six minutes it uses one generator seed and no
bootstrap intervals, where `scripts/51_tooth_loss_model.py` uses five seeds and 1,000 resamples; so the tooth-loss
numbers here have no intervals. A preset run writes only these files; every other committed result stays as it was.

The start dates are synthetic stand-ins for "the date a newer classification was adopted": 2021-04-01 for the visits
(which start in late 2020) and 2018-01-01 for the extract (whose practices switch diagnosis lists from 2018).

## The settings

| Setting | `repo_v1` | `exploratory_1` | Changed |
|---|---|---|---|
| status grouping | six | five | yes |
| also reported | none | three | yes |
| visits: minimum age | none | 18 | yes |
| visits: start date | none | 2021-04-01 | yes |
| plan with no gum-disease code | no answer | healthy or gingivitis | yes |
| stage IV rules reported | all six | all six | no (spec 032 US4 already reports the 20-teeth and 10-pairs rules) |
| tooth loss: minimum age | 18 | 18 | no |
| tooth loss: start date | none | 2018-01-01 | yes |
| tooth loss: split | by patient, 30% | by tooth (`visit`), 20% | yes |
| tooth loss: XGBoost tuning | none | 5-fold | yes |
| status classifier: split | by person, 20% | by visit, 20% | yes |
| status classifier: tuning | 5-fold | 5-fold | no |
| consistency groups | office, provider, sex, race, exam year, age band | the same plus insurance type | yes |
| CAL reliability ICC | off | on | yes |

## Headline comparison (SYNTHETIC)

| | `repo_v1` | `exploratory_1` |
|---|---|---|
| visits in the study set (left out: before the start date) | 4,343 (0) | 3,794 (549) |
| rules phenotype (`algorithm_design`): macro F1 at the main grouping | 0.739 (six) | 0.740 (five); 0.843 (three) |
| rules phenotype: periodontitis sensitivity / specificity | 0.973 / 0.878 | 0.925 / 0.889 |
| the note's stated status: macro F1 at the main grouping | 0.788 (six) | 0.803 (five) |
| tooth loss, held-out teeth (completed label set, shared features) | 242 | 88 |
| tooth loss: AUC, logistic / XGBoost | 0.836 / 0.856 | 0.895 / 0.827 |
| tooth loss: patients in both the training and the test part | 0 | 6 |
| status classifier, 5level: accuracy / macro F1 | 0.797 / 0.746 | 0.768 / 0.716 |
| status classifier, 3level: accuracy / macro F1 | 0.881 / 0.864 | 0.867 / 0.846 |
| status classifier: people in both the training and the test part | 0 | 405 |
| stage IV, all patients at stage III-IV: every missing tooth / fewer than 20 teeth / fewer than 10 pairs / truth | 273 / 46 / 181 / 97 | 127 / 25 / 92 / 45 |
| CAL reliability: ICC for the same site charted again (SEM) | not run | 0.683 (0.82 mm) |

How to read it:

- `repo_v1` reproduces the committed status-classifier results (`data/datasets/classify_status/`, 0.797 and 0.881
  accuracy), as it should: it is today's defaults.
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

Spec 032 US8 makes most of the `exploratory_1` settings the defaults, keeping the split by person; today's defaults
stay available as `repo_v1`. See also [tooth loss](tooth_loss.md).
