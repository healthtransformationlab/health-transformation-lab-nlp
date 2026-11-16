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


def test_with_the_exporter_off_no_step_is_counted_as_sent(fw, tmp_path, monkeypatch, capsys):
    tm.setup(tm.TelemetryConfig(exporter="off"))
    monkeypatch.setattr(fw.telemetry, "setup", lambda *a, **k: None)
    assert fw.main([str(_run(tmp_path)), "--label", "devset-x", "--platform", "modal", "--content", "full"]) == 0
    assert "content full, 0 steps in full; telemetry off" in capsys.readouterr().out


def _memory(fw, monkeypatch):
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    monkeypatch.setattr(fw.telemetry, "setup", lambda *a, **k: None)
    return exporter


def _sent(exporter) -> str:
    return json.dumps([[s.name, dict(s.attributes), s.status.description, [e.name for e in s.events]]
                       for s in exporter.get_finished_spans()])


def test_the_option_wins_over_the_setting_both_ways_and_leaves_the_setting_as_it_was(fw, tmp_path, monkeypatch):
    exporter = _memory(fw, monkeypatch)
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "full")
    assert fw.main([str(_run(tmp_path)), "--label", "devset-x", "--platform", "modal", "--content", "labels"]) == 0
    spans = exporter.get_finished_spans()
    assert not [s for s in spans if s.name == "agent_step"] and "TASK TEXT" not in _sent(exporter)
    assert next(s for s in spans if s.name == "run_forward").attributes["content_level_name"] == "labels"
    assert tm.content_level() == "full", "the option is for one call: the setting is put back"
    monkeypatch.delenv("DENTAL_TELEMETRY_CONTENT")
    assert fw.main([str(tmp_path), "--label", "devset-x", "--platform", "modal", "--content", "full"]) == 0
    assert tm.content_level() == "labels", "no setting before, none after"


def test_a_secret_inside_a_tool_call_or_a_json_output_is_redacted(fw, tmp_path, monkeypatch):
    """What the forwarder really sends: arguments are a dict and many outputs a JSON string, so a quoted secret sits
    behind JSON's escapes once written out (the review of PR 851, B1)."""
    exporter = _memory(fw, monkeypatch)
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "full")
    password, key = "S3cret" + "Passw0rd", "abcd1234" + "efgh5678ijkl"
    step = {"step_id": 4, "source": "agent", "message": f'I will set password = "{password}".',
            "tool_calls": [{"function_name": "run_command",
                            "arguments": {"command": f'export DB_PASSWORD="{password}" && pytest -q', "token": key}}],
            "observation": {"content": json.dumps({"status": "ok", "stdout": f'api_key = "{key}"\nMY_TOKEN={key}\n'})},
            "extra": {"timestamp": 1794845070.0}}
    root = _run(tmp_path)
    (root / "working/tasks/fastapi_1/results/traces/trace_fastapi_1.json").write_text(json.dumps({"steps": [step]}))
    result = root / "working/tasks/fastapi_1/result.json"
    result.write_text(json.dumps({**json.loads(result.read_text()), "patch": f'+PASSWORD = "{password}"\n'}))
    assert fw.main([str(root), "--label", "devset-x", "--platform", "modal"]) == 0
    sent = _sent(exporter)
    assert password not in sent and key not in sent
    a = next(s for s in exporter.get_finished_spans() if s.name == "agent_step").attributes
    assert "pytest -q" in a["arguments_text"] and '"status": "ok"' in a["output_text"] and tm.REDACTED in a["message_text"]


def test_a_task_takes_the_kernels_times_and_without_them_its_steps(fw, tmp_path, monkeypatch):
    exporter = _memory(fw, monkeypatch)
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "full")
    root = _run(tmp_path)
    result = root / "working/tasks/fastapi_1/result.json"
    result.write_text(json.dumps({**json.loads(result.read_text()), "started_unix": 1794845060.5, "ended_unix": 1794845400.25}))
    assert fw.main([str(root), "--label", "devset-x", "--platform", "modal"]) == 0
    task = next(s for s in exporter.get_finished_spans() if s.name == "agent_task" and s.attributes["instance_id"] == "fastapi_1")
    assert (task.start_time, task.end_time) == (1794845060_500_000_000, 1794845400_250_000_000)
    exporter.clear()
    result.write_text(json.dumps({k: v for k, v in json.loads(result.read_text()).items() if not k.endswith("_unix")}))
    assert fw.main([str(root), "--label", "devset-x", "--platform", "modal"]) == 0
    task = next(s for s in exporter.get_finished_spans() if s.name == "agent_task" and s.attributes["instance_id"] == "fastapi_1")
    assert (task.start_time, task.end_time) == (1794845064_000_000_000, 1794845067_000_000_000), "its first and last step"


