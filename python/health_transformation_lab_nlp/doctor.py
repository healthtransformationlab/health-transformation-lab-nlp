"""The pipeline doctor (spec 027): DataOps on top of the run tables.

Most of what breaks in production is visible in metadata before anyone reads a log; this measures the share. Every pipeline is a row in a config table
(`ops/pipeline_config.yaml`), every run is a row in a run table (`fact_pipeline_run`, from the spec 014 spans),
lineage says what fed what, and the runbook (`ops/runbook.yaml`) says what may be done per failure class.
The doctor reads those tables, never logs and never note text:

    signals      freshness, volume, schema, quality, duration, cost: a run against the pipeline's last ok runs
    classify     rules first, configuration-management classes before the rest (credential expiry,
                 vulnerability, deprecation, config drift between environments); `unknown` is the only class
                 the LLM (root-cause rung) ever sees
    recommend    the first allowed runbook action, the impact one hop down the lineage, severity, owner,
                 and a templated notification (no free LLM text)
    graduation   a reversible class runs unattended after N matches with the human; two misses send it back
    evaluate     the doctor against the repo's own incidents (data/ops/incident.csv), with 95% intervals
    ablation     the same, with the config table, the typed conventions, lineage, metrics or the run history
                 switched off one at a time: how much each piece of metadata buys

Agents recommend; code acts. Pure pandas; no Spark, no LLM call in this module.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import yaml

from .paths import REPO_ROOT
from .telemetry import traced

CONFIG_YAML = REPO_ROOT / "ops" / "pipeline_config.yaml"
RUNBOOK_YAML = REPO_ROOT / "ops" / "runbook.yaml"
INCIDENT_CSV = REPO_ROOT / "data" / "ops" / "incident.csv"
LINEAGE_CSV = REPO_ROOT / "data" / "ops" / "lineage_edge.csv"

RUN_COLUMNS = ["pipeline_name", "step_name", "run_id", "started_ts", "ended_ts", "run_status_code", "row_in_count",
               "row_out_count", "schema_sha256", "check_passed_count", "check_failed_count", "error_type_name",
               "error_text", "duration_seconds", "cost_usd", "git_commit_sha", "data_label_code"]
SIGNAL_NAMES = ["freshness_seconds", "volume_ratio", "is_schema_changed", "quality_ratio", "duration_ratio",
                "cost_ratio"]
CLASSES = ["credential_expiry", "vulnerability", "deprecation", "config_drift", "config", "platform", "schema_drift",
           "volume_anomaly", "quality_fail", "cost_anomaly", "source_late", "unknown"]
TRAILING_RUNS = 5
VOLUME_BOUNDS = (0.5, 2.0)
COST_BOUND = 3.0

# Configuration-management failures come first: they are invisible in logs until the damage is done and
# visible in tables before it. They are what pages people in practice.
_CREDENTIAL_TYPES = {"AuthenticationError", "PermissionError", "Unauthorized", "Forbidden", "ExpiredToken"}
_CREDENTIAL_WORDS = ("expired", "401", "403", "unauthorized", "invalid token", "token expired", "credential",
                     "authentication failed", "access denied")
_VULNERABILITY_WORDS = ("cve-", "vulnerability", "security advisory", "dependabot", "ghsa-", "critical severity")
_DEPRECATION_TYPES = {"DeprecationWarning", "FutureWarning", "NotFound", "ModelNotFound"}
_DEPRECATION_WORDS = ("deprecated", "no longer supported", "end of life", "end-of-life", "retired", "model not found",
                      "endpoint not found", "removed in version", "unsupported version")
_DRIFT_WORDS = ("differs between", "mismatch", "not in target", "only in dev", "only in prod", "config drift",
                "value differs", "environments differ")
_CONFIG_TYPES = {"MissingSetting", "KeyError", "ValueError"}
_CONFIG_WORDS = ("setting", "secret", "connection string", "is not set", "parameter", "credential", "token")
_PLATFORM_TYPES = {"Py4JException", "OSError", "ResourceExhausted", "CUDAError", "MemoryError", "TimeoutError"}
_PLATFORM_WORDS = ("gpu", "illegal seek", "signal", "killed", "memory", "py4j", "communication channel", "no space")

# What the LLM rung is handed when a rule can't decide (rung 3): the run row, the last N runs,
# lineage one hop each way, the runbook entry. Counted in fields, a proxy for tokens: the ablation's cost
# of troubleshooting without the metadata.
_LLM_CONTEXT_FIELDS = len(RUN_COLUMNS) * (1 + TRAILING_RUNS) + 4 * 4 + 6


def _text(x) -> str:
    return "" if x is None or (isinstance(x, float) and math.isnan(x)) else str(x)


def _float(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def _ts(x):
    t = pd.to_datetime(x, utc=True, errors="coerce")
    return t


def _ok_runs(run: dict, history: pd.DataFrame, n: int = TRAILING_RUNS) -> pd.DataFrame:
    if history is None or len(history) == 0:
        return pd.DataFrame(columns=RUN_COLUMNS)
    h = history[(history["pipeline_name"] == run["pipeline_name"]) & (history["run_status_code"] == "ok")]
    h = h.assign(_ended=_ts(h["ended_ts"])).sort_values("_ended")
    return h.tail(n)


def _duration(row) -> float:
    d = _float(row.get("duration_seconds")) if hasattr(row, "get") else float("nan")
    if not math.isnan(d):
        return d
    s, e = _ts(row.get("started_ts")), _ts(row.get("ended_ts"))
    if pd.isna(s) or pd.isna(e):
        return float("nan")
    return (e - s).total_seconds()


def _median(series: pd.Series) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.median()) if len(s) else float("nan")


def _ratio(value: float, baseline: float) -> float:
    if math.isnan(value) or math.isnan(baseline) or baseline == 0:
        return float("nan")
    return value / baseline


# --- loaders ---------------------------------------------------------------------------------------

@traced
def load_config(path: Path = CONFIG_YAML) -> pd.DataFrame:
    """`dim_pipeline`: one row per pipeline, from ops/pipeline_config.yaml."""
    raw = yaml.safe_load(Path(path).read_text())["pipelines"]
    rows = [{"pipeline_name": name, **fields} for name, fields in raw.items()]
    return pd.DataFrame(rows)


@traced
def load_runbook(path: Path = RUNBOOK_YAML) -> pd.DataFrame:
    """`dim_runbook_entry`: one row per failure class, from ops/runbook.yaml."""
    raw = yaml.safe_load(Path(path).read_text())["entries"]
    df = pd.DataFrame(raw)
    df["is_reversible"] = df["is_reversible"].astype(bool)
    return df


@traced
def load_incidents(path: Path = INCIDENT_CSV) -> pd.DataFrame:
    """The repo's own incidents as run rows with the action the owner took (spec 027 US4)."""
    inc = pd.read_csv(path, dtype={"schema_sha256": "string", "error_type_name": "string", "error_text": "string"})
    inc["is_reversible"] = inc["is_reversible"].astype(str).str.lower().eq("true")
    for c in ("started_ts", "ended_ts"):
        inc[c] = _ts(inc[c])
    return inc


