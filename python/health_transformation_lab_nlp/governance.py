"""Spend and speed in the data-quality report (spec 036 US4, #576).

    load_budgets(path)      ops/budgets.yaml: each budget or target with its period, limit, owner and action
    budget_checks(...)      each budget and target, checked: `cost` and `performance` rows in dq_check's columns
    cost_data_checks(...)   data-quality checks on the cost data itself: completeness (REPORT, billing lags),
                            plausibility, how recently each setting was read, estimates labelled as such
    checks(...)             both, as Load results adds them to dq_check

Rows have dq_check's analysis columns (check_name, category, clinic, n_checked, n_fail, pass_rate, status) plus
measure_text, the numbers behind the status. One row per budget, or per subject (model, pipeline) for those
measured per subject. Status is PASS, FAIL, or REPORT when there is nothing to measure yet or no threshold.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from .paths import REPO_ROOT
from .telemetry import traced

BUDGETS = REPO_ROOT / "ops" / "budgets.yaml"
MEASURES = ("allowance_hours", "pipeline_cost_usd", "gpu_hours_per_resolved_task", "p95_duration_seconds",
            "freshness_seconds")
PERIODS = ("week", "month", "all", "now")
FIELDS = ("budget_name", "category", "measure", "period", "limit", "unit", "owner_name", "action_text")
COLUMNS = ["check_name", "category", "clinic", "n_checked", "n_fail", "pass_rate", "status", "measure_text",
           "severity_code"]
# T011 (FR-016): the severity a failing row is routed by (AGENTS.md "Alerts and severity"). A passed budget, or cost
# data failing its own checks, is a check below threshold: SEV3, the daily digest. Performance takes the runbook's
# level for the matching failure class: drift (duration_drift) SEV4, a late pipeline (source_late) SEV3. A REPORT or a
# PASS has no severity: it isn't an alert.
COST_SEVERITY = "SEV3"
RUNBOOK_CLASS = {"p95_duration_seconds": "duration_drift", "freshness_seconds": "source_late"}
SETTINGS_MAX_AGE_DAYS = 90


@traced
def load_budgets(path: Path = BUDGETS) -> list[dict]:
    """Every entry with every field (limit may be empty only for freshness); refused, naming the field, otherwise."""
    import yaml
    out = (yaml.safe_load(Path(path).read_text()) or {}).get("budgets") or []
    for b in out:
        missing = [f for f in FIELDS if f not in b or (b[f] in (None, "") and f != "limit")]
        if missing or b["category"] not in ("cost", "performance") or b["measure"] not in MEASURES \
                or b["period"] not in PERIODS or (b["limit"] is None and b["measure"] != "freshness_seconds"):
            raise SystemExit(f"{Path(path).name}: budget {b.get('budget_name')!r} needs {', '.join(missing) or 'a valid category, measure, period and limit'}")
    return out


def _row(name, category, n_checked, n_fail, status, text, severity=None):
    return {"check_name": name, "category": category, "clinic": "All", "n_checked": int(n_checked),
            "n_fail": int(n_fail), "pass_rate": (1 - n_fail / n_checked) if n_checked else float("nan"),
            "status": status, "measure_text": text, "severity_code": severity if status == "FAIL" else None}


def _severity(measure: str) -> str:
    cls = RUNBOOK_CLASS.get(measure)
    if cls is None:
        return COST_SEVERITY
    from .doctor import load_runbook
    rb = load_runbook().set_index("failure_class_code")
    return str(rb.loc[cls, "severity_code"])


def _fmt(value: float, unit: str) -> str:
    return f"{value:.2f}" if "USD" in unit else f"{value:.1f}"


def _week(now: pd.Timestamp) -> tuple[pd.Timestamp, float]:
    """This week's start (Monday 00:00 UTC) and the share of it gone (at least a day's, so a Monday doesn't explode)."""
    start = (now - pd.Timedelta(days=now.weekday())).normalize()
    return start, max((now - start) / pd.Timedelta(days=7), 1 / 7)


def _ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True, errors="coerce")


