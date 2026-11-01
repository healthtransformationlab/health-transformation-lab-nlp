"""Spec 027 US5: the pipeline doctor as a job. The notebook (databricks/notebooks/13_pipeline_doctor.py) reads the
job run timeline, calls `doctor_job` and writes three gold tables; everything it decides is here, in pandas,
so it is tested without Spark. Run metadata only: never note text."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from health_transformation_lab_nlp import doctor, doctor_job

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("gold_model", ROOT / "diagrams" / "_build" / "gold_model.py")
gm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gm)

T0 = pd.Timestamp("2026-10-28 06:00:00", tz="UTC")
NOW = T0 + pd.Timedelta(days=1)
GOOD = {"catalog": "health_transformation_lab", "schema": "gold_perio_bench", "judge_endpoint": "none",
        "max_usd": "5", "lookback_days": "7", "span_table": "none", "decisions": "", "decided_by": "",
        "run_id": "991", "git_commit": "abc1234"}


def _timeline(rows):
    """Rows as the notebook's timeline query returns them (one per run)."""
    return pd.DataFrame(rows, columns=["job_name", "run_id", "started_ts", "ended_ts", "result_state",
                                       "termination_code"])


def _tl(run_id, state="SUCCEEDED", job="MedGemma reader", days_before=0, seconds=600, code=None):
    start = T0 - pd.Timedelta(days=days_before)
    return [job, run_id, start, start + pd.Timedelta(seconds=seconds), state, code]


@pytest.fixture
def config():
    return doctor.load_config()


@pytest.fixture
def runbook():
    return doctor.load_runbook()


@pytest.fixture
def lineage():
    return doctor.load_lineage()


@pytest.fixture
def runs(config):
    history = [_tl(str(100 + i), days_before=6 - i) for i in range(1, 6)]
    failed = _tl("200", state="FAILED", code="RUN_EXECUTION_ERROR")
    return doctor_job.timeline_runs(_timeline(history + [failed]), config, doctor_job.job_names())


# --- settings are checked before any work ---------------------------------------------------------

def test_good_settings_are_parsed():
    s = doctor_job.check_settings(GOOD)
    assert s["max_usd"] == 5.0 and s["lookback_days"] == 7 and s["span_table"] is None
    assert s["judge_endpoint"] is None and s["decisions"] == {}


@pytest.mark.parametrize("name,value", [("catalog", ""), ("schema", "gold perio"), ("max_usd", "five"),
                                        ("max_usd", "-1"), ("lookback_days", "0"), ("lookback_days", "x"),
                                        ("span_table", "just_a_table"), ("run_id", ""), ("run_id", "{{job.run_id}}"),
                                        ("judge_endpoint", "")])
def test_a_missing_or_malformed_setting_fails_naming_it(name, value):
    with pytest.raises(ValueError, match=name):
        doctor_job.check_settings({**GOOD, name: value})


def test_decisions_need_a_decider_and_known_action_codes():
    s = doctor_job.check_settings({**GOOD, "decisions": "200=retry, 201=page_owner", "decided_by": "repo owner"})
    assert s["decisions"] == {"200": "retry", "201": "page_owner"}
    with pytest.raises(ValueError, match="decided_by"):
        doctor_job.check_settings({**GOOD, "decisions": "200=retry"})
    with pytest.raises(ValueError, match="decisions"):
        doctor_job.check_settings({**GOOD, "decisions": "200=delete_everything", "decided_by": "repo owner"})
    with pytest.raises(ValueError, match="decisions"):
        doctor_job.check_settings({**GOOD, "decisions": "200", "decided_by": "repo owner"})


# --- the timeline becomes fact_pipeline_run --------------------------------------------------------

def test_job_names_map_every_bundle_job_to_its_pipeline_key(config):
    names = doctor_job.job_names()
    assert names["MedGemma reader"] == "medgemma_reader" and names["Pipeline doctor"] == "pipeline_doctor"
    assert set(names.values()) <= set(config["pipeline_name"])


def test_timeline_rows_become_run_rows_with_the_run_columns(runs):
    assert list(runs.columns) == doctor.RUN_COLUMNS
    assert set(runs["pipeline_name"]) == {"medgemma_reader"}
    last = runs[runs["run_id"] == "200"].iloc[0]
    assert last["run_status_code"] == "failed" and last["error_type_name"] == "RUN_EXECUTION_ERROR"
    assert last["duration_seconds"] == 600 and last["data_label_code"] == "synthetic"
    assert last["step_name"] == "job"


