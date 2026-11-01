# Databricks notebook source
# MAGIC %md
# MAGIC # MedGemma as a note reader (exploratory, spec 004)
# MAGIC
# MAGIC Personal learning project; synthetic notes only. See `docs/medgemma.md`.
# MAGIC
# MAGIC **Compute:** on Free Edition pick the serverless **GPU** option in the notebook compute
# MAGIC selector (limited, subject to capacity and fair use). Free Edition has no GPU serving
# MAGIC endpoints, so the model runs here in the notebook. On paid workspaces you can instead
# MAGIC serve it and use `--backend openai` or `ai_query`.
# MAGIC
# MAGIC **Compare with BERT:** set `limit` to 0 (all 240 review charts), optionally `lora_train` to
# MAGIC fine-tune first (the BERT encoders were fine-tuned on the same `train.csv`); the last cells run
# MAGIC `29_medgemma_vs_bert.py` against the committed encoder predictions.
# MAGIC
# MAGIC **Before running:** accept the HAI-DEF terms for the model on Hugging Face and put a
# MAGIC read token in a secret scope (`health_transformation_lab` / `hf_token`).

# COMMAND ----------

# MAGIC %pip install -q -e ../../python[llm,lora,azure]
# MAGIC %restart_python

# COMMAND ----------

import os
import time

dbutils.widgets.text("git_commit", "")  # noqa: F821  set by the job: the commit it was deployed from
from health_transformation_lab_nlp import tracking as _tracking
_tracking.use_git_commit(dbutils)  # noqa: F821  MLflow runs and the scripts it starts are tagged with it
dbutils.widgets.text("rung", "medgemma-1.5-4b-it")  # noqa: F821
dbutils.widgets.text("limit", "40")                  # noqa: F821  start small: GPU quota
dbutils.widgets.text("shots", "0")                   # noqa: F821
dbutils.widgets.text("lora_train", "0")              # noqa: F821  >0: LoRA fine-tune on this many train notes first
dbutils.widgets.text("catalog", "health_transformation_lab")      # noqa: F821  set by databricks.yml
dbutils.widgets.text("schema", "gold_perio_bench")  # noqa: F821
dbutils.widgets.text("hf_secret_scope", "health_transformation_lab")    # noqa: F821
dbutils.widgets.text("experiment_name", "")          # noqa: F821  the bundle's MLflow experiment; empty: yours
dbutils.widgets.text("run_id", "")                   # noqa: F821  the job run ({{job.run_id}}): every retry shares it
catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")  # noqa: F821
run_id = dbutils.widgets.get("run_id") or f"manual-{time.strftime('%Y%m%dT%H%M%S')}"  # noqa: F821
os.environ["HF_TOKEN"] = dbutils.secrets.get(dbutils.widgets.get("hf_secret_scope"), "hf_token")  # noqa: F821
from health_transformation_lab_nlp import llm_reader  # noqa: E402
from health_transformation_lab_nlp.registry import load_registry  # noqa: E402
_entry = {m["id"]: m for m in load_registry()["models"]}[dbutils.widgets.get("rung")]  # noqa: F821
if _entry.get("gated"):
    llm_reader.check_hf_access(_entry["hf"])   # #230: an expired token fails here, not after the GPU and the study build
dbutils.widgets.text("telemetry", "azure")           # noqa: F821  spec 014: off / console / azure / otlp
from health_transformation_lab_nlp import telemetry, tracking  # noqa: E402
telemetry.use_databricks_secret(dbutils, dbutils.widgets.get("telemetry"),  # noqa: F821  scripts inherit it
                                scope=dbutils.widgets.get("hf_secret_scope"))  # noqa: F821
tracking.pass_databricks_login()       # the scripts below log to MLflow with the notebook's login
# ... to the bundle's experiment: on Databricks the name must be an absolute path (tracking checks it)
os.environ["MLFLOW_TRACKING_URI"] = "databricks"
os.environ["DENTAL_MLFLOW_EXPERIMENT"] = (tracking.setting(dbutils.widgets.get("experiment_name"))  # noqa: F821  "None": unset (#131)
                                          or f"/Users/{spark.sql('select current_user()').first()[0]}/health-transformation-lab-nlp")  # noqa: F821
print("MLflow experiment:", os.environ["DENTAL_MLFLOW_EXPERIMENT"])

import torch  # noqa: E402

print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none (check compute selector)")

# COMMAND ----------

from health_transformation_lab_nlp import runlog  # noqa: E402

