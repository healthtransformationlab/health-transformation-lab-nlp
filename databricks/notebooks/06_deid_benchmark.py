# Databricks notebook source
# MAGIC %md
# MAGIC # De-identification benchmark, including the AI methods (spec 007)
# MAGIC
# MAGIC Runs `python/scripts/26_deid_benchmark.py` in a workspace, where the two engines that need
# MAGIC Databricks services can run (tasks T012b and T016):
# MAGIC
# MAGIC | Engine | What | Needs |
# MAGIC |---|---|---|
# MAGIC | `llm` | an LLM listing identifiers verbatim | a serving endpoint (OpenAI-compatible); pay-per-token Foundation Model endpoints work |
# MAGIC | `ai_mask` | Databricks SQL AI Function `ai_mask`: masks the listed entity types | a SQL warehouse (Free Edition's single 2X-Small warehouse is enough) |
# MAGIC | `hf_stanford`, `hf_obi` | clinical de-id transformers (MIT) | Hugging Face download; CPU is fine for 400 notes (already scored locally) |
# MAGIC | `presidio` | spaCy NER + recognizers | `presidio-analyzer` and a spaCy model (already scored locally) |
# MAGIC | `regex`, `regex_v2` | patterns | nothing (already scored locally) |
# MAGIC
# MAGIC The whole default engine set runs, not just the two new ones. The script overwrites its
# MAGIC output files, so they replace `data/deid/*.csv` in the repo only when every tier is run:
# MAGIC the challenge set (always), ASQ-PHI (`external_path`) and the John Snow Labs 48-note
# MAGIC CSV (`jsl48_path`). Leave either path empty and that tier's rows are missing from the
# MAGIC output; merge the new engines' rows into the repo files instead of replacing them.
# MAGIC Engines that still can't run here (Azure, AWS) are listed in `not_run.csv`, as before.
# MAGIC
# MAGIC **Free Edition notes** (per Databricks'
# MAGIC [Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
# MAGIC page: one 2X-Small SQL warehouse; no provisioned-throughput or GPU serving endpoints;
# MAGIC a fair-usage quota that can pause compute for the rest of the day). Serverless notebook
# MAGIC compute (CPU) is enough: the transformer engines took minutes on a laptop CPU. The `llm`
# MAGIC engine needs a pay-per-token endpoint name from the Serving tab. `ai_mask` sends one SQL
# MAGIC statement per note (the script caches each engine's output, so `ai_mask` and
# MAGIC `ai_mask+regex_v2+guard` share one call), so 1,451 notes (400 challenge + 1,051 ASQ-PHI)
# MAGIC take a while on the one warehouse; start with the challenge set alone if unsure.
# MAGIC
# MAGIC **Data.** Synthetic, labeled fake PHI only: the challenge set is generated here and kept
# MAGIC under `/tmp` on the compute, never written into the Git folder. ASQ-PHI (MIT) is the one
# MAGIC external set; upload its `synthetic_clinical_queries.txt` to a Unity Catalog volume and
# MAGIC give the path in `external_path` to score it too (the repo's results include it). The
# MAGIC John Snow Labs 48-note CSV may hold i2b2 notes, so it belongs on a volume too, never
# MAGIC in the Git folder (`jsl48_path`).
# MAGIC
# MAGIC **Getting results back.** With `save_to_repo` = `yes`, the result CSVs are copied into
# MAGIC `data/deid/` of this Git folder; commit them from the Git folder's dialog. `not_run.csv`
# MAGIC then shows which engines ran, and the prices for `llm` and `ai_mask` in `costs.yaml` are
# MAGIC still ILLUSTRATIVE until T008 fills them from the pricing page.

# COMMAND ----------

# MAGIC %pip install -q -e "../../python[models,azure]" presidio-analyzer https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# Pay-per-token Foundation Model endpoint for the llm engine; pick any chat model listed under Serving.
dbutils.widgets.text("git_commit", "")   # set by the job: the commit it was deployed from
dbutils.widgets.text("telemetry", "azure")  # noqa: F821  spec 014: off / console / azure / otlp
from health_transformation_lab_nlp import telemetry

