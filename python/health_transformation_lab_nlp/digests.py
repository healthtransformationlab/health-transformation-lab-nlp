"""The daily and weekly digests (spec 027 US8 T023, #359; spec 036 FR-016).

Every SEV3 and SEV4 alert this repo raises goes through pipeline-doctor's `digest` (installed from its repo, pinned
in pyproject.toml): one message per owner per period, grouped by severity then subject, each problem once with a
count, a repeat flagged. SEV1 and SEV2 never wait for a digest: the doctor pages them (13_pipeline_doctor.py).

    governance_alerts(dq_check, owners)  failing budget and target checks (spec 036), from gold dq_check
    decision_alerts(decisions)           the doctor's SEV3/SEV4 recommendations no one has decided yet
    forecast_alerts(today, history)      pipeline-doctor's forecaster on ops/secrets_register.yaml,
                                         ops/dependency_inventory.csv and the run history
    build(alerts, period, date, prev)    (items, messages) for one period; an item in the last digest too is a repeat
    periods_due(date)                    daily every day, weekly on Mondays
    rows(df, table, ...)                 typed rows with the batch key, for delta.replace_keys by digest_key
    alert_specs(...), ensure_alerts(...) one Databricks SQL alert per period that emails that period's message to the
                                         owner: Databricks sends it, so no mail credential (owner's choice, Nov 2026)
"""

from __future__ import annotations

import pandas as pd
from pipeline_doctor import digest as pd_digest
from pipeline_doctor import forecast as pd_forecast

from .paths import REPO_ROOT
from .telemetry import traced

ALERT_COLUMNS = list(pd_digest.ALERT_COLUMNS)
# a failing budget or target check as an alert: its class, and the runbook action to take first
CHECK_CLASS = {"cost": "cost_anomaly", "job_p95_duration": "duration_drift", "pipeline_freshness": "source_late"}
DEFAULT_OWNER = "repo owner"
ITEM_KEYS = ["owner_name", "subject_name", "predicted_failure_class_code"]

TABLES = {
    "fact_digest_item": [
        ("digest_key", "string"), ("digest_date", "date"), ("period_code", "string"), ("owner_name", "string"),
        ("subject_name", "string"), ("subject_kind_code", "string"), ("pipeline_names_text", "string"),
        ("predicted_failure_class_code", "string"), ("predicted_date", "date"), ("days_until_count", "bigint"),
        ("severity_code", "string"), ("recommended_action_code", "string"), ("evidence_text", "string"),
        ("alert_count", "bigint"), ("is_repeat", "boolean"), ("is_level_review", "boolean"),
        ("digest_run_id", "string"), ("loaded_ts", "timestamp"), ("git_commit_sha", "string")],
    "fact_digest_message": [
        ("digest_key", "string"), ("digest_date", "date"), ("period_code", "string"), ("owner_name", "string"),
        ("item_count", "bigint"), ("message_text", "string"),
        ("digest_run_id", "string"), ("loaded_ts", "timestamp"), ("git_commit_sha", "string")],
}


@traced
def load_budgets_owners() -> dict[str, str]:
    """{budget_name: owner_name} from ops/budgets.yaml."""
    from .governance import load_budgets
    return {b["budget_name"]: b["owner_name"] for b in load_budgets()}


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=ALERT_COLUMNS)


@traced
def governance_alerts(dq_check: pd.DataFrame, owners: dict[str, str]) -> pd.DataFrame:
    """One alert per failing cost or performance row of dq_check (gold names), with its severity (spec 036 T011)."""
    if dq_check is None or not len(dq_check):
        return _frame([])
    f = dq_check[dq_check["check_category_code"].isin(["cost", "performance"])
                 & (dq_check["check_status_code"] == "FAIL") & dq_check["severity_code"].notna()]
    rows = []
    for r in f.itertuples(index=False):
        parts = str(r.check_name).split(":")
        budget = parts[1] if len(parts) > 1 else ""
        rows.append({"subject_name": r.check_name, "subject_kind_code": "budget",
                     "pipeline_name": parts[2] if r.check_category_code == "performance" and len(parts) > 2 else None,
                     "predicted_failure_class_code": CHECK_CLASS.get(budget, CHECK_CLASS["cost"]),
                     "predicted_date": None, "days_until_count": None, "severity_code": r.severity_code,
                     "recommended_action_code": "fix_setting", "owner_name": owners.get(budget, DEFAULT_OWNER),
                     "evidence_text": r.measure_text})
    return _frame(rows)


