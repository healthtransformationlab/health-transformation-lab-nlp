# Judge scorecard (spec 012)

Every phenotyping system's answer on the 240 synthetic review charts before #467, an LLM judge's reading of the
same charts, and every README phenotyping metric computed twice: against the generator's truth and
against the judge. Built by `python/scripts/36_judge_scorecard.py`; method in
`python/dental_omop_nlp/judge_scorecard.py`; R twin `r/R/11_judge_scorecard.R`.

These files were made on the notes before #467 rebuilt them, and are kept as they ran: the leaderboard
(`docs/results.md`) leaves them out until the judge is rerun on the current 223 notes.

| File | What it is |
|---|---|
| `*chart_answers.csv` | visit_id, system, answer (one of six statuses, empty = none), note difficulty |
| `*judgments.csv` | one row per judge call: `status` (the judge's own status, no answer shown) or `verdict` (is this answer right?), quote, gate result, endpoint, prompt version, tokens |
| `*judge_metrics.csv` | per system and metric: `vs_truth` (the README number, by the README's names in `metric_label`), `vs_judge`, `difference` on the charts the judge gave a status for, and judge-corrected accuracy with a 95% range |
| `*judge_run.csv` | cost and speed per call type: calls, tokens, US$ at the endpoint's list price (total, per chart), latency (mean, median, 95th percentile), quote-gate failures, endpoint errors |
| `*judge_agreement.csv` | the judge's own status against the truth: coverage, agreement (95% range), kappa; overall, by truth status, by note difficulty |

- **`simulated_*`**: the simulated judge (truth with injected errors). A pipeline dry run, never a
  result. Rebuilt by `python/scripts/make_parity_inputs.sh`.
- **No prefix**: a real LLM judge run on a Databricks pay-per-token endpoint. Labelled *LLM
  judgment*; the endpoint and prompt version are in every row.

Notes come from `data/datasets/answer_key/review_key.csv`: synthetic, de-identified and through the
leak gate when the study was built. Only those notes go to an endpoint. The judge is checked
against the truth (`judge_agreement`), not against people: the reviewers in this repo are simulated.
