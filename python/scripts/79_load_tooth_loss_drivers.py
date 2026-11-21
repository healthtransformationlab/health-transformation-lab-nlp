"""Load the tooth-loss model comparison into Databricks (spec 042 US4, #867).

    python scripts/79_load_tooth_loss_drivers.py            # tables and MLflow runs
    python scripts/79_load_tooth_loss_drivers.py --dry-run  # count what would be written, send nothing

Reads the committed data/datasets/model_drivers/tooth_loss_*.csv (scripts/78_tooth_loss_drivers.py writes them) and
writes them to health_transformation_lab.gold_opendental_perio with a comment on every table and column, and one MLflow
run per model to /Shared/tooth-loss-model-comparison (health_transformation_lab_nlp/tooth_loss_drivers_load.py says
what and why). Loading again replaces the tables and adds no run for a model already logged at the same commit.
Settings: DATABRICKS_HOST and DATABRICKS_TOKEN (or any Databricks SDK auth), DATABRICKS_WAREHOUSE_ID (optional).
SYNTHETIC data.
"""

import argparse
import json
import os
import subprocess
import sys

from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp import tooth_loss_drivers_load as tdl


class CountOnly:
    def __init__(self):
        self.statements = 0

    def sql(self, statement):
        self.statements += 1

    def existing_run_models(self, commit):
        return set()

    def log_run(self, run):
        pass


ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

if not a.dry_run and not os.environ.get("DATABRICKS_HOST"):
    sys.exit("DATABRICKS_HOST is not set: the workspace to load into (docs/telemetry.md)")
telemetry.setup()
telemetry.start_script("79_load_tooth_loss_drivers", data_label="synthetic")
commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
tables = tdl.read_tables()
client = CountOnly() if a.dry_run else tdl.DatabricksClient(os.environ.get("DATABRICKS_WAREHOUSE_ID") or None)
summary = tdl.load(tables, client, tdl.new_batch(commit))
print(json.dumps(summary | {"dry_run": a.dry_run, "git_commit_sha": commit}))