@traced
def load_lineage(path: Path = LINEAGE_CSV) -> pd.DataFrame:
    """`dim_lineage_edge`: one row per edge. Committed CSV until the Unity Catalog system-table export exists."""
    return pd.read_csv(path)


@traced
def baseline_history(config: pd.DataFrame, n: int = TRAILING_RUNS, end: str = "2026-10-19T06:00:00Z",
                     row_count: int = 240, duration_seconds: float = 600.0, cost_usd: float = 0.8) -> pd.DataFrame:
    """SIMULATED trailing ok runs, `n` per pipeline, so the incident eval has a baseline to compare against.
    In a workspace these are the real last ok rows of `fact_pipeline_run`; here they are labelled simulated."""
    t_end = _ts(end)
    rows = []
    for p in config["pipeline_name"]:
        for i in range(n):
            start = t_end - pd.Timedelta(days=n - i)
            rows.append({"pipeline_name": p, "step_name": "sim:step", "run_id": f"sim:{p}:{i}", "started_ts": start,
                         "ended_ts": start + pd.Timedelta(seconds=duration_seconds), "run_status_code": "ok",
                         "row_in_count": row_count, "row_out_count": row_count, "schema_sha256": "abc",
                         "check_passed_count": 12, "check_failed_count": 0, "error_type_name": None,
                         "error_text": None, "duration_seconds": duration_seconds, "cost_usd": cost_usd,
                         "git_commit_sha": "sim", "data_label_code": "simulated"})
    return pd.DataFrame(rows)


# --- US1: signals and classification ---------------------------------------------------------------