def _model_runs(agent_runs: pd.DataFrame) -> pd.DataFrame:
    calib = agent_runs.get("is_calibration", pd.Series(False, index=agent_runs.index)).fillna(False).astype(bool)
    calib |= agent_runs["model_name"].astype(str).str.startswith("calib:")
    return agent_runs[~calib]


def _ok(pipeline_runs: pd.DataFrame) -> pd.DataFrame:
    return pipeline_runs[pipeline_runs["run_status_code"].astype(str) == "ok"]


def _weekly(b, values: pd.Series, when: pd.Series, now) -> dict:
    if not len(values):   # no runs recorded at all: nothing to measure, not a pass
        return _row(f"{b['category']}:{b['budget_name']}", b["category"], 0, 0, "REPORT",
                    f"no runs recorded. Owner: {b['owner_name']}. Action: {b['action_text']}")
    start, gone = _week(now)
    used = float(values[(when >= start) & (when <= now)].fillna(0).sum())
    projected = used / gone
    status = "FAIL" if projected > b["limit"] else "PASS"
    text = (f"{_fmt(used, b['unit'])} of {b['limit']:g} {b['unit']} this week, {_fmt(projected, b['unit'])} projected. "
            f"Owner: {b['owner_name']}. Action: {b['action_text']}")
    return _row(f"{b['category']}:{b['budget_name']}", b["category"], 1, status == "FAIL", status, text,
                _severity(b["measure"]))


