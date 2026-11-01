"""The pipeline doctor (spec 027): signals, rules-first classification, allow-listed recommendations,
graduation to automatic, and the eval on the repo's own incidents. Pure pandas; no Spark, no LLM."""

import ast

import pandas as pd
import pytest

from health_transformation_lab_nlp import doctor
from health_transformation_lab_nlp.paths import REPO_ROOT

T0 = pd.Timestamp("2026-10-28 06:00:00", tz="UTC")


def _run(pipeline="medgemma_reader", run_id="r9", status="failed", rows=240, sha="abc", failed=0, error_type=None,
         error_text=None, started=T0, seconds=600, step="read_notes"):
    return {"pipeline_name": pipeline, "step_name": step, "run_id": run_id, "started_ts": started,
            "ended_ts": started + pd.Timedelta(seconds=seconds), "run_status_code": status,
            "row_in_count": rows, "row_out_count": rows, "schema_sha256": sha, "check_passed_count": 12 - failed,
            "check_failed_count": failed, "error_type_name": error_type, "error_text": error_text,
            "git_commit_sha": "f6fd49e", "data_label_code": "synthetic"}


@pytest.fixture
def history():
    """Five ok runs, one a day, 240 rows, same schema, ten minutes each."""
    rows = [_run(run_id=f"r{i}", status="ok", started=T0 - pd.Timedelta(days=6 - i)) for i in range(1, 6)]
    return pd.DataFrame(rows)


@pytest.fixture
def lineage():
    return pd.DataFrame([
        {"upstream_name": "landing_perio_bench.review_notes", "downstream_name": "gold_perio_bench.fact_prediction",
         "edge_kind_code": "table", "pipeline_name": "medgemma_reader"},
        {"upstream_name": "gold_perio_bench.fact_prediction", "downstream_name": "gold_perio_bench.judge_metric",
         "edge_kind_code": "table", "pipeline_name": "judge_scorecard"},
        {"upstream_name": "gold_perio_bench.fact_prediction", "downstream_name": "scorecard dashboard",
         "edge_kind_code": "consumer", "pipeline_name": "judge_scorecard"},
        {"upstream_name": "gold_perio_bench.judge_metric", "downstream_name": "lab grader dashboard",
         "edge_kind_code": "consumer", "pipeline_name": "judge_scorecard"},
    ])


@pytest.fixture
def config():
    return doctor.load_config()


@pytest.fixture
def runbook():
    return doctor.load_runbook()


# --- US1: signals and classification -------------------------------------------------------------

def test_signals_compare_a_run_with_the_pipelines_last_ok_runs(history, config):
    run = _run(rows=120, sha="zzz", seconds=1800, failed=2)
    s = doctor.signals(run, history, config, now=T0 + pd.Timedelta(hours=2))
    assert s["freshness_seconds"] == pytest.approx(26 * 3600 - 600)      # last ok run ended T0 - 1 day + 10 min
    assert s["volume_ratio"] == pytest.approx(0.5)
    assert s["is_schema_changed"] is True
    assert s["quality_ratio"] == pytest.approx(10 / 12)
    assert s["duration_ratio"] == pytest.approx(3.0)


def test_signals_without_history_are_null_not_errors(config):
    s = doctor.signals(_run(), pd.DataFrame(columns=doctor.RUN_COLUMNS), config)
    assert pd.isna(s["volume_ratio"]) and pd.isna(s["duration_ratio"]) and s["is_schema_changed"] is None


@pytest.mark.parametrize("run, expected", [
    (_run(error_type="ResourceExhausted", error_text="No GPU available for serverless compute"), "platform"),
    (_run(error_type="Py4JException", error_text="Error while obtaining a new communication channel"), "platform"),
    (_run(error_type="OSError", error_text="[Errno 29] Illegal seek"), "platform"),
    (_run(error_type="MissingSetting", error_text="APPLICATIONINSIGHTS_CONNECTION_STRING is not set"), "config"),
    (_run(rows=10), "volume_anomaly"),
    (_run(sha="new-columns"), "schema_drift"),
    (_run(failed=3), "quality_fail"),
    (_run(error_type="RuntimeError", error_text="something nobody has seen before"), "unknown"),
    # configuration-management failures: what pages people in practice
    (_run(error_type="AuthenticationError", error_text="401 Unauthorized: token expired"), "credential_expiry"),
    (_run(error_type="RuntimeError", error_text="Dependabot: CVE-2026-1234 critical severity in requests"), "vulnerability"),
    (_run(error_type="NotFound", error_text="model medgemma-4b-it v1 is deprecated; endpoint not found"), "deprecation"),
    (_run(error_type="RuntimeError", error_text="judge_endpoint differs between dev and uat"), "config_drift"),
])
def test_classify_rules_cover_the_incidents_this_repo_has_had(run, expected, history, config):
    out = doctor.classify(run, history, config)
    assert out["failure_class_code"] == expected
    assert set(out["signals"]) >= {"freshness_seconds", "volume_ratio", "is_schema_changed", "quality_ratio",
                                   "duration_ratio"}


