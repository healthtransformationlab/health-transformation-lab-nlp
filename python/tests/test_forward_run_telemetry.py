"""014 US8 (#830): a development run's results reach Application Insights from a GitHub workflow. 014 US9 (#850): with
DENTAL_TELEMETRY_CONTENT=full, so does each task's trace: every step, the patch, secrets taken out."""
import importlib.util
import json
import re

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
    traces = tmp_path / "working" / "tasks" / "fastapi_1" / "results" / "traces"   # rich_2 has no trace
    traces.mkdir(parents=True)
    (traces / "trace_fastapi_1.json").write_text(json.dumps({"schema_version": "x", "steps": STEPS}))
    return tmp_path


KAGGLE_TOKEN = "KGAT_" + "a1B2c3D4" * 4
STEPS = [
    {"step_id": 1, "source": "system", "message": "SYSTEM PROMPT",
     "extra": {"event_type": "system_instruction", "elapsed_s": 0.0, "timestamp": 1794845064.0}},
    {"step_id": 2, "source": "user", "message": "TASK TEXT: fix the bug",
     "extra": {"event_type": "user_message", "elapsed_s": 0.1, "timestamp": 1794845064.25}},
    {"step_id": 3, "source": "agent", "message": "I will read the file.",
     "tool_calls": [{"tool_call_id": "call_3", "function_name": "read_file", "arguments": {"filepath": "x.py"}}],
     "observation": {"content": f"token = {KAGGLE_TOKEN}\n" + "L" * 9000,
                     "extra": {"tool_name": "read_file", "elapsed_s": 2.5, "timestamp": 1794845067.0}},
     "metrics": {"prompt_tokens": 9000, "completion_tokens": 40, "cached_tokens": 8000, "total_tokens": 9040},
     "extra": {"event_type": "tool_call", "elapsed_s": 2.0, "timestamp": 1794845066.5}},
]


def test_task_attrs_hold_numbers_and_labels_only(fw):
    a = fw.task_attrs({"patch": "+x", "agent_phase_seconds": "12.5", "tool_call_count": "3", "agent_error": None,
                       "verification": {"is_resolved": False}, "problem_statement": "T"}, "rich_9")
    assert a == {"instance_id": "rich_9", "agent_seconds": 12.5, "tool_call_count": 3, "is_patch_made": True,
                 "is_resolved": False, "agent_error_code": "none"}


def test_a_run_folder_becomes_one_run_span_and_one_span_a_task(fw, tmp_path, monkeypatch):
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    monkeypatch.setattr(fw.telemetry, "setup", lambda *a, **k: None)   # keep the memory exporter set above
    monkeypatch.delenv("DENTAL_TELEMETRY_CONTENT", raising=False)      # labels: the default
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
    assert not [s for s in spans if s.name.startswith("agent_step")], "labels mode sends no step"
    ids = {s.attributes.get("forward_id") for s in spans}
    assert len(ids) == 1 and re.fullmatch(r"[0-9a-f]{12}", ids.pop()), "one forward_id on every span"


def test_step_attrs_name_what_a_step_did(fw):
    a = fw.step_attrs(STEPS[2], "fastapi_1")
    assert a == {"instance_id": "fastapi_1", "step_num": 3, "source_name": "agent", "event_type_name": "tool_call",
                 "message_text": "I will read the file.", "tool_name": "read_file", "tool_call_count": 1,
                 "arguments_text": '{"filepath": "x.py"}', "output_text": STEPS[2]["observation"]["content"],
                 "prompt_token_count": 9000, "completion_token_count": 40, "cached_token_count": 8000,
                 "elapsed_seconds": 2.0}
    first = fw.step_attrs(STEPS[0], "fastapi_1")
    assert first["tool_name"] == "" and first["tool_call_count"] == 0 and first["arguments_text"] == ""
    assert first["output_text"] == "" and first["message_text"] == "SYSTEM PROMPT" and first["prompt_token_count"] == 0
    two = {"step_id": 9, "tool_calls": [{"function_name": "read_file", "arguments": {"filepath": "a"}},
                                        {"function_name": "run_command", "arguments": {"command": "ls"}}],
           "observation": {"content": [{"a": 1}]}}
    b = fw.step_attrs(two, "x_1")
    assert b["tool_name"] == "read_file, run_command" and b["tool_call_count"] == 2
    assert json.loads(b["arguments_text"]) == [{"filepath": "a"}, {"command": "ls"}] and b["output_text"] == '[{"a": 1}]'


