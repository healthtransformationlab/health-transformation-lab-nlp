"""Load the model ranking, its drivers and the LLM readers' traces into Databricks (spec 042 US2, #864).

What goes where, and why:

- **Gold tables** in `health_transformation_lab.gold_perio_bench`: the seven tables of model_drivers.TABLES plus
  `model_chart_result` (one row per method and chart: what it answered, whether that was right, unsafe or the wrong
  stage, and the chart's facts), so a question such as "which L3 charts does the leader miss" is one query. Each is
  created with its column types and a comment on the table and on every column (model_drivers.COMMENTS), which
  Catalog Explorer and Genie read. Every row carries the batch key (run_id, run_ts, git_commit_sha); a load replaces
  the table (CREATE OR REPLACE), so loading again is idempotent.
- **MLflow runs**, one per method, in `/Shared/perio-bench-model-ranking`: the method's features as params and its
  scores as metrics, so the experiment's compare view ranks them. A method already logged for the same commit is
  skipped.
- **MLflow traces**, one per LLM reader call (`llm_details_<model>.csv`): the synthetic note in, the model's answer
  out, its token use and latency, and code-scorer assessments (is_correct, is_unsafe_error, is_wrong_stage,
  is_gate_ok, is_fallback). Every text is scrubbed first (telemetry.scrub_value, ADR 0010). A trace whose tag
  trace_key is already in the experiment is skipped.

The client is passed in (tests use a fake; DatabricksClient is the workspace). Synthetic data only.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import model_drivers as md
from . import readme_results as rr
from .harm import severity
from .paths import DATASETS_DIR
from .telemetry import scrub_value, traced

EXPERIMENT = "/Shared/perio-bench-model-ranking"
CATALOG, SCHEMA = "health_transformation_lab", "gold_perio_bench"
TRACE_SCHEMA, TRACE_PREFIX = "ops_agent_trace", "perio_reader"   # the experiment's Unity Catalog trace tables
CHUNK = 1000
BATCH_COMMENTS = {"run_id": "The load's batch key: one per run of scripts/75_load_model_drivers.py",
                  "run_ts": "When that load ran (UTC, ISO 8601)",
                  "git_commit_sha": "The commit the tables were built from"}

_CHART = {"method_code": md._C["method_code"], "visit_id": "The synthetic review chart (visit) id",
          "predicted_group_code": "The status group the method answered; NULL when it gave none",
          "truth_group_code": "The generator's true status group", "is_correct": "True when the two agree",
          "is_unsafe_error": "True when the error could harm a patient if acted on (harm.severity S1 or S2: e.g. a "
                             "missed periodontitis or a missed stage 4)",
          "is_wrong_stage": "True when right that it is periodontitis but the stage is wrong",
          "is_no_answer": "True when the method gave no status",
          "difficulty_code": "L1 the note states the 2017 diagnosis, L2 in older terms, L3 left to be inferred",
          "dx_scheme_code": "How the note writes the diagnosis (2017, catalogue, old, short, none)",
          "note_style_code": "Note style (ehr, soap, chart_summary, narrative)"}
COMMENTS = {name: (table, cols | BATCH_COMMENTS) for name, (table, cols) in md.COMMENTS.items()} | {
    "model_chart_result": ("PerioBench: one row per note-reading method and synthetic review chart: what it "
                           "answered, whether that was right, unsafe or the wrong stage, and the chart's facts (spec "
                           "042). Agreement with the generator's answer key, not clinical accuracy.",
                           _CHART | BATCH_COMMENTS)}


# ---------- SQL ----------

@traced
def sql_literal(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA:
        return "NULL"
    if isinstance(v, (bool, np.bool_)):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _sql_type(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(s):
        return "BIGINT"
    if pd.api.types.is_float_dtype(s):
        return "DOUBLE"
    return "STRING"


@traced
def table_sql(name: str, df: pd.DataFrame, batch: dict, catalog: str = CATALOG, schema: str = SCHEMA,
              chunk: int = CHUNK) -> list[str]:
    """CREATE OR REPLACE with every column's type and comment and the table's comment, then INSERTs in chunks."""
    df = df.assign(**batch)
    table_comment, cols = COMMENTS[name]
    fq = f"{catalog}.{schema}.{name}"
    defs = ", ".join(f"{c} {_sql_type(df[c])} COMMENT {sql_literal(cols.get(c, ''))}" for c in df.columns)
    out = [f"CREATE OR REPLACE TABLE {fq} ({defs}) COMMENT {sql_literal(table_comment)}"]
    rows = ["(" + ",".join(sql_literal(v) for v in r) + ")" for r in df.itertuples(index=False)]
    out += [f"INSERT INTO {fq} VALUES " + ",".join(rows[i:i + chunk]) for i in range(0, len(rows), chunk)]
    return out


# ---------- what is loaded ----------

def _unsafe(truth: str, pred) -> bool:
    return isinstance(pred, str) and severity(truth, pred) != "S0"


def _wrong_stage(truth: str, pred) -> bool:
    return (isinstance(pred, str) and pred != truth and truth.startswith("periodontitis")
            and pred.startswith("periodontitis"))


@traced
def chart_result(inp: dict) -> pd.DataFrame:
    truth, pred, _ = rr.phenotype_predictions(inp)
    key = inp["key"].reindex(truth.index)
    frames = []
    for m in md.note_methods(inp):
        p = pred[m].where(pred[m].notna(), None)
        frames.append(pd.DataFrame({
            "method_code": m, "visit_id": truth.index.astype("int64"), "predicted_group_code": p.to_numpy(),
            "truth_group_code": truth.to_numpy(), "is_correct": (pred[m] == truth).to_numpy(),
            "is_unsafe_error": [_unsafe(t, x) for t, x in zip(truth, p)],
            "is_wrong_stage": [_wrong_stage(t, x) for t, x in zip(truth, p)],
            "is_no_answer": pred[m].isna().to_numpy(), "difficulty_code": key["difficulty"].to_numpy(),
            "dx_scheme_code": key["dx_scheme"].to_numpy(), "note_style_code": key["style"].to_numpy()}))
    return pd.concat(frames, ignore_index=True)


@traced
def tables(built: dict, inp: dict) -> dict:
    return {name: built[name] for name in md.TABLES} | {"model_chart_result": chart_result(inp)}


def _recorded_ns(file_name: str) -> int:
    man = pd.read_csv(DATASETS_DIR / "results_manifest.csv").set_index("file")
    ts = man["recorded_at"].get(file_name, "2026-11-01T00:00:00Z")
    return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1e9)


def _answer(raw):
    text = str(raw).strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return scrub_value(json.loads(text))
    except (ValueError, TypeError):
        return scrub_value(str(raw))


def _int(v, default=0) -> int:
    return default if v is None or (isinstance(v, float) and math.isnan(v)) else int(v)


@traced
def llm_traces(inp: dict) -> list[dict]:
    """One trace per LLM reader call of a method on the leaderboard, scored against the answer key."""
    truth, pred, _ = rr.phenotype_predictions(inp)
    key = inp["key"]
    methods = set(md.note_methods(inp))
    out = []
    for f in sorted(DATASETS_DIR.glob("llm_details_*.csv")):
        method = f.stem.removeprefix("llm_details_")
        if method not in methods:
            continue
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        clock = _recorded_ns(f.name)
        det = pd.read_csv(f).set_index("visit_id").reindex(truth.index)
        for vid, r in det.iterrows():
            p = pred[method].get(vid)
            p = p if isinstance(p, str) else None
            t = truth[vid]
            latency_ns = int(float(r.latency_s if r.latency_s == r.latency_s else 0) * 1e9) or 1
            out.append({
                "name": "perio reader",
                "tags": {"trace_key": hashlib.sha256(f"{method}|{sha}|{vid}".encode()).hexdigest(),
                         "method_code": method, "visit_id": str(vid), "file_sha256": sha,
                         "prompt_version_text": str(r.prompt_version), "is_simulated": "false",
                         "data_label": "synthetic"},
                "inputs": {"visit_id": int(vid), "model_code": method, "prompt_version_text": str(r.prompt_version),
                           "shots_count": _int(r.shots), "note_text": scrub_value(str(key.loc[vid, "note_text"]))},
                "outputs": {"answer": _answer(r.raw), "predicted_group_code": p, "truth_group_code": t},
                "attributes": {"gen_ai.operation.name": "chat", "gen_ai.request.model": method,
                               "gen_ai.usage.input_tokens": _int(r.input_tokens),
                               "gen_ai.usage.output_tokens": _int(r.output_tokens),
                               "backend_code": str(r.backend), "latency_seconds": float(latency_ns / 1e9)},
                "start_ns": clock, "end_ns": clock + latency_ns,
                "assessments": {"is_correct": bool(p == t), "is_unsafe_error": _unsafe(t, p),
                                "is_wrong_stage": _wrong_stage(t, p), "is_gate_ok": str(r.gate_ok) == "True",
                                "is_fallback": str(r.fallback) == "True"}})
            clock += latency_ns
    return out


METRICS = ("correct_count", "correct_pct", "correct_lo_pct", "correct_hi_pct", "rank_position_count",
           "rank_lo_count", "rank_hi_count", "leader_only_count", "method_only_count", "vs_leader_p_ratio",
           "leader_only_l3_count", "leader_only_stage4_count", "l3_correct_pct", "stage4_correct_pct")


@traced
def method_runs(built: dict, batch: dict) -> list[dict]:
    runs = []
    for r in built["model_rank"].to_dict("records"):
        runs.append({"run_name": r["method_code"],
                     "params": {k: str(r[k]) for k in md.FEATURES},
                     "metrics": {k: float(r[k]) for k in METRICS if r[k] == r[k]},
                     "tags": {"method_code": r["method_code"], "git_commit_sha": batch["git_commit_sha"],
                              "load_run_id": batch["run_id"], "data_label": "synthetic", "spec": "042"}})
    return runs


@traced
def load(built: dict, inp: dict, client, batch: dict, catalog: str = CATALOG, schema: str = SCHEMA,
         trace_limit: int | None = None) -> dict:
    tabs = tables(built, inp)
    for name, df in tabs.items():
        for stmt in table_sql(name, df, batch, catalog, schema):
            client.sql(stmt)
    done = client.existing_run_methods(batch["git_commit_sha"])
    runs = [r for r in method_runs(built, batch) if r["tags"]["method_code"] not in done]
    for r in runs:
        client.log_run(r)
    have = client.existing_trace_keys()
    traces = [t for t in llm_traces(inp) if t["tags"]["trace_key"] not in have][:trace_limit]
    for t in traces:
        client.write_trace(t)
    client.flush()
    return {"table_count": len(tabs), "row_count": int(sum(len(d) for d in tabs.values())),
            "run_written_count": len(runs), "trace_written_count": len(traces)}


@traced
def new_batch(commit: str) -> dict:
    now = datetime.now(timezone.utc)
    return {"run_id": f"model-drivers-{now:%Y%m%dT%H%M%SZ}", "run_ts": now.isoformat(timespec="seconds"),
            "git_commit_sha": commit}


# ---------- the workspace ----------

class DatabricksClient:
    """SQL through a warehouse (the Statement Execution API) and MLflow on the workspace. Settings: DATABRICKS_HOST and
    DATABRICKS_TOKEN (or any auth the Databricks SDK finds), DATABRICKS_WAREHOUSE_ID (optional: the first warehouse).
    The experiment is made on first use with its traces stored in Unity Catalog (TRACE_SCHEMA, TRACE_PREFIX), so they
    can be queried in SQL; MLflow can't move an experiment's traces later."""

    def __init__(self, warehouse_id: str | None = None, experiment: str = EXPERIMENT):
        import mlflow
        from databricks.sdk import WorkspaceClient
        from mlflow.entities import SpanType
        from mlflow.entities.trace_location import UnityCatalog
        self.ws, self.mlflow, self.span_type = WorkspaceClient(), mlflow, SpanType
        self.warehouse_id = warehouse_id or next(iter(self.ws.warehouses.list())).id
        os.environ.setdefault("MLFLOW_TRACING_SQL_WAREHOUSE_ID", self.warehouse_id)   # UC trace reads and writes
        mlflow.set_tracking_uri("databricks")
        exp = mlflow.get_experiment_by_name(experiment)
        if exp is None:
            exp = mlflow.set_experiment(experiment, trace_location=UnityCatalog(CATALOG, TRACE_SCHEMA, TRACE_PREFIX))
        else:
            loc = getattr(exp, "trace_location", None)
            mlflow.set_experiment(experiment_id=exp.experiment_id, **({"trace_location": loc} if loc else {}))
        self.experiment_id = exp.experiment_id

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
    def existing_trace_keys(self) -> set[str]:
        traces = self.mlflow.search_traces(locations=[self.experiment_id], return_type="list", max_results=100_000)
        return {t.info.tags.get("trace_key") for t in traces} - {None}

    @traced
    def existing_run_methods(self, commit: str) -> set[str]:
        runs = self.mlflow.search_runs([self.experiment_id], filter_string=f"tags.git_commit_sha = '{commit}'",
                                       output_format="list")
        return {r.data.tags.get("method_code") for r in runs} - {None}

    @traced
    def log_run(self, run: dict) -> None:
        with self.mlflow.start_run(experiment_id=self.experiment_id, run_name=run["run_name"]):
            self.mlflow.set_tags(run["tags"])
            self.mlflow.log_params(run["params"])
            self.mlflow.log_metrics(run["metrics"])

    @traced
    def write_trace(self, t: dict) -> None:
        m = self.mlflow
        span = m.start_span_no_context(name=t["name"], span_type=self.span_type.LLM, inputs=t["inputs"],
                                       tags=t["tags"], attributes=t["attributes"], start_time_ns=t["start_ns"])
        span.end(outputs=t["outputs"], end_time_ns=t["end_ns"])   # a wrong answer is an assessment, not an error
        from mlflow.entities import AssessmentSource
        src = AssessmentSource(source_type="CODE", source_id="model_drivers_load.code_scorers")
        for name, value in t["assessments"].items():
            m.log_feedback(trace_id=span.trace_id, name=name, value=bool(value), source=src)

    @traced
    def flush(self) -> None:
        self.mlflow.flush_trace_async_logging()
