# Databricks notebook source
# MAGIC %md
# MAGIC # LLM judge monitoring (uat / prod)
# MAGIC
# MAGIC Registers the repo's judges on this environment's MLflow experiment and starts
# MAGIC production monitoring: Databricks scores a sample of live traces from the serving
# MAGIC endpoint and attaches each judge's assessment to the trace. Synthetic data only.
# MAGIC
# MAGIC | Scorer | Kind | Traces scored |
# MAGIC |---|---|---|
# MAGIC | `perio_status_supported` | custom judge (`make_judge`), AAP criteria + verbatim quote | `sample_rate` |
# MAGIC | `aap_guidelines` | built-in Guidelines judge, plain-language AAP rules | `sample_rate` |
# MAGIC | `no_phi_in_note` | deterministic de-identification scan (no LLM) | all |
# MAGIC
# MAGIC Re-running is safe: scorers are re-registered with the current definitions.
# MAGIC To stop: `python scripts/25_judge_monitoring.py stop --experiment-id <id>`.

# COMMAND ----------

# MAGIC %pip install -q -e "../../python[track,azure]"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("git_commit", "")   # set by the job: the commit it was deployed from
from health_transformation_lab_nlp import tracking as _tracking
_tracking.use_git_commit(dbutils)   # MLflow runs and the scripts it starts are tagged with it
dbutils.widgets.text("judge_endpoint", "none")
dbutils.widgets.text("experiment_id", "")
dbutils.widgets.text("sample_rate", "0.1")
endpoint = dbutils.widgets.get("judge_endpoint")
experiment_id = dbutils.widgets.get("experiment_id")
rate = float(dbutils.widgets.get("sample_rate"))
if endpoint in ("", "none"):
    dbutils.notebook.exit("judge_endpoint not set for this target; monitoring not started")

# COMMAND ----------

import mlflow

from health_transformation_lab_nlp.mlflow_judge import start_monitoring

mlflow.set_tracking_uri("databricks")
started = start_monitoring(f"databricks:/{endpoint}", experiment_id, sample_rate=rate)
print("monitoring:", started)
