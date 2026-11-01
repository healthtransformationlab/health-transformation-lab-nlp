# Study datasets (synthetic)

Built by `python/scripts/10_build_study.py` (seed 42, 1,200 people). Every
value is generated; the notes contained fake PHI that the de-identification
step removed before anything was written here. `build_summary.json` records
the counts and de-id recall for this build.

| File | Use |
|------|-----|
| `train.csv` | Train the AI model. `label` = chart truth, `stated_status` = what the clinician wrote, `grade`, `extent`. |
| `review_tasks.json` | Import into Label Studio (`labelstudio/README.md`). |
| `answer_key/` | **Reviewers must not open this.** Generator truth, each evidence type's reading, the algorithm's call, per chart. Used by `13_reliability.py` and the scoring scripts. `answer_key/reference_answers.csv`: the correct status, grade and extent per review visit, the fields the MedGemma reader returns (`53_reference_answers.py`, spec 004 US5). |
| `method_agreement.csv` | Pairwise agreement between the evidence types (note, exam form, procedure codes and diagnosis codes completed/planned, probing chart, radiograph AI) (status level and perio yes/no). |
| `method_coverage.csv` | How often each evidence type says anything. |
| `deid_report.csv` | Per note: PHI characters, removed, over-redacted, leaked values. |
| `ai_predictions_*.csv` | One file per AI model, predictions on the review charts. |