@traced
def signals(run: dict, history: pd.DataFrame, config: pd.DataFrame, now=None) -> dict:
    """The six signals for one run against the pipeline's last ok runs. Missing history gives NaN / None, never
    an error: a brand-new pipeline is classified on its error alone."""
    ok = _ok_runs(run, history)
    if now is None:
        now = _ts(run.get("ended_ts"))
        if pd.isna(now):
            now = _ts(run.get("started_ts"))
        if pd.isna(now):
            now = pd.Timestamp.now(tz="UTC")
    else:
        now = _ts(now)
    last_ok_end = _ts(ok["ended_ts"]).max() if len(ok) else pd.NaT
    freshness = float("nan") if pd.isna(last_ok_end) else (now - last_ok_end).total_seconds()
    volume = _ratio(_float(run.get("row_out_count")), _median(ok["row_out_count"]) if len(ok) else float("nan"))
    sha, last_sha = _text(run.get("schema_sha256")), (_text(ok.iloc[-1]["schema_sha256"]) if len(ok) else "")
    schema = None if not sha or not last_sha else sha != last_sha
    passed, failed = _float(run.get("check_passed_count")), _float(run.get("check_failed_count"))
    checks = (0 if math.isnan(passed) else passed) + (0 if math.isnan(failed) else failed)
    quality = float("nan") if checks == 0 else (0 if math.isnan(passed) else passed) / checks
    duration = _ratio(_duration(run), _median(ok.apply(_duration, axis=1)) if len(ok) else float("nan"))
    cost = _ratio(_float(run.get("cost_usd")), _median(ok["cost_usd"]) if len(ok) and "cost_usd" in ok else float("nan"))
    return {"freshness_seconds": freshness, "volume_ratio": volume, "is_schema_changed": schema,
            "quality_ratio": quality, "duration_ratio": duration, "cost_ratio": cost}


def _sla(config: pd.DataFrame, pipeline: str) -> float:
    c = config[config["pipeline_name"] == pipeline]
    return _float(c.iloc[0]["sla_seconds"]) if len(c) else float("nan")


@traced
def classify(run: dict, history: pd.DataFrame, config: pd.DataFrame, now=None) -> dict:
    """Rules first, in order; the first that fires wins. Returns the class, the rule that fired and the signals."""
    s = signals(run, history, config, now)
    etype, etext = _text(run.get("error_type_name")), _text(run.get("error_text")).lower()
    sla = _sla(config, run["pipeline_name"])
    started = _ts(run.get("started_ts"))

    def hit(cls, rule):
        return {"failure_class_code": cls, "rule_name": rule, "signals": s}

    if etype in _CREDENTIAL_TYPES or any(w in etext for w in _CREDENTIAL_WORDS):
        return hit("credential_expiry", "error_type_or_text:credential")
    if any(w in etext for w in _VULNERABILITY_WORDS):
        return hit("vulnerability", "error_text:vulnerability")
    if etype in _DEPRECATION_TYPES or any(w in etext for w in _DEPRECATION_WORDS):
        return hit("deprecation", "error_type_or_text:deprecation")
    if any(w in etext for w in _DRIFT_WORDS):
        return hit("config_drift", "error_text:config_drift")
    if etype in _CONFIG_TYPES or any(w in etext for w in _CONFIG_WORDS):
        return hit("config", "error_type_or_text:config")
    if etype in _PLATFORM_TYPES or any(w in etext for w in _PLATFORM_WORDS):
        return hit("platform", "error_type_or_text:platform")
    if s["is_schema_changed"] is True:
        return hit("schema_drift", "schema_sha256_changed")
    v = s["volume_ratio"]
    if not math.isnan(v) and (v < VOLUME_BOUNDS[0] or v > VOLUME_BOUNDS[1]):
        return hit("volume_anomaly", "row_out_count_vs_trailing_median")
    failed = _float(run.get("check_failed_count"))
    if not math.isnan(failed) and failed > 0:
        return hit("quality_fail", "check_failed_count")
    c = s["cost_ratio"]
    if not math.isnan(c) and c > COST_BOUND:
        return hit("cost_anomaly", "cost_usd_vs_trailing_median")
    f = s["freshness_seconds"]
    if pd.isna(started) or (not math.isnan(f) and not math.isnan(sla) and f > sla):
        return hit("source_late", "never_started_or_freshness_over_sla")
    return hit("unknown", "no_rule")


# --- US2: recommend ---------------------------------------------------------------------------------

