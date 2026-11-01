# Databricks notebook source
# MAGIC %md
# MAGIC # Pipeline doctor (spec 027 US5)
# MAGIC
# MAGIC Reads what ran, decides what kind of failure each failed run is, and recommends the next action from the
# MAGIC runbook's allow-list. It reads tables about runs (names, states, times, counts, error types), never note
# MAGIC text or row-level data, and it acts on nothing: agents recommend; code acts.
# MAGIC
# MAGIC 1. Settings are checked first (`doctor_job.check_settings`); a missing or malformed one fails the run, naming it.
# MAGIC 2. `system.lakeflow.job_run_timeline` (60 days, this workspace, this bundle's jobs) and, when `span_table` is
# MAGIC    set, the span export become `fact_pipeline_run`.
# MAGIC 3. `health_transformation_lab_nlp.doctor`: the six signals for every run in the last `lookback_days`
# MAGIC    (`fact_pipeline_signal`); for every failed run the class, the first allowed action, the impact and the
# MAGIC    severity (`fact_remediation_decision`). Approvals are the `decisions` parameter (`run_id=action_code`)
# MAGIC    until an approval UI exists; earlier decisions are carried forward and decide graduation.
# MAGIC 4. Every write is delete-then-append by `run_id`; every row carries this run's `doctor_run_id`.
# MAGIC 5. A **new** SEV1 or SEV2 decision fails this run with the drafted notification, so the job's failure
# MAGIC    notification reaches the owner; SEV3 and SEV4 stay in the table for the daily and weekly digests.
# MAGIC
# MAGIC The root-cause rung (an LLM on `unknown` runs, under `max_usd`, spec 027 US6) is not built yet: the job
# MAGIC counts the runs it would see. Serverless CPU. Needs `SELECT` on `system.lakeflow`.

# COMMAND ----------

# MAGIC %pip install -q -e ../../python

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

import pandas as pd
from health_transformation_lab_nlp import delta, doctor, doctor_job, tracking

dbutils.widgets.text("git_commit", "")  # noqa: F821  set by the job: the commit it was deployed from
commit = tracking.use_git_commit(dbutils)  # noqa: F821
dbutils.widgets.text("run_id", "")  # noqa: F821  {{job.run_id}}: the batch key on every row
dbutils.widgets.text("catalog", "health_transformation_lab")  # noqa: F821
dbutils.widgets.text("schema", "gold_perio_bench")  # noqa: F821
dbutils.widgets.text("judge_endpoint", "none")  # noqa: F821
dbutils.widgets.text("max_usd", "5")  # noqa: F821
dbutils.widgets.text("lookback_days", "7")  # noqa: F821
dbutils.widgets.text("span_table", "none")  # noqa: F821
dbutils.widgets.text("decisions", "")  # noqa: F821  run_id=action_code,...
dbutils.widgets.text("decided_by", "")  # noqa: F821
names = ("git_commit", "run_id", "catalog", "schema", "judge_endpoint", "max_usd", "lookback_days", "span_table",
         "decisions", "decided_by")
settings = doctor_job.check_settings({n: dbutils.widgets.get(n) for n in names})  # noqa: F821
catalog, schema = settings["catalog"], settings["schema"]


def table(name: str) -> str:
    return f"{catalog}.{schema}.{name}"


# COMMAND ----------

# Cheap checks before the work: this workspace's id, read access to the system tables, the span export if set.
from databricks.sdk import WorkspaceClient

workspace_id = str(WorkspaceClient().get_workspace_id())
if not workspace_id.isdigit():
    raise RuntimeError(f"workspace id {workspace_id!r} is not a number; cannot scope the system tables")
try:
    spark.sql("select 1 from system.lakeflow.job_run_timeline limit 1").collect()  # noqa: F821
    spark.sql("select 1 from system.lakeflow.jobs limit 1").collect()  # noqa: F821
except Exception as e:  # noqa: BLE001
    raise RuntimeError("system.lakeflow: this job's identity needs USE CATALOG on system and SELECT on "
                       f"system.lakeflow (a metastore admin grants it): {type(e).__name__}") from None
if settings["span_table"] and not spark.catalog.tableExists(settings["span_table"]):  # noqa: F821
    raise RuntimeError(f"span_table: {settings['span_table']} does not exist; set it to none to run without it")
