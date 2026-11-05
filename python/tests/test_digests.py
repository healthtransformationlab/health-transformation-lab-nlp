"""Spec 027 US8 T023 (#359): the daily and weekly digests. Every SEV3 and SEV4 alert this repo raises, from the
budget and target checks (spec 036), the doctor's open recommendations and pipeline-doctor's forecaster, goes
through pipeline-doctor's digest: one message per owner per period, each problem once, repeats flagged. A
Databricks SQL alert per period emails the message to the owner (no new credential)."""
import pandas as pd
import pytest

from health_transformation_lab_nlp import digests as dg
from health_transformation_lab_nlp.paths import REPO_ROOT

TODAY = pd.Timestamp("2026-11-05", tz="UTC")          # a Thursday
MONDAY = pd.Timestamp("2026-11-09", tz="UTC")


def _check(name="cost:kaggle_gpu_allowance", category="cost", status="FAIL", severity="SEV3",
           text="24.0 of 20 allowance hours this week, 24.0 projected. Owner: repo owner. Action: lower the cap"):
    return {"check_name": name, "check_category_code": category, "check_status_code": status,
            "severity_code": severity, "measure_text": text, "clinic_code": "All"}


def _decision(severity="SEV4", decided=None, cls="duration_drift", pipeline="study_benchmark", run_id="9"):
    return {"pipeline_name": pipeline, "run_id": run_id, "run_started_ts": TODAY - pd.Timedelta(days=1),
            "failure_class_code": cls, "recommended_action_code": "investigate", "severity_code": severity,
            "owner_name": "repo owner", "impact_text": "gold_perio_bench.fact_prediction", "decided_action_code": decided}


# --- alerts from this repo's tables ---------------------------------------------------------------------------------

def test_failing_budget_checks_become_alerts_with_their_owner_and_numbers():
    checks = pd.DataFrame([_check(), _check(name="cost:ok", status="PASS", severity=None),
                           _check(name="conformance:x", category="conformance", severity=None)])
    a = dg.governance_alerts(checks, dg.load_budgets_owners())
    assert len(a) == 1 and list(a.columns) == dg.ALERT_COLUMNS
    row = a.iloc[0]
    assert (row.subject_name, row.subject_kind_code, row.severity_code) == ("cost:kaggle_gpu_allowance", "budget", "SEV3")
    assert row.owner_name == "repo owner" and "24.0 projected" in row.evidence_text
    assert row.predicted_failure_class_code == "cost_anomaly" and row.recommended_action_code == "fix_setting"


def test_performance_checks_name_their_pipeline_and_class():
    checks = pd.DataFrame([_check(name="performance:job_p95_duration:study_benchmark", category="performance",
                                  severity="SEV4"),
                           _check(name="performance:pipeline_freshness:study_benchmark", category="performance")])
    a = dg.governance_alerts(checks, dg.load_budgets_owners()).set_index("subject_name")
    assert a.loc["performance:job_p95_duration:study_benchmark", "predicted_failure_class_code"] == "duration_drift"
    assert a.loc["performance:pipeline_freshness:study_benchmark", "predicted_failure_class_code"] == "source_late"
    assert set(a["pipeline_name"]) == {"study_benchmark"}


def test_open_sev3_and_sev4_recommendations_become_alerts_and_decided_or_paged_ones_dont():
    dec = pd.DataFrame([_decision(), _decision(run_id="8", decided="investigate"),
                        _decision(run_id="7", severity="SEV2"), _decision(run_id="6", severity="SEV3", cls="quality_fail")])
    a = dg.decision_alerts(dec)
    assert sorted(a["severity_code"]) == ["SEV3", "SEV4"]                 # SEV2 paged already; decided: closed
    assert set(a["subject_kind_code"]) == {"pipeline_run"} and list(a.columns) == dg.ALERT_COLUMNS


def test_the_forecaster_reads_the_real_register_and_inventory():
    a = dg.forecast_alerts(TODAY)
    assert list(a.columns) == dg.ALERT_COLUMNS and len(a)
    kinds = set(a["subject_kind_code"])          # credential, pipeline, or the inventory's kind (model, runtime...)
    inventory = set(pd.read_csv(REPO_ROOT / "ops" / "dependency_inventory.csv")["dependency_kind_code"])
    assert "credential" in kinds and kinds <= {"credential", "pipeline"} | inventory
    assert a["severity_code"].isin(["SEV1", "SEV2", "SEV3", "SEV4"]).all()


# --- the digests --------------------------------------------------------------------------------------------------

def _alerts():
    return pd.concat([dg.governance_alerts(pd.DataFrame([_check(), _check(name="performance:job_p95_duration:x",
                                                                           category="performance", severity="SEV4")]),
                                           dg.load_budgets_owners()),
                      dg.decision_alerts(pd.DataFrame([_decision(severity="SEV3")]))], ignore_index=True)


