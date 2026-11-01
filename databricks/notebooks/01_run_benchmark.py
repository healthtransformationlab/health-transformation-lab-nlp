# Databricks notebook source
# MAGIC %md
# MAGIC # Dental notes → periodontal status: benchmark on Databricks Free Edition
# MAGIC
# MAGIC Runs the Python side of the repo end to end on serverless (CPU). Synthetic data only.
# MAGIC
# MAGIC 1. Build synthetic OMOP tables + labeled SOAP notes (no Synthea/Java needed; stand-in population)
# MAGIC 2. Patient-level split
# MAGIC 3. Baseline rungs (rules, structured, TF-IDF) — seconds
# MAGIC 4. One encoder rung (DistilBERT) — minutes on CPU at this sample size; `run_encoder=false` skips it
# MAGIC    and the torch install (the bundle's dev target does, as a quick smoke test)
# MAGIC 5. Optional: LLM challenger via `ai_query` on a Foundation Model endpoint
# MAGIC 6. Results and OMOP tables land as Delta in the gold schema; files in the landing volume
# MAGIC    (`databricks/resources/unity_catalog.yml`). The study notes are `dim_study_note` (overwritten) and the
# MAGIC    scores `benchmark_metric`, replaced per job run so a retry adds nothing (spec 031)
# MAGIC
# MAGIC **Free Edition notes:** serverless is Python/SQL only (no R). Limited serverless GPU is
# MAGIC available from the notebook compute selector, subject to capacity and fair-use limits
# MAGIC ([Databricks, June 2026](https://www.databricks.com/blog/whats-coming-next-free-edition));
# MAGIC GPU *serving* endpoints are not. CPU is enough for this notebook. The R side of
# MAGIC this repo runs locally or in Posit against the same `labeled_notes.csv` + `split.csv`.
# MAGIC Get the repo in via *Workspace → Create → Git folder* with the public GitHub URL.

# COMMAND ----------

dbutils.widgets.dropdown("run_encoder", "false", ["true", "false"])   # uat/prod jobs set "true" (databricks.yml)

# COMMAND ----------

import subprocess, sys

run_encoder = dbutils.widgets.get("run_encoder") == "true"
pip = [sys.executable, "-m", "pip", "install", "-q"]
if run_encoder:
    # CPU-only torch (~200 MB) instead of PyPI's default CUDA build (~2.5 GB with the
    # nvidia-* wheels); serverless here is CPU. Installed first so [models] finds it.
    subprocess.check_call(pip + ["torch", "--index-url", "https://download.pytorch.org/whl/cpu"])
subprocess.check_call(pip + ["-e", "../../python[models,track]" if run_encoder else "../../python[track]"])

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import os
import time

run_encoder = dbutils.widgets.get("run_encoder") == "true"   # widget defined above the install

dbutils.widgets.text("git_commit", "")   # set by the job: the commit it was deployed from
from health_transformation_lab_nlp import tracking as _tracking
_tracking.use_git_commit(dbutils)   # MLflow runs and the scripts it starts are tagged with it
dbutils.widgets.text("catalog", "health_transformation_lab")
dbutils.widgets.text("schema", "gold_perio_bench")              # tables
dbutils.widgets.text("landing_schema", "landing_perio_bench")   # data volume
dbutils.widgets.text("n_people", "300")
dbutils.widgets.dropdown("leak_assessment", "false", ["true", "false"])
dbutils.widgets.text("experiment_id", "")   # set per target by the bundle (resources/jobs.yml)
dbutils.widgets.text("run_id", "")          # the job run ({{job.run_id}}): the batch key, the same for every retry
catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
run_id = dbutils.widgets.get("run_id") or f"manual-{time.strftime('%Y%m%dT%H%M%S')}"
landing = dbutils.widgets.get("landing_schema")

# The bundle creates these; IF NOT EXISTS covers running the notebook by hand.
for s in (schema, landing):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{s}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{landing}.data")
os.environ["DENTAL_DATA_ROOT"] = f"/Volumes/{catalog}/{landing}/data"

# COMMAND ----------

# MAGIC %md ## 1–2. Build data and split

# COMMAND ----------

import sys
import pandas as pd
from health_transformation_lab_nlp import paths
from health_transformation_lab_nlp.build import build

# paths reads the env var at import time; reload after setting it.
import importlib; importlib.reload(paths)
sys.path.insert(0, str(paths.REPO_ROOT / "eval"))
from split import make_split
from score import score

labeled = build(paths.OMOP_DIR, paths.LABELS_DIR, synthea_csv=None,
                n_people=int(dbutils.widgets.get("n_people")),
                leak_assessment=dbutils.widgets.get("leak_assessment") == "true")
split = make_split(labeled)
split.to_csv(paths.LABELS_DIR / "split.csv", index=False)
df = labeled.merge(split, on="person_id")
train, test = df[df.split == "train"], df[df.split == "test"]
print(len(train), len(test))

