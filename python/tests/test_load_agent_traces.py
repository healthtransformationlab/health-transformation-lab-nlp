"""Spec 041 US2 (#857): a finished run's traces go to the Unity Catalog experiment, once per task-run.

The fixture runs (tests/fixtures/agent_runs/) are synthetic. A fake client stands in for MLflow: it records what would
be written and answers which trace keys are already there. The trace shape is plan.md's "What a trace looks like".
"""

import hashlib
import importlib.util
import json
import shutil

import pytest
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

FIXTURES = REPO_ROOT / "python/tests/fixtures/agent_runs"
FAKE = "ghp_" + "Q7w" * 12          # built here so no token-shaped text is committed


@pytest.fixture(scope="module")
def lt():
    spec = importlib.util.spec_from_file_location("load_agent_traces", REPO_ROOT / "kaggle" / "load_agent_traces.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def runs(tmp_path):
    shutil.copytree(FIXTURES, tmp_path / "runs")
    for p in (tmp_path / "runs").rglob("*.json"):
        p.write_text(p.read_text().replace("__FAKE_TOKEN__", FAKE))
    return tmp_path / "runs"


class FakeClient:
    def __init__(self):
        self.traces = []

    def existing_keys(self, run_label):
        return {t["tags"]["trace_key"] for t in self.traces if t["tags"]["run_label"] == run_label}

    def write(self, trace, source_run_id=None):
        self.traces.append(trace)

    def start_load(self, run_label, agent_name, params):
        return "fake-run"

    def end_load(self, run_id, metrics):
        self.metrics = metrics

    def confirm(self, run_label, keys):
        return set(keys) - self.existing_keys(run_label)


class DroppingClient(FakeClient):
    """Says it wrote, but nothing arrives: what MLflow does when traces are not routed to Unity Catalog."""

    def write(self, trace, source_run_id=None):
        pass


def _trace(lt, runs, iid="demo_101"):
    return lt.task_trace(runs / "demo-run/tasks" / iid, "demo-run", "demo agent")


def test_trace_key_is_the_sha256_of_label_agent_and_task(lt):
    assert lt.trace_key("r", "a", "t") == hashlib.sha256(b"r|a|t").hexdigest()


def test_the_experiment_setting_matches_the_bundle(lt):
    exp = yaml.safe_load((REPO_ROOT / "databricks/resources/agent_traces.yml").read_text())["resources"]["experiments"]
    assert lt.DEFAULT_EXPERIMENT == exp["coding_agent_runs"]["name"] == "/Shared/coding-agent-runs"


def test_root_span_holds_issue_patch_and_outcome(lt, runs):
    t = _trace(lt, runs)
    assert t["root"]["name"] == "demo_101" and t["root"]["is_ok"] is True
    assert "negative numbers" in t["root"]["inputs"]["issue"]
    assert "return a + b" in t["root"]["outputs"]["patch"] and t["root"]["outputs"]["outcome_code"] == "solved"
    assert t["tags"] == {"trace_key": lt.trace_key("demo-run", "demo agent", "demo_101"), "run_label": "demo-run",
                         "agent_name": "demo agent", "instance_id": "demo_101", "repo_name": "demo",
                         "outcome_code": "solved", "ended_code": "ended_itself", "is_resolved": "true",
                         "verdict_source_code": "kernel", "kernel_grade_code": "graded"}


def test_each_model_turn_is_an_llm_span_and_each_call_a_tool_span_named_by_the_tool(lt, runs):
    turns = _trace(lt, runs)["steps"]
    assert [t["name"] for t in turns] == ["model turn"] * 4
    assert [[c["name"] for c in t["tools"]] for t in turns] == [
        ["run_command", "read_file"], ["edit_file"], ["edit_file"], ["submit_patch"]]
    first = turns[0]
    assert first["attributes"]["mlflow.chat.tokenUsage"] == {"input_tokens": 1000, "output_tokens": 50,
                                                             "total_tokens": 1050}
    assert first["attributes"]["step_num"] == 3
    assert first["tools"][0]["attributes"]["step_num"] == 3


def test_the_second_calls_output_comes_from_its_own_system_step(lt, runs):
    read = _trace(lt, runs)["steps"][0]["tools"][1]
    assert read["inputs"] == {"filepath": "demo/math.py", "start_line": 1, "end_line": 20}
    assert "def add(a, b)" in json.dumps(read["outputs"])


def test_a_failed_edit_is_an_error_span_and_a_good_one_is_ok(lt, runs):
    turns = _trace(lt, runs)["steps"]
    assert turns[1]["tools"][0]["is_ok"] is False and turns[2]["tools"][0]["is_ok"] is True


def test_turn_and_tool_times_split_thinking_from_tool_time(lt, runs):
    turns = _trace(lt, runs)["steps"]
    t0 = 1794800000.0
    ns = lambda s: round(s * 1_000_000) * 1000
    assert turns[1]["start_ns"] == turns[0]["tools"][-1]["end_ns"] == ns(t0 + 4.7)   # after the last output
    assert turns[1]["end_ns"] == turns[1]["tools"][0]["start_ns"] == ns(t0 + 9.0)
    assert turns[1]["tools"][0]["end_ns"] == ns(t0 + 9.2)


def test_a_timed_out_task_without_a_patch(lt, runs):
    t = _trace(lt, runs, "demo_102")
    assert t["tags"]["outcome_code"] == "no_patch" and t["tags"]["ended_code"] == "time_cap"
    assert t["root"]["is_ok"] is False and [s["tools"] for s in t["steps"]] == [[]]


def test_no_secret_reaches_a_span(lt, runs):
    text = json.dumps(_trace(lt, runs), default=str)
    assert FAKE not in text and "def add(a, b)" in text


def test_a_second_load_writes_nothing(lt, runs):
    client = FakeClient()
    first = lt.load_run(runs, "demo-run", "demo agent", client)
    again = lt.load_run(runs, "demo-run", "demo agent", client)
    assert first == {"written": 2, "skipped": 0, "failed": 0, "unconfirmed": 0}
    assert again == {"written": 0, "skipped": 2, "failed": 0, "unconfirmed": 0} and len(client.traces) == 2
    tags = client.traces[0]["tags"]
    assert {"loaded_ts", "git_commit_sha"} <= set(tags) and tags["loaded_ts"].endswith("Z")


def test_a_write_that_never_arrives_is_counted_unconfirmed(lt, runs):
    """November 17: traces started without the experiment's Unity Catalog location set were dropped with no error.
    The loader checks every key it wrote is in the experiment afterwards."""
    assert lt.load_run(runs, "demo-run", "demo agent", DroppingClient())["unconfirmed"] == 2


def test_dry_run_builds_and_writes_nothing(lt, runs):
    client = FakeClient()
    assert lt.load_run(runs, "demo-run", "demo agent", client, dry_run=True) == {"written": 0, "skipped": 0,
                                                                                 "failed": 0, "built": 2}
    assert client.traces == []


def test_limit(lt, runs):
    client = FakeClient()
    assert lt.load_run(runs, "demo-run", "demo agent", client, limit=1)["written"] == 1


def test_a_missing_setting_fails_at_once_and_names_it(lt, runs, monkeypatch, capsys):
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    with pytest.raises(SystemExit) as e:
        lt.main([str(runs), "--label", "demo-run", "--agent", "demo agent"])
    assert "DATABRICKS_HOST" in str(e.value)
    with pytest.raises(SystemExit) as e:
        lt.main([str(runs / "nowhere"), "--label", "demo-run", "--agent", "demo agent", "--dry-run"])
    assert "nowhere" in str(e.value)


def test_model_name_is_on_every_turn_when_given(lt, runs):
    t = lt.task_trace(runs / "demo-run/tasks/demo_101", "demo-run", "demo agent", model_name="gemma-4-31b")
    assert {s["attributes"]["mlflow.llm.model"] for s in t["steps"]} == {"gemma-4-31b"}


def test_spans_carry_the_opentelemetry_genai_names(lt, runs):
    """Databricks' trace charts follow OpenTelemetry's GenAI conventions: a tool call is an execute_tool operation
    with gen_ai.tool.name, a model turn a chat operation with its model and token use, the task an invoke_agent."""
    t = lt.task_trace(runs / "demo-run/tasks/demo_101", "demo-run", "demo agent", model_name="gemma-4-31b")
    turn, tool = t["steps"][0], t["steps"][0]["tools"][0]
    assert tool["attributes"]["gen_ai.operation.name"] == "execute_tool"
    assert tool["attributes"]["gen_ai.tool.name"] == tool["name"] == "run_command"
    assert turn["attributes"]["gen_ai.operation.name"] == "chat"
    assert turn["attributes"]["gen_ai.request.model"] == turn["attributes"]["gen_ai.response.model"] == "gemma-4-31b"
    assert (turn["attributes"]["gen_ai.usage.input_tokens"], turn["attributes"]["gen_ai.usage.output_tokens"]) == (1000, 50)
    assert t["root"]["attributes"]["gen_ai.operation.name"] == "invoke_agent"
    assert t["root"]["attributes"]["gen_ai.agent.name"] == "demo agent"


def _verdicts(tmp_path, rows):
    p = tmp_path / "verdicts.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_read_verdicts_maps_each_task_to_resolved(lt, tmp_path):
    """#881: official_verify.py writes one JSON line per task; extra fields and blank lines are ignored."""
    p = _verdicts(tmp_path, [{"instance_id": "demo_101", "resolved": False, "seconds": 3.1},
                             {"instance_id": "demo_102", "resolved": True}])
    p.write_text(p.read_text() + "\n")
    assert lt.read_verdicts(p) == {"demo_101": False, "demo_102": True}


def test_a_verdict_overrides_the_kernels_is_resolved(lt, runs):
    """#881: on this repository's own tasks the kernel says "Missing test specification"; the verifier's verdict wins."""
    t = lt.task_trace(runs / "demo-run/tasks/demo_102", "demo-run", "demo agent", verdicts={"demo_102": True})
    assert t["tags"]["is_resolved"] == "true" and t["tags"]["outcome_code"] == "solved"
    assert t["tags"]["verdict_source_code"] == "official_verify" and t["root"]["is_ok"] is True
    t = lt.task_trace(runs / "demo-run/tasks/demo_101", "demo-run", "demo agent", verdicts={"demo_101": False})
    assert t["tags"]["is_resolved"] == "false" and t["tags"]["outcome_code"] == "patch_failed"
    assert t["root"]["is_ok"] is False


def test_a_task_missing_from_the_verdicts_is_not_loaded(lt, runs, capsys):
    client = FakeClient()
    counts = lt.load_run(runs, "demo-run", "demo agent", client, verdicts={"demo_101": True})
    assert counts == {"written": 1, "skipped": 0, "failed": 1, "unconfirmed": 0}
    assert "demo_102: not loaded (no verdict)" in capsys.readouterr().out
    assert client.traces[0]["tags"]["verdict_source_code"] == "official_verify"


def test_the_cli_reads_the_verdicts_file(lt, runs, tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(lt, "load_run", lambda *a, **k: seen.update(k) or {"written": 0, "skipped": 0, "failed": 0})
    p = _verdicts(tmp_path, [{"instance_id": "demo_101", "resolved": True}])
    assert lt.main([str(runs), "--label", "demo-run", "--agent", "demo agent", "--dry-run", "--verdicts", str(p)]) == 0
    assert seen["verdicts"] == {"demo_101": True}


NO_SPEC = "Missing test specification (empty test_patch and FAIL_TO_PASS; secret hydration failed or unavailable)"


def _with_result(runs, iid, **changes):
    p = runs / "demo-run/tasks" / iid / "result.json"
    r = json.loads(p.read_text())
    r.update(changes)
    p.write_text(json.dumps(r))


def test_the_kernels_missing_test_spec_note_is_not_the_runs_error(lt, runs):
    """#894: the kernel cannot grade our own repositories' tasks, whose tests are kept out of the agent's bundle. That
    note is about grading, not the run: the agent ended by itself, and the trace must say so."""
    _with_result(runs, "demo_101", agent_error=None, error_text=NO_SPEC)
    t = lt.task_trace(runs / "demo-run/tasks/demo_101", "demo-run", "demo agent", verdicts={"demo_101": True})
    assert t["tags"]["ended_code"] == "ended_itself" and t["tags"]["kernel_grade_code"] == "no_test_spec"
    assert t["root"]["outputs"]["error_text"] == "" and t["root"]["outputs"]["ended_code"] == "ended_itself"
    assert lt._run_error({"agent_error": None, "error_text": NO_SPEC}) is None


def test_a_real_error_still_wins_over_the_note(lt, runs):
    _with_result(runs, "demo_102", error_text=NO_SPEC)
    t = lt.task_trace(runs / "demo-run/tasks/demo_102", "demo-run", "demo agent", verdicts={"demo_102": False})
    assert t["tags"]["ended_code"] == "time_cap" and t["tags"]["kernel_grade_code"] == "no_test_spec"
    assert lt._run_error({"agent_error": "Agent exceeded session timeout (5.0 min)", "error_text": NO_SPEC}).startswith("Agent")
