"""Spec 035 US2 (#544): Gemma 4 as the harness's model, and the per-task bundle that runs it on a Kaggle GPU without
anything that holds an answer: Gemma 4's own tool-call format in and out (the chat template's, read on Kaggle), and
a bundle with one task's snapshot, no reference patch or tests, and none of this repository's later code."""
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

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
    # -I keeps the repo package off the path; numpy (on Kaggle's image) is put back by hand, since -I also drops the
    # user site, where the deploy job's pip installs it ("Defaulting to user installation")
    import numpy
    numpy_dir = str(Path(numpy.__file__).resolve().parent.parent)
    r = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(out)!r}); "
                        f"sys.path.append({numpy_dir!r}); "
                        "import htl_agent.agent_harness as h, htl_agent.gemma_agent as g; "
                        "assert not any(m.startswith('health_transformation_lab_nlp') for m in sys.modules); "
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


def test_a_thought_without_its_opening_marker_is_dropped():   # seen on Kaggle with thinking off (htlnlp_170)
    r = ga.parse_reply("I will read the file first.<channel|>Reading.<|tool_call>call:get_status{}<tool_call|>",
                       hit_limit=False)
    assert r["content"] == "Reading." and r["tool_calls"][0]["name"] == "get_status"


# --- turn after turn: only the new tokens are read (the cache keeps the rest) ------------------------------------

def _enc(text):   # a stand-in tokenizer: one id per character
    return [ord(c) for c in text]


def _render(name, response):   # a stand-in for the chat template's tool_response text
    return f"response:{name}{{{json.dumps(response, sort_keys=True)}}}"


def _call(cid, name, args):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def test_tool_results_extend_the_tokens_the_model_already_read():
    prev = _enc("PROMPT<|tool_call>call:get_status{}<tool_call|><|tool_response>")   # ends at the stop marker
    new = [{"role": "assistant", "content": "", "tool_calls": [_call("a", "get_status", {})]},
           {"role": "tool", "tool_call_id": "a", "content": json.dumps({"status": "ok"})}]
    ids = ga.extend_ids(prev, new, _render, _enc)
    assert ids == prev + _enc('response:get_status{{"status": "ok"}}<tool_response|>')


def test_several_results_each_get_their_marker_after_the_first():
    prev = _enc("P<|tool_response>")
    new = [{"role": "assistant", "content": "", "tool_calls": [_call("a", "x", {}), _call("b", "y", {})]},
           {"role": "tool", "tool_call_id": "a", "content": "1"}, {"role": "tool", "tool_call_id": "b", "content": "2"}]
    assert ga.extend_ids(prev, new, _render, _enc) == prev + _enc(
        "response:x{1}<tool_response|><|tool_response>response:y{2}<tool_response|>")


def test_a_nudge_after_a_closed_turn_opens_a_new_one():
    prev = _enc("P Done.<turn|>")
    new = [{"role": "assistant", "content": "Done."}, {"role": "user", "content": "Please continue"}]
    assert ga.extend_ids(prev, new, _render, _enc) == prev + _enc(
        "\n<|turn>user\nPlease continue<turn|>\n<|turn>model\n")


@pytest.mark.parametrize("prev,new", [
    ("P<turn|>", [{"role": "assistant", "content": "", "tool_calls": [_call("a", "x", {})]},
                  {"role": "tool", "tool_call_id": "a", "content": "1"}]),          # results after a closed turn
    ("P<|tool_response>", [{"role": "assistant", "content": "", "tool_calls": [_call("a", "x", {})]},
                           {"role": "tool", "tool_call_id": "a", "content": "1"},
                           {"role": "user", "content": "nudge"}]),                  # a user turn inside an open one
    ("P", []),                                                                        # nothing new
])
def test_any_other_shape_falls_back_to_a_full_render(prev, new):
    assert ga.extend_ids(_enc(prev), new, _render, _enc) is None


