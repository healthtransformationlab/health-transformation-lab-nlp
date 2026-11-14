# Databricks notebook source
# MAGIC %md
# MAGIC # Load the synthetic OMOP CDM into Lakebase (Postgres)
# MAGIC
# MAGIC Creates the OMOP CDM 5.4 + dental extension in a Lakebase schema and loads the
# MAGIC synthetic tables (`python/health_transformation_lab_nlp/db.py`). Synthetic data only.
# MAGIC
# MAGIC **Credentials**, in order:
# MAGIC 1. A full SQLAlchemy URL in secret `<secret_scope>/lakebase_url` (simplest; the
# MAGIC    password is an OAuth token, so refresh it when it expires).
# MAGIC 2. Otherwise the Databricks SDK generates a short-lived token for `lakebase_instance`.
# MAGIC    The SDK call names have changed across Lakebase releases: **untested here**,
# MAGIC    check your SDK version if it fails and fall back to option 1.

# COMMAND ----------

# MAGIC %pip install -q -e ../../python[db] databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

import subprocess
import uuid

dbutils.widgets.text("git_commit", "")  # noqa: F821  set by the job: the commit it was deployed from
dbutils.widgets.text("telemetry", "azure")  # noqa: F821  spec 014: off / console / azure / otlp
from health_transformation_lab_nlp import telemetry  # noqa: E402
telemetry.use_databricks_secret(dbutils, dbutils.widgets.get("telemetry"))  # noqa: F821  scripts inherit it
from health_transformation_lab_nlp import tracking as _tracking
_tracking.use_git_commit(dbutils)  # noqa: F821  MLflow runs and the scripts it starts are tagged with it
dbutils.widgets.text("lakebase_instance", "dental-dev")        # noqa: F821
dbutils.widgets.text("lakebase_database", "databricks_postgres")  # noqa: F821
dbutils.widgets.text("lakebase_schema", "cdm_dev")             # noqa: F821
dbutils.widgets.text("secret_scope", "health_transformation_lab")                 # noqa: F821
w = {k: dbutils.widgets.get(k) for k in ("lakebase_instance", "lakebase_database", "lakebase_schema",  # noqa: F821
                                          "secret_scope")}

try:
    url = dbutils.secrets.get(w["secret_scope"], "lakebase_url")  # noqa: F821
except Exception:
    from databricks.sdk import WorkspaceClient
    ws = WorkspaceClient()
    inst = ws.database.get_database_instance(name=w["lakebase_instance"])
    cred = ws.database.generate_database_credential(request_id=str(uuid.uuid4()),
                                                    instance_names=[w["lakebase_instance"]])
    user = ws.current_user.me().user_name
    url = (f"postgresql+psycopg://{user}:{cred.token}@{inst.read_write_dns}:5432/"
           f"{w['lakebase_database']}?sslmode=require")

# COMMAND ----------

subprocess.run(["python", "../../python/scripts/01_build_dataset.py"], check=True)
r = subprocess.run(["python", "../../python/scripts/05_load_omop_db.py", "--url", url,
                    "--schema", w["lakebase_schema"]], capture_output=True, text=True)
print(r.stdout[-3000:], r.stderr[-2000:])
assert r.returncode == 0