@traced
def budget_checks(budgets: list[dict], agent_runs: pd.DataFrame, pipeline_runs: pd.DataFrame,
                  config: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    rows = []
    agents = _model_runs(agent_runs)
    for b in budgets:
        name, cat, m = f"{b['category']}:{b['budget_name']}", b["category"], b["measure"]
        tail = f"Owner: {b['owner_name']}. Action: {b['action_text']}"
        if m == "allowance_hours":
            rows.append(_weekly(b, agents["allowance_hours"], _ts(agents["run_ts"]), now))
        elif m == "pipeline_cost_usd":
            rows.append(_weekly(b, pipeline_runs["cost_usd"], _ts(pipeline_runs["started_ts"]), now))
        elif m == "gpu_hours_per_resolved_task":
            priced = agents[agents["gpu_hours"].notna()]
            if not len(priced):
                rows.append(_row(name, cat, 0, 0, "REPORT", f"no priced runs yet. {tail}"))
            for model, g in priced.groupby("model_name"):
                resolved = int(g["is_resolved"].astype(bool).sum())
                per = g["gpu_hours"].sum() / resolved if resolved else math.inf
                status = "FAIL" if per > b["limit"] else "PASS"
                rows.append(_row(f"{name}:{model}", cat, 1, status == "FAIL", status,
                                 f"{per:.2f} {b['unit']} ({resolved} resolved of {len(g)}); limit {b['limit']:g}. {tail}",
                                 _severity(m)))
        elif m == "p95_duration_seconds":
            ok = _ok(pipeline_runs)
            ok = ok[_ts(ok["started_ts"]) >= now - pd.Timedelta(days=30)]
            for pipe, g in ok.groupby("pipeline_name"):
                p95 = float(g["duration_seconds"].quantile(0.95))
                status = "FAIL" if p95 > b["limit"] else "PASS"
                rows.append(_row(f"{name}:{pipe}", cat, 1, status == "FAIL", status,
                                 f"p95 {p95:.0f} s over {len(g)} ok runs; limit {b['limit']:g} s. {tail}", _severity(m)))
        elif m == "freshness_seconds":
            sla = dict(zip(config["pipeline_name"], config["sla_seconds"]))
            ok = _ok(pipeline_runs)
            for pipe, g in ok.groupby("pipeline_name"):
                end = _ts(g["ended_ts"]) if "ended_ts" in g else _ts(g["started_ts"])
                last = end.fillna(_ts(g["started_ts"])).max()
                age, limit = (now - last).total_seconds(), sla.get(pipe)
                if limit is None or pd.isna(limit):
                    rows.append(_row(f"{name}:{pipe}", cat, 0, 0, "REPORT", f"{age:.0f} s; no sla_seconds. {tail}"))
                    continue
                status = "FAIL" if age > float(limit) else "PASS"
                rows.append(_row(f"{name}:{pipe}", cat, 1, status == "FAIL", status,
                                 f"{age:.0f} s since its last ok run; SLA {float(limit):.0f} s. {tail}", _severity(m)))
    return pd.DataFrame(rows, columns=COLUMNS)


@traced
def cost_data_checks(agent_runs: pd.DataFrame, pipeline_runs: pd.DataFrame, settings: dict,
                     now: pd.Timestamp) -> pd.DataFrame:
    rows = []
    has = pipeline_runs["cost_usd"].notna()
    rows.append(_row("cost:completeness:pipeline_runs", "cost", len(pipeline_runs), int((~has).sum()), "REPORT",
                     f"{int(has.sum())} of {len(pipeline_runs)} job runs have a cost (billing lags, or isn't granted)"))
    agents = _model_runs(agent_runs)
    priced = agents["estimated_cost_usd"].notna()
    rows.append(_row("cost:completeness:agent_runs", "cost", len(agents), int((~priced).sum()), "REPORT",
                     f"{int(priced.sum())} of {len(agents)} agent task runs have an estimate"))
    c, d = pipeline_runs["cost_usd"], pipeline_runs["duration_seconds"]
    bad = (c < 0) | ((c == 0) & (d > 0))
    rows.append(_row("cost:plausibility", "cost", int(has.sum()), int(bad.sum()), "FAIL" if bad.any() else "PASS",
                     "no negative cost, and no zero cost on a run that took time", COST_SEVERITY))
    stale = [k for k, v in settings.items() if isinstance(v, dict) and "read_date" in v
             and (now - pd.Timestamp(v["read_date"], tz="UTC")).days > SETTINGS_MAX_AGE_DAYS]
    n = sum(1 for v in settings.values() if isinstance(v, dict) and "read_date" in v)
    rows.append(_row("cost:settings_current", "cost", n, len(stale), "FAIL" if stale else "PASS",
                     f"read within {SETTINGS_MAX_AGE_DAYS} days (ops/cost_settings.yaml)"
                     + (f"; stale: {', '.join(stale)}" if stale else ""), COST_SEVERITY))
    est = agent_runs[agent_runs["estimated_cost_usd"].notna()]
    unlabelled = ~est["price_basis_text"].astype(str).str.startswith("estimate:")
    calib = agent_runs["model_name"].astype(str).str.startswith("calib:")
    mislabelled = calib & ~agent_runs.get("is_calibration", pd.Series(False, index=agent_runs.index)).fillna(False).astype(bool)
    n_fail = int(unlabelled.sum() + mislabelled.sum())
    rows.append(_row("cost:estimates_labelled", "cost", len(est) + int(calib.sum()), n_fail,
                     "FAIL" if n_fail else "PASS", "every estimate says so; every calib: run is labelled calibration",
                     COST_SEVERITY))
    return pd.DataFrame(rows, columns=COLUMNS)


@traced
def with_provenance(df: pd.DataFrame) -> pd.DataFrame:
    """The rows with the files they're built from and those files' SHA-256 together, as every dq_check row has."""
    import hashlib
    files = ["ops/budgets.yaml", "ops/cost_settings.yaml"]
    h = hashlib.sha256()
    for f in files:
        h.update((REPO_ROOT / f).read_bytes())
    return df.reset_index(drop=True).assign(source_files=",".join(files), sha256=h.hexdigest())


@traced
def checks(budgets: list[dict], agent_runs: pd.DataFrame, pipeline_runs: pd.DataFrame, config: pd.DataFrame,
           settings: dict, now: pd.Timestamp) -> pd.DataFrame:
    return pd.concat([budget_checks(budgets, agent_runs, pipeline_runs, config, now),
                      cost_data_checks(agent_runs, pipeline_runs, settings, now)], ignore_index=True)
