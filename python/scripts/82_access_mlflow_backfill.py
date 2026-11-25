"""Load a past AccessBench run from the gold table into MLflow's evaluation view (spec 045 US6, #961).

    python scripts/82_access_mlflow_backfill.py --run-id 608662392694095 --warehouse-id <id>

Reads `fact_access_answer` for that run through a SQL warehouse and logs it with `access_mlflow.log_run`, one MLflow
run per answering model plus one for the control answers. No model is called. The experiment is the bundle's
(`--experiment-id`, or found by its name, `.../health-transformation-lab-nlp-experiment`). Needs DATABRICKS_HOST
and a workspace credential; the questions are synthetic.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

from health_transformation_lab_nlp import access_batch, access_mlflow, gold_names, telemetry

TABLE = "health_transformation_lab.gold_access_bench.fact_access_answer"
EXPERIMENT_SUFFIX = "/health-transformation-lab-nlp-experiment"
BOOLS = ("is_phi_leak", "is_truncated", "is_invented_contact", "is_simulated", "is_next_step_pass", "is_control_match")
FLOATS = ("score_ratio", "coverage_ratio", "latency_seconds", "cost_usd")
INTS = ("covered_key_point_count", "positive_point_count", "covered_positive_point_count", "resource_level_num",
        "link_count", "broken_link_count", "unchecked_link_count", "input_token_count", "output_token_count")


def typed(df: pd.DataFrame) -> pd.DataFrame:
    """The SQL API returns every cell as text: give the gold columns their types back."""
    out = df.copy()
    for c in BOOLS:
        if c in out:
            out[c] = out[c].map(lambda v: None if v is None else str(v).lower() == "true")
    for c in FLOATS:
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    for c in INTS:
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("Int64")
    return out


def read_gold(run_id: str, warehouse_id: str) -> pd.DataFrame:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementParameterListItem
    w = WorkspaceClient()
    res = w.statement_execution.execute_statement(
        statement=f"select * from {TABLE} where run_id = :run_id", warehouse_id=warehouse_id, wait_timeout="50s",
        parameters=[StatementParameterListItem(name="run_id", value=run_id)])
    if res.status.state.value != "SUCCEEDED":
        raise RuntimeError(f"query {res.status.state.value}: {res.status.error}")
    cols = [c.name for c in res.manifest.schema.columns]
    rows = list(res.result.data_array or [])
    chunk = res.result.next_chunk_index
    while chunk:
        part = w.statement_execution.get_statement_result_chunk_n(res.statement_id, chunk)
        rows += part.data_array or []
        chunk = part.next_chunk_index
    return typed(pd.DataFrame(rows, columns=cols))


def find_experiment() -> str:
    from databricks.sdk import WorkspaceClient
    for e in WorkspaceClient().experiments.search_experiments(filter="name LIKE '%health-transformation-lab-nlp-experiment'"):
        if e.name.endswith(EXPERIMENT_SUFFIX):
            return e.experiment_id
    raise SystemExit("no experiment named *health-transformation-lab-nlp-experiment: pass --experiment-id")


def main(argv=None) -> int:
    telemetry.setup()
    telemetry.start_script("82_access_mlflow_backfill", data_label="synthetic")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run-id", required=True, help="the AccessBench batch's Databricks job run id")
    p.add_argument("--warehouse-id", default=os.environ.get("DATABRICKS_WAREHOUSE_ID", ""),
                   help="SQL warehouse to read the gold table (default: DATABRICKS_WAREHOUSE_ID)")
    p.add_argument("--experiment-id", default="", help="MLflow experiment (default: the bundle's, found by name)")
    a = p.parse_args(argv)
    if not a.warehouse_id:
        p.error("--warehouse-id (or DATABRICKS_WAREHOUSE_ID) is required")
    gold = read_gold(a.run_id, a.warehouse_id)
    if gold.empty:
        print(f"no rows for run {a.run_id} in {TABLE}", file=sys.stderr)
        return 1
    fact = gold_names.from_gold(gold, "fact_access_answer")
    import mlflow
    mlflow.set_tracking_uri("databricks")
    experiment_id = a.experiment_id or find_experiment()
    mlflow.set_experiment(experiment_id=experiment_id)
    judge = str(fact["judge_endpoint"].iloc[0])
    version = str(fact["prompt_version"].iloc[0])
    runs = access_mlflow.log_run(fact, {r["id"]: r for r in access_batch.all_items()}, batch_run_id=a.run_id,
                                 judge_endpoint=judge, prompt_version=version, configure=False)
    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    print(f"logged {len(fact)} answers from run {a.run_id} into experiment {experiment_id}")
    for name, rid in runs.items():
        print(f"  {name}: {host}/ml/experiments/{experiment_id}/evaluation-runs?selectedRunUuid={rid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
