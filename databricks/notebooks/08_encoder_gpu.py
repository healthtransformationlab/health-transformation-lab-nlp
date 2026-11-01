# Databricks notebook source
# MAGIC %md
# MAGIC # Encoders that need a GPU (spec 002 T017)
# MAGIC
# MAGIC Fine-tunes each encoder in `rungs` on the training notes and predicts the 240 review charts with
# MAGIC `python/scripts/11_ai_predict.py`, the same script that runs the smaller encoders on a laptop.
# MAGIC Synthetic data only. The large ModernBERTs and the Longformers are too slow on CPU; GatorTron-base
# MAGIC diverged on CPU at the default learning rate (every chart called healthy), so `lr_overrides` reruns it
# MAGIC lower.
# MAGIC
# MAGIC Predictions are copied to the landing volume (`encoder_gpu/`) and written to `fact_prediction` in the gold
# MAGIC schema with `source_code` databricks, replaced per job run and method so a retry adds nothing (spec 031), as
# MAGIC the MedGemma reader does. To score them with the other models, copy the CSVs into `data/datasets/`, then run
# MAGIC `python/scripts/28_ladder_vs_truth.py` and `35_readme_results.py`.
# MAGIC
# MAGIC No GPU free? The *Fine-tune the GPU encoders on a free Kaggle GPU* workflow does the same work on Kaggle
# MAGIC (`kaggle/encoder_gpu.ipynb`, with this job's `encoder_gpu_rungs` and `encoder_gpu_lr`) and commits the results.

# COMMAND ----------

# MAGIC %pip install -q -e ../../python[models,azure]

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

import os
import shutil
import sys
import tempfile
import time

import pandas as pd
from health_transformation_lab_nlp import gold_names, runlog
from health_transformation_lab_nlp.delta import replace_batch
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT
from health_transformation_lab_nlp.results_store import run_prediction_rows
from health_transformation_lab_nlp.rungs import output_tag

dbutils.widgets.text("git_commit", "")  # noqa: F821  set by the job: the commit it was deployed from
from health_transformation_lab_nlp import tracking as _tracking
_tracking.use_git_commit(dbutils)  # noqa: F821  MLflow runs and the scripts it starts are tagged with it
dbutils.widgets.text("rungs", "modernbert-large,bioclinical-modernbert-large,longformer-base,clinical-longformer,gatortron-base")  # noqa: F821
dbutils.widgets.text("lr_overrides", "gatortron-base=2e-5")             # noqa: F821  rung=rate, comma-separated
dbutils.widgets.text("epochs", "3")                                     # noqa: F821
dbutils.widgets.text("max_len", "256")                                  # noqa: F821
dbutils.widgets.text("catalog", "health_transformation_lab")                          # noqa: F821  set by databricks.yml
dbutils.widgets.text("schema", "gold_perio_bench")                # noqa: F821
dbutils.widgets.text("landing_schema", "landing_perio_bench")     # noqa: F821
dbutils.widgets.text("telemetry", "azure")                              # noqa: F821  spec 014
dbutils.widgets.text("run_id", "")   # noqa: F821  the job run ({{job.run_id}}): the batch key, the same for every retry
run_id = dbutils.widgets.get("run_id") or f"manual-{time.strftime('%Y%m%dT%H%M%S')}"  # noqa: F821
from health_transformation_lab_nlp import telemetry, tracking  # noqa: E402
telemetry.use_databricks_secret(dbutils, dbutils.widgets.get("telemetry"))  # noqa: F821  scripts inherit it
tracking.pass_databricks_login()       # the scripts below log to MLflow with the notebook's login
w = {k: dbutils.widgets.get(k) for k in ("rungs", "lr_overrides", "epochs", "max_len", "catalog",  # noqa: F821
                                          "schema", "landing_schema")}

rungs = [r.strip() for r in w["rungs"].split(",") if r.strip()]
lrs = dict(x.strip().split("=") for x in w["lr_overrides"].split(",") if "=" in x)
out_dir = f"/Volumes/{w['catalog']}/{w['landing_schema']}/data/encoder_gpu"
work = tempfile.mkdtemp(prefix="encoder_gpu_")   # training checkpoints: local scratch, not workspace files
os.makedirs(out_dir, exist_ok=True)

# COMMAND ----------

done, failed = [], []
for rung in rungs:
    lr = float(lrs.get(rung, 5e-5))
    cmd = [sys.executable, str(REPO_ROOT / "python" / "scripts" / "11_ai_predict.py"), "--rung", rung,
           "--epochs", w["epochs"], "--max-len", w["max_len"], "--lr", str(lr)]
    # printed as it runs and kept in a log on the landing volume, which survives if this notebook's Python dies
    if runlog.run(cmd, log_path=f"{runlog.log_dir(w['catalog'])}/encoder_gpu_{rung}.log", cwd=work):  # failure skips one rung
        failed.append(rung)
        continue
    method = rung + output_tag(lr=lr)
    path = DATASETS_DIR / f"ai_predictions_{method}.csv"
    shutil.copy(path, out_dir)
    done.append((method, path))

# COMMAND ----------

run_ts = pd.Timestamp.now(tz="UTC")
for method, path in done:
    preds = run_prediction_rows(path, method, source="databricks", run_id=run_id,
                                git_commit=dbutils.widgets.get("git_commit"), run_ts=run_ts)  # noqa: F821
    key = {"source_code": "databricks", "run_id": run_id, "method_name": method}
    n = replace_batch(spark, gold_names.to_gold(preds, "fact_prediction"),  # noqa: F821
                      f"{w['catalog']}.{w['schema']}.fact_prediction", key)
    print(f"fact_prediction: {n} rows for run {run_id}, {method}")
print("done:", [m for m, _ in done], "| failed:", failed)
if failed:
    raise RuntimeError(f"encoders that failed: {failed} (the others' predictions are saved)")
