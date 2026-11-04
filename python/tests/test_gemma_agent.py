"""Spec 035 US2 (#544): Gemma 4 as the harness's model, and the per-task bundle that runs it on a Kaggle GPU without
anything that holds an answer: Gemma 4's own tool-call format in and out (the chat template's, read on Kaggle), and
a bundle with one task's snapshot, no reference patch or tests, and none of this repository's later code."""
import io
import json
import subprocess
import sys
import tarfile

import pytest

from health_transformation_lab_nlp import agent_harness as ah
from health_transformation_lab_nlp import gemma_agent as ga
from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

Q = '<|"|>'


# --- replies: Gemma 4's tool-call format ------------------------------------------------------------------------

def test_a_tool_call_is_parsed_with_its_typed_arguments():
    r = ga.parse_reply(f"<|tool_call>call:read_file{{filepath:{Q}python/a.py{Q},start_line:3,end_line:9}}<tool_call|>",
                       hit_limit=False)
    assert r["tool_calls"] == [{"id": "call-0", "name": "read_file",
                                "arguments": {"filepath": "python/a.py", "start_line": 3, "end_line": 9}}]
    assert r["finish_reason"] == "tool_calls" and r["content"] == ""


def test_strings_keep_every_character_the_delimiters_hold():
    code = 'def f(x):\n    return {"a": [1, 2]}, x  # :,{}[]\n'
    r = ga.parse_reply(f"<|tool_call>call:edit_file{{filepath:{Q}a.py{Q},old_string:{Q}x{Q},new_string:{Q}{code}{Q},"
                       f"allow_multiple:false}}<tool_call|>", hit_limit=False)
    assert r["tool_calls"][0]["arguments"] == {"filepath": "a.py", "old_string": "x", "new_string": code,
                                               "allow_multiple": False}


def test_nested_lists_and_objects_parse():
    r = ga.parse_reply(f"<|tool_call>call:get_code_subgraph{{nodes:[{Q}a.b{Q},{Q}c.d{Q}],opts:{{k:2}}}}<tool_call|>",
                       hit_limit=False)
    assert r["tool_calls"][0]["arguments"] == {"nodes": ["a.b", "c.d"], "opts": {"k": 2}}


def test_several_calls_text_and_thinking():
    text = (f"<|channel>thought\nI should look first.<channel|>Looking.<|tool_call>call:get_status{{}}<tool_call|>"
            f"<|tool_call>call:run_command{{command:{Q}ls{Q}}}<tool_call|>")
    r = ga.parse_reply(text, hit_limit=False)
    assert [c["name"] for c in r["tool_calls"]] == ["get_status", "run_command"]
    assert [c["id"] for c in r["tool_calls"]] == ["call-0", "call-1"]
    assert r["content"] == "Looking." and "thought" not in r["content"]


def test_json_arguments_are_accepted_too():
    r = ga.parse_reply('<|tool_call>call:read_file{"filepath": "a.py"}<tool_call|>', hit_limit=False)
    assert r["tool_calls"][0]["arguments"] == {"filepath": "a.py"}


def test_plain_text_and_a_cut_off_call():
    assert ga.parse_reply("Done.<turn|>", hit_limit=False) == {"content": "Done.", "tool_calls": [],
                                                                "finish_reason": "stop"}
    cut = ga.parse_reply(f"<|tool_call>call:write_file{{filepath:{Q}a.py{Q},content:{Q}def", hit_limit=True)
    assert cut["tool_calls"] == [] and cut["finish_reason"] == "length"
    assert "<|tool_call>" in cut["content"]                     # so the harness sends its unclosed-call nudge
    assert ah._nudge(cut) == ah.NUDGE_UNCLOSED


def test_unparseable_arguments_come_back_as_an_error_not_a_crash():
    r = ga.parse_reply("<|tool_call>call:read_file{filepath:<tool_call|>", hit_limit=False)
    assert r["tool_calls"][0]["name"] == "read_file" and isinstance(r["tool_calls"][0]["arguments"], str)
    s = ah.Session(REPO_ROOT)
    assert json.loads(ah.call_tool(s, "read_file", r["tool_calls"][0]["arguments"]))["status"] == "error"


# --- messages: the harness's OpenAI-style history in Gemma 4's shape ------------------------------------------------

