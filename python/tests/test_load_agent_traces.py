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
                         "outcome_code": "solved", "ended_code": "ended_itself", "is_resolved": "true"}


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
