"""Spec 014 US6 (#666): the coding-agent runs are traced too. Kaggle kernels run with internet off, so spans go to a
file: through the tracing SDK where the package is installed (DENTAL_TELEMETRY=file), and through the Kaggle bundle's
own dependency-free tracer, which writes the same JSON layout. A span carries numbers and short labels, never the
prompt, the reply, a command or a patch."""
import importlib.util
import inspect
import json
import logging
import subprocess
import tarfile

import pytest

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import agent_harness as ah
from health_transformation_lab_nlp import gemma_agent as ga
from health_transformation_lab_nlp import telemetry as tm
from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

SPAN_KEYS = {"name", "context", "kind", "parent_id", "start_time", "end_time", "status", "attributes", "events",
             "links", "resource"}


@pytest.fixture
def mem():
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    yield exporter
    tm.setup(tm.TelemetryConfig(exporter="off"))


def _lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _spans(path):
    return [line for line in _lines(path) if "context" in line]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "kaggle" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- the package: a file exporter for runs with no network, and annotate() -----------------------------------------

def test_the_file_exporter_writes_each_span_as_a_json_line(tmp_path):
    out = tmp_path / "run" / "telemetry.jsonl"
    tm.setup(tm.TelemetryConfig(exporter="file", file_path=str(out)))
    try:
        with tm.trace_call("agent_kernel.task", level="step", instance_id="htlnlp_1"):
            with tm.trace_call("gemma_agent.GemmaModel.step"):
                tm.annotate(output_token_count=12)
    finally:
        tm.setup(tm.TelemetryConfig(exporter="off"))
    spans = _spans(out)
    assert [s["name"] for s in spans] == ["gemma_agent.GemmaModel.step", "agent_kernel.task"]   # children end first
    turn, task = spans
    assert set(turn) == SPAN_KEYS
    assert turn["parent_id"] == task["context"]["span_id"]
    assert turn["attributes"]["output_token_count"] == 12
    assert task["attributes"]["instance_id"] == "htlnlp_1" and task["attributes"]["environment"] == "dev"


def test_the_file_exporter_reads_its_path_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("DENTAL_TELEMETRY", "file")
    monkeypatch.setenv("DENTAL_TELEMETRY_FILE", str(tmp_path / "t.jsonl"))
    c = tm.config_from_env()
    assert (c.exporter, c.file_path) == ("file", str(tmp_path / "t.jsonl"))


def test_the_file_exporter_without_a_path_warns_and_turns_telemetry_off(caplog):
    with caplog.at_level(logging.WARNING):
        tm.setup(tm.TelemetryConfig(exporter="file"))
    assert tm.active_exporter() == "off" and "DENTAL_TELEMETRY_FILE" in caplog.text


def test_annotate_keeps_numbers_and_short_labels_and_drops_text(mem):
    with tm.trace_call("agent_harness.call_tool"):
        tm.annotate(tool_name="read_file", exit_code=0, turn_seconds=1.5, is_error=False, instance_id="htlnlp_1",
                    command_text="cat notes.txt", reply="free text", model_name="x" * 80)
    (span,) = mem.get_finished_spans()
    a = dict(span.attributes)
    assert (a["tool_name"], a["exit_code"], a["turn_seconds"], a["is_error"], a["instance_id"]) == (
        "read_file", 0, 1.5, False, "htlnlp_1")
    assert not {"command_text", "reply", "model_name"} & set(a)


def test_annotate_does_nothing_when_telemetry_is_off():
    tm.setup(tm.TelemetryConfig(exporter="off"))
    tm.annotate(output_token_count=1)     # no span to put it on, and no error


@tm.traced
def _noisy(n):
    tm.annotate(call_num=n)


def test_annotate_never_lands_on_a_parent_when_a_call_made_no_span(mem):
    """Past DENTAL_TELEMETRY_MAX_CALLS a function is only counted; what it annotates is dropped, not put on the
    caller's span, which would mislabel it."""
    with tm.trace_call("outer"):
        for n in range(1, tm.MAX_SPANS_PER_CALLER + 3):
            _noisy(n)
    spans = {s.name: s for s in mem.get_finished_spans()}
    assert "call_num" not in spans["outer"].attributes
    made = [s.attributes["call_num"] for s in mem.get_finished_spans() if s.name.endswith("_noisy")]
    assert made == list(range(1, tm.MAX_SPANS_PER_CALLER + 1))


# --- the harness: each model turn and each tool call --------------------------------------------------------------

def test_a_model_turn_puts_its_tokens_and_seconds_on_its_span(mem):
    with tm.trace_call("gemma_agent.GemmaModel.step"):
        ga._record_turn({"prompt_tokens": 900, "prefill_tokens": 120, "output_tokens": 64, "seconds": 2.5},
                        "gemma-4-e4b-it")
    (span,) = mem.get_finished_spans()
    a = dict(span.attributes)
    assert (a["prompt_token_count"], a["prefill_token_count"], a["output_token_count"], a["turn_seconds"]) == (
        900, 120, 64, 2.5)
    assert a["model_name"] == "gemma-4-e4b-it" and a["is_over_context"] is False