if not settings["span_table"]:
    print("warning: span_table is none, so runs carry state, times and termination codes only (no counts, schema "
          "hash, checks or cost); classes that need them fall to unknown")
if not settings["judge_endpoint"]:
    print("judge_endpoint is none: the root-cause rung is off")

# COMMAND ----------

# One row per run: first and last timeline slice, the final state and termination code; the job's current name.
timeline = spark.sql(f"""
with job_name as (
  select job_id, name,
    row_number() over (partition by job_id order by change_time desc) as name_rank
  from system.lakeflow.jobs
  where workspace_id = '{workspace_id}'
), run as (
  select job_id, cast(run_id as string) as run_id,
    min(period_start_time) as started_ts,
    max(period_end_time) as ended_ts,
    max_by(result_state, period_end_time) as result_state,
    max_by(termination_code, period_end_time) as termination_code
  from system.lakeflow.job_run_timeline
  where workspace_id = '{workspace_id}'
    and period_start_time >= current_timestamp() - interval {doctor_job.HISTORY_DAYS} days
  group by job_id, run_id
)
select j.name as job_name, r.run_id, r.started_ts, r.ended_ts, r.result_state, r.termination_code
from run r
inner join job_name j on r.job_id = j.job_id and j.name_rank = 1
""").toPandas()  # noqa: F821

config, runbook, lineage = doctor.load_config(), doctor.load_runbook(), doctor.load_lineage()
runs = doctor_job.timeline_runs(timeline, config, doctor_job.job_names())
if settings["span_table"]:
    spans = spark.table(settings["span_table"]).toPandas()  # noqa: F821
    runs = doctor_job.merge_spans(runs, spans)
print(f"{len(timeline)} job runs read, {len(runs)} finished runs of this bundle's jobs")

# COMMAND ----------

now = pd.Timestamp.now(tz="UTC")
since = now - pd.Timedelta(days=settings["lookback_days"])
previous = None
if spark.catalog.tableExists(table("fact_remediation_decision")):  # noqa: F821
    previous = spark.table(table("fact_remediation_decision")).toPandas()  # noqa: F821
signals, decisions = doctor_job.diagnose(runs, config, runbook, lineage, since, previous=previous,
                                         decisions=settings["decisions"], decided_by=settings["decided_by"], now=now)
notify_now, digest = doctor_job.notifications(decisions, previous)   # before the write: new means not yet recorded
unknown = int((decisions["failure_class_code"] == "unknown").sum()) if len(decisions) else 0
print(f"{len(signals)} runs in the last {settings['lookback_days']} days, {len(decisions)} failed")
print(f"root-cause rung (spec 027 US6, not built): {unknown} unknown runs would go to it, budget "
      f"US${settings['max_usd']:.2f}")
if len(decisions):
    display(decisions[["pipeline_name", "run_id", "failure_class_code", "recommended_action_code",  # noqa: F821
                       "severity_code", "run_mode_code", "decided_action_code"]])

# COMMAND ----------

batch = {"doctor_run_id": settings["run_id"], "loaded_ts": now, "doctor_git_commit_sha": commit}


def write(name: str, df: pd.DataFrame) -> None:
    """Delete-then-append by run_id: a run read again, by this doctor run or a later one, replaces its rows."""
    n = delta.replace_keys(spark, doctor_job.rows(df, name, **batch), table(name), "run_id",  # noqa: F821
                           schema=doctor_job.ddl(name))
    print(f"{name}: {n} rows")


write("fact_pipeline_run", runs)
write("fact_pipeline_signal", signals)
write("fact_remediation_decision", decisions)   # last: a failure above leaves the decisions to make next time

# COMMAND ----------

# Notifications at the runbook's severity (AGENTS.md "Alerts and severity"). SEV3/SEV4: the digests read the
# table (the digest job is spec 027 T023). A new SEV1/SEV2 fails this run so the job's failure notification
# carries the drafted text to the owner; the rows above are already written, so nothing is lost or repeated.
print("for the digests:", digest or "nothing new")
if notify_now:
    raise RuntimeError(f"{len(notify_now)} new SEV1/SEV2 decision(s) for the owner:\n" + "\n".join(notify_now))
print("no new SEV1/SEV2 decisions")