@traced
def decision_alerts(decisions: pd.DataFrame) -> pd.DataFrame:
    """The doctor's SEV3/SEV4 recommendations still awaiting a decision (gold fact_remediation_decision). SEV1/SEV2
    were paged when first seen; a decided one is closed."""
    if decisions is None or not len(decisions):
        return _frame([])
    f = decisions[decisions["severity_code"].isin(["SEV3", "SEV4"]) & decisions["decided_action_code"].isna()]
    rows = [{"subject_name": f"{r.pipeline_name} run {r.run_id}", "subject_kind_code": "pipeline_run",
             "pipeline_name": r.pipeline_name, "predicted_failure_class_code": r.failure_class_code,
             "predicted_date": str(pd.Timestamp(r.run_started_ts).date()) if pd.notna(r.run_started_ts) else None,
             "days_until_count": None, "severity_code": r.severity_code,
             "recommended_action_code": r.recommended_action_code, "owner_name": r.owner_name or DEFAULT_OWNER,
             "evidence_text": f"recommended {r.recommended_action_code}; affects {r.impact_text or 'no downstream on record'}"}
            for r in f.itertuples(index=False)]
    return _frame(rows)


@traced
def forecast_alerts(today, history: pd.DataFrame | None = None) -> pd.DataFrame:
    """pipeline-doctor's forecaster on this repo's register, inventory and run history: expiries, deprecations,
    trends. Rows in every severity; the digest takes SEV3 and SEV4 (SEV1/SEV2 forecasts: see build)."""
    from .doctor import load_config
    register = pd_forecast.load_credential_register(REPO_ROOT / "ops" / "secrets_register.yaml")
    inventory = pd_forecast.load_dependency_inventory(REPO_ROOT / "ops" / "dependency_inventory.csv")
    out = pd_forecast.forecast_all(load_config(), today, register=register, inventory=inventory, history=history)
    return out.reindex(columns=ALERT_COLUMNS)


@traced
def periods_due(date) -> list[str]:
    return ["daily", "weekly"] if pd.Timestamp(date).weekday() == 0 else ["daily"]