def test_a_turn_past_the_context_says_so(mem):
    with tm.trace_call("gemma_agent.GemmaModel.step"):
        ga._record_turn({"prompt_tokens": 40000, "prefill_tokens": 0, "output_tokens": 0, "seconds": 0.0,
                         "over_context": True}, "gemma-4-e4b-it")
    (span,) = mem.get_finished_spans()
    assert span.attributes["is_over_context"] is True and span.attributes["output_token_count"] == 0


def test_the_model_records_every_turn_it_takes():
    src = inspect.getsource(ga.GemmaModel.step)
    assert src.count("_record_turn(self.turns[-1]") == 2     # the normal turn and the one past the context


def test_a_tool_call_names_its_tool_and_never_its_arguments(mem):
    out = json.loads(ah.call_tool(None, "no_such_tool", {"command": "cat /etc/passwd"}))
    assert out["error_type"] == "UnknownTool"
    spans = [s for s in mem.get_finished_spans() if s.name == "agent_harness.call_tool"]
    assert spans and spans[-1].attributes["tool_name"] == "unknown"
    assert spans[-1].attributes["tool_error_code"] == "UnknownTool"
    assert not any("passwd" in str(v) for s in mem.get_finished_spans() for v in s.attributes.values())


# --- the Kaggle bundle: a dependency-free tracer with the same API and the same layout -----------------------------

def test_the_bundle_tracer_is_off_unless_asked(monkeypatch, tmp_path):
    monkeypatch.delenv("DENTAL_TELEMETRY", raising=False)
    monkeypatch.setenv("DENTAL_TELEMETRY_FILE", str(tmp_path / "t.jsonl"))
    bt = _load("bundle_telemetry")
    bt.setup()

    @bt.traced
    def f():
        bt.annotate(output_token_count=1)
        return 7

    assert f() == 7 and bt.active_exporter() == "off" and not (tmp_path / "t.jsonl").exists()


def test_the_bundle_tracer_writes_the_packages_span_layout(monkeypatch, tmp_path):
    pkg = tmp_path / "pkg.jsonl"
    tm.setup(tm.TelemetryConfig(exporter="file", file_path=str(pkg)))
    try:
        with tm.trace_call("x"):
            pass
    finally:
        tm.setup(tm.TelemetryConfig(exporter="off"))
    (reference,) = _spans(pkg)

    out = tmp_path / "bundle.jsonl"
    monkeypatch.setenv("DENTAL_TELEMETRY", "file")
    monkeypatch.setenv("DENTAL_TELEMETRY_FILE", str(out))
    bt = _load("bundle_telemetry")
    bt.setup()

    @bt.traced
    def inner():
        bt.annotate(output_token_count=5, command_text="rm -rf /")

    @bt.traced
    def outer():
        inner()

    bt.start_script("agent_kernel", instance_id="htlnlp_1", model_name="gemma-4-e4b-it")
    outer()
    bt.end_script()
    spans = _spans(out)
    assert [s["name"].rsplit(".", 1)[-1] for s in spans] == ["inner", "outer", "agent_kernel"]
    i, o, k = spans
    for s in spans:
        assert set(s) == set(reference)
        assert set(s["context"]) == set(reference["context"]) and set(s["resource"]) == set(reference["resource"])
        assert s["attributes"]["environment"] == "dev" and s["attributes"]["data_product_id"] == tm.DATA_PRODUCT
        assert s["context"]["trace_id"] == k["context"]["trace_id"]
    assert (i["parent_id"], o["parent_id"], k["parent_id"]) == (o["context"]["span_id"], k["context"]["span_id"], None)
    assert i["attributes"]["output_token_count"] == 5 and "command_text" not in i["attributes"]
    assert k["attributes"]["instance_id"] == "htlnlp_1" and k["attributes"]["pipeline.kind"] == "script"


def test_the_bundle_tracer_records_the_error_type_and_never_the_message(monkeypatch, tmp_path):
    out = tmp_path / "t.jsonl"
    monkeypatch.setenv("DENTAL_TELEMETRY", "file")
    monkeypatch.setenv("DENTAL_TELEMETRY_FILE", str(out))
    bt = _load("bundle_telemetry")
    bt.setup()

    @bt.traced
    def boom():
        raise ValueError("the patient's note says")

    with pytest.raises(ValueError):
        boom()
    (span,) = _spans(out)
    assert span["status"]["status_code"] == "ERROR" and span["attributes"]["error.type"] == "ValueError"
    assert "note says" not in out.read_text()


