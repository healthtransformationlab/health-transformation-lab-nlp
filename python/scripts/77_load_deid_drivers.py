"""Load the de-identification ranking and its drivers into Databricks (spec 042 US3, #866).

    python scripts/77_load_deid_drivers.py            # replace the deid_* tables
    python scripts/77_load_deid_drivers.py --dry-run  # count the statements and rows, send nothing

Tables go to health_transformation_lab.gold_perio_bench (deid_drivers.LOAD_TABLES) with a comment on every table and
column (deid_drivers.COMMENTS) and the batch key (run_id, run_ts, git_commit_sha); CREATE OR REPLACE makes a reload
idempotent. Settings: DATABRICKS_HOST and DATABRICKS_TOKEN (or any Databricks SDK auth), DATABRICKS_WAREHOUSE_ID
(optional: the first warehouse). Fake PHI on synthetic notes only.
"""

import argparse
import json
import os
import subprocess
import sys

from health_transformation_lab_nlp import deid_drivers as dd
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("77_load_deid_drivers", data_label="synthetic")


class CountOnly:
    def __init__(self):
        self.statements = 0

    def sql(self, statement):
        self.statements += 1


class Warehouse:
    """SQL through a warehouse, with the Statement Execution API."""

    def __init__(self, warehouse_id=None):
        from databricks.sdk import WorkspaceClient
        self.ws = WorkspaceClient()
        self.warehouse_id = warehouse_id or next(iter(self.ws.warehouses.list())).id
        self.statements = 0

    def sql(self, statement):
        from databricks.sdk.service.sql import StatementState
        res = self.ws.statement_execution.execute_statement(statement=statement, warehouse_id=self.warehouse_id,
                                                            wait_timeout="50s")
        while res.status.state in (StatementState.PENDING, StatementState.RUNNING):
            res = self.ws.statement_execution.get_statement(res.statement_id)
        if res.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"{res.status.state}: {res.status.error.message if res.status.error else ''} "
                               f"in {statement[:120]}")
        self.statements += 1


ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

if not a.dry_run and not os.environ.get("DATABRICKS_HOST"):
    sys.exit("DATABRICKS_HOST is not set: the workspace to load into (docs/telemetry.md)")
commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip() or "unknown"
client = CountOnly() if a.dry_run else Warehouse(os.environ.get("DATABRICKS_WAREHOUSE_ID") or None)
summary = dd.load(dd.build(dd.load_span_result()), client, dd.new_batch(commit))
print(json.dumps(summary | {"statement_count": client.statements, "dry_run": a.dry_run, "git_commit_sha": commit}))