@traced
def build(alerts: pd.DataFrame, period: str, date, previous: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(items, messages) for one period's digest on `date`. An item whose (owner, subject, class) was in the
    previous digest of this period is a repeat; a repeating SEV2 is flagged for level review."""
    day = pd.Timestamp(date).date()
    key = f"{day.isoformat()}/{period}"
    items = pd_digest.digest(alerts, period)
    if previous is not None and len(previous) and len(items):
        seen = set(map(tuple, previous[ITEM_KEYS].astype(str).values))
        items["is_repeat"] = [tuple(map(str, k)) in seen for k in items[ITEM_KEYS].values]
        items["is_level_review"] = items["is_repeat"] & (items["severity_code"] == "SEV2")
    items = items.assign(digest_key=key, digest_date=day, period_code=period)
    texts = pd_digest.render(items, period) if len(items) else {}
    messages = pd.DataFrame([{"digest_key": key, "digest_date": day, "period_code": period, "owner_name": owner,
                              "item_count": int((items["owner_name"].astype(str) == owner).sum()),
                              "message_text": text} for owner, text in texts.items()],
                            columns=["digest_key", "digest_date", "period_code", "owner_name", "item_count",
                                     "message_text"])
    return items, messages


@traced
def rows(df: pd.DataFrame, table: str, digest_run_id: str, loaded_ts, git_commit_sha: str) -> pd.DataFrame:
    """df under the table's declared columns, in order, with the batch key; missing values None."""
    df = df.assign(digest_run_id=digest_run_id, loaded_ts=pd.Timestamp(loaded_ts), git_commit_sha=git_commit_sha or None)
    out = {}
    for name, _ in TABLES[table]:
        values = df[name].tolist() if name in df.columns else [None] * len(df)
        out[name] = pd.Series([None if (v is None or (not isinstance(v, (list, dict)) and pd.isna(v))) else v
                               for v in values], dtype=object)
    return pd.DataFrame(out, columns=[n for n, _ in TABLES[table]])


@traced
def ddl(table: str) -> str:
    return ", ".join(f"{n} {t}" for n, t in TABLES[table])


# --- the alerts that email the digests ------------------------------------------------------------------------------

ALERT_SCHEDULES = {"daily": "0 47 7 * * ?", "weekly": "0 47 7 ? * MON"}   # after the digest job (07:32 UTC)


@traced
def alert_specs(catalog: str, schema: str, email: str, warehouse_id: str) -> list[dict]:
    """One Databricks SQL alert per period: it reads today's message for that period and, when there is one,
    emails it to the owner. No email set: no alerts, and a warning (the digests are still built)."""
    if not (email or "").strip():
        print("warning: digest_email is empty, so no alert emails the digests (set the ALERT_EMAIL variable)")
        return []
    out = []
    for period, cron in ALERT_SCHEDULES.items():
        out.append({
            "display_name": f"Pipeline digest ({period})",
            "query_text": (f"select owner_name, item_count, message_text\nfrom {catalog}.{schema}.fact_digest_message\n"
                           f"where period_code = '{period}' and digest_date = current_date()"),
            "warehouse_id": warehouse_id, "schedule": cron, "subscriptions": [email.strip()],
            "custom_summary": f"Pipeline {period} digest",
            "custom_description": (f"The {period} digest (AGENTS.md 'Alerts and severity'): each open problem once, "
                                   "with its action.\n\n{{QUERY_RESULT_TABLE}}")})
    return out


@traced
def ensure_alerts(api, specs: list[dict]) -> None:
    """Create each alert, or update it in place when one of that name exists (idempotent: a rerun changes
    nothing). `api` is WorkspaceClient().alerts_v2."""
    from databricks.sdk.service import sql
    existing = {a.display_name: a.id for a in api.list_alerts()}
    for s in specs:
        alert = sql.AlertV2(
            display_name=s["display_name"], query_text=s["query_text"], warehouse_id=s["warehouse_id"],
            custom_summary=s["custom_summary"], custom_description=s["custom_description"],
            schedule=sql.CronSchedule(quartz_cron_schedule=s["schedule"], timezone_id="UTC"),
            evaluation=sql.AlertV2Evaluation(
                source=sql.AlertV2OperandColumn(name="item_count", aggregation=sql.Aggregation.SUM),
                comparison_operator=sql.ComparisonOperator.GREATER_THAN,
                threshold=sql.AlertV2Operand(value=sql.AlertV2OperandValue(double_value=0)),
                empty_result_state=sql.AlertEvaluationState.OK,
                notification=sql.AlertV2Notification(
                    notify_on_ok=False,
                    subscriptions=[sql.AlertV2Subscription(user_email=e) for e in s["subscriptions"]])))
        if s["display_name"] in existing:
            api.update_alert(id=existing[s["display_name"]], alert=alert,
                             update_mask="query_text,warehouse_id,schedule,evaluation,custom_summary,custom_description")
        else:
            api.create_alert(alert=alert)


@traced
def page_now(alerts: pd.DataFrame) -> str:
    """The SEV1/SEV2 alerts that can't wait for a digest (a credential expiring within 7 days, a forecast date
    already passed), rendered; empty when there are none. The job fails with this text, so its failure email
    pages the owner, as the doctor does for a new SEV1/SEV2 run."""
    now = pd_digest.immediate(alerts)
    return "\n\n".join(pd_digest.render(now, "now").values()) if len(now) else ""
