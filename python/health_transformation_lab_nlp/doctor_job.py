"""The pipeline doctor as a Databricks job (spec 027 US5): everything databricks/notebooks/13_pipeline_doctor.py
decides, in pandas, so it is tested without Spark. The notebook only reads and writes tables.

    check_settings   the job's parameters, checked before any work; a bad one fails naming it
    job_names        job display name -> pipeline key, from databricks/resources/jobs.yml (as ops/pipeline_config.yaml)
    timeline_runs    system.lakeflow.job_run_timeline rows (one per run) -> fact_pipeline_run rows
    merge_spans      the span export (optional), one row per run, fills what the timeline can't say
    diagnose         doctor.signals for every recent run; doctor.classify and doctor.recommend for every failed
                     one; doctor.graduation on past decisions; approvals given as a job parameter
    notifications    new SEV1/SEV2 decisions notify now; SEV3/SEV4 wait for the digest (AGENTS.md severity table)
    rows, ddl        frames as the declared gold columns and Spark types (diagrams/_build/gold_model.py)

Run metadata only: names, counts, durations, states, error types. Never note text or row-level data. The job
never acts on a recommendation: it records it, and the owner's decision when one is given. Agents recommend;
code acts, and the code that acts is not written yet.
"""

from __future__ import annotations

import math
import re

import pandas as pd
import yaml

from . import doctor
from .paths import REPO_ROOT
from .telemetry import traced

JOBS_YML = REPO_ROOT / "databricks" / "resources" / "jobs.yml"
SELF = "pipeline_doctor"            # its own runs are never diagnosed: a page it raised is not a new failure
HISTORY_DAYS = 60                   # job runs read for the trailing ok runs; weekly jobs need five weeks
MAX_LOOKBACK_DAYS = 30
NOTIFY_NOW = ("SEV1", "SEV2")       # AGENTS.md "Alerts and severity": the owner directly; SEV3/4 go to the digests

# system.lakeflow.job_run_timeline result_state -> run_status_code. Runs still going (null), cancelled, skipped
# or blocked are neither failures nor ok baselines, so they are left out.
STATES = {"SUCCEEDED": "ok", "FAILED": "failed", "ERROR": "failed", "TIMED_OUT": "timed_out", "TIMEDOUT": "timed_out"}

_BATCH = [("doctor_run_id", "string"), ("loaded_ts", "timestamp"), ("doctor_git_commit_sha", "string")]
_RUN_TYPES = {"started_ts": "timestamp", "ended_ts": "timestamp", "row_in_count": "bigint", "row_out_count": "bigint",
              "check_passed_count": "bigint", "check_failed_count": "bigint", "duration_seconds": "double",
              "cost_usd": "double"}
TABLES = {
    "fact_pipeline_run": [(c, _RUN_TYPES.get(c, "string")) for c in doctor.RUN_COLUMNS] + _BATCH,
    "fact_pipeline_signal": [("pipeline_name", "string"), ("step_name", "string"), ("run_id", "string"),
                             ("started_ts", "timestamp"), ("run_status_code", "string"),
                             ("freshness_seconds", "double"), ("sla_seconds", "double"), ("volume_ratio", "double"),
                             ("is_schema_changed", "boolean"), ("quality_ratio", "double"),
                             ("duration_ratio", "double"), ("cost_ratio", "double")] + _BATCH,
    "fact_remediation_decision": [("pipeline_name", "string"), ("run_id", "string"), ("run_started_ts", "timestamp"),
                                  ("failure_class_code", "string"), ("rule_name", "string"),
                                  ("recommended_action_code", "string"), ("is_reversible", "boolean"),
                                  ("severity_code", "string"), ("owner_name", "string"), ("impact_text", "string"),
                                  ("notification_text", "string"), ("run_mode_code", "string"),
                                  ("decided_action_code", "string"), ("decided_by_name", "string"),
                                  ("decided_ts", "timestamp"), ("is_match", "boolean")] + _BATCH,
}

_NAME = re.compile(r"[a-z_][a-z0-9_]*")
_TABLE = re.compile(r"\w+\.\w+\.\w+")
_TOKEN = re.compile(r"[\w.:+@/-]+")


