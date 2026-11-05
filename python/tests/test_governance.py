"""Spec 036 US4 (#576): the data-quality report covers spend and speed. Every budget and performance target is
declared once (ops/budgets.yaml) and checked each period in dq_check's own columns, categories `cost` and
`performance`; the cost data gets data-quality checks of its own."""
import pandas as pd
import pytest
import yaml

from health_transformation_lab_nlp import governance as gv
from health_transformation_lab_nlp.paths import REPO_ROOT

NOW = pd.Timestamp("2026-11-05 12:00", tz="UTC")          # a Thursday: 3.5 of the week's 7 days gone
COLUMNS = ["check_name", "category", "clinic", "n_checked", "n_fail", "pass_rate", "status", "measure_text"]


def _budget(**kw):
    base = {"budget_name": "b", "category": "cost", "measure": "allowance_hours", "period": "week", "limit": 20,
            "unit": "allowance hours", "owner_name": "repo owner", "action_text": "pause the run"}
    return {**base, **kw}


def _agent(**kw):
    base = {"instance_id": "t1", "model_name": "gemma-4-e4b-it", "is_calibration": False, "is_resolved": True,
            "run_ts": NOW - pd.Timedelta(days=1), "allowance_hours": 1.0, "gpu_hours": 2.0,
            "estimated_cost_usd": 1.38, "price_basis_text": "estimate: 0.69 USD per T4 GPU-hour (s, read d)"}
    return {**base, **kw}


def _pipe(**kw):
    base = {"pipeline_name": "study_benchmark", "run_id": "1", "started_ts": NOW - pd.Timedelta(days=1),
            "run_status_code": "ok", "duration_seconds": 600.0, "cost_usd": 0.5}
    return {**base, **kw}


CONFIG = pd.DataFrame([{"pipeline_name": "study_benchmark", "sla_seconds": 604800}])
SETTINGS = {"kaggle_weekly_allowance_hours": {"value": 30, "source": "s", "read_date": "2026-11-04"},
            "t4_usd_per_gpu_hour": {"value": 0.69, "source": "s", "read_date": "2026-11-04"}}


# --- the register -------------------------------------------------------------------------------------------------

def test_the_register_declares_each_budget_with_its_limit_owner_and_action():
    budgets = gv.load_budgets()
    assert len(budgets) >= 4
    for b in budgets:
        assert b["category"] in ("cost", "performance") and b["owner_name"] and b["action_text"]
        assert b["measure"] in gv.MEASURES and b["period"] in gv.PERIODS


def test_a_budget_missing_a_field_is_refused_naming_it(tmp_path):
    p = tmp_path / "budgets.yaml"
    bad = _budget()
    del bad["owner_name"]
    p.write_text(yaml.safe_dump({"budgets": [bad]}))
    with pytest.raises(SystemExit, match="owner_name"):
        gv.load_budgets(p)


# --- budgets and targets ----------------------------------------------------------------------------------------

def test_a_week_projected_past_its_budget_fails_with_the_numbers():
    runs = pd.DataFrame([_agent(allowance_hours=6.0), _agent(allowance_hours=6.0)])     # 12 h by mid-week
    out = gv.budget_checks([_budget()], runs, pd.DataFrame([_pipe()]), CONFIG, NOW)
    row = out.iloc[0]
    assert row["check_name"] == "cost:b" and row["status"] == "FAIL"                    # 24 h projected > 20
    assert "12.0 of 20" in row["measure_text"] and "24.0 projected" in row["measure_text"]
    assert list(out.columns) == COLUMNS


def test_runs_before_this_week_and_calibration_runs_dont_count():
    runs = pd.DataFrame([_agent(allowance_hours=30.0, run_ts=NOW - pd.Timedelta(days=9)),
                         _agent(allowance_hours=30.0, is_calibration=True), _agent(allowance_hours=2.0)])
    row = gv.budget_checks([_budget()], runs, pd.DataFrame([_pipe()]), CONFIG, NOW).iloc[0]
    assert row["status"] == "PASS" and "2.0 of 20" in row["measure_text"]


def test_gpu_hours_per_resolved_task_is_checked_per_model():
    b = _budget(budget_name="per_task", measure="gpu_hours_per_resolved_task", period="all", limit=1.0,
                unit="GPU-hours per resolved task")
    runs = pd.DataFrame([_agent(), _agent(is_resolved=False), _agent(model_name="other", gpu_hours=0.5)])
    out = gv.budget_checks([b], runs, pd.DataFrame([_pipe()]), CONFIG, NOW).set_index("check_name")
    assert out.loc["cost:per_task:gemma-4-e4b-it", "status"] == "FAIL"                 # 4 h for 1 resolved
    assert out.loc["cost:per_task:other", "status"] == "PASS"


def test_nothing_to_measure_is_reported_not_passed():
    b = _budget(budget_name="per_task", measure="gpu_hours_per_resolved_task", period="all", limit=1.0)
    out = gv.budget_checks([b], pd.DataFrame([_agent(gpu_hours=None)]), pd.DataFrame([_pipe()]), CONFIG, NOW)
    assert out.iloc[0]["status"] == "REPORT"