def test_running_cancelled_skipped_and_unknown_jobs_are_left_out(config):
    rows = _timeline([_tl("1"), _tl("2", state=None), _tl("3", state="CANCELED"), _tl("4", state="SKIPPED"),
                      _tl("5", job="Someone else's job"), _tl("6", state="TIMED_OUT")])
    out = doctor_job.timeline_runs(rows, config, doctor_job.job_names())
    assert dict(zip(out["run_id"], out["run_status_code"])) == {"1": "ok", "6": "timed_out"}


def test_span_rows_fill_what_the_timeline_cannot_say(runs):
    spans = pd.DataFrame([{"pipeline_name": "medgemma_reader", "run_id": "200", "row_out_count": 12,
                           "error_type_name": "ResourceExhausted", "error_text": "No GPU available",
                           "cost_usd": 0.4}])
    out = doctor_job.merge_spans(runs, spans)
    row = out[out["run_id"] == "200"].iloc[0]
    assert row["error_type_name"] == "ResourceExhausted" and row["row_out_count"] == 12 and row["cost_usd"] == 0.4
    assert len(out) == len(runs) and list(out.columns) == doctor.RUN_COLUMNS
    assert doctor_job.merge_spans(runs, None).equals(runs)


def test_span_rows_with_note_text_or_unknown_columns_are_refused(runs):
    with pytest.raises(ValueError, match="note_text"):
        doctor_job.merge_spans(runs, pd.DataFrame([{"pipeline_name": "x", "run_id": "1", "note_text": "..."}]))


# --- diagnosis: signals, decisions, graduation ----------------------------------------------------

def test_every_recent_run_gets_its_signals_and_every_failure_a_decision(runs, config, runbook, lineage):
    sig, dec = doctor_job.diagnose(runs, config, runbook, lineage, since=T0 - pd.Timedelta(hours=1))
    assert list(sig["run_id"]) == ["200"]                         # only runs inside the lookback window
    assert set(doctor.SIGNAL_NAMES) <= set(sig.columns)
    assert sig.iloc[0]["volume_ratio"] != sig.iloc[0]["volume_ratio"]        # no counts in the timeline: NaN
    assert sig.iloc[0]["duration_ratio"] == pytest.approx(1.0)               # against the five ok runs before it
    d = dec.iloc[0]
    rb = runbook.set_index("failure_class_code")
    assert d["recommended_action_code"] in rb.loc[d["failure_class_code"], "allowed_action_codes"]
    assert d["severity_code"] == rb.loc[d["failure_class_code"], "severity_code"]
    assert d["run_mode_code"] == "recommend_only"                  # no decisions yet
    assert pd.isna(d["decided_action_code"]) and pd.isna(d["is_match"])


def test_a_failed_run_has_spent_its_retries_so_retry_is_not_recommended(runs, config, runbook, lineage):
    spans = pd.DataFrame([{"pipeline_name": "medgemma_reader", "run_id": "200",
                           "error_type_name": "ResourceExhausted", "error_text": "No GPU available"}])
    _, dec = doctor_job.diagnose(doctor_job.merge_spans(runs, spans), config, runbook, lineage,
                                 since=T0 - pd.Timedelta(hours=1))
    assert dec.iloc[0]["failure_class_code"] == "platform"
    assert dec.iloc[0]["recommended_action_code"] == "rerun"       # the job's 6 retries already ran in the run


def test_an_approval_is_recorded_and_carried_forward(runs, config, runbook, lineage):
    since = T0 - pd.Timedelta(hours=1)
    _, first = doctor_job.diagnose(runs, config, runbook, lineage, since=since, decisions={"200": "page_owner"},
                                   decided_by="repo owner", now=NOW)
    d = first.iloc[0]
    assert d["decided_action_code"] == "page_owner" and d["decided_by_name"] == "repo owner"
    assert d["decided_ts"] == NOW and bool(d["is_match"]) == (d["recommended_action_code"] == "page_owner")
    _, again = doctor_job.diagnose(runs, config, runbook, lineage, since=since, previous=first)
    assert again.iloc[0]["decided_action_code"] == "page_owner"    # a rerun of the doctor keeps the decision