def _cols(table: str) -> list[str]:
    return [n for n, _ in TABLES[table]]


def _null(v) -> bool:
    if v is None or v is pd.NaT or v is pd.NA:
        return True
    return isinstance(v, float) and math.isnan(v)


# --- settings -------------------------------------------------------------------------------------

@traced
def check_settings(widgets: dict) -> dict:
    """The job's parameters, parsed. A required one missing or malformed raises ValueError starting with its
    name, before any work. `none` switches off the judge endpoint (root-cause rung) or the span export."""
    def get(name: str) -> str:
        return str(widgets.get(name, "") or "").strip()

    out = {}
    for name in ("catalog", "schema"):
        if not _NAME.fullmatch(get(name)):
            raise ValueError(f"{name}: {get(name)!r} is not a lowercase Unity Catalog name")
        out[name] = get(name)
    endpoint = get("judge_endpoint")
    if not endpoint or not _TOKEN.fullmatch(endpoint):
        raise ValueError(f"judge_endpoint: {endpoint!r}; give a serving endpoint name, or none to switch the "
                         "root-cause rung off")
    out["judge_endpoint"] = None if endpoint == "none" else endpoint
    try:
        out["max_usd"] = float(get("max_usd"))
    except ValueError:
        raise ValueError(f"max_usd: {get('max_usd')!r} is not a number of US dollars") from None
    if not out["max_usd"] > 0:
        raise ValueError(f"max_usd: {out['max_usd']} must be above 0")
    days = get("lookback_days")
    if not days.isdigit() or not 1 <= int(days) <= MAX_LOOKBACK_DAYS:
        raise ValueError(f"lookback_days: {days!r} must be a whole number of days, 1 to {MAX_LOOKBACK_DAYS}")
    out["lookback_days"] = int(days)
    span = get("span_table")
    if span != "none" and not _TABLE.fullmatch(span):
        raise ValueError(f"span_table: {span!r} must be catalog.schema.table, or none")
    out["span_table"] = None if span == "none" else span
    run_id = get("run_id")
    if not _TOKEN.fullmatch(run_id):
        raise ValueError(f"run_id: {run_id!r}; the job sets it ({{{{job.run_id}}}}), pass one when running by hand")
    out["run_id"], out["git_commit"] = run_id, get("git_commit")
    actions = {a for codes in doctor.load_runbook()["allowed_action_codes"] for a in codes}
    out["decisions"] = {}
    for item in filter(None, (s.strip() for s in get("decisions").split(","))):
        run, _, action = item.partition("=")
        run, action = run.strip(), action.strip()
        if not _TOKEN.fullmatch(run) or action not in actions:
            raise ValueError(f"decisions: {item!r} must be run_id=action_code, the action one of {sorted(actions)}")
        out["decisions"][run] = action
    out["decided_by"] = get("decided_by")
    if out["decisions"] and not out["decided_by"]:
        raise ValueError("decided_by: required when decisions are given (who decided, as in ops/pipeline_config.yaml)")
    return out


# --- the run table --------------------------------------------------------------------------------

@traced
def job_names(path=JOBS_YML) -> dict[str, str]:
    """Job display name (what system.lakeflow.jobs holds) -> the job's key in the bundle (the pipeline name)."""
    jobs = yaml.safe_load(path.read_text())["resources"]["jobs"]
    return {j["name"]: key for key, j in jobs.items()}