@pytest.mark.parametrize("content", ["labels", "full"])
def test_one_odd_file_costs_its_own_task_and_no_text_from_it_is_sent(fw, tmp_path, monkeypatch, capsys, content):
    exporter = _memory(fw, monkeypatch)
    root = _run(tmp_path)
    for iid, text in (("bad_1", "{ cut off"), ("bad_2", "[1, 2]"),
                      ("odd_3", json.dumps({"agent_phase_seconds": "n/a password=S3cretPassw0rd", "tool_call_count": "x",
                                            "patch": 7, "started_unix": "Infinity", "verification": "no"}))):
        (root / "working/tasks" / iid).mkdir()
        (root / "working/tasks" / iid / "result.json").write_text(text)
    traces = root / "working/tasks/odd_3/results/traces"
    traces.mkdir(parents=True)
    (traces / "a.json").write_text("[1, 2]")                                  # a list, not a trace
    (traces / "b.json").write_text('{"steps": ["text", {"step_id": "x", "observation": "plain", "metrics": 5, '
                                   '"tool_calls": ["no", {"function_name": "ls"}], "extra": {"timestamp": 1e999}}]}')
    assert fw.main([str(root), "--label", "devset-x", "--platform", "modal", "--content", content]) == 0
    out = capsys.readouterr().out
    assert "bad_1: skipped (JSONDecodeError)" in out and "bad_2: skipped (ValueError)" in out
    assert "3 of 5 tasks" in out and "S3cretPassw0rd" not in out and "S3cretPassw0rd" not in _sent(exporter)
    tasks = {s.attributes["instance_id"]: s.attributes for s in exporter.get_finished_spans() if s.name == "agent_task"}
    assert set(tasks) == {"fastapi_1", "rich_2", "odd_3"}
    assert tasks["odd_3"]["agent_seconds"] == 0 and tasks["odd_3"]["tool_call_count"] == 0 and tasks["odd_3"]["is_resolved"] is False
    if content == "full":
        odd = [s.attributes for s in exporter.get_finished_spans() if s.name == "agent_step" and s.attributes["instance_id"] == "odd_3"]
        assert len(odd) == 1 and odd[0]["output_text"] == "plain" and odd[0]["tool_name"] == "ls" and odd[0]["step_num"] == 0
        assert "a.json holds no steps" in out


def test_a_task_that_failed_in_the_kernel_says_so(fw):
    a = fw.task_attrs({"error": "RuntimeError: the sandbox did not start", "trace": "Traceback ..."}, "rich_7")
    assert a["agent_error_code"] == "other" and a["is_patch_made"] is False


def test_the_kernels_own_spans_carry_the_forwarding_too(fw, tmp_path, monkeypatch):
    exporter = _memory(fw, monkeypatch)
    monkeypatch.delenv("DENTAL_TELEMETRY_CONTENT", raising=False)
    root = _run(tmp_path)
    (root / "working" / "telemetry.jsonl").write_text(json.dumps({
        "name": "call_llm", "context": {"trace_id": "0x" + "a" * 32, "span_id": "0x01"}, "kind": "SpanKind.INTERNAL",
        "parent_id": None, "start_time": "2026-11-16T15:29:01.353211Z", "end_time": "2026-11-16T15:29:02.353211Z",
        "status": {"status_code": "UNSET"}, "attributes": {"gen_ai.operation.name": "call_llm", "prompt": "P" * 100}}) + "\n")
    assert fw.main([str(root), "--label", "devset-x", "--platform", "kaggle"]) == 0
    spans = exporter.get_finished_spans()
    llm = next(s for s in spans if s.name == "call_llm")
    assert llm.attributes["run_label"] == "devset-x" and "prompt" not in llm.attributes, "labels only, as before"
    assert {s.attributes.get("forward_id") for s in spans} == {llm.attributes["forward_id"]}


def test_the_queue_is_sent_on_after_every_task_and_a_failed_send_is_reported(fw, tmp_path, monkeypatch, capsys):
    _memory(fw, monkeypatch)
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "full")
    calls = []
    monkeypatch.setattr(fw.telemetry, "flush", lambda *a, **k: calls.append(1) or len(calls) != 1)   # the first one fails
    assert fw.main([str(_run(tmp_path)), "--label", "devset-x", "--platform", "modal"]) == 0
    assert len(calls) == 3, "once a task, and once at the end"
    assert "telemetry export: FAILED" in capsys.readouterr().err


def test_the_workflow_asks_for_the_content_level_full_by_default():
    text = (REPO_ROOT / ".github" / "workflows" / "forward-run-telemetry.yml").read_text()
    block = text[text.index("      content:"):]
    assert "options: [full, labels]" in block and "default: full" in block
    assert "DENTAL_TELEMETRY_CONTENT: ${{ inputs.content }}" in text