def test_a_row_carries_its_token_totals(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(runner.ah, "score_patch", lambda task, row, patch, src, work, sandboxed: {**row, "is_resolved": True})
    settings = {"name": "m", "budget": {"time_minutes": 30}, "model": {"max_new_tokens": 2048, "reuse_cache": True}}
    turns = [{"prompt_tokens": 100, "prefill_tokens": 100, "output_tokens": 10, "seconds": 2.0},
             {"prompt_tokens": 150, "prefill_tokens": 40, "output_tokens": 5, "seconds": 1.5}]
    row = runner.row_for({"instance_id": "x"}, {"row": {"instance_id": "x"}, "patch": "", "turns": turns},
                         tmp_path / "s.tgz", tmp_path, "u", settings)
    assert (row["prompt_token_count"], row["prefill_token_count"], row["output_token_count"]) == (250, 140, 15)
    assert row["is_cache_reused"] is True and row["model_seconds"] == 3.5


# --- what each task cost (spec 036 US2, #569) ----------------------------------------------------------------------

COST = {"kaggle_weekly_allowance_hours": {"value": 30.0, "source": "s", "read_date": "d"},
        "t4_usd_per_gpu_hour": {"value": 0.69, "source": "s", "read_date": "d"}}


def test_a_row_carries_its_session_time_gpu_hours_and_estimate(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(runner.ah, "score_patch", lambda task, row, patch, src, work, sandboxed: {**row, "is_resolved": True})
    settings = {"name": "m", "budget": {"time_minutes": 30}, "model": {"max_new_tokens": 2048}}
    result = {"row": {"instance_id": "x"}, "patch": "", "turns": [], "gpus": ["Tesla T4", "Tesla T4"],
              "started_ts": "2026-11-04T20:00:00Z", "finished_ts": "2026-11-04T20:05:00Z"}
    row = runner.row_for({"instance_id": "x"}, result, tmp_path / "s.tgz", tmp_path, "u", settings, 900.0, COST)
    assert row["script_seconds"] == 300.0 and row["session_seconds"] == 900.0 and row["gpu_count"] == 2
    assert row["allowance_hours"] == 0.25 and row["gpu_hours"] == 0.5
    assert row["estimated_cost_usd"] == pytest.approx(0.345) and row["price_basis_text"].startswith("estimate:")
    assert set(runner.EXTRA) >= {"session_seconds", "gpu_hours", "kaggle_allowance_ratio", "estimated_cost_usd"}


def test_a_failed_kernel_still_counts_its_session(runner, tmp_path):
    settings = {"name": "m", "budget": {"time_minutes": 30}, "model": {}}
    row = runner.row_for({"instance_id": "x"}, {"error": "OutOfMemoryError"}, tmp_path / "s.tgz", tmp_path, "u",
                         settings, 1140.0, COST)
    assert row["is_resolved"] is False and row["allowance_hours"] == pytest.approx(1140 / 3600, abs=1e-4)


def test_the_queue_runs_cheapest_first_and_small_fixes_first_among_the_unrun(runner):
    tasks = {"a": {"patch": "x" * 50}, "b": {"patch": "x" * 10}, "c": {"patch": "x" * 99}}
    q = runner.queue(["a", "b", "c"], tasks, past={"c": 300.0, "d": 900.0})
    assert list(q) == ["c", "b", "a"]                     # c ran in 5 min; b and a expect the median, smaller first
    assert q["a"] == q["b"] == 600.0


def test_an_upload_kaggle_drops_is_tried_again(runner, tmp_path, monkeypatch):   # a 499 ended a stretch (#615)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setattr(runner, "_wait_dataset", lambda api, ref: None)

    class Api:
        calls = 0

        def dataset_status(self, ref):
            raise RuntimeError("404")

        def dataset_create_new(self, folder, public, dir_mode):
            Api.calls += 1
            if Api.calls < 3:
                raise RuntimeError("499 Client Error")
            return type("R", (), {"status": "ok"})()

    runner._upload_bundle(Api(), tmp_path, "u/x")
    assert Api.calls == 3


def test_an_upload_that_keeps_failing_still_fails(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)

    class Api:
        def dataset_status(self, ref):
            raise RuntimeError("404")

        def dataset_create_new(self, folder, public, dir_mode):
            raise RuntimeError("499 Client Error")

    with pytest.raises(RuntimeError):
        runner._upload_bundle(Api(), tmp_path, "u/x")


def test_the_workflow_runs_the_batch_and_keeps_its_rows():   # #615: not tied to a cloud session's container
    import yaml
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "kaggle-agent.yml").read_text())
    job = wf["jobs"]["run"]
    assert job["environment"] == "dev" and job["timeout-minutes"] < 360
    text = "\n".join(str(s.get("run", "")) for s in job["steps"])
    assert "health-transformation-lab-coding-agent-tasks" in text            # the published, gated set
    assert "apparmor_restrict_unprivileged_userns=0" in text                  # the scoring sandbox's unshare
    assert "60_kaggle_agent.py --ids" in text and "--max-gpu-hours" in text
    keep = [s for s in job["steps"] if "git push" in str(s.get("run", ""))]
    assert keep and keep[0].get("if") == "always()"                          # rows kept even when a step fails
    assert "concurrency" in wf


