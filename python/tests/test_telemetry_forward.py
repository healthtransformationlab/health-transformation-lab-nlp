"""Spec 014 US7 (#791): spans written to a file on a machine with no network (a Kaggle or Colab GPU run) are sent on
later through whichever exporter is set up, with their own start and end times, attributes and parentage."""
import json
import time

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.trace import StatusCode

from health_transformation_lab_nlp import telemetry as tm


@pytest.fixture
def mem():
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    yield exporter
    tm.setup(tm.TelemetryConfig(exporter="off"))


def _iso(ns: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ns // 1_000_000_000)) + f".{ns % 1_000_000_000 // 1000:06d}Z"


def _line(name, span_id, parent_id, start_ns, end_ns, attributes, status="UNSET", trace_id="0x" + "a" * 32):
    return json.dumps({"name": name, "context": {"trace_id": trace_id, "span_id": span_id, "trace_state": "[]"},
                       "kind": "SpanKind.INTERNAL", "parent_id": parent_id, "start_time": _iso(start_ns),
                       "end_time": _iso(end_ns), "status": {"status_code": status}, "attributes": attributes,
                       "events": [], "links": [], "resource": {"attributes": {}, "schema_url": ""}}) + "\n"


T0 = 1_763_000_000_123_456_000   # November 2025, whole microseconds (the file keeps microseconds)


def test_forwarded_spans_keep_their_times_attributes_and_parents(mem, tmp_path):
    path = tmp_path / "telemetry.jsonl"
    path.write_text(   # children first, as a file exporter writes them
        _line("execute_tool shell", "0x02", "0x01", T0 + 1_000_000, T0 + 2_000_000, {"tool_name": "shell"})
        + _line("official_agent_kernel.task", "0x01", None, T0, T0 + 5_000_000,
                {"instance_id": "htlnlp_1", "output_token_count": 64}, status="ERROR"))
    assert tm.forward_spans(path) == 2
    spans = {s.name: s for s in mem.get_finished_spans()}
    task, tool = spans["official_agent_kernel.task"], spans["execute_tool shell"]
    assert (task.start_time, task.end_time) == (T0, T0 + 5_000_000)
    assert (tool.start_time, tool.end_time) == (T0 + 1_000_000, T0 + 2_000_000)
    assert task.attributes["instance_id"] == "htlnlp_1" and task.attributes["output_token_count"] == 64
    assert tool.attributes["tool_name"] == "shell"
    assert tool.parent is not None and tool.parent.span_id == task.context.span_id
    assert tool.context.trace_id == task.context.trace_id and task.parent is None
    assert task.status.status_code == StatusCode.ERROR


def test_a_file_written_by_the_file_exporter_is_read_back_whole(tmp_path):
    path = tmp_path / "run" / "telemetry.jsonl"
    tm.setup(tm.TelemetryConfig(exporter="file", file_path=str(path)))
    with tm.pipeline_step("outer", rows=3), tm.pipeline_step("inner"):
        pass
    tm.record_value("data_quality.pass_rate", 0.9)
    mem = tm.setup(tm.TelemetryConfig(exporter="memory"))   # flushes the file, then sends to memory
    written = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    try:
        assert tm.forward_spans(path) == 2
        spans = {s.name: s for s in mem.get_finished_spans()}
        assert spans["inner"].parent.span_id == spans["outer"].context.span_id
        assert spans["outer"].attributes["rows"] == 3
        outer = next(w for w in written if w.get("name") == "outer")
        assert tm._iso_ns(outer["start_time"]) == spans["outer"].start_time
    finally:
        tm.setup(tm.TelemetryConfig(exporter="off"))


def test_metrics_lines_a_cut_off_last_line_and_long_text_are_left_out(mem, tmp_path):
    path = tmp_path / "telemetry.jsonl"
    path.write_text(json.dumps({"resource_metrics": []}) + "\n"
                    + _line("step", "0x01", None, T0, T0 + 10, {"note_text": "x" * 500, "row_count": 2})
                    + '{"name": "half a li')
    assert tm.forward_spans(path) == 1
    (span,) = mem.get_finished_spans()
    assert "note_text" not in span.attributes and span.attributes["row_count"] == 2


def test_with_the_exporter_off_nothing_is_sent(tmp_path):
    tm.setup(tm.TelemetryConfig(exporter="off"))
    path = tmp_path / "telemetry.jsonl"
    path.write_text(_line("step", "0x01", None, T0, T0 + 10, {}))
    assert tm.forward_spans(path) == 0


def test_a_missing_file_sends_nothing(mem, tmp_path):
    assert tm.forward_spans(tmp_path / "absent.jsonl") == 0
    assert not mem.get_finished_spans()


# ---- kaggle/official_agent_run.py --collect ------------------------------------------------------------------------

def _runner():
    import importlib.util

    from health_transformation_lab_nlp.paths import REPO_ROOT
    spec = importlib.util.spec_from_file_location("official_agent_run", REPO_ROOT / "kaggle" / "official_agent_run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_telemetry_file_without_the_package_does_not_abort(monkeypatch, tmp_path, capsys):
    import sys
    run = _runner()
    (tmp_path / "telemetry.jsonl").write_text("{}\n")
    hidden = [k for k in sys.modules if k == "health_transformation_lab_nlp"
              or k.startswith("health_transformation_lab_nlp.")]
    for key in hidden:
        monkeypatch.delitem(sys.modules, key, raising=False)
    import builtins
    real = builtins.__import__

    def boom(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "health_transformation_lab_nlp":
            raise ModuleNotFoundError("blocked", name="health_transformation_lab_nlp")
        return real(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", boom)
    assert run.forward_run_telemetry(tmp_path) == 0
    err = capsys.readouterr().out
    assert "health_transformation_lab_nlp" in err and "grading continues" in err


def test_launch_names_the_missing_module(monkeypatch):
    import importlib
    run = _runner()
    real = importlib.import_module

    def fake(name, package=None):
        if name == "swegemma":
            raise ModuleNotFoundError("No module named 'swegemma'", name="swegemma")
        return real(name, package)

    monkeypatch.setattr(run.importlib, "import_module", fake)
    with pytest.raises(SystemExit, match="swegemma"):
        run.require_launch_imports()


def test_launch_puts_the_repo_package_on_the_path():
    import sys
    run = _runner()
    root = str(run.REPO_ROOT / "python")
    sys.path[:] = [p for p in sys.path if p != root]
    try:
        run.ensure_repo_package_path()
        assert sys.path[0] == root
    finally:
        if root not in sys.path:
            sys.path.insert(0, root)


def test_a_missing_telemetry_file_does_not_need_the_package(monkeypatch, tmp_path):
    run = _runner()
    import builtins
    real = builtins.__import__

    def boom(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "health_transformation_lab_nlp":
            raise ModuleNotFoundError("blocked", name="health_transformation_lab_nlp")
        return real(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", boom)
    assert run.forward_run_telemetry(tmp_path) == 0


def test_collect_forwards_the_runs_spans(mem, tmp_path):
    run = _runner()
    (tmp_path / "telemetry.jsonl").write_text(_line("official_agent_kernel.task", "0x01", None, T0, T0 + 10, {}))
    assert run.forward_run_telemetry(tmp_path) == 1
    assert [s.name for s in mem.get_finished_spans()] == ["official_agent_kernel.task"]
    assert run.forward_run_telemetry(tmp_path / "no_spans_here") == 0


def test_collect_sets_telemetry_up_and_forwards_after_collecting():
    import inspect
    run = _runner()
    main, batch = inspect.getsource(run.main), inspect.getsource(run.run_batch)
    assert "telemetry.setup()" in main and 'telemetry.start_script("official_agent_run"' in main
    assert "forward_run_telemetry(out)" in batch


def test_telemetry_off_by_default_stays_off(monkeypatch, tmp_path):
    monkeypatch.delenv("DENTAL_TELEMETRY", raising=False)
    tm.setup()
    run = _runner()
    (tmp_path / "telemetry.jsonl").write_text(_line("step", "0x01", None, T0, T0 + 10, {}))
    assert tm.active_exporter() == "off" and run.forward_run_telemetry(tmp_path) == 0
