"""Every AccessBench run in MLflow's evaluation view (spec 045 US6, #961). Local SQLite store, no model calls."""
import json

import pandas as pd
import pytest

from health_transformation_lab_nlp import access_batch, access_keypoint_judge as ak, access_mlflow as am


@pytest.fixture
def store(tmp_path, monkeypatch):
    uri = f"sqlite:///{tmp_path}/mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_REGISTRY_URI", uri)
    monkeypatch.setenv("DENTAL_MLFLOW", "1")
    monkeypatch.setenv("MLFLOW_DISABLE_AGENT_HINT", "1")
    monkeypatch.setenv("DENTAL_MLFLOW_EXPERIMENT", "accessbench-test")
    return uri


def _batch():
    return access_batch.run(endpoints=["sim:a", "sim:b"], limit=2, fixture="perio_screening", controls=True,
                            run_id="r1", run_ts="2026-11-25T00:00:00Z", git_commit="abc")


def _items():
    return {r["id"]: r for r in access_batch.all_items()}


def test_one_row_per_answer_with_question_answer_and_expectations():
    fact = _batch()["fact_access_answer"]
    rows = am.evaluation_rows(fact, _items())
    assert len(rows) == len(fact)
    r = rows[0]
    item = _items()[r["inputs"]["question_id"]]
    assert r["inputs"]["question"] == item["prompt"]
    assert r["inputs"]["model"] == fact.iloc[0]["endpoint"]
    assert r["outputs"]["answer"] == fact.iloc[0]["answer"]
    assert r["expectations"]["points_to_make"] == ak.positive_points(item)
    assert r["expectations"]["must_not_do"] == ak.negative_checks(item)


def test_scorers_report_the_stored_grades_without_calling_a_model():
    fact = _batch()["fact_access_answer"]
    row = fact.iloc[0].to_dict()
    scorers = {s.name: s for s in am.make_scorers(fact)}
    assert set(scorers) == set(am.SCORERS)
    inputs = {"question_id": row["question_id"], "model": row["endpoint"], "question": "q"}
    pts = scorers["points_met"](inputs=inputs, outputs={"answer": row["answer"]}, expectations={})
    assert pts.value == pytest.approx(row["coverage_ratio"])
    assert "met" in pts.rationale and "simulated" in pts.rationale        # each point's verdict and span
    assert scorers["harm"](inputs=inputs, outputs={}, expectations={}).value == row["harm"]
    assert scorers["next_step"](inputs=inputs, outputs={}, expectations={}).value is True
    assert scorers["repeated_identifier"](inputs=inputs, outputs={}, expectations={}).value is False


def test_a_control_answer_reports_whether_the_judge_graded_it_as_expected():
    fact = _batch()["fact_access_answer"]
    ctl = fact[fact["endpoint"] == "control:good"].iloc[0]
    scorers = {s.name: s for s in am.make_scorers(fact)}
    fb = scorers["control_as_expected"](inputs={"question_id": ctl["question_id"], "model": ctl["endpoint"]},
                                        outputs={}, expectations={})
    assert fb.value is True
    model_row = fact[~fact["endpoint"].str.startswith("control:")].iloc[0]
    none = scorers["control_as_expected"](inputs={"question_id": model_row["question_id"], "model": model_row["endpoint"]},
                                          outputs={}, expectations={})
    assert none.value is None


def test_a_failed_judge_verdict_is_reported_as_an_error_not_a_grade():
    fact = _batch()["fact_access_answer"].copy()
    fact.loc[0, ["harm", "point_verdict_text", "coverage_ratio", "error"]] = [None, None, 0.0, "judge_parse: cut off"]
    row = fact.iloc[0]
    scorers = {s.name: s for s in am.make_scorers(fact)}
    fb = scorers["harm"](inputs={"question_id": row["question_id"], "model": row["endpoint"]}, outputs={}, expectations={})
    assert fb.value is None and "judge_parse" in fb.error.error_message


def test_log_run_makes_one_mlflow_run_per_model_plus_one_for_controls(store):
    import mlflow
    fact = _batch()["fact_access_answer"]
    runs = am.log_run(fact, _items(), batch_run_id="r1", judge_endpoint="sim:judge", prompt_version=ak.PROMPT_VERSION)
    assert set(runs) == {"sim:a", "sim:b", "controls"}
    got = mlflow.get_run(runs["sim:a"])
    assert got.data.tags["accessbench_run_id"] == "r1"
    assert got.data.tags["judge_endpoint"] == "sim:judge"
    assert got.data.metrics["points_met_mean"] == pytest.approx(fact[fact["endpoint"] == "sim:a"]["coverage_ratio"].mean())
    traces = mlflow.search_traces(run_id=runs["sim:a"], return_type="list")
    assert len(traces) == int((fact["endpoint"] == "sim:a").sum())


def test_rows_read_back_from_gold_log_the_same_way():
    from health_transformation_lab_nlp import gold_names
    fact = _batch()["fact_access_answer"]
    back = gold_names.from_gold(gold_names.to_gold(fact, "fact_access_answer"), "fact_access_answer")
    assert len(am.evaluation_rows(back, _items())) == len(fact)
    assert {s.name for s in am.make_scorers(back)} == set(am.SCORERS)
