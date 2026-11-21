# Where results are stored, and where Lakebase could help

> Personal learning project; synthetic data only. Databricks features are
> described from public docs. See [DISCLAIMER](../DISCLAIMER.md).

## Today

| What | Where | Format |
|---|---|---|
| Generated datasets (train, review tasks, answer key) | `data/datasets/` | CSV / JSON, in git |
| Reviewer labels | Label Studio project → JSON export → `scripts/12_import_review.py` → `data/review/reviewer_labels.csv` | CSV |
| Reliability, acceptance test, by-level | `data/review/[simulated_]reliability/` | CSV |
| Model predictions, LLM reader details | `data/datasets/ai_predictions_<rung>.csv`, `llm_details_<rung>.csv` | CSV |
| Judge verdicts, cost-effectiveness | `data/corpus/` | CSV / Parquet / PNG |
| Model runs (optional) | MLflow (`pip install -e ".[track]"`; workspace MLflow on Databricks) | MLflow runs |
| On Databricks | `health_transformation_lab.gold_perio_bench.*` Delta tables (notebook 01); `fact_llm_call` (notebook 03) | Delta |
| Every committed result, wherever it ran (spec 016) | `result_files`, `ai_predictions`, `llm_reader_runs` in `gold_perio_bench`, loaded by the **Load results** job after each deploy; source in `data/datasets/results_manifest.csv` | Delta |
| How the models rank and what drives the score (spec 042) | `model_rank`, `model_feature`, `model_contrast`, `model_feature_effect`, `chart_feature_effect`, `driver_fit`, `driver_drop`, `model_chart_result` in `gold_perio_bench`, every column commented; a run per method and a trace per LLM reader call in `/Shared/perio-bench-model-ranking` (traces in `ops_agent_trace.perio_reader_*`), loaded by `python/scripts/75_load_model_drivers.py`; [model_drivers.md](model_drivers.md) | Delta, MLflow |
| OMOP target for model output | `NOTE_NLP` (a flag for review, never `CONDITION_OCCURRENCE`) | OMOP table |

Files in git are fine for a synthetic learning repo: every result is
reproducible from a seed. They aren't a tracking system. Nothing records who
reviewed what and when, label edits over time, or which prompt, model version
and data version produced each number, except by reading commit history.

## A layout for the real workspace

| Layer | Use it for | Why |
|---|---|---|
| **Delta / Unity Catalog** (analytical) | OMOP tables, `NOTE_NLP`, predictions, judge verdicts, reliability tables, cost tables | Large scans, versioned (time travel), governed, joins with OMOP |
| **MLflow** | Each model / prompt run: params (rung, prompt version, shots, adapter), metrics (kappa vs humans, unsafe rate), artifacts | Built for experiment tracking and model registry |
| **Lakebase** (operational Postgres) | Things that change row by row while people work: the review queue and assignments, labels as they're saved, adjudication, judge queue status, a run ledger | Low-latency transactional writes, many small updates, app back-ends |