def test_the_bundle_tracer_keeps_what_the_package_keeps(monkeypatch, tmp_path, mem):
    attrs = dict(tool_name="read_file", exit_code=0, turn_seconds=1.5, is_error=False, instance_id="htlnlp_1",
                 command_text="cat notes.txt", reply="free text", model_name="x" * 80, tool_error_code="Timeout")
    with tm.trace_call("p"):
        tm.annotate(**attrs)
    (p,) = mem.get_finished_spans()
    out = tmp_path / "t.jsonl"
    monkeypatch.setenv("DENTAL_TELEMETRY", "file")
    monkeypatch.setenv("DENTAL_TELEMETRY_FILE", str(out))
    bt = _load("bundle_telemetry")
    bt.setup()

    @bt.traced
    def b():
        bt.annotate(**attrs)

    b()
    (s,) = _spans(out)
    assert {k for k in s["attributes"] if k in attrs} == {k for k in p.attributes if k in attrs}


def test_the_bundle_tracer_traces_every_turn_of_a_task(monkeypatch, tmp_path):
    """A file costs nothing to ingest, so the bundle keeps every call (the package caps them for Azure's allowance)."""
    out = tmp_path / "t.jsonl"
    monkeypatch.setenv("DENTAL_TELEMETRY", "file")
    monkeypatch.setenv("DENTAL_TELEMETRY_FILE", str(out))
    bt = _load("bundle_telemetry")
    bt.setup()

    @bt.traced
    def turn():
        pass

    bt.start_script("agent_kernel")
    for _ in range(60):
        turn()
    bt.end_script()
    assert sum(s["name"].endswith("turn") for s in _spans(out)) == 60


@pytest.fixture(scope="module")
def sample():
    rows = [json.loads(line) for line in (TASKS_DIR / "tasks_sample.jsonl").read_text().splitlines() if line.strip()]
    return rows[0]


def _snapshot(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=src, check=True)
    (src / "f.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=src, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "c"], cwd=src, check=True)
    tgz = tmp_path / "snap.tgz"
    with tarfile.open(tgz, "w:gz") as t:
        t.add(src, arcname=".")
    return tgz


def test_the_bundle_ships_the_tracer_in_place_of_the_stub(tmp_path, sample):
    ab = _load("agent_bundle")
    out = ab.build(sample, _snapshot(tmp_path), None, None, tmp_path / "b", "", ["read_file"], ah.Budget())
    shipped = (out / "htl_agent" / "telemetry.py").read_text()
    assert shipped == (REPO_ROOT / "kaggle" / "bundle_telemetry.py").read_text()
    assert "opentelemetry" not in shipped      # not the package's module, which tasks change


# --- the kernels ---------------------------------------------------------------------------------------------------

def test_the_local_kernel_writes_its_spans_beside_result_json():
    src = (REPO_ROOT / "kaggle" / "agent_kernel.py").read_text()
    assert 'os.environ.setdefault("DENTAL_TELEMETRY", "file")' in src
    assert 'os.environ.setdefault("DENTAL_TELEMETRY_FILE", "/kaggle/working/telemetry.jsonl")' in src
    assert "tm.setup()" in src and "tm.start_script(" in src and "tm.end_script()" in src


def test_the_official_kernel_still_runs_as_the_competition_does():
    """Its runs are compared with the competition's, so it keeps tracing off; its timing and tokens come from the
    evaluator's own result."""
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    assert '"OTEL_SDK_DISABLED": "true"' in src


# --- the runner: python/scripts/60_kaggle_agent.py keeps each task's spans ----------------------------------------

def _runner():
    spec = importlib.util.spec_from_file_location("kaggle_agent", REPO_ROOT / "python" / "scripts" / "60_kaggle_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_runner_keeps_each_tasks_spans_and_a_rerun_replaces_them(tmp_path):
    runner = _runner()
    out = tmp_path / "output"
    out.mkdir()
    (out / "telemetry.jsonl").write_text('{"name": "first"}\n')
    folder = tmp_path / "telemetry" / "gemma-4-e4b-it"
    kept = runner.keep_telemetry(out, folder, "htlnlp_1")
    assert kept == folder / "htlnlp_1.jsonl" and kept.read_text() == '{"name": "first"}\n'
    (out / "telemetry.jsonl").write_text('{"name": "rerun"}\n')
    assert runner.keep_telemetry(out, folder, "htlnlp_1").read_text() == '{"name": "rerun"}\n'
    assert runner.keep_telemetry(tmp_path / "no_output", folder, "htlnlp_2") is None


def test_the_runner_never_keeps_an_earlier_runs_spans():
    """The kernel's output folder is cleared before each download, so a kernel that wrote no spans leaves none."""
    src = (REPO_ROOT / "python" / "scripts" / "60_kaggle_agent.py").read_text()
    clear = src.index('shutil.rmtree(work / "output", ignore_errors=True)')
    run = src.index('result = _run_kernel(api, k, kref, work / "output"')
    keep = src.index('keep_telemetry(work / "output", OUT_DIR / "telemetry" / a.model, iid)')
    assert clear < run < keep