def test_configuration_management_classes_win_over_the_rest(history, config):
    """An expired token on a run that also wrote no rows is a credential problem, not a volume anomaly."""
    run = _run(rows=0, error_type="AuthenticationError", error_text="403 access denied: token expired")
    assert doctor.classify(run, history, config)["failure_class_code"] == "credential_expiry"


def test_a_run_that_never_started_is_source_late(history, config):
    late = _run(status=None, started=pd.NaT, seconds=0)
    out = doctor.classify(late, history, config, now=T0 + pd.Timedelta(days=3))
    assert out["failure_class_code"] == "source_late"


def test_config_covers_every_job_in_the_bundle(config):
    import yaml
    jobs = yaml.safe_load((REPO_ROOT / "databricks" / "resources" / "jobs.yml").read_text())["resources"]["jobs"]
    assert set(jobs) <= set(config["pipeline_name"]), set(jobs) - set(config["pipeline_name"])
    assert {"owner_name", "sla_seconds", "retry_max_count", "runbook_name", "data_label_code"} <= set(config.columns)


# --- US2: recommendations from the allow-list ------------------------------------------------------

def test_recommend_takes_the_first_allowed_action_with_impact_severity_and_owner(history, config, runbook, lineage):
    run = _run(error_type="ResourceExhausted", error_text="No GPU available")
    rec = doctor.recommend(run, history, config, runbook, lineage)
    entry = runbook[runbook["failure_class_code"] == "platform"].iloc[0]
    assert rec["recommended_action_code"] == entry["allowed_action_codes"][0]
    assert rec["recommended_action_code"] in entry["allowed_action_codes"]
    assert rec["severity_code"] == entry["severity_code"]
    assert rec["owner_name"] == config.set_index("pipeline_name").loc["medgemma_reader", "owner_name"]
    assert "gold_perio_bench.fact_prediction" in rec["downstream_names"]
    assert "scorecard dashboard" in rec["downstream_names"]          # one hop past the table
    assert "lab grader dashboard" not in rec["downstream_names"]     # two hops away
    assert rec["is_reversible"] == bool(entry["is_reversible"])


def test_recommend_moves_past_retry_when_retries_are_exhausted(history, config, runbook, lineage):
    run = _run(error_type="ResourceExhausted", error_text="No GPU available")
    rec = doctor.recommend(run, history, config, runbook, lineage, attempts_so_far=6)
    entry = runbook[runbook["failure_class_code"] == "platform"].iloc[0]
    assert rec["recommended_action_code"] == entry["allowed_action_codes"][1]
    assert rec["recommended_action_code"] != "retry"


def test_recommend_never_returns_an_action_off_the_list(history, config, runbook, lineage):
    for cls in runbook["failure_class_code"]:
        run = _run()
        rec = doctor.recommend(run, history, config, runbook, lineage, failure_class_code=cls)
        allowed = runbook.set_index("failure_class_code").loc[cls, "allowed_action_codes"]
        assert rec["recommended_action_code"] in allowed


def test_notification_names_pipeline_class_action_and_impact_and_carries_no_row_data(history, config, runbook,
                                                                                    lineage):
    run = _run(error_type="OSError", error_text="[Errno 29] Illegal seek")
    rec = doctor.recommend(run, history, config, runbook, lineage)
    text = rec["notification_text"]
    for piece in ("medgemma_reader", "platform", rec["recommended_action_code"], rec["severity_code"],
                  "fact_prediction"):
        assert piece in text
    assert "row_out_count" not in text and "person_id" not in text and "note" not in text.lower()


# --- US3: graduation ------------------------------------------------------------------------------

def _decisions(cls, matches):
    return pd.DataFrame([{"pipeline_name": "medgemma_reader", "run_id": f"r{i}", "failure_class_code": cls,
                          "recommended_action_code": "retry", "decided_action_code": "retry" if m else "rerun",
                          "decided_by_name": "owner", "decided_ts": T0 + pd.Timedelta(hours=i), "is_match": m,
                          "run_mode_code": "recommend_only"} for i, m in enumerate(matches)])


def test_a_reversible_class_graduates_after_n_matches(runbook):
    g = doctor.graduation(_decisions("platform", [True] * 5), runbook, n=5)
    assert g.set_index("failure_class_code").loc["platform", "run_mode_code"] == "automatic"


