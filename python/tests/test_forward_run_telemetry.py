"""014 US8 (#830): a development run's results reach Application Insights from a GitHub workflow."""
import importlib.util
import json

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import telemetry as tm


@pytest.fixture(scope="module")
def fw():
    spec = importlib.util.spec_from_file_location("forward_run_telemetry", REPO_ROOT / "kaggle" / "forward_run_telemetry.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(tmp_path):
    for iid, res in (("fastapi_1", {"patch": "diff --git a/x.py b/x.py\n+secret_code()", "agent_phase_seconds": "301.5",
                                    "tool_call_count": "28", "agent_error": "Agent exceeded session timeout (5.0 min)",
                                    "verification": {"is_resolved": True}, "problem_statement": "TASK TEXT"}),
                     ("rich_2", {"patch": "", "agent_phase_seconds": 90, "tool_call_count": 7, "agent_error": None,
                                 "verification": {"is_resolved": False}})):
        d = tmp_path / "working" / "tasks" / iid
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps(res))
    return tmp_path


def test_task_attrs_hold_numbers_and_labels_only(fw):
    a = fw.task_attrs({"patch": "+x", "agent_phase_seconds": "12.5", "tool_call_count": "3", "agent_error": None,
                       "verification": {"is_resolved": False}, "problem_statement": "T"}, "rich_9")
    assert a == {"instance_id": "rich_9", "agent_seconds": 12.5, "tool_call_count": 3, "is_patch_made": True,
                 "is_resolved": False, "agent_error_code": "none"}


def test_a_run_folder_becomes_one_run_span_and_one_span_a_task(fw, tmp_path, monkeypatch):
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    monkeypatch.setattr(fw.telemetry, "setup", lambda *a, **k: None)   # keep the memory exporter set above
    assert fw.main([str(_run(tmp_path)), "--label", "devset-x", "--platform", "modal"]) == 0
    spans = exporter.get_finished_spans()
    tasks = [s for s in spans if s.name == "agent_task"]
    run = [s for s in spans if s.name == "run_forward"]
    assert len(run) == 1 and run[0].attributes["run_label"] == "devset-x" and run[0].attributes["platform_name"] == "modal"
    assert run[0].attributes["task_count"] == 2
    by = {s.attributes["instance_id"]: s.attributes for s in tasks}
    assert by["fastapi_1"]["agent_error_code"] == "timeout" and by["fastapi_1"]["is_resolved"] is True
    assert by["rich_2"]["is_patch_made"] is False and by["rich_2"]["tool_call_count"] == 7
    sent = json.dumps([dict(s.attributes) for s in spans])
    assert "TASK TEXT" not in sent and "secret_code" not in sent      # no task text, no patch