**Lakebase** is Databricks' managed Postgres. It went GA on 22 January 2026,
with autoscaling, scale-to-zero, instant branching and point-in-time restore.
Tables sync from Unity Catalog into Postgres; Postgres tables sync back to
Delta via change data capture (Lakehouse sync, beta). Lakebase Search adds a
pgvector-compatible vector extension (GA September 2026). Free Edition allows
**one Lakebase project per account**, with scale-to-zero compute
([release notes](https://docs.databricks.com/aws/en/release-notes/lakebase/),
[Free Edition limits](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)).

## Lakebase use cases worth testing

1. **Label Studio's database.** Label Studio can run on PostgreSQL. Pointing it
   at Lakebase keeps every saved label in a governed database and syncs it to
   Delta, with no manual export/import step. Check: reliability numbers from the
   synced Delta table equal those from the JSON export path.
2. **Review workflow state.** Which reviewer has which chart, due dates,
   blinded vs unblinded rounds, adjudication of disagreements. That's the
   bookkeeping the multi-reviewer validation step needs. A small Databricks App
   on Lakebase can serve it (Free Edition allows 3 apps).
3. **Run ledger.** One row per prediction run: rung, model id and revision,
   prompt version (`judge-v2`, `reader-v2`), shots, adapter, dataset hash, git
   commit, and who ran it. Joins to MLflow run ids. Answers "which settings made
   this number?"
4. **Judge and reader queues.** Status per note (queued, sent, gate failed,
   done) for million-note batch jobs, so a restart resumes instead of re-paying.
5. **Vector store for retrieval** (see [rag_and_vocabulary.md](rag_and_vocabulary.md)):
   OMOP concept names and synonyms, or labeled example notes, with embeddings in
   Lakebase Search next to the relational vocabulary tables.

Keep in Delta: anything analytical or large (OMOP, a million notes,
predictions). Keep in MLflow: model runs. Lakebase is for the working state
in between.

## Implemented

- `health_transformation_lab_nlp/db.py` + `scripts/05_load_omop_db.py`: OMOP CDM 5.4 (OHDSI Postgres DDL)
  + dental extension + synthetic data into any Postgres, including Lakebase. Tested
  on Postgres 16 in CI; the `perio_chart` view reproduces every label.
- `databricks/notebooks/04_load_lakebase.py` and the `load_lakebase` bundle job, with
  `lakebase_instance` / `lakebase_schema` set per environment (dev, uat, prod).
- R: `r/R/01_etl_synthea.R` defaults to Postgres / Lakebase (`DENTAL_DBMS=postgresql`);
  Databricks SQL (`spark`) is the other option. DuckDB has been removed.

## Results from anywhere, in one place (spec 016)

MedGemma runs where a GPU is free: a Databricks job, Kaggle (the *Run MedGemma on a free Kaggle GPU* workflow) or a laptop.
The GPU encoders of spec 002 T017 do too: the Databricks `encoder_gpu` job, or Kaggle (the *Fine-tune the GPU
encoders on a free Kaggle GPU* workflow, `kaggle/encoder_gpu.ipynb`, with that job's rungs and learning rates).
All of them end in the same gold tables:

1. **Kaggle**: when the workflow collects a run (`wait` or `collect_only`, with `open_pr` on), it opens a pull
   request that adds `ai_predictions_<rung>.csv` (and, for MedGemma, `llm_details_<rung>.csv`) to `data/datasets/` and a row per
   file in `results_manifest.csv` (`source = kaggle`, the workflow run URL). A run with fewer rows than the
   committed file (a 10-note test) is never committed. The PR is opened with the workflow's token, which doesn't
   start CI: push a commit to it to run the checks. The repo setting *Allow GitHub Actions to create and approve
   pull requests* must be on; if it's off, the branch is pushed and the log links to open the PR by hand.
2. **Laptop**: commit the CSVs as before; they load with `source = repo`.
3. **Databricks**: the MedGemma reader job writes `fact_prediction` and `fact_llm_call` itself, with
   `source_code = databricks`, its job `run_id` and `run_ts`; a retry of the run replaces its rows. Its CSVs in the
   Git folder are scratch.

After every deploy, `deploy.yml` starts **Load results** (`databricks/notebooks/10_load_results.py`). It appends
each file version (SHA-256) it hasn't loaded yet to `dim_result_file`, `fact_prediction` (method, visit, predicted status) and
`fact_llm_call`, and logs one MLflow run per new LLM file (gate-failure and fallback rates, agreement with the
answer key). Loading again adds nothing; a changed file is a new version and the old rows stay. `simulated_*`
files are never loaded. If Databricks is down at the deploy, or Load results fails, *Catch up Databricks after
an outage* runs it later by itself ([operations.md](operations.md#when-databricks-is-down-catch-up-without-anyone-remembering-issue-189)).

Every gold table, column by column, with ERDs: [gold_tables.md](gold_tables.md).

```sql
select source_code, method_name, count(*) from health_transformation_lab.gold_perio_bench.fact_prediction group by all;
```

## Cautions

- Only de-identified data in Label Studio and any review app; the same final de-identification check (leak gate) applies.
- Free Edition: one project, scale-to-zero (first query after idle is slower), fair-use quotas.
- Lakehouse sync and LTAP direct writes were beta at last check; confirm status before relying on them.
