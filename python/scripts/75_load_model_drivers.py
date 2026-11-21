"""Load the model ranking, its drivers and the LLM readers' traces into Databricks (spec 042 US2, #864).

    python scripts/75_load_model_drivers.py                 # tables, runs and traces
    python scripts/75_load_model_drivers.py --dry-run       # count what would be written, send nothing
    python scripts/75_load_model_drivers.py --trace-limit 5 # a first look

Tables go to health_transformation_lab.gold_perio_bench with a comment on every table and column; one MLflow run per
method and one trace per LLM reader call go to /Shared/perio-bench-model-ranking (health_transformation_lab_nlp/
model_drivers_load.py says what and why). Loading again adds no run or trace and replaces the tables. Settings:
DATABRICKS_HOST and DATABRICKS_TOKEN (or any Databricks SDK auth), DATABRICKS_WAREHOUSE_ID (optional). Synthetic data.
"""

import argparse
import json
import os
import subprocess
import sys

from health_transformation_lab_nlp import model_drivers as md
from health_transformation_lab_nlp import model_drivers_load as ld
from health_transformation_lab_nlp import readme_results as rr
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("75_load_model_drivers", data_label="synthetic")


class CountOnly:
    def __init__(self):
        self.statements = 0

    def sql(self, statement):
        self.statements += 1

    def existing_trace_keys(self):
        return set()

    def existing_run_methods(self, commit):
        return set()

    def log_run(self, run):
        pass

    def write_trace(self, trace):
        pass

    def flush(self):
        pass


ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--trace-limit", type=int)
a = ap.parse_args()

if not a.dry_run and not os.environ.get("DATABRICKS_HOST"):
    sys.exit("DATABRICKS_HOST is not set: the workspace to load into (docs/telemetry.md)")
commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
inp = rr.load_inputs()
built = md.build(inp)
client = CountOnly() if a.dry_run else ld.DatabricksClient(os.environ.get("DATABRICKS_WAREHOUSE_ID") or None)
summary = ld.load(built, inp, client, ld.new_batch(commit), trace_limit=a.trace_limit)
print(json.dumps(summary | {"dry_run": a.dry_run, "git_commit_sha": commit}))
