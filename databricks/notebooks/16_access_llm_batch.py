# Databricks notebook source
# MAGIC %md
# MAGIC # AccessBench LLM batch (spec 043, #917)
# MAGIC
# MAGIC Scores up to five synthetic AccessBench questions against one or more pay-per-token
# MAGIC Foundation Model endpoints (or a simulated dry-run), then writes
# MAGIC `gold_access_bench.dim_access_question` and `fact_access_answer`.
# MAGIC
# MAGIC Default `mode` is **simulated** (no model calls, no spend). Set `mode=live` and
# MAGIC `endpoints` to run against Serving. Stops further live calls when `max_usd` is exceeded.
# MAGIC Synthetic prompts with planted identifiers only; every simulated row is labelled.

# COMMAND ----------

import subprocess, sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-e", "../../python"])

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("git_commit", "")   # set by the job: the commit it was deployed from
dbutils.widgets.text("telemetry", "azure")  # noqa: F821  spec 014: off / console / azure / otlp
from health_transformation_lab_nlp import telemetry

telemetry.use_databricks_secret(dbutils, dbutils.widgets.get("telemetry"))  # noqa: F821
telemetry.setup()
telemetry.start_script("16_access_llm_batch", data_label="synthetic")
from health_transformation_lab_nlp import tracking as _tracking
_tracking.use_git_commit(dbutils)

dbutils.widgets.text("catalog", "health_transformation_lab")
dbutils.widgets.text("schema", "gold_access_bench")
dbutils.widgets.text("run_id", "")
dbutils.widgets.text("endpoints", "sim:llama")
dbutils.widgets.text("limit", "5")
dbutils.widgets.dropdown("fixture", "phi", ["phi", "perio_screening", "discount_voucher", "all"])  # noqa: F821  #929
dbutils.widgets.dropdown("controls", "true", ["true", "false"])  # noqa: F821  spec 045 US3: seeded control answers
dbutils.widgets.text("answer_max_tokens", "1500")  # noqa: F821  #931: answers were cut off at 300
dbutils.widgets.text("judge_endpoint", "sim:judge")
dbutils.widgets.text("max_usd", "1")
dbutils.widgets.dropdown("mode", "simulated", ["simulated", "live"])
dbutils.widgets.text("usd_per_million_in", "0")
dbutils.widgets.text("usd_per_million_out", "0")
dbutils.widgets.text("experiment_id", "")  # noqa: F821  spec 045 US6: the bundle's MLflow experiment; empty skips logging

# COMMAND ----------

import os

import pandas as pd
from databricks.sdk import WorkspaceClient

from health_transformation_lab_nlp import access_batch, gold_names
from health_transformation_lab_nlp.delta import replace_batch

catalog = dbutils.widgets.get("catalog").strip()
schema = dbutils.widgets.get("schema").strip()
run_id = dbutils.widgets.get("run_id").strip() or "manual"
mode = dbutils.widgets.get("mode").strip()
endpoints = [e.strip() for e in dbutils.widgets.get("endpoints").split(",") if e.strip()]
limit = int(dbutils.widgets.get("limit").strip() or "5")
fixture = dbutils.widgets.get("fixture").strip() or "phi"  # noqa: F821
controls = dbutils.widgets.get("controls").strip() == "true"  # noqa: F821
answer_max_tokens = int(dbutils.widgets.get("answer_max_tokens").strip() or "1500")  # noqa: F821
judge_endpoint = dbutils.widgets.get("judge_endpoint").strip() or "sim:judge"
max_usd = float(dbutils.widgets.get("max_usd").strip() or "1")
usd_in = float(dbutils.widgets.get("usd_per_million_in").strip() or "0")
usd_out = float(dbutils.widgets.get("usd_per_million_out").strip() or "0")
run_ts = pd.Timestamp.now(tz="UTC")
git_commit = dbutils.widgets.get("git_commit").strip()

chat = None
if mode == "live":
    w = WorkspaceClient()
    host = w.config.host.rstrip("/")
    token = w.config.authenticate()["Authorization"].split(" ", 1)[1]
    os.environ["DATABRICKS_HOST"] = host
    os.environ["DATABRICKS_TOKEN"] = token
    os.environ.setdefault("READER_BASE_URL", f"{host}/serving-endpoints")
    os.environ.setdefault("READER_API_KEY", token)

out = access_batch.run(
    endpoints=endpoints,
    limit=limit,
    fixture=fixture,
    controls=controls,
    answer_max_tokens=answer_max_tokens,
    mode=mode,
    judge_endpoint=judge_endpoint,
    max_usd=max_usd,
    run_id=run_id,
    run_ts=run_ts,
    git_commit=git_commit,
    chat=chat,
    usd_per_million_in=usd_in,
    usd_per_million_out=usd_out,
)

key = {"run_id": run_id}
for name, df in out.items():
    table = f"{catalog}.{schema}.{name}"
    n = replace_batch(spark, gold_names.to_gold(df, name), table, key)  # noqa: F821
    print(f"wrote {n} rows to {table}")

fact = out["fact_access_answer"]

# spec 045 US6 (#961): the same grades in MLflow's evaluation view, one run per model. No model is called again,
# and a logging failure leaves the gold tables as written.
experiment_id = dbutils.widgets.get("experiment_id").strip()  # noqa: F821
if experiment_id:
    try:
        import mlflow
        from health_transformation_lab_nlp import access_keypoint_judge, access_mlflow
        mlflow.set_experiment(experiment_id=experiment_id)
        runs = access_mlflow.log_run(fact, {r["id"]: r for r in access_batch.all_items()}, batch_run_id=run_id,
                                     judge_endpoint=judge_endpoint, prompt_version=access_keypoint_judge.PROMPT_VERSION,
                                     configure=False)
        print(f"MLflow evaluation runs in experiment {experiment_id}: {runs}")
    except Exception as e:  # noqa: BLE001 - optional: warn and keep the gold write
        print(f"WARNING: MLflow logging skipped: {type(e).__name__}: {e}")

ctl = fact[fact["endpoint"].str.startswith("control:")]
if len(ctl):
    # a judge that misses the seeded harmful answers can't support "no live answer was harmful"
    print(f"controls graded as expected: {int(ctl['is_control_match'].fillna(False).sum())} of {len(ctl)}")
    display(ctl[["question_id", "endpoint", "harm", "is_next_step_pass", "covered_positive_point_count", "is_control_match"]])  # noqa: F821
display(fact)  # noqa: F821