# COMMAND ----------

# OMOP + labels as Delta, so Genie / SQL / R-via-Connect can read them. The labelled notes go under their gold
# names (spec 031), each row with this run's key.
from health_transformation_lab_nlp import gold_names
from health_transformation_lab_nlp.delta import replace_batch

batch = {"run_id": run_id, "run_ts": pd.Timestamp.now(tz="UTC"), "git_commit": dbutils.widgets.get("git_commit")}
for t in ["person", "visit_occurrence", "measurement", "note"]:
    spark.createDataFrame(pd.read_parquet(paths.OMOP_DIR / f"{t}.parquet")) \
         .write.mode("overwrite").saveAsTable(f"{catalog}.{schema}.{t}")
spark.createDataFrame(gold_names.to_gold(df.assign(**batch), "dim_study_note")).write.mode("overwrite") \
     .option("overwriteSchema", "true").saveAsTable(f"{catalog}.{schema}.dim_study_note")
display(spark.table(f"{catalog}.{schema}.dim_study_note").limit(5))

# COMMAND ----------

# MAGIC %md ## 3–4. Ladder

# COMMAND ----------

import mlflow
from health_transformation_lab_nlp.registry import load_registry
from health_transformation_lab_nlp.rungs import make_rung

reg = load_registry()
if dbutils.widgets.get("experiment_id"):
    mlflow.set_experiment(experiment_id=dbutils.widgets.get("experiment_id"))
else:
    mlflow.set_experiment(f"/Users/{spark.sql('select current_user()').first()[0]}/health-transformation-lab-nlp")

def run(rung_id, **kw):
    with mlflow.start_run(run_name=rung_id):
        model = make_rung(rung_id, reg, **kw).fit(train)
        pred, proba = model.predict(test)
        res = score(test["label"], pred, proba, model_id=rung_id)
        headline = res[res["class"] == ""].set_index("metric")["value"].dropna()
        mlflow.log_params({"rung": rung_id, "n_train": len(train), "n_test": len(test), **kw})
        mlflow.log_metrics(headline.to_dict())
        return res

results = [run(r) for r in ["rules_baseline", "structured_baseline", "tfidf_logreg"]]

# COMMAND ----------

# One encoder rung, small for CPU (~600 notes x 2 epochs x 192 tokens). On serverless CPU this took
# over 16 minutes, so the bundle turns it off in dev and on in uat and prod.
if run_encoder:
    results.append(run("distilbert-base", epochs=2, max_len=192, batch_size=16))

# COMMAND ----------

all_res = pd.concat(results)
# One batch per job run: a retry or repair replaces this run's rows instead of adding them again (spec 031).
metrics = all_res.astype({"value": "float"}).assign(timestamp=pd.to_datetime(all_res["timestamp"], utc=True),
                                                    job_run_id=run_id, run_ts=batch["run_ts"],
                                                    git_commit=batch["git_commit"])
n = replace_batch(spark, gold_names.to_gold(metrics, "benchmark_metric"), f"{catalog}.{schema}.benchmark_metric",
                  {"run_id": run_id})
print(f"{catalog}.{schema}.benchmark_metric: {n} rows for run {run_id}")
display(all_res[all_res["class"] == ""].pivot(index="model_id", columns="metric", values="value").round(3))

# COMMAND ----------

# MAGIC %md ## 5. Optional: LLM challenger
# MAGIC Zero-shot on the test notes via a Foundation Model endpoint. Check the endpoint name under
# MAGIC *Serving* in your workspace; pay-per-token endpoints vary by region and over time.
# MAGIC Skipped unless `llm_endpoint` is set (e.g. `databricks-meta-llama-3-3-70b-instruct`).

# COMMAND ----------

dbutils.widgets.text("llm_endpoint", "none")
llm_endpoint = dbutils.widgets.get("llm_endpoint")
if llm_endpoint not in ("", "none"):
    import re
    if not re.fullmatch(r"[\w.-]+", llm_endpoint):
        raise ValueError(f"llm_endpoint is not a serving endpoint name: {llm_endpoint!r}")
    llm = spark.sql(f"""
        SELECT note_id, truth_status_code AS label,
          ai_query(
            '{llm_endpoint}',
            CONCAT('Classify the periodontal status in this dental SOAP note. Answer with exactly one of: ',
                   'healthy, gingivitis, periodontitis_stage_1, periodontitis_stage_2, periodontitis_stage_3, periodontitis_stage_4.\\n\\n',
                   note_text),
            failOnError => false
          ).result AS pred
        FROM {catalog}.{schema}.dim_study_note
        WHERE split_code = 'test'""").toPandas()
    llm["pred"] = llm["pred"].fillna("").str.strip().str.lower()
    display(score(llm["label"], llm["pred"], None, model_id="llm_challenger"))