# Scripts print as they go and into a log on the landing volume, which survives if this notebook's Python dies.
log = f"{runlog.log_dir(catalog)}/medgemma_reader_{dbutils.widgets.get('rung')}.log"  # noqa: F821
print("logs:", log, "(each run after the first writes a time-stamped file next to it)")

# Build the synthetic datasets if this is a fresh Git folder
if not os.path.exists("../../data/datasets/answer_key/review_key.csv"):
    runlog.run(["python", "../../python/scripts/10_build_study.py"], log_path=log, check=True)

adapter = None
if int(dbutils.widgets.get("lora_train") or 0):  # noqa: F821
    adapter = "/tmp/medgemma-lora"
    runlog.run(["python", "../../python/scripts/17_medgemma_lora.py", "--rung", dbutils.widgets.get("rung"),  # noqa: F821
                "--max-train", dbutils.widgets.get("lora_train"), "--out", adapter],  # noqa: F821
               log_path=log, check=True)

args = ["python", "../../python/scripts/11_ai_predict.py", "--rung", dbutils.widgets.get("rung"),  # noqa: F821
        "--backend", "hf", "--shots", dbutils.widgets.get("shots")]  # noqa: F821
if adapter:
    args += ["--adapter", adapter]
if int(dbutils.widgets.get("limit") or 0):  # noqa: F821  0 = all review notes
    args += ["--limit", dbutils.widgets.get("limit")]  # noqa: F821
runlog.run(args, log_path=log, check=True)   # a crash or a kill stops here and says how it ended

# COMMAND ----------

import pandas as pd  # noqa: E402

from health_transformation_lab_nlp.rungs import output_tag  # noqa: E402

rung = dbutils.widgets.get("rung") + output_tag(adapter=adapter, shots=int(dbutils.widgets.get("shots")))  # noqa: F821
d = pd.read_csv(f"../../data/datasets/llm_details_{rung}.csv")
key = pd.read_csv("../../data/datasets/answer_key/review_key.csv").set_index("visit_id")
d["truth"] = key.loc[d.visit_id, "truth_status"].values
d["difficulty"] = key.loc[d.visit_id, "difficulty"].values
print(f"gate pass {d.gate_ok.mean():.1%}, fallback {d.fallback.mean():.1%}, "
      f"{d.latency_s.mean():.1f}s/note -> {1 / d.latency_s.mean():.2f} notes/s unbatched")
display(d.assign(correct=d.pred == d.truth).groupby("difficulty")["correct"].agg(["mean", "size"]))  # noqa: F821
# Against the generator truth only. The study result is against reviewers: 13_reliability.py.

# COMMAND ----------

# MedGemma vs the fine-tuned BERT encoders (committed ai_predictions_<encoder>.csv), paired bootstrap CIs.
# Meaningful only with limit = 0: the encoders scored all 240 charts.
if int(dbutils.widgets.get("limit") or 0):  # noqa: F821
    print("skipped: set limit to 0 so MedGemma scores all 240 charts, as the encoders did")
else:
    if runlog.run(["python", "../../python/scripts/29_medgemma_vs_bert.py"], log_path=log) == 0:
        display(pd.read_csv("../../data/datasets/ladder/medgemma_vs_bert.csv"))  # noqa: F821

# COMMAND ----------

# Keep the run in Unity Catalog, next to every other method's results (spec 016): predictions in
# fact_prediction, per-note details in fact_llm_call, under the gold names (spec 018). Keyed by
# (source_code, run_id, method_name): a retry of this job run replaces its rows instead of adding them again.
# The CSVs in the Git folder are scratch.
from health_transformation_lab_nlp import gold_names  # noqa: E402
from health_transformation_lab_nlp.delta import replace_batch  # noqa: E402
from health_transformation_lab_nlp.results_store import run_rows  # noqa: E402

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")  # noqa: F821
preds, details = run_rows("../../data/datasets", rung, source="databricks", run_id=run_id,
                          git_commit=dbutils.widgets.get("git_commit"), run_ts=pd.Timestamp.now(tz="UTC"))  # noqa: F821
details = details.merge(d[["visit_id", "truth", "difficulty"]], on="visit_id", validate="one_to_one")
key = {"source_code": "databricks", "run_id": run_id, "method_name": rung}
for rows, name in ((preds, "fact_prediction"), (details, "fact_llm_call")):
    n = replace_batch(spark, gold_names.to_gold(rows, name), f"{catalog}.{schema}.{name}", key)  # noqa: F821
    print(f"{catalog}.{schema}.{name}: {n} rows for run {run_id}, {rung}")