def test_p95_duration_and_freshness_are_performance_checks_per_pipeline():
    pipes = pd.DataFrame([_pipe(run_id=str(i), duration_seconds=600.0 * (i + 1)) for i in range(20)])
    p95 = _budget(budget_name="p95", category="performance", measure="p95_duration_seconds", period="month",
                  limit=3600, unit="seconds")
    fresh = _budget(budget_name="fresh", category="performance", measure="freshness_seconds", period="now",
                    limit=None, unit="seconds since the last ok run (limit: the pipeline's sla_seconds)")
    out = gv.budget_checks([p95, fresh], pd.DataFrame([_agent()]), pipes, CONFIG, NOW).set_index("check_name")
    assert out.loc["performance:p95:study_benchmark", "status"] == "FAIL"              # p95 of 600..12000 s
    assert out.loc["performance:fresh:study_benchmark", "status"] == "PASS"            # a day old, SLA a week
    stale = pipes.assign(started_ts=NOW - pd.Timedelta(days=10))
    out = gv.budget_checks([fresh], pd.DataFrame([_agent()]), stale, CONFIG, NOW)
    assert out.iloc[0]["status"] == "FAIL"


def test_pipeline_cost_per_week_uses_billing_costs():
    b = _budget(budget_name="dbx", measure="pipeline_cost_usd", limit=1.0, unit="USD at list price")
    pipes = pd.DataFrame([_pipe(cost_usd=0.4), _pipe(run_id="2", cost_usd=0.4)])
    row = gv.budget_checks([b], pd.DataFrame([_agent()]), pipes, CONFIG, NOW).iloc[0]
    assert row["status"] == "FAIL" and "0.80 of 1" in row["measure_text"]               # 1.60 projected


# --- the cost data itself ---------------------------------------------------------------------------------------

def test_cost_completeness_is_reported_with_its_share():
    pipes = pd.DataFrame([_pipe(), _pipe(run_id="2", cost_usd=None)])
    out = gv.cost_data_checks(pd.DataFrame([_agent()]), pipes, SETTINGS, NOW).set_index("check_name")
    row = out.loc["cost:completeness:pipeline_runs"]
    assert row["status"] == "REPORT" and row["n_checked"] == 2 and row["n_fail"] == 1   # billing lags: a share


def test_a_negative_or_zero_cost_on_a_run_that_used_compute_fails():
    pipes = pd.DataFrame([_pipe(cost_usd=-1.0), _pipe(run_id="2", cost_usd=0.0), _pipe(run_id="3")])
    row = gv.cost_data_checks(pd.DataFrame([_agent()]), pipes, SETTINGS, NOW).set_index("check_name").loc[
        "cost:plausibility"]
    assert row["status"] == "FAIL" and row["n_fail"] == 2


def test_a_setting_read_over_90_days_ago_fails():
    old = {**SETTINGS, "t4_usd_per_gpu_hour": {"value": 0.69, "source": "s", "read_date": "2026-06-01"}}
    row = gv.cost_data_checks(pd.DataFrame([_agent()]), pd.DataFrame([_pipe()]), old, NOW).set_index(
        "check_name").loc["cost:settings_current"]
    assert row["status"] == "FAIL" and row["n_fail"] == 1


def test_an_unlabelled_estimate_fails():
    runs = pd.DataFrame([_agent(), _agent(price_basis_text="0.69 per hour")])
    row = gv.cost_data_checks(runs, pd.DataFrame([_pipe()]), SETTINGS, NOW).set_index("check_name").loc[
        "cost:estimates_labelled"]
    assert row["status"] == "FAIL" and row["n_fail"] == 1


def test_load_results_adds_the_governance_rows_to_dq_check():
    nb = (REPO_ROOT / "databricks" / "notebooks" / "10_load_results.py").read_text()
    assert "governance.checks(" in nb and "dq_check" in nb


def test_a_week_with_no_runs_recorded_is_reported_not_passed():
    empty = pd.DataFrame(columns=list(_pipe()))
    row = gv.budget_checks([_budget(budget_name="dbx", measure="pipeline_cost_usd", limit=1.0, unit="USD")],
                           pd.DataFrame([_agent()]), empty, CONFIG, NOW).iloc[0]
    assert row["status"] == "REPORT"


def test_governance_rows_become_dq_check_rows_with_provenance():
    from health_transformation_lab_nlp import gold_names, grader_tables
    from health_transformation_lab_nlp.paths import DATASETS_DIR
    dq = grader_tables.dq_tables(DATASETS_DIR)["dq_check"]
    gov = gv.with_provenance(gv.checks([_budget()], pd.DataFrame([_agent()]), pd.DataFrame([_pipe()]), CONFIG,
                                       SETTINGS, NOW))
    both = pd.concat([dq, gov[dq.columns]], ignore_index=True)
    gold = gold_names.to_gold(both.assign(git_commit="abc", loaded_at=NOW), "dq_check")
    assert set(gold["check_category_code"]) >= {"cost", "conformance"} and gold["measure_text"].notna().any()
    assert gov["source_files"].iloc[0] == "ops/budgets.yaml,ops/cost_settings.yaml"