def test_the_graph_is_found_under_either_name(runner, tmp_path):   # #621: local builds name it by instance id
    task = {"instance_id": "htlnlp_9", "repo": "o/r", "base_commit": "abc"}
    (tmp_path / "g").mkdir(), (tmp_path / "e").mkdir()
    (tmp_path / "g" / "htlnlp_9.json").write_text("{}")
    (tmp_path / "e" / "htlnlp_9.npz").write_bytes(b"")
    assert runner.graph_files(task, tmp_path / "g", tmp_path / "e") == (tmp_path / "g" / "htlnlp_9.json",
                                                                       tmp_path / "e" / "htlnlp_9.npz")
    (tmp_path / "g" / "r_abc.json").write_text("{}")
    assert runner.graph_files(task, tmp_path / "g", tmp_path / "e")[0] == tmp_path / "g" / "r_abc.json"


def test_a_task_without_its_graph_stops_the_run_before_any_upload(runner, tmp_path):
    task = {"instance_id": "htlnlp_9", "repo": "o/r", "base_commit": "abc"}
    with pytest.raises(SystemExit, match="htlnlp_9"):
        runner.check_graphs([task], tmp_path, tmp_path, ["read_file", "search_similar_code"])
    runner.check_graphs([task], tmp_path, tmp_path, ["read_file", "edit_file"])   # no graph tools: nothing needed


def test_the_workflow_keeps_the_transcripts_and_ends_inside_the_job():   # #621
    import yaml
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "kaggle-agent.yml").read_text())
    steps = wf["jobs"]["run"]["steps"]
    keep = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert keep and keep[0]["if"] == "always()" and "/output" in keep[0]["with"]["path"]
    assert "h <= 5 " in "\n".join(str(s.get("run", "")) for s in steps)


# --- the Colab run (#656) ------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def colab():
    import importlib.util
    spec = importlib.util.spec_from_file_location("colab_agent", REPO_ROOT / "python" / "scripts" / "62_colab_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_colab_bundles_have_their_own_slug_and_the_fuller_settings(colab):
    assert colab.colab_slug("htlnlp_pr56") == "htlnlp-colab-htlnlp-pr56" != runner_slug("htlnlp_pr56")
    assert colab.MODEL_CFG["max_new_tokens"] == 16384 and colab.MODEL_CFG["thinking"] is True
    assert (colab.BUDGET.tool_calls, colab.BUDGET.turns, colab.BUDGET.command_timeout) == (100, 500, 300)


def runner_slug(i):
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent_bundle", REPO_ROOT / "kaggle" / "agent_bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.slug(i)


def test_the_notebook_runs_one_task_at_a_time_and_resumes():
    nb = json.loads((REPO_ROOT / "kaggle" / "colab_agent.ipynb").read_text())
    src = "\n".join("".join(c["source"]) for c in nb["cells"])
    assert 'userdata.get("KAGGLE_API_TOKEN")' in src and "KAGGLE_API_TOKEN=" not in src.replace('os.environ["KAGGLE_API_TOKEN"] =', "")
    assert "shutil.rmtree(bundle" in src and "done = {p.stem" in src     # one bundle on disk; done tasks skipped
    assert "htlnlp-colab-results" in src


def test_the_bundle_check_reads_a_snapshot_another_user_owns():
    src = (REPO_ROOT / "kaggle" / "agent_bundle.py").read_text()
    assert '"safe.directory=*"' in src