def test_two_misses_in_a_row_send_a_class_back_to_recommend_only(runbook):
    g = doctor.graduation(_decisions("platform", [True] * 5 + [False, False]), runbook, n=5)
    assert g.set_index("failure_class_code").loc["platform", "run_mode_code"] == "recommend_only"


def test_fewer_than_n_decisions_stay_recommend_only(runbook):
    g = doctor.graduation(_decisions("platform", [True] * 4), runbook, n=5)
    assert g.set_index("failure_class_code").loc["platform", "run_mode_code"] == "recommend_only"


def test_a_non_reversible_class_never_graduates(runbook):
    assert not runbook.set_index("failure_class_code").loc["schema_drift", "is_reversible"]
    g = doctor.graduation(_decisions("schema_drift", [True] * 20), runbook, n=5)
    assert g.set_index("failure_class_code").loc["schema_drift", "run_mode_code"] == "recommend_only"


def test_graduation_lists_every_class_even_without_decisions(runbook):
    g = doctor.graduation(_decisions("platform", []), runbook)
    assert set(g["failure_class_code"]) == set(runbook["failure_class_code"])
    assert (g["run_mode_code"] == "recommend_only").all()


# --- US4: the incident set ------------------------------------------------------------------------

def test_incident_set_holds_the_repos_own_incidents_with_the_action_taken():
    inc = doctor.load_incidents()
    assert len(inc) >= 8
    assert {"failure_class_code", "decided_action_code", "is_reversible", "recorded_in_text"} <= set(inc.columns)
    assert {"platform", "volume_anomaly", "schema_drift", "config", "quality_fail"} <= set(inc["failure_class_code"])


def test_lineage_covers_every_pipeline_that_has_an_incident(config):
    lin = doctor.load_lineage()
    assert {"upstream_name", "downstream_name", "edge_kind_code", "pipeline_name"} <= set(lin.columns)
    outputs = {o for row in config["output_names"] for o in row}
    for p in doctor.load_incidents()["pipeline_name"].unique():
        own = set(config.set_index("pipeline_name").loc[p, "output_names"])
        assert lin["upstream_name"].isin(own).any(), f"{p}: no consumer of its outputs in lineage_edge.csv"
    assert outputs >= set(lin.loc[lin["edge_kind_code"] == "table", "upstream_name"]) - {"landing_perio_bench.review_notes"}


def test_evaluate_reports_accuracy_agreement_and_share_without_llm_with_intervals(config, runbook):
    lineage = doctor.load_lineage()
    report = doctor.evaluate(doctor.load_incidents(), config, runbook, lineage)
    assert {"failure_class_code", "incident_count", "class_accuracy_ratio", "class_accuracy_ci_low",
            "class_accuracy_ci_high", "action_agreement_ratio", "no_llm_ratio"} <= set(report.columns)
    total = report[report["failure_class_code"] == "all"].iloc[0]
    assert total["incident_count"] >= 8
    assert total["class_accuracy_ratio"] == 1.0        # the rules were written from these incidents
    assert 0 <= total["class_accuracy_ci_low"] <= total["class_accuracy_ratio"] <= total["class_accuracy_ci_high"] <= 1
    assert total["no_llm_ratio"] == 1.0
    assert total["impact_known_ratio"] == 1.0


def test_ablation_shows_what_each_piece_of_metadata_buys(config, runbook):
    """The claim behind spec 027: the config table, typed conventions, lineage, metrics and run history each
    carry part of the troubleshooting. Switching one off costs accuracy, impact, or LLM load."""
    ab = doctor.ablation(doctor.load_incidents(), config, runbook, doctor.load_lineage()).set_index("condition_name")
    full = ab.loc["full"]
    assert full["class_accuracy_ratio"] == 1.0 and full["llm_context_field_count"] == 0
    assert ab.loc["no_lineage", "impact_known_ratio"] == 0.0
    assert ab.loc["no_config", "impact_known_ratio"] == 0.0
    assert ab.loc["no_config", "action_agreement_ratio"] < full["action_agreement_ratio"]
    assert ab.loc["no_conventions", "class_accuracy_ratio"] < full["class_accuracy_ratio"]
    assert ab.loc["no_metrics", "class_accuracy_ratio"] < full["class_accuracy_ratio"]
    assert ab.loc["no_history", "no_llm_ratio"] < 1.0 and ab.loc["no_history", "llm_context_field_count"] > 0


# --- constitution ---------------------------------------------------------------------------------

def test_the_doctor_never_imports_the_notes():
    tree = ast.parse((REPO_ROOT / "python" / "health_transformation_lab_nlp" / "doctor.py").read_text())
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not names & {"notes", "clinical_notes", "note_reader", "llm_reader", "labels"}, names
