"""Load the tooth-loss model comparison into Databricks (spec 042 US4, #867).

- **Gold tables** in `health_transformation_lab.gold_opendental_perio`: the four tables of tooth_loss_drivers
  (ALL_TABLES), read from the committed CSVs in data/datasets/model_drivers/, each created with its column types and a
  comment on the table and on every column (tooth_loss_drivers.COMMENTS plus the batch key's). Every row carries the
  batch key (run_id, run_ts, git_commit_sha); a load replaces the table (CREATE OR REPLACE), so loading again is
  idempotent.
- **MLflow runs**, one per model, in `/Shared/tooth-loss-model-comparison`: the model, is_prespecified and its tuned
  settings per label set and predictor set as params; AUC, Brier and calibration slope with their 95% bounds, per label
  set, predictor set and set of teeth, as metrics. A model already logged for the same commit is skipped.

The client is passed in (tests use a fake). SYNTHETIC data only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from . import tooth_loss_drivers as tld
from .model_drivers_load import _sql_type, sql_literal
from .telemetry import traced

EXPERIMENT = "/Shared/tooth-loss-model-comparison"
CATALOG, SCHEMA = "health_transformation_lab", "gold_opendental_perio"
CHUNK = 1000
BATCH_COMMENTS = {"run_id": "The load's batch key: one per run of scripts/79_load_tooth_loss_drivers.py",
                  "run_ts": "When that load ran (UTC, ISO 8601)",
                  "git_commit_sha": "The commit the tables were built from"}
COMMENTS = {name: (table, cols | BATCH_COMMENTS) for name, (table, cols) in tld.COMMENTS.items()}
METRICS = ("auc_ratio", "auc_lo_ratio", "auc_hi_ratio", "brier_ratio", "brier_lo_ratio", "brier_hi_ratio",
           "calibration_slope_coef", "calibration_slope_lo_coef", "calibration_slope_hi_coef")


@traced
def read_tables(out_dir=None) -> dict[str, pd.DataFrame]:
    """The committed comparison tables (scripts/78_tooth_loss_drivers.py writes them)."""
    out_dir = out_dir or tld.OUT_DIR
    return {name: pd.read_csv(out_dir / f"{name}.csv") for name in tld.ALL_TABLES}


@traced
def table_sql(name: str, df: pd.DataFrame, batch: dict, catalog: str = CATALOG, schema: str = SCHEMA,
              chunk: int = CHUNK) -> list[str]:
    """CREATE OR REPLACE with every column's type and comment and the table's comment, then INSERTs in chunks.
    A column with no comment is an error, so nothing reaches Unity Catalog undescribed."""
    df = df.assign(**batch)
    table_comment, cols = COMMENTS[name]
    missing = [c for c in df.columns if not cols.get(c)]
    if missing:
        raise ValueError(f"{name}: no comment for {missing}")
    fq = f"{catalog}.{schema}.{name}"
    defs = ", ".join(f"{c} {_sql_type(df[c])} COMMENT {sql_literal(cols[c])}" for c in df.columns)
    out = [f"CREATE OR REPLACE TABLE {fq} ({defs}) COMMENT {sql_literal(table_comment)}"]
    rows = ["(" + ",".join(sql_literal(v) for v in r) + ")" for r in df.itertuples(index=False)]
    out += [f"INSERT INTO {fq} VALUES " + ",".join(rows[i:i + chunk]) for i in range(0, len(rows), chunk)]
    return out


@traced
def model_runs(rank: pd.DataFrame, batch: dict) -> list[dict]:
    """One MLflow run per model: params (model, is_prespecified, tuned settings per label set and predictor set) and
    metrics (<label set>.<predictor set>.<set of teeth>.<metric>) from the main seed's rank table."""
    runs = []
    for model, g in rank.groupby("model_code", sort=False):
        first = g.iloc[0]
        params = {"model_code": model, "model_text": first.model_text, "model_family_code": first.model_family_code,
                  "is_prespecified": str(bool(first.is_prespecified)).lower(),
                  "generator_seed_num": str(int(first.generator_seed_num))}
        for (ls, fs), h in g.groupby(["label_set_code", "feature_set_code"], sort=False):
            hyper = json.loads(h.hyperparameter_text.iloc[0]) if isinstance(h.hyperparameter_text.iloc[0], str) else {}
            params |= {f"{ls}.{fs}.{k}": str(v) for k, v in hyper.items()}
        metrics = {f"{r.label_set_code}.{r.feature_set_code}.{r.eval_set_code}.{k}": float(getattr(r, k))
                   for r in g.itertuples() for k in METRICS if getattr(r, k) == getattr(r, k)}
        runs.append({"run_name": model, "params": params, "metrics": metrics,
                     "tags": {"model_code": model, "is_prespecified": params["is_prespecified"],
                              "git_commit_sha": batch["git_commit_sha"], "load_run_id": batch["run_id"],
                              "data_label": "synthetic", "spec": "042"}})
    return runs