@pytest.mark.parametrize("how", ["setting", "option"])
def test_full_content_sends_every_step_and_the_patch_with_secrets_out(fw, tmp_path, monkeypatch, how):
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    monkeypatch.setattr(fw.telemetry, "setup", lambda *a, **k: None)
    argv = [str(_run(tmp_path)), "--label", "devset-x", "--platform", "colab"]
    if how == "setting":
        monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "full")
    else:
        monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "labels")
        argv += ["--content", "full"]
    assert fw.main(argv) == 0
    spans = exporter.get_finished_spans()
    run = next(s for s in spans if s.name == "run_forward")
    tasks = {s.attributes["instance_id"]: s for s in spans if s.name == "agent_task"}
    steps = sorted((s for s in spans if s.name == "agent_step"), key=lambda s: s.attributes["step_num"])
    parts = [s for s in spans if s.name == "agent_step_part"]
    assert run.attributes["content_level_name"] == "full" and set(tasks) == {"fastapi_1", "rich_2"}
    assert [s.attributes["step_num"] for s in steps] == [1, 2, 3], "one span a step; rich_2 has no trace"
    assert all(s.parent.span_id == tasks["fastapi_1"].context.span_id for s in steps)
    assert all(t.parent.span_id == run.context.span_id for t in tasks.values())
    assert steps[1].attributes["message_text"] == "TASK TEXT: fix the bug" and steps[1].attributes["source_name"] == "user"
    last = steps[2].attributes
    assert last["tool_name"] == "read_file" and last["arguments_text"] == '{"filepath": "x.py"}'
    assert last["prompt_token_count"] == 9000 and last["run_label"] == "devset-x" and last["platform_name"] == "colab"
    assert last["output_text_part_count"] == 2 and len(parts) == 1 and parts[0].attributes["step_num"] == 3
    assert last["output_text"] + parts[0].attributes["part_text"] == f"token = {tm.REDACTED}\n" + "L" * 9000
    assert (steps[2].start_time, steps[2].end_time) == (1794845066_500_000_000, 1794845067_000_000_000)
    task = tasks["fastapi_1"].attributes
    assert task["patch_text"] == "diff --git a/x.py b/x.py\n+secret_code()" and task["is_resolved"] is True
    assert task["agent_error_text"] == "Agent exceeded session timeout (5.0 min)" and task["agent_error_code"] == "timeout"
    assert tasks["rich_2"].attributes["patch_text"] == "" and tasks["rich_2"].attributes["agent_error_text"] == ""
    assert KAGGLE_TOKEN not in json.dumps([dict(s.attributes) for s in spans])
    ids = {s.attributes.get("forward_id") for s in spans}
    assert len(ids) == 1 and re.fullmatch(r"[0-9a-f]{12}", ids.pop())


def test_a_setting_that_is_neither_value_stops_before_anything_is_sent(fw, tmp_path, monkeypatch):
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    monkeypatch.setattr(fw.telemetry, "setup", lambda *a, **k: None)
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "all")
    with pytest.raises(SystemExit) as e:
        fw.main([str(_run(tmp_path)), "--label", "devset-x", "--platform", "modal"])
    assert "DENTAL_TELEMETRY_CONTENT" in str(e.value) and exporter.get_finished_spans() == ()


def test_the_workflow_asks_for_the_content_level_full_by_default():
    text = (REPO_ROOT / ".github" / "workflows" / "forward-run-telemetry.yml").read_text()
    block = text[text.index("      content:"):]
    assert "options: [full, labels]" in block and "default: full" in block
    assert "DENTAL_TELEMETRY_CONTENT: ${{ inputs.content }}" in text