def _impact(pipeline: str, config: pd.DataFrame, lineage: pd.DataFrame) -> list[str]:
    c = config[config["pipeline_name"] == pipeline]
    outputs = list(c.iloc[0]["output_names"]) if len(c) and isinstance(c.iloc[0].get("output_names"), list) else []
    hop = [] if lineage is None or len(lineage) == 0 else \
        lineage.loc[lineage["upstream_name"].isin(outputs), "downstream_name"].tolist()
    seen, out = set(), []
    for name in outputs + hop:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _impact_known(pipeline: str, config: pd.DataFrame, lineage: pd.DataFrame) -> bool:
    """True when lineage names something beyond the pipeline's own outputs: the consumers a failure reaches."""
    c = config[config["pipeline_name"] == pipeline]
    outputs = list(c.iloc[0]["output_names"]) if len(c) and isinstance(c.iloc[0].get("output_names"), list) else []
    return bool(outputs) and lineage is not None and len(lineage) > 0 and \
        bool(lineage["upstream_name"].isin(outputs).any())


def _notification(run: dict, cls: str, action: str, severity: str, owner: str, impact: list[str]) -> str:
    etype = _text(run.get("error_type_name")) or "no error type"
    affects = ", ".join(impact) if impact else "no downstream on record"
    return (f"{severity} · {run['pipeline_name']} run {run.get('run_id')} classified {cls} ({etype}). "
            f"Recommended action: {action}. Affects: {affects}. Owner: {owner}. "
            f"Approve or override; the decision is recorded.")


@traced
def recommend(run: dict, history: pd.DataFrame, config: pd.DataFrame, runbook: pd.DataFrame,
              lineage: pd.DataFrame, attempts_so_far: int = 0, failure_class_code: str | None = None,
              now=None) -> dict:
    """The first allowed action for the run's class (past `retry` once the pipeline's retries are spent), the
    impact one hop down the lineage, severity, owner, and a templated notification. Never an action off the list."""
    cls = failure_class_code or classify(run, history, config, now)["failure_class_code"]
    entry = runbook[runbook["failure_class_code"] == cls].iloc[0]
    actions = list(entry["allowed_action_codes"])
    c = config[config["pipeline_name"] == run["pipeline_name"]]
    retry_max = int(_float(c.iloc[0]["retry_max_count"])) if len(c) and not math.isnan(_float(c.iloc[0]["retry_max_count"])) else 0
    if actions and actions[0] == "retry" and attempts_so_far >= retry_max and len(actions) > 1:
        actions = actions[1:]
    action = actions[0]
    owner = c.iloc[0]["owner_name"] if len(c) else entry["escalate_to_name"]
    impact = _impact(run["pipeline_name"], config, lineage)
    return {"pipeline_name": run["pipeline_name"], "run_id": run.get("run_id"), "failure_class_code": cls,
            "recommended_action_code": action, "downstream_names": impact, "is_reversible": bool(entry["is_reversible"]),
            "severity_code": entry["severity_code"], "owner_name": owner,
            "notification_text": _notification(run, cls, action, entry["severity_code"], owner, impact)}


# --- US3: graduation --------------------------------------------------------------------------------

@traced
def graduation(decisions: pd.DataFrame, runbook: pd.DataFrame, n: int = TRAILING_RUNS) -> pd.DataFrame:
    """Per failure class: `automatic` when the last `n` recommendations matched the human's decision and the
    class is reversible; `recommend_only` with fewer than `n` decisions, after two misses in a row, or for a
    non-reversible class. The rule is code, not a prompt."""
    rows = []
    for _, e in runbook.iterrows():
        cls = e["failure_class_code"]
        d = decisions[decisions["failure_class_code"] == cls] if len(decisions) else decisions
        d = d.sort_values("decided_ts") if len(d) else d
        recent = d["is_match"].astype(bool).tolist()[-n:] if len(d) else []
        last_two_missed = len(recent) >= 2 and not recent[-1] and not recent[-2]
        automatic = bool(e["is_reversible"]) and len(recent) >= n and all(recent) and not last_two_missed
        rows.append({"failure_class_code": cls, "decision_count": len(d), "recent_match_count": int(sum(recent)),
                     "is_reversible": bool(e["is_reversible"]),
                     "run_mode_code": "automatic" if automatic else "recommend_only"})
    return pd.DataFrame(rows)


# --- US4: evaluation on the incident set -----------------------------------------------------------