def test_an_approval_off_the_runbook_list_for_that_class_is_refused(runs, config, runbook, lineage):
    with pytest.raises(ValueError, match="not allowed"):
        doctor_job.diagnose(runs, config, runbook, lineage, since=T0 - pd.Timedelta(hours=1),
                            decisions={"200": "merge_schema"}, decided_by="repo owner")


def test_run_mode_comes_from_graduation_on_past_decisions(runs, config, runbook, lineage):
    since = T0 - pd.Timedelta(hours=1)
    _, dec = doctor_job.diagnose(runs, config, runbook, lineage, since=since)
    cls, action = dec.iloc[0]["failure_class_code"], dec.iloc[0]["recommended_action_code"]
    past = pd.DataFrame([{"pipeline_name": "medgemma_reader", "run_id": f"p{i}", "failure_class_code": cls,
                          "recommended_action_code": action, "decided_action_code": action,
                          "decided_ts": T0 - pd.Timedelta(days=10 - i), "is_match": True} for i in range(5)])
    _, dec = doctor_job.diagnose(runs, config, runbook, lineage, since=since, previous=past)
    reversible = bool(runbook.set_index("failure_class_code").loc[cls, "is_reversible"])
    assert dec.iloc[0]["run_mode_code"] == ("automatic" if reversible else "recommend_only")


def test_the_doctor_does_not_diagnose_its_own_runs(config, runbook, lineage):
    tl = _timeline([_tl("300", state="FAILED", job="Pipeline doctor")])
    runs = doctor_job.timeline_runs(tl, config, doctor_job.job_names())
    sig, dec = doctor_job.diagnose(runs, config, runbook, lineage, since=T0 - pd.Timedelta(hours=1))
    assert sig.empty and dec.empty


# --- notifications at the runbook's severity ------------------------------------------------------

def _decision(run_id, severity):
    return {"pipeline_name": "medgemma_reader", "run_id": run_id, "severity_code": severity,
            "notification_text": f"{severity} · medgemma_reader run {run_id}"}


def test_only_new_sev1_and_sev2_decisions_notify_now_the_rest_wait_for_the_digest():
    dec = pd.DataFrame([_decision("1", "SEV1"), _decision("2", "SEV2"), _decision("3", "SEV3"),
                        _decision("4", "SEV4"), _decision("5", "SEV2")])
    previous = pd.DataFrame([_decision("5", "SEV2")])               # already notified on an earlier run
    now, digest = doctor_job.notifications(dec, previous)
    assert [n.split(" run ")[1] for n in now] == ["1", "2"]
    assert digest == {"SEV3": 1, "SEV4": 1}


# --- rows are written under the declared gold columns ---------------------------------------------

@pytest.mark.parametrize("table", sorted(doctor_job.TABLES))
def test_the_job_tables_are_declared_in_the_gold_model(table):
    from health_transformation_lab_nlp import gold_names
    assert [(c.name, c.type) for c in gm.TABLES[table].columns] == doctor_job.TABLES[table]
    assert list(gold_names.TABLES[table].values()) == [n for n, _ in doctor_job.TABLES[table]]


def test_rows_for_spark_have_the_declared_columns_and_plain_python_values(runs, config, runbook, lineage):
    sig, dec = doctor_job.diagnose(runs, config, runbook, lineage, since=T0 - pd.Timedelta(hours=1))
    batch = {"doctor_run_id": "991", "loaded_ts": NOW, "doctor_git_commit_sha": "abc1234"}
    for table, df in {"fact_pipeline_run": runs, "fact_pipeline_signal": sig,
                      "fact_remediation_decision": dec}.items():
        out = doctor_job.rows(df, table, **batch)
        assert list(out.columns) == [n for n, _ in doctor_job.TABLES[table]]
        for name, kind in doctor_job.TABLES[table]:
            for v in out[name]:
                if v is None:
                    continue
                expected = {"bigint": int, "double": float, "boolean": bool, "string": str,
                            "timestamp": pd.Timestamp}[kind]
                assert isinstance(v, expected), (table, name, v)
        assert set(out["doctor_run_id"]) == {"991"}
    assert "string" in doctor_job.ddl("fact_pipeline_run") and "is_match boolean" in doctor_job.ddl(
        "fact_remediation_decision")


def test_the_job_module_never_touches_the_notes():
    text = (ROOT / "python" / "health_transformation_lab_nlp" / "doctor_job.py").read_text()
    for name in ("import notes", "clinical_notes", "note_reader", "review_key"):
        assert name not in text
