# Plan: How each model ranks, and what drives its score (spec 042)

## Method (US1)

`python/health_transformation_lab_nlp/model_drivers.py`, called by `python/scripts/74_model_drivers.py`.

- **Inputs**: `readme_results.load_inputs()` and `phenotype_predictions()`: the same predictions and truth the
  leaderboard uses, at the default five status groups; no answer counts wrong.
- **Features of a method**: from its id (`+cw`, `+sN`, `+lrX`, `+rules4`) and `models.yaml` (`domain`, `max_len`);
  the architecture family from each model's card.
- **Rank**: correct count, the leaderboard's bootstrap CI, the paired rank range among the 43
  (`readme_results.paired_rank_range`), exact McNemar against the leader, and where the leader-only charts are
  (L3, stage 4).
- **Contrasts**: all pairs differing in exactly one of approach, family, size, domain, input, stage 4 rule, class
  weighting, seed, learning rate; oriented starting point (a) to change (b).
- **Drivers**: logistic regression over (method, chart) runs; chart facts (difficulty, true group, diagnosis scheme,
  style, measurements given, copy-forward, length band), model features, or both; 5-fold out-of-fold AUC grouped by
  chart, 95% CI by chart bootstrap (1,000); leave-one-group-out AUC drop.

## Loading (US2)

`python/scripts/75_load_model_drivers.py`, runnable from a laptop, a cloud session or a Databricks job:

- Tables: each CSV with the batch key, written by the SQL Statement API (`CREATE OR REPLACE TABLE ... AS SELECT` over
  inline `VALUES`), then `COMMENT ON TABLE` and `ALTER TABLE ... ALTER COLUMN ... COMMENT` from `model_drivers.COMMENTS`.
- MLflow: experiment `/Shared/perio-bench-model-ranking`; a run per method tagged `git_commit_sha`; a trace per row of
  `llm_details_<model>.csv` (root span LLM: the scrubbed prompt reference and raw answer; token use; latency), with
  assessments from code scorers comparing the answer to the answer key.
