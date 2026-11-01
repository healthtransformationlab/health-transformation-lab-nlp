# Study datasets (synthetic)

Built by `python/scripts/10_build_study.py` (seed 42, 1,200 people). Every
value is generated; the notes contained fake PHI that the de-identification
step removed before anything was written here. `build_summary.json` records
the counts and de-id recall for this build.

| File | Use |
|------|-----|
| `train.csv` | Train the AI model. `label` = chart truth, `stated_status` = what the clinician wrote, `grade`, `extent`. |
| `review_tasks.json` | Import into Label Studio (`labelstudio/README.md`). |
| `answer_key/` | **Reviewers must not open this.** Generator truth, each evidence type's reading, the algorithm's call, per chart. Used only by `13_reliability.py`. |
| `method_agreement.csv` | Pairwise agreement between the evidence types (note, exam form, procedure codes and diagnosis codes completed/planned, probing chart, radiograph AI) (status level and perio yes/no). |
| `method_coverage.csv` | How often each evidence type says anything. |
| `deid_report.csv` | Per note: PHI characters, removed, over-redacted, leaked values. |
| `ai_predictions_*.csv` | One file per AI model, predictions on the review charts. |
| `medical_record.csv` | **Synthetic** medical record, one row per person (spec 023): diabetes (the visits' HbA1c ≥ 6.5), hypertension, chronic kidney disease, cardiovascular disease, COPD, blood pressure, ASA class, and `is_synthetic`. Join on `person_id`; HbA1c stays in `visits_structured.csv`. |

## The medical record (`medical_record.csv`, spec 023)

Every value in it is synthetic: no real person's medical record is in it or behind it. Each condition is drawn
from the person's periodontal status and age band at their latest visit, using a published base rate by age and
a published odds ratio for periodontitis, each cited in `python/health_transformation_lab_nlp/medical_record.py`
(`CONDITIONS`). The links are associations built into the generator, not causes; the generator never changes a
chart or a label to fit a condition. Diabetes is the visits' own HbA1c ≥ 6.5, never drawn separately. The record
has its own random stream, so adding it changed no other file here. Haematologic and endocrine conditions other
than diabetes are not modelled yet (no checked source).
