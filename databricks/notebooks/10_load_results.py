# Databricks notebook source
# MAGIC %md
# MAGIC # Load results: every committed model result into the gold tables (spec 016)
# MAGIC
# MAGIC Model answers on the 240 synthetic review notes are made in three places: Databricks jobs (which
# MAGIC write their own tables), Kaggle's free GPU (collected into a pull request by the `kaggle-medgemma`
# MAGIC workflow) and laptops. Whatever is committed under `data/datasets/` is deployed with the bundle;
# MAGIC this job, run after every deploy, appends each file version it hasn't seen yet:
# MAGIC
# MAGIC - `dim_result_file`: one row per file version (SHA-256), with its source (`kaggle`, `repo`) and run URL
# MAGIC - `fact_prediction`: method, visit_id, predicted status
# MAGIC - `fact_llm_call`: the LLM reader details, next to the rows the MedGemma reader job writes
# MAGIC   (`source_code = databricks`)
# MAGIC
# MAGIC Columns take their gold names (spec 018, `health_transformation_lab_nlp.gold_names`) as they are written.
# MAGIC
# MAGIC and logs one MLflow run per new LLM file. Running it again adds nothing. `simulated_*` files are
# MAGIC never loaded. Serverless CPU.

# COMMAND ----------

# MAGIC %pip install -q -e ../../python[track]

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

import os
import re
from pathlib import Path

import pandas as pd
from health_transformation_lab_nlp import gold_names, grader_tables, results_store, tracking
from pyspark.sql import functions as F

dbutils.widgets.text("git_commit", "")  # noqa: F821  set by the job: the commit it was deployed from
commit = tracking.use_git_commit(dbutils)  # noqa: F821
dbutils.widgets.text("catalog", "health_transformation_lab")  # noqa: F821
dbutils.widgets.text("schema", "gold_perio_bench")  # noqa: F821
dbutils.widgets.text("experiment_name", "")  # noqa: F821  the bundle's experiment; empty: no MLflow runs
catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")  # noqa: F821
experiment = tracking.setting(dbutils.widgets.get("experiment_name"))  # noqa: F821  "None" or "": no runs (#131)


def table(name: str) -> str:
    return f"{catalog}.{schema}.{name}"


# COMMAND ----------

# The files deployed with the bundle, next to this notebook (as notebook 03 reads them). If there are none,
# say so and stop; a run with nothing new must not display an empty table, which crashed every run after the
# first one (issue #71).
data_dir = Path("../../data/datasets").resolve()
if not data_dir.is_dir() or not (files := results_store.result_files(data_dir)).shape[0]:
    raise RuntimeError(f"No result files in {data_dir}: expected ai_predictions_*.csv / llm_details_*.csv "
                       "deployed with the bundle (data/datasets/). Check the deploy synced data/.")
print("reading", data_dir)
loaded = set()
if spark.catalog.tableExists(table("dim_result_file")):  # noqa: F821
    loaded = {r.file_sha256 for r in spark.table(table("dim_result_file")).select("file_sha256").collect()}  # noqa: F821
# The reader job (03) writes its CSVs into this folder and loads them itself, source 'databricks': those
# versions are already in the tables, so loading them again would duplicate its rows as source 'repo'.
if spark.catalog.tableExists(table("fact_prediction")):  # noqa: F821
    reader = spark.table(table("fact_prediction"))  # noqa: F821
    loaded |= {r.file_sha256 for r in reader.where("source_code = 'databricks'").select("file_sha256").distinct().collect()}
new = results_store.new_files(files, loaded)
print(f"{len(files)} result files deployed, {len(new)} new or changed")
if len(new):
    display(new)  # noqa: F821

# COMMAND ----------

now = pd.Timestamp.now(tz="UTC")


def append(df: pd.DataFrame, name: str):
    """Append these file versions under their gold names. Rows of the same versions are deleted first, so a load
    that failed partway (no dim_result_file row yet) is redone, not duplicated. An empty column takes the type the
    table already has (an all-null `error_text` reads as a number in one file, text in another); other columns keep their own type,
    so a real mismatch fails loudly instead of turning values to null. New columns are added (mergeSchema)."""
    if not len(df):
        return
    df = gold_names.to_gold(df.assign(git_commit=commit, loaded_at=now), name)
    empty = [c for c in df.columns if df[c].isna().all()]
    sdf = spark.createDataFrame(df.astype({c: "string" for c in empty}))  # noqa: F821
    if spark.catalog.tableExists(table(name)):  # noqa: F821
        schema = spark.table(table(name)).schema  # noqa: F821
        hashes = ", ".join(f"'{h}'" for h in sorted(set(df.file_sha256)) if re.fullmatch(r"[0-9a-f]{64}", h))
        if hashes:
            # the reader job's own rows carry their CSV's sha256 too, keyed by run: never touch them here
            spark.sql(f"DELETE FROM {table(name)} WHERE file_sha256 IN ({hashes}) AND source_code <> 'databricks'")  # noqa: F821
        for field in schema:
            if field.name in empty:
                sdf = sdf.withColumn(field.name, F.col(field.name).cast(field.dataType))
    sdf.write.mode("append").option("mergeSchema", "true").saveAsTable(table(name))


preds = new[new.kind == "predictions"]
details = new[new.kind == "llm_details"]
append(results_store.prediction_rows(preds, data_dir), "fact_prediction")
append(results_store.detail_rows(details, data_dir).assign(run_ts=now), "fact_llm_call")
append(new, "dim_result_file")           # last: a failure above leaves these versions to load next time

# COMMAND ----------

# One MLflow run per new LLM file, in the bundle's experiment. Tracking never fails the job.
if experiment and len(details):
    os.environ["MLFLOW_TRACKING_URI"] = "databricks"
    os.environ["DENTAL_MLFLOW_EXPERIMENT"] = experiment
    truth = pd.read_csv(data_dir / "answer_key" / "review_key.csv").set_index("visit_id").truth_status
    for f in details.itertuples():
        d = pd.read_csv(data_dir / f.file)
        first = d.iloc[0]
        params = {"method": f.method, "source": f.source, "run_url": f.run_url, "file_sha256": f.sha256,
                  "prompt_version": first.get("prompt_version", ""), "shots": first.get("shots", "")}
        with tracking.track("load_results", f"{f.method} ({f.source})", params=params) as run:
            run.log_metrics(results_store.llm_run_metrics(d, truth))

print("loaded:", list(new.file) or "nothing new")

# COMMAND ----------

# The graders' tables (spec 019): data quality, and the lab grader (a SIMULATED sample until real runs exist). Each is small and built whole from the
# deployed CSVs, so it is overwritten on every run: a rerun leaves the same rows. sha256 says which files it holds.
for name, df in {**grader_tables.dq_tables(data_dir), **grader_tables.lab_tables(data_dir)}.items():
    df = gold_names.to_gold(df.assign(git_commit=commit, loaded_at=now), name)   # gold column names
    empty = [c for c in df.columns if df[c].isna().all()]
    spark.createDataFrame(df.astype({c: "string" for c in empty})) \
        .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table(name))  # noqa: F821
    print(f"{name}: {len(df)} rows")