def test_tool_results_go_back_inside_the_model_turn_that_called_them():
    history = [
        {"role": "system", "content": "SYS"}, {"role": "user", "content": "Fix it"},
        {"role": "assistant", "content": "<|channel>thought\nhmm<channel|>", "tool_calls": [
            {"id": "a", "type": "function", "function": {"name": "read_file", "arguments": '{"filepath": "x.py"}'}},
            {"id": "b", "type": "function", "function": {"name": "get_status", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "a", "content": json.dumps({"status": "ok", "content": "1"})},
        {"role": "tool", "tool_call_id": "b", "content": "not json"},
        {"role": "user", "content": "Please continue"},
    ]
    out = ga.to_gemma_messages(history)
    assert [m["role"] for m in out] == ["system", "user", "assistant", "user"]
    a = out[2]
    assert a["tool_calls"][0]["function"]["arguments"] == {"filepath": "x.py"}   # a mapping, as the template wants
    assert a["tool_responses"] == [{"name": "read_file", "response": {"status": "ok", "content": "1"}},
                                   {"name": "get_status", "response": "not json"}]
    assert a["content"] == ""                                                    # thoughts aren't sent back


# --- the bundle: one task, nothing that holds an answer ------------------------------------------------------------

@pytest.fixture(scope="module")
def sample():
    rows = [json.loads(line) for line in (TASKS_DIR / "tasks_sample.jsonl").read_text().splitlines() if line.strip()]
    return rows[0]


def _snapshot(tmp_path, commits=1):
    src = tmp_path / "src"
    src.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=src, check=True)
    for n in range(commits):
        (src / f"f{n}.py").write_text(f"x = {n}\n")
        subprocess.run(["git", "add", "-A"], cwd=src, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", f"c{n}"], cwd=src,
                       check=True)
    tgz = tmp_path / "snap.tgz"
    with tarfile.open(tgz, "w:gz") as t:
        t.add(src, arcname=".")
    return tgz


def test_the_bundle_holds_one_task_without_its_answer(tmp_path, sample):
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent_bundle", REPO_ROOT / "kaggle" / "agent_bundle.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    out = ab.build(sample, _snapshot(tmp_path), None, None, tmp_path / "b", "SYSTEM PROMPT", ["read_file"],
                   ah.Budget(time_minutes=30))
    task = json.loads((out / "task.json").read_text())
    assert set(task) <= ab.TASK_FIELDS and "patch" not in task and "test_patch" not in task
    assert task["problem_statement"] == sample["problem_statement"]
    code = sorted(p.name for p in (out / "htl_agent").iterdir())
    assert code == ["__init__.py", "agent_harness.py", "gemma_agent.py", "task_gate.py", "telemetry.py"]
    assert "opentelemetry" not in (out / "htl_agent" / "telemetry.py").read_text()   # a stub, not ours
    cfg = json.loads((out / "agent.json").read_text())
    assert cfg["instruction"] == "SYSTEM PROMPT" and cfg["budget"]["time_minutes"] == 30
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert names == {"task.json", "agent.json", "snapshot.tgz", "dataset-metadata.json",
                     *(f"htl_agent/{c}" for c in code)}
    meta = json.loads((out / "dataset-metadata.json").read_text())
    assert meta["id"].endswith("/htlnlp-agent-" + sample["instance_id"].replace("_", "-"))


def test_a_snapshot_with_history_is_refused(tmp_path, sample):
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent_bundle", REPO_ROOT / "kaggle" / "agent_bundle.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    with pytest.raises(SystemExit, match="commit"):
        ab.build(sample, _snapshot(tmp_path, commits=2), None, None, tmp_path / "b", "", ["read_file"], ah.Budget())


def test_no_task_changes_the_code_the_bundle_ships():
    """agent_harness.py, gemma_agent.py and task_gate.py go to Kaggle beside the task; telemetry.py is replaced by a
    stub, since tasks change it. A task whose fix touched a shipped file would hand the agent its answer."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent_bundle", REPO_ROOT / "kaggle" / "agent_bundle.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    tasks = TASKS_DIR / "tasks.jsonl"
    rows = [json.loads(line) for line in (tasks if tasks.exists() else TASKS_DIR / "tasks_sample.jsonl")
            .read_text().splitlines() if line.strip()]
    for r in rows:
        assert ab.touched_shipped(r) == [], r["instance_id"]



def test_the_shipped_code_imports_without_the_rest_of_the_package(tmp_path, sample):
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent_bundle", REPO_ROOT / "kaggle" / "agent_bundle.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    out = ab.build(sample, _snapshot(tmp_path), None, None, tmp_path / "b", "", ["read_file"], ah.Budget())
    r = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(out)!r}); "
                        "import htl_agent.agent_harness as h, htl_agent.gemma_agent as g; "
                        "print(h.HARNESS_NAME, g.parse_reply('x', hit_limit=False)['content'])"],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["htlnlp-harness-v1", "x"]


# --- the runner: python/scripts/60_kaggle_agent.py ---------------------------------------------------------------

@pytest.fixture(scope="module")
def runner():
    import importlib.util
    spec = importlib.util.spec_from_file_location("kaggle_agent", REPO_ROOT / "python" / "scripts" / "60_kaggle_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_kernel_is_private_offline_and_sees_one_task(runner):
    m = runner.kernel_metadata("someone", "htlnlp-agent-htlnlp-170", "google/gemma-4/transformers/gemma-4-e4b-it/1")
    assert m["is_private"] and m["enable_gpu"] and not m["enable_internet"]
    assert m["dataset_sources"] == ["someone/htlnlp-agent-htlnlp-170"] and m["kernel_sources"] == []
    assert m["id"] == "someone/htlnlp-run-htlnlp-170" == f"someone/{runner.kernel_slug('htlnlp_170')}"   # 409 otherwise
    assert m["model_sources"] == ["google/gemma-4/transformers/gemma-4-e4b-it/1"]


def test_a_rerun_replaces_its_tasks_row(runner, tmp_path):
    path = tmp_path / "runs.csv"
    runner.merge_rows(path, [{"instance_id": "b", "is_resolved": False}, {"instance_id": "a", "is_resolved": True}]
                      ).to_csv(path, index=False)
    out = runner.merge_rows(path, [{"instance_id": "b", "is_resolved": True}])
    assert out["instance_id"].tolist() == ["a", "b"] and out["is_resolved"].tolist() == [True, True]
    assert list(out.columns) == ah.RUN_COLUMNS + runner.EXTRA


def test_a_failed_kernel_is_a_row_not_a_crash(runner, tmp_path):
    settings = {"name": "gemma-4-e4b-it", "budget": {"time_minutes": 30}, "model": {"max_new_tokens": 2048}}
    row = runner.row_for({"instance_id": "x"}, {"error": "OutOfMemoryError: CUDA"}, tmp_path / "s.tgz", tmp_path,
                         "https://www.kaggle.com/code/u/k", settings)
    assert row["is_resolved"] is False and row["error_text"].startswith("OutOfMemoryError")