telemetry.use_databricks_secret(dbutils, dbutils.widgets.get("telemetry"))  # noqa: F821  scripts inherit it
from health_transformation_lab_nlp import tracking as _tracking
_tracking.use_git_commit(dbutils)   # MLflow runs and the scripts it starts are tagged with it
dbutils.widgets.text("llm_endpoint", "databricks-meta-llama-3-3-70b-instruct")
# SQL warehouse for ai_mask; empty = the first warehouse the workspace has (Free Edition has one).
dbutils.widgets.text("sql_warehouse_id", "")
# Empty = the script's default engine set (every engine; the ones without credentials are reported as not run).
dbutils.widgets.text("engines", "")
dbutils.widgets.text("n_notes", "400")
# ASQ-PHI as downloaded (synthetic_clinical_queries.txt), e.g. /Volumes/health_transformation_lab/landing_perio_bench/data/synthetic_clinical_queries.txt
dbutils.widgets.text("external_path", "")
# John Snow Labs' 48-note benchmark CSV, on a volume (tier jsl48); empty = skip that tier.
dbutils.widgets.text("jsl48_path", "")
dbutils.widgets.dropdown("save_to_repo", "yes", ["yes", "no"])
# A volume folder to copy the result CSVs to (the De-id AI methods job sets it); empty = don't.
dbutils.widgets.text("out_dir", "")

# COMMAND ----------

import os
import subprocess
from pathlib import Path

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
host, token = ctx.browserHostName().get(), ctx.apiToken().get()

endpoint = dbutils.widgets.get("llm_endpoint").strip()
if endpoint:
    os.environ["DEID_LLM_BASE_URL"] = f"https://{host}/serving-endpoints"
    os.environ["DEID_LLM_MODEL"] = endpoint
    os.environ["DEID_LLM_API_KEY"] = token

warehouse = dbutils.widgets.get("sql_warehouse_id").strip()
if not warehouse:
    from databricks.sdk import WorkspaceClient
    found = list(WorkspaceClient().warehouses.list())
    warehouse = found[0].id if found else ""
    print("SQL warehouse:", f"{found[0].name} ({warehouse})" if found else "none found; ai_mask will be reported as not run")
if warehouse:
    os.environ["DATABRICKS_HOST"] = host
    os.environ["DATABRICKS_TOKEN"] = token
    os.environ["DATABRICKS_WAREHOUSE_ID"] = warehouse

data_root = "/tmp/dental_data"                     # fake-PHI challenge notes stay on the compute
os.environ["DENTAL_DATA_ROOT"] = data_root
cmd = ["python", "../../python/scripts/26_deid_benchmark.py", "--n-notes", dbutils.widgets.get("n_notes")]
if dbutils.widgets.get("engines").strip():
    cmd += ["--engines", dbutils.widgets.get("engines").strip()]
external = dbutils.widgets.get("external_path").strip()
if external:
    assert Path(external).exists(), f"external_path not found: {external}"
    cmd += ["--external", external, "--tiers", "all,unseen,external"]
jsl48 = dbutils.widgets.get("jsl48_path").strip()
if jsl48:
    assert Path(jsl48).exists(), f"jsl48_path not found: {jsl48}"
    cmd += ["--jsl48", jsl48]
print(" ".join(cmd))
r = subprocess.run(cmd, capture_output=True, text=True, check=False)   # return code checked below
print(r.stdout[-6000:], r.stderr[-2000:])
assert r.returncode == 0, "benchmark failed; see stderr above"

# COMMAND ----------

import pandas as pd

deid_dir = Path(data_root) / "deid"
display(pd.read_csv(deid_dir / "not_run.csv"))
display(pd.read_csv(deid_dir / "scores.csv"))
display(pd.read_csv(deid_dir / "cost_effectiveness.csv"))

# COMMAND ----------

# Copy the result CSVs (never the notes) into this Git folder's data/deid, ready to commit.
import shutil

out_dir = dbutils.widgets.get("out_dir").strip()
if out_dir:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    print("copied to", out_dir, ":", ", ".join(Path(shutil.copy(p, Path(out_dir) / p.name)).name
                                              for p in sorted(deid_dir.glob("*.csv"))))

if dbutils.widgets.get("save_to_repo") == "yes":
    repo_deid = (Path.cwd() / "../../data/deid").resolve()
    repo_deid.mkdir(parents=True, exist_ok=True)
    copied = [Path(shutil.copy(p, repo_deid / p.name)).name for p in sorted(deid_dir.glob("*.csv"))]
    print("copied to", repo_deid, ":", ", ".join(copied))
    print("Next: if a tier was skipped, merge the new engines' rows into the repo's CSVs rather than committing\n"
          "these wholesale; then commit from the Git folder dialog and tick T012b / T016 in specs/007-deid-methods/tasks.md.")
