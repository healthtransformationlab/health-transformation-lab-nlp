# Databricks notebook source
# MAGIC %md
# MAGIC # Migrate coding-agent traces to Unity Catalog (spec 041 US3, #858) — fallback only
# MAGIC
# MAGIC **Preferred path:** reload run folders with `kaggle/load_agent_traces.py` so each tool call is a `TOOL`
# MAGIC span named after the tool (plan.md Order step 3). Databricks' migrate copies step-numbered span names
# MAGIC and splits the Tool calls tab.
# MAGIC
# MAGIC **This notebook** is for a source experiment that still holds traces whose run folders are gone. It calls
# MAGIC `databricks.migrations.migrate_traces_to_uc.run`, leaves the source experiment as a backup (never deletes
# MAGIC it), and writes count rows to `health_transformation_lab.ops_agent_trace.trace_migration_check`
# MAGIC (delete-then-append by `run_id`).
# MAGIC
# MAGIC Needs a classic cluster (Databricks Runtime 15.3+) with a SQL warehouse the identity can use — not Free
# MAGIC Edition serverless alone. If migrate cannot run here, reload folders instead and record that on #858.

# COMMAND ----------

# MAGIC %pip install -q "databricks-agents>=1.10.1"

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

from datetime import datetime, timezone

import mlflow
from mlflow.tracking import MlflowClient

from health_transformation_lab_nlp import table_comments

dbutils.widgets.text("source_experiment_id", "")  # noqa: F821
dbutils.widgets.text("target_experiment_name", "/Shared/coding-agent-runs")  # noqa: F821
dbutils.widgets.text("git_commit", "")  # noqa: F821
dbutils.widgets.text("run_id", "")  # noqa: F821

source_experiment_id = dbutils.widgets.get("source_experiment_id").strip()  # noqa: F821
target_experiment_name = dbutils.widgets.get("target_experiment_name").strip() or "/Shared/coding-agent-runs"  # noqa: F821
git_commit_sha = dbutils.widgets.get("git_commit").strip()  # noqa: F821
run_id = dbutils.widgets.get("run_id").strip() or f"manual-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"  # noqa: F821
run_ts = datetime.now(timezone.utc)

if not source_experiment_id:
    raise RuntimeError("source_experiment_id: missing; set the source MLflow experiment id")

client = MlflowClient()
target = client.get_experiment_by_name(target_experiment_name)
if target is None:
    raise RuntimeError(f"target_experiment_name: {target_experiment_name!r} does not exist; deploy the bundle first")
target_experiment_id = target.experiment_id
source = client.get_experiment(source_experiment_id)
source_experiment_name = source.name if source else source_experiment_id

print("migrate", source_experiment_id, "->", target_experiment_id, target_experiment_name)

# COMMAND ----------

from databricks.migrations.migrate_traces_to_uc import run as migrate_traces_to_uc

migrate_traces_to_uc(
    source_experiment_id=source_experiment_id,
    target_experiment_id=target_experiment_id,
)

# COMMAND ----------

# Count traces and assessments by name in each experiment; write the check table.
CHECK = "health_transformation_lab.ops_agent_trace.trace_migration_check"

spark.sql(f"""
create table if not exists {CHECK} (
  experiment_id string,
  experiment_name string,
  assessment_name string,
  trace_count bigint,
  assessment_count bigint,
  run_id string,
  run_ts timestamp,
  git_commit_sha string
) using delta
comment 'one row per experiment and assessment name after a US3 migrate or reload check (spec 041)'
""")

rows = []
for exp_id, exp_name in ((source_experiment_id, source_experiment_name),
                         (target_experiment_id, target_experiment_name)):
    traces = client.search_traces(experiment_ids=[exp_id], max_results=5000)
    # search_traces may page; count what we got and note if truncated
    n_traces = len(traces)
    by_name: dict[str | None, int] = {None: 0}
    for tr in traces:
        assessments = getattr(tr, "assessments", None) or getattr(getattr(tr, "info", None), "assessments", None) or []
        if not assessments and hasattr(tr, "data"):
            assessments = getattr(tr.data, "assessments", []) or []
        for a in assessments:
            name = getattr(a, "name", None) or getattr(a, "assessment_name", None)
            by_name[name] = by_name.get(name, 0) + 1
        by_name[None] = by_name.get(None, 0)  # trace-count row uses assessment_name null
    rows.append((exp_id, exp_name, None, n_traces, 0, run_id, run_ts, git_commit_sha))
    for name, n in by_name.items():
        if name is None:
            continue
        rows.append((exp_id, exp_name, name, n_traces, n, run_id, run_ts, git_commit_sha))

safe_run = run_id.replace("'", "''")
spark.sql(
    "delete from health_transformation_lab.ops_agent_trace.trace_migration_check "
    f"where run_id = '{safe_run}'"
)

import pandas as pd

pdf = pd.DataFrame(rows, columns=[
    "experiment_id", "experiment_name", "assessment_name", "trace_count", "assessment_count",
    "run_id", "run_ts", "git_commit_sha",
])
spark.createDataFrame(pdf).write.mode("append").saveAsTable(CHECK)
table_comments.apply(spark, CHECK)  # noqa: F821  spec 034: comments after every write
display(pdf)  # noqa: F821

# Surface migrate skips when the helper left a table
for skip in ("_migration_skipped", "migration_skipped"):
    for schema in ("health_transformation_lab.ops_agent_trace", "default"):
        full = f"{schema}.{skip}"
        try:
            if spark.catalog.tableExists(full):  # noqa: F821
                print("skipped rows in", full)
                display(spark.table(full).limit(50))  # noqa: F821
        except Exception:
            pass

print("source kept as backup; counts written to", CHECK, "run_id", run_id)