@traced
def timeline_runs(timeline: pd.DataFrame, config: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    """One row per finished run of a job this bundle deploys, under fact_pipeline_run's columns. The timeline
    gives state, times and the termination code (as the error type); counts, schema hash and checks come from
    the span export (merge_spans) when there is one."""
    labels = dict(zip(config["pipeline_name"], config["data_label_code"]))
    rows = []
    for r in timeline.itertuples(index=False):
        pipeline, status = names.get(r.job_name), STATES.get(str(r.result_state).upper())
        if pipeline is None or status is None or pipeline not in labels:
            continue
        start, end = doctor._ts(r.started_ts), doctor._ts(r.ended_ts)
        code = None if _null(r.termination_code) or status == "ok" else str(r.termination_code)
        rows.append({"pipeline_name": pipeline, "step_name": "job", "run_id": str(r.run_id), "started_ts": start,
                     "ended_ts": end, "run_status_code": status, "row_in_count": None, "row_out_count": None,
                     "schema_sha256": None, "check_passed_count": None, "check_failed_count": None,
                     "error_type_name": code, "error_text": None,
                     "duration_seconds": (end - start).total_seconds() if not (pd.isna(start) or pd.isna(end))
                     else float("nan"),
                     "cost_usd": float("nan"), "git_commit_sha": None, "data_label_code": labels[pipeline]})
    out = pd.DataFrame(rows, columns=doctor.RUN_COLUMNS)
    return out.sort_values(["pipeline_name", "started_ts"], kind="stable").reset_index(drop=True)


@traced
def merge_spans(runs: pd.DataFrame, spans: pd.DataFrame | None) -> pd.DataFrame:
    """Fill each run from the span export: one row per (pipeline_name, run_id) with any of fact_pipeline_run's
    columns. A span value that is set wins (its error type is the exception, more exact than a termination
    code). A column that isn't a run column, or that names a note, is refused."""
    if spans is None or not len(spans):
        return runs
    bad = [c for c in spans.columns if "note" in c.lower() or c not in doctor.RUN_COLUMNS]
    if bad:
        raise ValueError(f"span export: columns {bad} are not fact_pipeline_run columns (run metadata only)")
    out = runs.copy().astype({c: object for c in spans.columns if c in runs.columns})
    key = list(zip(out["pipeline_name"], out["run_id"].astype(str)))
    for s in spans.to_dict("records"):
        hit = [i for i, k in zip(out.index, key) if k == (s["pipeline_name"], str(s["run_id"]))]
        for c, v in s.items():
            if c not in ("pipeline_name", "run_id") and not _null(v):
                out.loc[hit, c] = v
    return out


# --- diagnosis ------------------------------------------------------------------------------------

def _empty(table: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[c for c in _cols(table) if c not in dict(_BATCH)])


@traced
def diagnose(runs: pd.DataFrame, config: pd.DataFrame, runbook: pd.DataFrame, lineage: pd.DataFrame, since,
             previous: pd.DataFrame | None = None, decisions: dict | None = None, decided_by: str = "",
             now=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(signals, decisions) for the runs that started at or after `since`, each against its pipeline's runs that
    ended before it. A failed run has spent the retries its job defines, so the recommendation starts past
    `retry`. `previous` is fact_remediation_decision as it stands: decisions in it are carried forward and feed
    graduation. `decisions` (run_id -> action code) records the owner's approvals; an action off the runbook's
    list for that run's class, or a run that isn't a failure being diagnosed, raises ValueError."""
    now = pd.Timestamp.now(tz="UTC") if now is None else doctor._ts(now)
    decisions = decisions or {}
    runs = runs[runs["pipeline_name"] != SELF]
    recent = runs[doctor._ts(runs["started_ts"]) >= doctor._ts(since)]
    previous = previous if previous is not None and len(previous) else pd.DataFrame(columns=_cols(
        "fact_remediation_decision"))
    decided = previous[previous["decided_action_code"].notna()]
    modes = dict(doctor.graduation(decided, runbook)[["failure_class_code", "run_mode_code"]].values)
    carried = {str(r["run_id"]): r for r in decided.to_dict("records")}
    allowed = {e["failure_class_code"]: list(e["allowed_action_codes"]) for e in runbook.to_dict("records")}
    sla = dict(zip(config["pipeline_name"], config["sla_seconds"]))
    retries = dict(zip(config["pipeline_name"], config["retry_max_count"]))
    signal_rows, decision_rows = [], []
    for run in recent.to_dict("records"):
        mine = runs[(runs["pipeline_name"] == run["pipeline_name"])]
        history = mine[doctor._ts(mine["ended_ts"]) < doctor._ts(run["started_ts"])]
        s = doctor.signals(run, history, config)
        signal_rows.append({k: run[k] for k in ("pipeline_name", "step_name", "run_id", "started_ts",
                                                 "run_status_code")} | {"sla_seconds": sla.get(run["pipeline_name"])} | s)
        if run["run_status_code"] not in ("failed", "timed_out"):
            continue
        c = doctor.classify(run, history, config)
        rec = doctor.recommend(run, history, config, runbook, lineage,
                               attempts_so_far=int(retries.get(run["pipeline_name"], 0) or 0),
                               failure_class_code=c["failure_class_code"])
        run_id = str(run["run_id"])
        row = {"pipeline_name": run["pipeline_name"], "run_id": run_id, "run_started_ts": run["started_ts"],
               "failure_class_code": c["failure_class_code"], "rule_name": c["rule_name"],
               "recommended_action_code": rec["recommended_action_code"], "is_reversible": rec["is_reversible"],
               "severity_code": rec["severity_code"], "owner_name": rec["owner_name"],
               "impact_text": ", ".join(rec["downstream_names"]), "notification_text": rec["notification_text"],
               "run_mode_code": modes.get(c["failure_class_code"], "recommend_only"),
               "decided_action_code": None, "decided_by_name": None, "decided_ts": pd.NaT, "is_match": None}
        if run_id in decisions:
            action = decisions.pop(run_id)
            if action not in allowed[c["failure_class_code"]]:
                raise ValueError(f"decisions: {action} is not allowed for run {run_id} ({c['failure_class_code']}: "
                                 f"{allowed[c['failure_class_code']]})")
            row |= {"decided_action_code": action, "decided_by_name": decided_by, "decided_ts": now}
        elif run_id in carried:
            row |= {k: carried[run_id][k] for k in ("decided_action_code", "decided_by_name", "decided_ts")}
        if row["decided_action_code"] is not None:
            row["is_match"] = row["decided_action_code"] == row["recommended_action_code"]
        decision_rows.append(row)
    if decisions:
        raise ValueError(f"decisions: run(s) {sorted(decisions)} are not failed runs in the lookback window")
    sig = pd.DataFrame(signal_rows) if signal_rows else _empty("fact_pipeline_signal")
    dec = pd.DataFrame(decision_rows) if decision_rows else _empty("fact_remediation_decision")
    return sig, dec


@traced
def notifications(decisions: pd.DataFrame, previous: pd.DataFrame | None = None) -> tuple[list[str], dict]:
    """(texts to send now, {severity: count} for the digest). Only decisions on runs not already in `previous`
    count, so a doctor run that reads the same failure again does not page again. SEV1 and SEV2 go to the owner
    now; SEV3 and SEV4 wait for the daily and weekly digests."""
    seen = set() if previous is None or not len(previous) else set(previous["run_id"].astype(str))
    new = decisions[~decisions["run_id"].astype(str).isin(seen)] if len(decisions) else decisions
    if not len(new):
        return [], {}
    now = new[new["severity_code"].isin(NOTIFY_NOW)].sort_values("severity_code", kind="stable")
    later = new[~new["severity_code"].isin(NOTIFY_NOW)]["severity_code"].value_counts().sort_index()
    return list(now["notification_text"]), {k: int(v) for k, v in later.items()}


# --- rows for Spark -------------------------------------------------------------------------------

_CAST = {"string": str, "bigint": int, "double": float, "boolean": bool,
         "timestamp": lambda v: doctor._ts(v)}


@traced
def rows(df: pd.DataFrame, table: str, doctor_run_id: str, loaded_ts, doctor_git_commit_sha: str) -> pd.DataFrame:
    """df as `table`'s declared columns, in order, with the batch key on every row and plain Python values
    (None for missing), so Spark takes them under ddl(table) whatever pandas inferred."""
    df = df.assign(doctor_run_id=doctor_run_id, loaded_ts=doctor._ts(loaded_ts),
                   doctor_git_commit_sha=doctor_git_commit_sha or None)
    out = {}
    for name, kind in TABLES[table]:
        values = df[name].tolist() if name in df.columns else [None] * len(df)
        out[name] = pd.Series([None if _null(v) else _CAST[kind](v) for v in values], dtype=object)
    return pd.DataFrame(out, columns=_cols(table))


@traced
def ddl(table: str) -> str:
    """Spark DDL for the table's declared columns."""
    return ", ".join(f"{n} {t}" for n, t in TABLES[table])