def test_the_daily_digest_holds_sev3_and_the_weekly_sev4_one_message_per_owner():
    items, messages = dg.build(_alerts(), "daily", TODAY, previous=None)
    assert set(items["severity_code"]) == {"SEV3"} and len(messages) == 1
    m = messages.iloc[0]
    assert m.owner_name == "repo owner" and m.item_count == 2 and "daily digest for repo owner" in m.message_text
    items, messages = dg.build(_alerts(), "weekly", TODAY, previous=None)
    assert set(items["severity_code"]) == {"SEV4"} and messages.iloc[0].item_count == 1


def test_an_item_in_the_last_digest_too_is_a_repeat():
    first, _ = dg.build(_alerts(), "daily", TODAY - pd.Timedelta(days=1), previous=None)
    items, messages = dg.build(_alerts(), "daily", TODAY, previous=first)
    assert items["is_repeat"].all() and "(repeat)" in messages.iloc[0].message_text


def test_no_alerts_means_no_message():
    items, messages = dg.build(pd.DataFrame(columns=dg.ALERT_COLUMNS), "daily", TODAY, previous=None)
    assert items.empty and messages.empty


def test_periods_due_daily_and_the_weekly_on_mondays():
    assert dg.periods_due(TODAY) == ["daily"] and dg.periods_due(MONDAY) == ["daily", "weekly"]


def test_rows_are_typed_with_the_batch_key():
    items, messages = dg.build(_alerts(), "daily", TODAY, previous=None)
    r = dg.rows(messages, "fact_digest_message", digest_run_id="42", loaded_ts=TODAY, git_commit_sha="abc")
    assert list(r.columns) == [n for n, _ in dg.TABLES["fact_digest_message"]]
    assert r["digest_key"].iloc[0] == "2026-11-05/daily" and r["digest_run_id"].iloc[0] == "42"


# --- the alerts that email them -------------------------------------------------------------------------------------

def test_one_alert_per_period_reads_that_periods_message_and_emails_the_owner():
    specs = dg.alert_specs("health_transformation_lab", "gold_perio_bench", "owner@example.com", "wh1")
    assert [s["display_name"] for s in specs] == ["Pipeline digest (daily)", "Pipeline digest (weekly)"]
    daily = specs[0]
    assert "gold_perio_bench.fact_digest_message" in daily["query_text"] and "period_code = 'daily'" in daily["query_text"]
    assert "current_date()" in daily["query_text"] and daily["warehouse_id"] == "wh1"
    assert daily["subscriptions"] == ["owner@example.com"] and "{{QUERY_RESULT_TABLE}}" in daily["custom_description"]
    assert specs[1]["schedule"].endswith("MON")   # the weekly alert fires on Mondays


def test_ensure_alerts_creates_the_missing_and_updates_the_rest():
    class Api:
        def __init__(self):
            self.made, self.updated = [], []

        def list_alerts(self):
            return [type("A", (), {"display_name": "Pipeline digest (daily)", "id": "a1"})()]

        def create_alert(self, alert):
            self.made.append(alert.display_name)

        def update_alert(self, id, alert, update_mask):
            self.updated.append((id, alert.display_name))

    api = Api()
    dg.ensure_alerts(api, dg.alert_specs("c", "s", "o@example.com", "wh"))
    assert api.updated == [("a1", "Pipeline digest (daily)")] and api.made == ["Pipeline digest (weekly)"]


def test_no_email_set_means_no_alerts_and_a_warning(capsys):
    assert dg.alert_specs("c", "s", "", "wh") == []
    assert "digest_email" in capsys.readouterr().out


def test_the_package_is_pinned():
    text = (REPO_ROOT / "python" / "pyproject.toml").read_text()
    assert "pipeline-doctor @ git+https://github.com/healthtransformationlab/pipeline-doctor@" in text


def test_the_alert_uses_the_sdks_own_types():   # the fake client can't check them; the live API would
    from databricks.sdk.service import sql
    src = (REPO_ROOT / "python" / "health_transformation_lab_nlp" / "digests.py").read_text()
    assert "empty_result_state=sql.AlertEvaluationState.OK" in src and hasattr(sql.AlertEvaluationState, "OK")


def test_the_digest_tables_are_declared_as_written():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gold_model", REPO_ROOT / "diagrams" / "_build" / "gold_model.py")
    gm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gm)
    for name, cols in dg.TABLES.items():
        assert [(c.name, c.type) for c in gm.TABLES[name].columns] == cols, name


def test_a_sev2_forecast_pages_now_instead_of_waiting():
    a = pd.DataFrame([{"subject_name": "dental-omop-ci OAuth secret", "subject_kind_code": "credential",
                       "pipeline_name": None, "predicted_failure_class_code": "credential_expiry",
                       "predicted_date": "2026-11-09", "days_until_count": 4, "severity_code": "SEV2",
                       "recommended_action_code": "fix_setting", "owner_name": "repo owner",
                       "evidence_text": "expires 2026-11-09"}], columns=dg.ALERT_COLUMNS)
    text = dg.page_now(a)
    assert "dental-omop-ci OAuth secret" in text and "credential_expiry" in text
    assert dg.page_now(_alerts()) == ""                         # SEV3/SEV4 only: nothing to page
    items, _ = dg.build(a, "daily", TODAY, previous=None)
    assert items.empty                                          # never in a digest: paged instead