@traced
def load(tables: dict[str, pd.DataFrame], client, batch: dict, catalog: str = CATALOG, schema: str = SCHEMA) -> dict:
    for name, df in tables.items():
        for stmt in table_sql(name, df, batch, catalog, schema):
            client.sql(stmt)
    done = client.existing_run_models(batch["git_commit_sha"])
    runs = [r for r in model_runs(tables["tooth_loss_model_rank"], batch) if r["tags"]["model_code"] not in done]
    for r in runs:
        client.log_run(r)
    return {"table_count": len(tables), "row_count": int(sum(len(d) for d in tables.values())),
            "run_written_count": len(runs), "run_skipped_count": len(done)}


@traced
def new_batch(commit: str) -> dict:
    now = datetime.now(timezone.utc)
    return {"run_id": f"tooth-loss-drivers-{now:%Y%m%dT%H%M%SZ}", "run_ts": now.isoformat(timespec="seconds"),
            "git_commit_sha": commit}


class DatabricksClient:
    """SQL through a warehouse (the Statement Execution API) and MLflow runs on the workspace. Settings: DATABRICKS_HOST
    and DATABRICKS_TOKEN (or any auth the Databricks SDK finds), DATABRICKS_WAREHOUSE_ID (optional: the first one)."""

    def __init__(self, warehouse_id: str | None = None, experiment: str = EXPERIMENT):
        import mlflow
        from databricks.sdk import WorkspaceClient
        self.ws, self.mlflow = WorkspaceClient(), mlflow
        self.warehouse_id = warehouse_id or next(iter(self.ws.warehouses.list())).id
        mlflow.set_tracking_uri("databricks")
        self.experiment_id = mlflow.set_experiment(experiment).experiment_id

    @traced
    def sql(self, statement: str):
        from databricks.sdk.service.sql import StatementState
        res = self.ws.statement_execution.execute_statement(statement=statement, warehouse_id=self.warehouse_id,
                                                            wait_timeout="50s")
        while res.status.state in (StatementState.PENDING, StatementState.RUNNING):
            res = self.ws.statement_execution.get_statement(res.statement_id)
        if res.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"{res.status.state}: {res.status.error.message if res.status.error else ''} "
                               f"in {statement[:120]}")
        return res

    @traced
    def existing_run_models(self, commit: str) -> set[str]:
        runs = self.mlflow.search_runs([self.experiment_id], filter_string=f"tags.git_commit_sha = '{commit}'",
                                       output_format="list")
        return {r.data.tags.get("model_code") for r in runs} - {None}

    @traced
    def log_run(self, run: dict) -> None:
        with self.mlflow.start_run(experiment_id=self.experiment_id, run_name=run["run_name"]):
            self.mlflow.set_tags(run["tags"])
            self.mlflow.log_params(run["params"])
            self.mlflow.log_metrics(run["metrics"])

