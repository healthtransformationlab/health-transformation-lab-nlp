# Databricks notebook source
# MAGIC %md
# MAGIC # Pipeline digest: one message per owner per period (spec 027 US8 T023, #359)
# MAGIC
# MAGIC Every SEV3 and SEV4 alert this repo raises, built into the daily digest (and on Mondays the weekly one) by
# MAGIC pipeline-doctor's `digest`, the shared package pinned in `python/pyproject.toml`:
# MAGIC - failing budget and target checks (`dq_check`, categories cost and performance; spec 036);
# MAGIC - the pipeline doctor's SEV3 and SEV4 recommendations no one has decided yet (`fact_remediation_decision`);
# MAGIC - pipeline-doctor's forecaster on `ops/secrets_register.yaml`, `ops/dependency_inventory.csv` and the run
# MAGIC   history (`fact_pipeline_run`): expiries, deprecations, trends.
# MAGIC
# MAGIC Writes `fact_digest_item` and `fact_digest_message`, delete-then-append by `digest_key` (a rerun the same day
# MAGIC replaces that day's digest). Two Databricks SQL alerts, one per period, email the day's message to
# MAGIC `digest_email`: Databricks sends it, so there is no mail credential. A SEV1 or SEV2 forecast can't wait for a
# MAGIC digest: the run fails with its text, so the job's failure email pages the owner. Names, codes and counts
# MAGIC only, never note text or row data.

# COMMAND ----------

# MAGIC %pip install -q -e ../../python

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

import pandas as pd
from health_transformation_lab_nlp import delta, digests, table_comments, tracking

dbutils.widgets.text("git_commit", "")  # noqa: F821  set by the job: the commit it was deployed from
commit = tracking.use_git_commit(dbutils)  # noqa: F821
dbutils.widgets.text("run_id", "")  # noqa: F821  {{job.run_id}}: the batch key on every row
dbutils.widgets.text("catalog", "health_transformation_lab")  # noqa: F821
dbutils.widgets.text("schema", "gold_perio_bench")  # noqa: F821
dbutils.widgets.text("digest_email", "")  # noqa: F821  who the SQL alerts email; empty: digests built, no email
catalog, schema = dbutils.widgets.get("catalog").strip(), dbutils.widgets.get("schema").strip()  # noqa: F821
run_id = dbutils.widgets.get("run_id").strip() or "manual"  # noqa: F821
email = dbutils.widgets.get("digest_email").strip()  # noqa: F821
if not catalog or not schema:   # required settings: fail at once, naming them (AGENTS.md, configuration)
    raise ValueError("catalog and schema are required job parameters")


def table(name: str) -> str:
    return f"{catalog}.{schema}.{name}"


def read(name: str):
    return spark.table(table(name)).toPandas() if spark.catalog.tableExists(table(name)) else None  # noqa: F821

# COMMAND ----------

now = pd.Timestamp.now(tz="UTC")
alerts = pd.concat([digests.governance_alerts(read("dq_check"), digests.load_budgets_owners()),
                    digests.decision_alerts(read("fact_remediation_decision")),
                    digests.forecast_alerts(now, read("fact_pipeline_run"))], ignore_index=True)
print(f"{len(alerts)} alerts:", alerts["severity_code"].value_counts().to_dict() if len(alerts) else {})

# COMMAND ----------

items_table, messages_table = table("fact_digest_item"), table("fact_digest_message")
batch = {"digest_run_id": run_id, "loaded_ts": now, "git_commit_sha": commit}


def write(name: str, df: pd.DataFrame, key: str) -> None:
    """Delete-then-append by digest_key; a rerun that finds nothing still clears the day's earlier rows."""
    t = table(name)
    if not len(df) and spark.catalog.tableExists(t):  # noqa: F821
        spark.sql(f"DELETE FROM {t} WHERE digest_key = '{key}'")  # noqa: F821  key: a date and a period code
    n = delta.replace_keys(spark, digests.rows(df, name, **batch), t, "digest_key",  # noqa: F821
                           schema=digests.ddl(name))
    table_comments.apply(spark, t)  # noqa: F821
    print(f"{name} {key}: {n} rows")


for period in digests.periods_due(now):
    prior = read("fact_digest_item")   # the last earlier digest of this period: its items make today's repeats
    if prior is not None and len(prior):
        day = pd.to_datetime(prior["digest_date"])
        prior = prior[(prior["period_code"] == period) & (day < now.tz_localize(None).normalize())]
        prior = prior[pd.to_datetime(prior["digest_date"]) == pd.to_datetime(prior["digest_date"]).max()]
    items, messages = digests.build(alerts, period, now, previous=prior)
    key = f"{now.date().isoformat()}/{period}"
    write("fact_digest_item", items, key)
    write("fact_digest_message", messages, key)
    for m in messages.itertuples():
        print(m.message_text)

# COMMAND ----------

# The two SQL alerts that email the digests, created or updated in place. Optional: a failure here warns and the
# digests above are already written (AGENTS.md, configuration: optional settings warn).
try:
    from databricks.sdk import WorkspaceClient
    ws = WorkspaceClient()
    warehouses = list(ws.warehouses.list())
    if not warehouses:
        print("warning: no SQL warehouse, so no alert can email the digests")
    else:
        specs = digests.alert_specs(catalog, schema, email, warehouses[0].id)
        digests.ensure_alerts(ws.alerts_v2, specs)
        print(f"alerts: {[s['display_name'] for s in specs] or 'none (no digest_email)'}")
except Exception as e:  # noqa: BLE001 - the email is optional; the tables hold the digests either way
    print(f"warning: the digest alerts weren't set up ({type(e).__name__}: {str(e)[:200]})")

# COMMAND ----------

# SEV1/SEV2 forecasts page now: fail the run with their text, so the job's failure email reaches the owner. The
# digests are already written, so nothing is lost.
page = digests.page_now(alerts)
if page:
    raise RuntimeError(page)