def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _score_rows(incidents: pd.DataFrame, config: pd.DataFrame, runbook: pd.DataFrame, lineage: pd.DataFrame,
                history: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, inc in incidents.iterrows():
        run = {c: inc.get(c) for c in RUN_COLUMNS}
        out = classify(run, history, config)
        pred = out["failure_class_code"]
        rec = recommend(run, history, config, runbook, lineage, failure_class_code=pred)
        rows.append({"incident_id": inc["incident_id"], "failure_class_code": inc["failure_class_code"],
                     "predicted_class_code": pred, "is_class_ok": pred == inc["failure_class_code"],
                     "is_action_ok": rec["recommended_action_code"] == inc["decided_action_code"],
                     "is_no_llm": pred != "unknown",
                     "is_impact_known": _impact_known(run["pipeline_name"], config, lineage),
                     "llm_context_field_count": 0 if pred != "unknown" else _LLM_CONTEXT_FIELDS})
    return pd.DataFrame(rows)


def _summarise(scored: pd.DataFrame) -> pd.DataFrame:
    def agg(g: pd.DataFrame, name: str) -> dict:
        n = len(g)
        k = int(g["is_class_ok"].sum())
        lo, hi = _wilson(k, n)
        return {"failure_class_code": name, "incident_count": n, "class_accuracy_ratio": k / n if n else float("nan"),
                "class_accuracy_ci_low": lo, "class_accuracy_ci_high": hi,
                "action_agreement_ratio": g["is_action_ok"].mean() if n else float("nan"),
                "no_llm_ratio": g["is_no_llm"].mean() if n else float("nan"),
                "impact_known_ratio": g["is_impact_known"].mean() if n else float("nan"),
                "llm_context_field_count": int(g["llm_context_field_count"].sum())}
    rows = [agg(g, cls) for cls, g in scored.groupby("failure_class_code", sort=True)]
    rows.append(agg(scored, "all"))
    return pd.DataFrame(rows)


@traced
def evaluate(incidents: pd.DataFrame, config: pd.DataFrame, runbook: pd.DataFrame, lineage: pd.DataFrame,
             history: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per class and overall: classification accuracy (Wilson 95% interval), agreement of the recommended
    action with the owner's decision, share resolved without the LLM, share with a known impact, and the
    fields the LLM rung would have been handed. With `history` None, a SIMULATED baseline of ok runs is used."""
    history = baseline_history(config) if history is None else history
    return _summarise(_score_rows(incidents, config, runbook, lineage, history))


# --- the ablation: what each piece of metadata buys -----------------------------------------------

ABLATIONS = {
    "full": "config table, typed conventions, lineage, metrics and run history all on",
    "no_config": "no config table: no SLA, no retry policy, no output names (impact unknown, late sources unseen)",
    "no_conventions": "no typed, consistently named signals: only error_text and row counts, as a plain log gives",
    # switch-off test: each condition hides one piece of metadata; whatever drops is what that piece contributed
    "no_lineage": "no lineage table: the impact of a failure is unknown",
    "no_metrics": "no OpenTelemetry metrics: no duration, no cost per run",
    "no_history": "no run history: no trailing median for volume, schema, duration or cost",
}


def _ablate(name: str, incidents: pd.DataFrame, config: pd.DataFrame, lineage: pd.DataFrame,
            history: pd.DataFrame):
    inc, cfg, lin, hist = incidents.copy(), config.copy(), lineage, history
    if name == "no_config":
        cfg = cfg.assign(sla_seconds=float("nan"), retry_max_count=0, output_names=[[] for _ in range(len(cfg))])
    elif name == "no_conventions":
        for c in ("error_type_name", "schema_sha256", "check_passed_count", "check_failed_count", "cost_usd"):
            inc[c] = None
    elif name == "no_lineage":
        lin = lineage.iloc[0:0]
    elif name == "no_metrics":
        inc = inc.assign(duration_seconds=float("nan"), cost_usd=float("nan"))
        hist = history.assign(duration_seconds=float("nan"), cost_usd=float("nan"))
    elif name == "no_history":
        hist = history.iloc[0:0]
    return inc, cfg, lin, hist


@traced
def ablation(incidents: pd.DataFrame, config: pd.DataFrame, runbook: pd.DataFrame, lineage: pd.DataFrame,
             history: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per condition: the overall `evaluate` numbers with one piece of metadata switched off. The
    difference from `full` is what that piece buys in classification, LLM load and known impact."""
    history = baseline_history(config) if history is None else history
    rows = []
    for name, description in ABLATIONS.items():
        inc, cfg, lin, hist = _ablate(name, incidents, config, lineage, history)
        total = _summarise(_score_rows(inc, cfg, runbook, lin, hist))
        total = total[total["failure_class_code"] == "all"].iloc[0].to_dict()
        total.pop("failure_class_code")
        rows.append({"condition_name": name, "description_text": description, **total})
    return pd.DataFrame(rows)
