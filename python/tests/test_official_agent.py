"""Spec 028 US5 (T011b, #636): the agent through the competition's own evaluator on a Kaggle GPU. The bundle one
task runs beside holds no reference patch and no tests; the sample is drawn with a seed and stratified by tier, never
by cost; the kernel is private, offline, and sees one task's bundle, the competition's wheelhouse and the model."""
import importlib.util
import json
import subprocess
import tarfile

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "kaggle" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ob():
    return _load("official_agent_bundle")


@pytest.fixture(scope="module")
def run():
    return _load("official_agent_run")


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


TASK = {"instance_id": "htlnlp_7", "repo": "healthtransformationlab/health-transformation-lab-nlp",
        "base_commit": "a" * 40, "problem_statement": "The loader drops the last row.", "hints_text": "see #6",
        "created_at": "2026-10-27T00:00:00Z", "patch": "diff --git a/x.py b/x.py\n+SECRET_FIX = 1\n",
        "test_patch": "diff --git a/tests/test_x.py b/tests/test_x.py\n+SECRET_TEST = 1\n"}


def _submission(tmp_path):
    sub = tmp_path / "agent"
    (sub / "prompts").mkdir(parents=True)
    (sub / "paper").mkdir()
    (sub / "agent.yaml").write_text("name: a\nmodel: gemma-4-e4b-it-qat-w4a16-ct\n")
    (sub / "eval_config.yaml").write_text("evaluation:\n  max_tool_calls: 40\n")
    (sub / "prompts" / "system.md").write_text("fix it")
    (sub / "paper" / "writeup.md").write_text("not part of the submission")
    (sub / "README.md").write_text("not part of the submission")
    return sub


def test_the_bundle_holds_one_task_in_the_evaluators_layout_without_its_answer(ob, tmp_path):
    graph, emb = tmp_path / "g.json", tmp_path / "e.npz"
    graph.write_text("{}")
    emb.write_bytes(b"npz")
    out = ob.build(TASK, _snapshot(tmp_path), graph, emb, _submission(tmp_path), tmp_path / "b", "someone")
    row = json.loads((out / "tasks.jsonl").read_text())
    assert not row.get("patch") and not row.get("test_patch")
    assert {k: row[k] for k in ("instance_id", "repo", "base_commit", "problem_statement", "hints_text")} == \
        {k: TASK[k] for k in ("instance_id", "repo", "base_commit", "problem_statement", "hints_text")}
    stem = "health-transformation-lab-nlp_" + "a" * 40          # the competition's name for a graph or embedding
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert names == {"official_task.json", "tasks.jsonl", "snapshots/htlnlp_7.tgz", f"graphs/{stem}.json",
                     f"embeddings/{stem}.npz", "submission/agent.yaml", "submission/eval_config.yaml",
                     "submission/prompts/system.md", "dataset-metadata.json"}
    for p in out.rglob("*"):                                    # the answer is in no file of the bundle
        if p.is_file() and p.suffix != ".tgz":
            assert b"SECRET_" not in p.read_bytes(), p
    assert json.loads((out / "official_task.json").read_text())["instance_id"] == "htlnlp_7"
    assert json.loads((out / "dataset-metadata.json").read_text())["id"] == "someone/htlnlp-official-htlnlp-7"


def test_the_bundle_carries_budget_overrides_and_refuses_a_snapshot_with_history(ob, tmp_path):
    out = ob.build(TASK, _snapshot(tmp_path), None, None, _submission(tmp_path), tmp_path / "b", "someone",
                   budget_overrides={"max_time_minutes": 10.0})
    assert json.loads((out / "official_task.json").read_text())["budget_overrides"] == {"max_time_minutes": 10.0}
    (tmp_path / "two").mkdir()
    with pytest.raises(SystemExit, match="commit"):
        ob.build(TASK, _snapshot(tmp_path / "two", commits=2), None, None, tmp_path / "agent", tmp_path / "c", "someone")


def test_a_submission_without_an_agent_config_is_refused(ob, tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit, match="agent.yaml"):
        ob.build(TASK, _snapshot(tmp_path), None, None, tmp_path / "empty", tmp_path / "b", "someone")


def test_the_sample_is_seeded_and_stratified_by_tier(run):
    tiers = {f"a{i}": "A" for i in range(39)} | {f"b{i}": "B" for i in range(34)} | {f"c{i}": "C" for i in range(20)}
    s = run.sample(tiers, 20, seed=7)
    assert len(s) == len(set(s)) == 20 and set(s) <= set(tiers)
    counts = {t: sum(tiers[i] == t for i in s) for t in "ABC"}
    assert counts == {"A": 9, "B": 7, "C": 4}                    # 20 x 39/93, 34/93, 20/93, largest remainder
    assert s == run.sample(dict(reversed(list(tiers.items()))), 20, seed=7)   # the order of the input does not matter
    assert s != run.sample(tiers, 20, seed=8)
    assert s == sorted(s)


def test_the_sample_never_asks_for_more_than_there_is(run):
    with pytest.raises(SystemExit, match="only 3"):
        run.sample({"a": "A", "b": "B", "c": "C"}, 4, seed=1)
    assert run.sample({"a": "A", "b": "B", "c": "C"}, 3, seed=1) == ["a", "b", "c"]


def test_the_kernel_is_private_offline_and_sees_one_task_the_wheelhouse_and_the_model(run):
    meta = run.kernel_metadata("someone", "htlnlp_7", "NvidiaL4", None)
    assert meta["id"] == "someone/htlnlp-offrun-htlnlp-7" and meta["code_file"] == "official_agent_kernel.py"
    assert meta["is_private"] is True and meta["enable_internet"] is False and meta["enable_gpu"] is True
    assert meta["dataset_sources"] == ["someone/htlnlp-official-htlnlp-7", run.WHEELHOUSE]
    assert meta["model_sources"] == [run.MODEL_SOURCE] and meta["competition_sources"] == []
    assert meta["machine_shape"] == "NvidiaL4" and "docker_image" not in meta
    assert run.kernel_metadata("someone", "htlnlp_7", None, "img@sha256:1")["docker_image"] == "img@sha256:1"


def test_a_run_row_records_the_harness_the_settings_and_the_evaluators_verdict(run):
    result = {"instance_id": "htlnlp_7", "patch": "diff --git a/x b/x\n", "tool_call_count": 6, "llm_call_count": 8,
              "agent_phase_seconds": 61.2, "load_seconds": 200.0, "model_name": "gemma-4-e4b-it-qat-w4a16-ct",
              "harness_name": "swegemma (Evaluator.evaluate_task, subprocess sandbox)",
              "versions": {"swegemma": "0.2.11", "vllm": "0.19.1"},
              "server": {"gpus": ["NVIDIA L4"] * 4, "tensor_parallel_size": 4, "dtype": "bfloat16"},
              "budgets": {"timeout_seconds": 120, "max_tool_calls": 40, "max_time_minutes": 5.0, "max_turns": 60},
              "generation_defaults": {"max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096}}}
    verdict = {"resolved": True, "test_exit_code": 0, "error": None}
    result.update(started_ts="2026-11-10T15:00:00Z", finished_ts="2026-11-10T15:10:30Z")
    row = run.row_for(result, verdict, tier="A", kernel_url="https://k")
    assert row["script_seconds"] == 630.0 and row["run_ts"] == "2026-11-10T15:10:30Z"
    assert list(row) == run.COLUMNS
    assert row["is_resolved"] is True and row["agent_patch_bytes"] == 19 and row["tier_code"] == "A"
    assert row["harness_name"].startswith("swegemma 0.2.11") and row["gpu_count"] == 4 and row["gpu_name"] == "NVIDIA L4"
    assert row["max_time_minutes"] == 5.0 and row["max_output_tokens"] == 16384 and row["thinking_budget"] == 4096
    assert row["is_in_sample"] is True
    failed = run.row_for({"instance_id": "htlnlp_7", "error": "RuntimeError: no GPU"}, None, tier="A", kernel_url="k",
                         in_sample=False)
    assert failed["is_resolved"] is False and failed["reason_text"] == "kernel failed" and "no GPU" in failed["error_text"]
    assert failed["is_in_sample"] is False


def test_the_settings_say_how_the_sample_was_drawn_and_what_differs_from_the_competition(run):
    result = {"model_name": "gemma-4-e4b-it-qat-w4a16-ct", "harness_name": "swegemma (Evaluator.evaluate_task, subprocess sandbox)",
              "versions": {"swegemma": "0.2.11", "vllm": "0.19.1"},
              "server": {"gpus": ["NVIDIA L4"] * 4, "tensor_parallel_size": 4, "dtype": "bfloat16"},
              "budgets": {"timeout_seconds": 120, "verification_timeout_seconds": 300, "max_tool_calls": 40,
                          "max_time_minutes": 5.0, "max_turns": 60},
              "generation_defaults": {"max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096}}}
    s = run.settings_for(result, seed=7, drawn=["a", "b"], pool_count=93, machine_shape="NvidiaL4", docker_image="img",
                         competition="gemma-4-developer-agent", agent_commit="abc123")
    assert s["sample"] == {"seed": 7, "drawn_count": 2, "pool_count": 93, "instance_ids": ["a", "b"],
                           "method_text": s["sample"]["method_text"]} and "stratified" in s["sample"]["method_text"]
    assert s["harness_name"].startswith("swegemma 0.2.11") and s["agent_commit_sha"] == "abc123"
    diffs = {d["setting_name"]: d for d in s["differences_from_competition_defaults"]}
    assert diffs["max_time_minutes"] == {"setting_name": "max_time_minutes", "used": 5.0, "competition_default": 60.0,
                                         "source_text": "the submission's eval_config.yaml"}
    assert diffs["max_tool_calls"]["used"] == 40 and diffs["max_tool_calls"]["competition_default"] == 100
    assert diffs["timeout_seconds"]["used"] == 120 and "max_output_tokens" not in diffs     # the same as the default
    assert any("no reference patch" in n for n in s["notes"])
    assert any(n.startswith("Each task ran alone in a private, offline kernel") for n in s["notes"])
    batch = run.settings_for(result, seed=7, drawn=["a", "b"], pool_count=93, machine_shape="NvidiaL4", docker_image="img",
                             competition="gemma-4-developer-agent", agent_commit="abc123", tasks_per_kernel=2)
    assert not any("Each task ran alone in a private, offline kernel" in n for n in batch["notes"])
    assert any(n.startswith("All 2 tasks were given to one private, offline kernel, each sealed until its turn") for n in batch["notes"])


# --- a batch: several tasks in one kernel, each sealed until its turn (the GPU allowance decides, #636) -----------

def test_a_batch_seals_each_task_and_names_the_order(ob, tmp_path):
    key = bytes(range(32))
    tasks = [dict(TASK, instance_id=f"htlnlp_{n}") for n in (7, 8)]
    snap = _snapshot(tmp_path)
    out = ob.build_batch(tasks, lambda t: (snap, None, None), _submission(tmp_path), tmp_path / "b", "someone", key,
                         order=["htlnlp_8", "htlnlp_7"], settings={"deadline_minutes": 50})
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert names == {"official_batch.json", "sealed/htlnlp_7.bin", "sealed/htlnlp_8.bin", "submission/agent.yaml",
                     "submission/eval_config.yaml", "submission/prompts/system.md", "dataset-metadata.json"}
    meta = json.loads((out / "official_batch.json").read_text())
    assert meta["instance_ids"] == ["htlnlp_8", "htlnlp_7"] and meta["deadline_minutes"] == 50
    for p in out.rglob("*"):                       # nothing readable holds an answer, a statement or the key
        if p.is_file():
            blob = p.read_bytes()
            assert b"SECRET_" not in blob and key.hex().encode() not in blob and key not in blob, p
    sealed = (out / "sealed" / "htlnlp_7.bin").read_bytes()
    assert b"The loader drops" not in sealed and b"ustar" not in sealed      # not a readable tar, not the statement
    assert sealed != (out / "sealed" / "htlnlp_8.bin").read_bytes()           # each task has its own keystream
    assert json.loads((out / "dataset-metadata.json").read_text())["id"] == "someone/htlnlp-official-batch"


def test_the_kernel_opens_what_the_bundle_sealed(ob, tmp_path):
    import ast
    import io
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "unseal")
    ns: dict = {}
    exec("import hashlib\n" + ast.get_source_segment(src, fn), ns)   # noqa: S102 - our own kernel's function
    key = bytes(range(32))
    snap = _snapshot(tmp_path)
    out = ob.build_batch([TASK], lambda t: (snap, None, None), _submission(tmp_path), tmp_path / "b", "someone", key,
                         order=["htlnlp_7"])
    plain = ns["unseal"]((out / "sealed" / "htlnlp_7.bin").read_bytes(), key, "htlnlp_7")
    with tarfile.open(fileobj=io.BytesIO(plain)) as t:
        members = sorted(m.name for m in t.getmembers() if m.isfile())
        row = json.loads(t.extractfile("tasks.jsonl").read())
    assert members == ["official_task.json", "snapshots/htlnlp_7.tgz", "tasks.jsonl"]
    assert row["problem_statement"] == TASK["problem_statement"] and not row.get("patch") and not row.get("test_patch")
    assert ns["unseal"]((out / "sealed" / "htlnlp_7.bin").read_bytes(), bytes(32), "htlnlp_7")[:5] != plain[:5]
    assert 'SEAL_KEY = ""' in src                                              # the key is never committed


def test_a_batch_kernel_carries_its_key_and_the_committed_one_does_not(run):
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    keyed = run.kernel_source(src, bytes(range(32)))
    assert f'SEAL_KEY = "{bytes(range(32)).hex()}"' in keyed and 'SEAL_KEY = ""' not in keyed
    meta = run.kernel_metadata("someone", "batch", None, None)
    assert meta["id"] == "someone/htlnlp-offrun-batch" and meta["dataset_sources"][0] == "someone/htlnlp-official-batch"


def test_a_trace_is_counted_by_tool_kind_and_outside_paths(run):
    trace = {"final_metrics": {"total_prompt_tokens": 900, "total_completion_tokens": 70},
             "steps": [{"tool_calls": [{"function_name": "read_file", "arguments": {"filepath": "python/a.py"}}]},
                       {"tool_calls": [{"function_name": "search_similar_code", "arguments": {"query": "x"}},
                                       {"function_name": "code_analyzer", "arguments": {"request": "y"}}]},
                       {"tool_calls": [{"function_name": "load_skill", "arguments": {"name": "pipeline-doctor"}},
                                       {"function_name": "run_command", "arguments": {"command": "ls /kaggle/input"}}]},
                       {"tool_calls": [{"function_name": "write_file",          # text the model wrote is not a path
                                        "arguments": {"filepath": "a.py", "content": "P = '../../data'  # /etc/x"}}]},
                       {"message": "no tools here"}]}
    c = run.trace_counts(trace)
    assert c == {"prompt_token_count": 900, "output_token_count": 70, "graph_tool_call_count": 1,
                 "sub_agent_call_count": 1, "skill_call_count": 1, "outside_workspace_call_count": 1}
    assert run.trace_counts({})["outside_workspace_call_count"] == 0
    row = run.row_for({"instance_id": "htlnlp_7", "patch": "", "trace_counts": c}, None, tier="B", kernel_url="k")
    assert row["graph_tool_call_count"] == 1 and row["prompt_token_count"] == 900 and row["reason_text"] == "empty patch"


# --- the competition's own development set (028 AI4, #668) ---------------------------------------------------------

DEV_ROW = {"instance_id": "fastapi_15661", "repo": "fastapi/fastapi", "base_commit": "abc123",
           "problem_statement": "Query params drop a default", "hints_text": "", "created_at": "2025-01-01",
           "patch": "diff --git a/fastapi/params.py b/fastapi/params.py\n+SECRET_FIX\n",
           "test_patch": "diff --git a/tests/test_q.py b/tests/test_q.py\n+def test_q(): pass\n",
           "FAIL_TO_PASS": "[\"tests/test_q.py::test_q\"]", "PASS_TO_PASS": "[]"}


def _kernel_functions(*names):
    """The kernel's own functions, run here without Kaggle (as test_the_kernel_opens_what_the_bundle_sealed does)."""
    import ast
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    ns: dict = {}
    exec("import glob, json, os, shutil\nfrom pathlib import Path\n", ns)   # noqa: S102 - our own kernel's code
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            exec(ast.get_source_segment(src, node), ns)                     # noqa: S102
    return ns


def test_a_development_set_draw_is_stratified_by_repository(run):
    tasks = {**{f"fastapi_{n}": {"repo": "fastapi/fastapi"} for n in range(6)},
             **{f"rich_{n}": {"repo": "Textualize/rich"} for n in range(4)}}
    strata = run.strata(tasks, {}, "competition")
    assert set(strata.values()) == {"fastapi/fastapi", "Textualize/rich"}
    drawn = run.sample(strata, 5, 7)
    assert sum(i.startswith("fastapi_") for i in drawn) == 3 and sum(i.startswith("rich_") for i in drawn) == 2
    assert run.sample(strata, 5, 7) == drawn                                   # seeded
    assert run.strata({"htlnlp_7": {}}, {"htlnlp_7": "A", "htlnlp_8": "B"}, "published") == {"htlnlp_7": "A"}


def test_a_development_set_bundle_holds_the_submission_and_the_order_and_no_task(ob, tmp_path):
    out = ob.build_competition_batch(["rich_2", "fastapi_9"], _submission(tmp_path), tmp_path / "b", "someone",
                                     {"deadline_minutes": 240, "seed": 1})
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert names == {"official_batch.json", "submission/agent.yaml", "submission/eval_config.yaml",
                     "submission/prompts/system.md", "dataset-metadata.json"}
    meta = json.loads((out / "official_batch.json").read_text())
    assert meta["instance_ids"] == ["rich_2", "fastapi_9"] and meta["source"] == "competition"
    assert meta["deadline_minutes"] == 240
    assert json.loads((out / "dataset-metadata.json").read_text())["id"] == "someone/htlnlp-official-devset"


def test_the_kernel_stages_a_development_task_from_the_mounted_competition(tmp_path):
    ns = _kernel_functions("find_competition", "stage_competition_task")
    comp = tmp_path / "input" / "gemma-4-developer-agent"
    for d in ("snapshots", "graphs", "embeddings", "wheels", "sandbox"):
        (comp / d).mkdir(parents=True)
    (comp / "HARNESS_README.md").write_text("the harness")
    (comp / "tasks.jsonl").write_text(json.dumps(DEV_ROW) + "\n"
                                      + json.dumps(dict(DEV_ROW, instance_id="rich_1", repo="Textualize/rich")) + "\n")
    (comp / "snapshots" / "fastapi_15661.tgz").write_bytes(b"snap")
    (comp / "graphs" / "fastapi_abc123.json").write_text("{}")
    (comp / "embeddings" / "fastapi_abc123.npz").write_bytes(b"vectors")
    assert ns["find_competition"](tmp_path / "input") == comp
    work = tmp_path / "work"
    ns["stage_competition_task"](comp, "fastapi_15661", work)
    (row,) = [json.loads(line) for line in (work / "tasks.jsonl").read_text().splitlines()]
    assert row["instance_id"] == "fastapi_15661" and "patch" not in row      # never the reference fix
    assert row["test_patch"] == DEV_ROW["test_patch"] and row["FAIL_TO_PASS"] == DEV_ROW["FAIL_TO_PASS"]
    snap = work / "snapshots" / "fastapi_15661.tgz"
    assert snap.is_symlink() and snap.read_bytes() == b"snap"                  # linked, not copied
    assert (work / "graphs" / "fastapi_abc123.json").exists() and (work / "embeddings" / "fastapi_abc123.npz").exists()
    # the evaluator finds the tests' dependencies beside tasks.jsonl (swegemma's resolve_wheels_dir): the pilot of
    # November 11 had none there, and its verification stopped before any test ran (exit code 2)
    assert (work / "wheels").is_symlink() and (work / "wheels").resolve() == (comp / "wheels").resolve()
    assert (work / "sandbox").is_symlink() and (work / "sandbox").resolve() == (comp / "sandbox").resolve()
    with pytest.raises(SystemExit):
        ns["stage_competition_task"](comp, "httpx_1", work)


def test_the_kernel_never_runs_beside_a_reference_patch_and_takes_tests_only_for_the_competitions_tasks():
    ns = _kernel_functions("check_task_fields")
    ns["check_task_fields"](has_patch=False, has_tests=True, with_tests=True)      # a development task
    ns["check_task_fields"](has_patch=False, has_tests=False, with_tests=False)     # one of ours
    with pytest.raises(SystemExit):
        ns["check_task_fields"](has_patch=True, has_tests=True, with_tests=True)
    with pytest.raises(SystemExit):
        ns["check_task_fields"](has_patch=False, has_tests=True, with_tests=False)


def test_a_development_row_takes_the_evaluators_own_verdict(run):
    assert run.verdict_from_kernel({"verification": {"is_resolved": True, "test_exit_code": 0}}) == {
        "resolved": True, "test_exit_code": 0}
    assert run.verdict_from_kernel({"patch": ""}) is None


def test_a_batch_counts_each_tasks_trace(run, tmp_path):
    trace = tmp_path / "tasks" / "fastapi_15661" / "results" / "traces" / "trace_fastapi_15661.json"
    trace.parent.mkdir(parents=True)
    trace.write_text(json.dumps({"final_metrics": {"total_prompt_tokens": 50, "total_completion_tokens": 5},
                                 "steps": [{"tool_calls": [{"function_name": "run_command",
                                                            "arguments": {"command": "cat /kaggle/input/x"}}]}]}))
    counts = run.batch_trace_counts(tmp_path, "fastapi_15661")
    assert counts["prompt_token_count"] == 50 and counts["outside_workspace_call_count"] == 1
    assert run.batch_trace_counts(tmp_path, "rich_1") is None


def test_the_development_set_has_its_own_table(run, tmp_path, monkeypatch):
    import pandas as pd
    monkeypatch.setattr(run, "OUT_DIR", tmp_path)
    row = {c: None for c in run.COLUMNS} | {"instance_id": "fastapi_15661", "is_resolved": False}
    path = run.write_table(pd, [row], "gemma-4-e4b-it-qat-w4a16-ct", label="devset")
    assert path.name == "gemma-4-e4b-it-qat-w4a16-ct_swegemma_devset.csv"
    assert run.write_table(pd, [row], "gemma-4-e4b-it-qat-w4a16-ct").name == "gemma-4-e4b-it-qat-w4a16-ct_swegemma.csv"


# --- the official kernel's telemetry, behind a switch (spec 014 US6, 036 US2; #668) ---------------------------------

class _FakeSpan:
    """What the tracing SDK hands an exporter: to_json() as the SDK writes it."""

    def __init__(self, attributes):
        self.attributes = attributes

    def to_json(self, indent=None):
        return json.dumps({"name": "call_llm", "context": {"trace_id": "0x1", "span_id": "0x2", "trace_state": "[]"},
                           "kind": "SpanKind.INTERNAL", "parent_id": "0x3", "start_time": "t0", "end_time": "t1",
                           "status": {"status_code": "ERROR", "description": "the request said: def secret()"},
                           "attributes": self.attributes, "events": [{"name": "reply", "attributes": {"text": "x"}}],
                           "links": [], "resource": {"attributes": {"service.name": "svc", "host.arch": "x" * 90},
                                                     "schema_url": ""}})


def test_a_kernel_span_keeps_counts_and_short_labels_and_never_the_request_or_reply():
    ns = _kernel_functions("_keep_attribute", "span_line")
    ns.update(MAX_SPAN_TEXT=64, SPAN_TEXT_KEYS=("_name", "_code", "_id", ".name", ".model", ".type", ".system",
                                                ".operation"))
    request = json.dumps({"contents": "def secret(): return 42  # the task's code"})
    line = json.loads(ns["span_line"](_FakeSpan({
        "gen_ai.usage.input_tokens": 1200, "gen_ai.usage.output_tokens": 80, "gen_ai.request.model": "gemma-4-e4b",
        "gen_ai.tool.name": "read_file", "instance_id": "fastapi_15661", "gcp.vertex.agent.llm_request": request,
        "gcp.vertex.agent.llm_response": "the patch is ...", "gen_ai.operation.name": "chat"})))
    a = line["attributes"]
    assert a["gen_ai.usage.input_tokens"] == 1200 and a["gen_ai.request.model"] == "gemma-4-e4b"
    assert a["gen_ai.tool.name"] == "read_file" and a["instance_id"] == "fastapi_15661"
    assert "gcp.vertex.agent.llm_request" not in a and "gcp.vertex.agent.llm_response" not in a
    assert line["events"] == [] and line["status"] == {"status_code": "ERROR"}
    assert "host.arch" not in line["resource"]["attributes"] and "secret" not in json.dumps(line)


def test_the_kernel_traces_and_samples_the_gpus_only_when_asked():
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    assert 'meta.get("telemetry")' in src and "start_tracing(OUT / \"telemetry.jsonl\")" in src
    assert "start_gpu_sampler(OUT / \"gpu_samples.csv\")" in src
    assert '"OTEL_SDK_DISABLED": "true"' in src                 # the default stays as the competition runs it


def test_a_tasks_gpu_use_is_summed_from_the_samples_between_its_start_and_end(run, tmp_path):
    from datetime import datetime, timezone
    csv = tmp_path / "gpu_samples.csv"
    lines = ["timestamp,gpu_index,utilization_pct,memory_used_mb,power_w"]
    for s in range(0, 30, 5):                                  # two GPUs, every 5 seconds from 12:00:00
        for g in (0, 1):
            lines.append(f"2026/11/11 12:00:{s:02d}.000, {g}, {50 + 10 * g}, {1000 + s}, {60.0 + g}")
    csv.write_text("\n".join(lines) + "\n")
    t0 = datetime(2026, 11, 11, 12, 0, 5, tzinfo=timezone.utc).timestamp()
    stats = run.gpu_stats(csv, t0, t0 + 10)                    # 12:00:05 to 12:00:15: three samples a GPU
    assert stats["gpu_sample_count"] == 6 and stats["avg_gpu_utilization_pct"] == 55.0
    assert stats["max_gpu_memory_used_mb"] == 1015.0
    assert abs(stats["gpu_energy_wh"] - (60.0 + 61.0) * 10 / 3600) < 1e-9   # each GPU's mean power over 10 s
    assert run.gpu_stats(tmp_path / "none.csv", t0, t0 + 10) is None


def test_the_runner_asks_the_kernel_for_telemetry_only_with_the_switch(run):
    class A:
        deadline_minutes, seed, telemetry = 45.0, 7, False
    assert "telemetry" not in run.batch_meta(A, {})
    A.telemetry = True
    assert run.batch_meta(A, {"max_time_minutes": 5.0}) == {"budget_overrides": {"max_time_minutes": 5.0},
                                                            "deadline_minutes": 45.0, "seed": 7, "telemetry": True}


# --- the controls on the development set: the reference patch and an empty one (028 AI4, #668) ---------------------

@pytest.fixture(scope="module")
def controls():
    return _load("official_controls_run")


def test_the_controls_kernel_runs_on_a_cpu_offline_beside_the_competition_and_the_evaluator(controls):
    meta = controls.kernel_metadata("someone", "gemma-4-developer-agent", "gcr.io/kaggle-private-byod/python@sha256:x")
    assert meta["id"] == "someone/htlnlp-offrun-devset-controls" and meta["is_private"] is True
    assert meta["enable_gpu"] is False and meta["enable_internet"] is False and meta["model_sources"] == []
    assert meta["competition_sources"] == ["gemma-4-developer-agent"]
    assert meta["dataset_sources"] == ["someone/htlnlp-official-devset-controls", controls.WHEELHOUSE]
    assert meta["docker_image"].endswith("sha256:x")


def test_the_controls_bundle_holds_the_submission_the_verifier_and_the_ids(controls, tmp_path):
    out = controls.build_bundle(["rich_2", "fastapi_9"], _submission(tmp_path), tmp_path / "b", "someone")
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert names == {"controls.json", "official_verify.py", "submission/agent.yaml", "submission/eval_config.yaml",
                     "submission/prompts/system.md", "dataset-metadata.json"}
    meta = json.loads((out / "controls.json").read_text())
    assert meta["instance_ids"] == ["rich_2", "fastapi_9"] and meta["kinds"] == ["oracle", "null"]
    assert (out / "official_verify.py").read_text() == (REPO_ROOT / "kaggle" / "official_verify.py").read_text()


def test_a_control_row_keeps_the_verdict_and_never_the_test_output(controls):
    row = controls.row_for({"instance_id": "rich_2", "patch_kind": "oracle", "resolved": True, "test_exit_code": 0,
                            "error": None, "seconds": 41.2, "output_tail": "def test(): the repo's test output"},
                           "2026-11-11T14:00:00Z")
    assert row == {"instance_id": "rich_2", "patch_source_code": "reference", "is_resolved": True,
                   "test_exit_code": 0, "error_text": None, "verify_seconds": 41.2, "run_ts": "2026-11-11T14:00:00Z"}
    assert controls.row_for({"instance_id": "x", "patch_kind": "null", "resolved": False, "test_exit_code": 1,
                             "error": "E" * 900, "seconds": 3}, "t")["error_text"] == "E" * 200


def test_the_controls_kernel_verifies_from_the_competitions_own_folder():
    src = (REPO_ROOT / "kaggle" / "official_controls_kernel.py").read_text()
    assert 'str(comp / "tasks.jsonl")' in src and 'str(comp / "snapshots")' in src   # wheels/ and sandbox/ beside them
    assert '"--patch", kind' in src and "install_wheelhouse()" in src


# --- the same tasks with and without a failing test's report (028 AI7, #674) ----------------------------------------

def test_a_named_batch_has_its_own_dataset_kernel_and_table(ob, run, tmp_path, monkeypatch):
    """Two arms of one experiment run side by side: a batch's name reaches its dataset, its kernel and its table, so
    neither arm overwrites the other."""
    import pandas as pd
    snap = _snapshot(tmp_path)
    out = ob.build_batch([TASK], lambda t: (snap, None, None), _submission(tmp_path), tmp_path / "b",
                         "someone", bytes(range(32)), order=["htlnlp_7"], name="report")
    assert json.loads((out / "dataset-metadata.json").read_text())["id"] == "someone/htlnlp-official-report"
    meta = run.kernel_metadata("someone", "report", None, None)
    assert meta["id"] == "someone/htlnlp-offrun-report" and "someone/htlnlp-official-report" in meta["dataset_sources"]
    assert run.batch_name("published", None) == "batch" and run.batch_name("competition", None) == "devset"
    assert run.batch_name("published", "report") == "report"
    with pytest.raises(SystemExit):
        run.batch_name("published", "Not A Slug")
    monkeypatch.setattr(run, "OUT_DIR", tmp_path)
    row = {c: None for c in run.COLUMNS} | {"instance_id": "htlnlp_7", "is_resolved": False}
    assert run.write_table(pd, [row], "m", label="report").name == "m_swegemma_report.csv"


def test_a_context_is_appended_to_a_tasks_hints_and_every_task_must_have_one(run):
    tasks = {"a": {"instance_id": "a", "hints_text": "see #6"}, "b": {"instance_id": "b", "hints_text": ""}}
    out = run.with_context(tasks, {"a": "Failing test report:\n- ERROR x", "b": "Failing test report:\n- FAILED y"},
                           ["a", "b"])
    assert out["a"]["hints_text"] == "see #6\n\nFailing test report:\n- ERROR x"
    assert out["b"]["hints_text"] == "Failing test report:\n- FAILED y"
    assert tasks["a"]["hints_text"] == "see #6"                 # the tasks as published are not changed
    with pytest.raises(SystemExit, match="b"):                  # an arm where one task lacks its context is not that arm
        run.with_context(tasks, {"a": "x"}, ["a", "b"])


def test_the_settings_record_which_context_an_arm_had_by_hash_and_size_never_its_text(run, tmp_path):
    import hashlib
    f = tmp_path / "ctx.jsonl"
    f.write_text(json.dumps({"instance_id": "a", "context_text": "Failing test report:\n- ERROR x"}) + "\n"
                 + json.dumps({"instance_id": "z", "context_text": "not drawn"}) + "\n")
    ctx = run.read_context(f)
    assert ctx["a"] == "Failing test report:\n- ERROR x" and set(ctx) == {"a", "z"}
    note = run.context_note(f, ctx, ["a"])
    assert note == {"file_name": "ctx.jsonl", "file_sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                    "task_count": 1, "max_context_chars": len(ctx["a"]), "added_to": "hints_text"}
    assert "ERROR x" not in json.dumps(note)


def test_a_run_of_given_ids_says_so_in_its_settings(run):
    """An arm of the experiment runs ids fixed by its pre-registration: the settings must not say this run drew them."""
    s = {"sample": {"seed": 7, "drawn_count": 2, "pool_count": 93, "instance_ids": ["a", "b"],
                    "method_text": "drawn with the seed from the published tasks"}, "notes": []}
    out = run.given_sample(s, "the 20 of November 10 and 10 more by seed 20261111")
    assert out["sample"]["method_text"] == ("the ids were given to this run, not drawn by it: the 20 of November 10 "
                                            "and 10 more by seed 20261111")
    assert out["sample"]["seed"] is None and out["sample"]["order_seed"] == 7
    assert s["sample"]["seed"] == 7                                   # the input is left alone


def test_every_row_of_a_batch_carries_the_kernels_finish_time_as_its_batch_key(run):
    """AGENTS.md, "Failures, retries and reruns": every written row carries its batch key. A batch kernel writes its
    start and end once, beside its runs; each task's row takes the end, and never the whole kernel's time as its own."""
    res = {"model_name": "m", "started_ts": "2026-11-11T14:42:48Z", "finished_ts": "2026-11-11T17:07:13Z",
           "runs": {"a": {"instance_id": "a", "patch": "x", "agent_phase_seconds": 9.0},
                    "b": {"instance_id": "b", "is_skipped": True}}}
    done = run.batch_results(res)
    assert list(done) == ["a"]                                        # a task the kernel did not reach has no row
    row = run.row_for({"instance_id": "a", **done["a"]}, {"resolved": True, "test_exit_code": 0}, "A", "url")
    assert row["run_ts"] == "2026-11-11T17:07:13Z"
    assert row["script_seconds"] is None and row["model_name"] == "m"


# --- a model server that stops answering mid-batch (028 AI7, #674: the statement arm's kernel of November 11) --------

def test_a_task_whose_agent_got_no_answer_from_the_model_is_not_run(run):
    """The pre-registration's rule: a task the kernel did not reach, or whose agent phase did not start, is "not run".
    With the model server gone a task makes no model call at all and ends at its time limit: no attempt was made, so
    it has no row and is counted with the tasks the kernel skipped."""
    res = {"model_name": "m", "finished_ts": "2026-11-11T19:30:00Z", "runs": {
        "ran": {"instance_id": "ran", "patch": "", "llm_call_count": 12, "tool_call_count": 12,
                "agent_error": "Agent exceeded session timeout (5.0 min)"},
        "no_tools": {"instance_id": "no_tools", "patch": "", "llm_call_count": 3, "tool_call_count": 0},
        "dead": {"instance_id": "dead", "patch": "", "llm_call_count": 0, "tool_call_count": 0,
                 "agent_error": "Agent exceeded session timeout (5.0 min)"},
        "refused": {"instance_id": "refused", "patch": "", "llm_call_count": 0, "tool_call_count": 0,
                    "agent_phase_seconds": 104.7,
                    "agent_error": "Sandbox execution error: litellm.InternalServerError: Connection error."},
        "prompt": {"instance_id": "prompt", "patch": "", "llm_call_count": 0, "tool_call_count": 0,
                   "agent_error": "Context variable not found: `hints`."},
        "skipped": {"instance_id": "skipped", "is_skipped": True}}}
    res["runs"]["dead"]["agent_phase_seconds"] = 300.8
    # a timeout after real model calls is a run; so is a task whose own prompt failed before any call (the hints
    # defect of November 10): an arm whose added text broke the prompt must not lose those tasks from its count
    assert list(run.batch_results(res)) == ["ran", "no_tools", "prompt"]
    assert run.not_run_reasons(res) == {"dead": "no answer from the model server (no model call)",
                                       "refused": "no answer from the model server (no model call)",
                                       "skipped": "not reached by the kernel"}
    assert run.not_run_rows(res, ["skipped", "refused", "ran", "dead"]) == [     # in the run's order, each with how it ended
        {"instance_id": "skipped", "reason_text": "not reached by the kernel", "error_kind_code": None, "agent_seconds": None},
        {"instance_id": "refused", "reason_text": "no answer from the model server (no model call)",
         "error_kind_code": "server_error", "agent_seconds": 104.7},
        {"instance_id": "dead", "reason_text": "no answer from the model server (no model call)",
         "error_kind_code": "time_limit", "agent_seconds": 300.8}]


def test_the_kernel_stops_a_batch_when_the_model_server_stops_answering():
    """Two tasks in a row with no model call and an error: the server is gone, and every further task would only
    spend the GPU allowance (the kernel of November 11 spent three and a half hours that way)."""
    gone = _kernel_functions("server_gone")["server_gone"]
    ok = {"llm_call_count": 9, "tool_call_count": 7}
    dead = {"llm_call_count": 0, "tool_call_count": 0, "agent_error": "Agent exceeded session timeout (5.0 min)"}
    assert gone([ok, ok, dead]) is False                              # one could be the task's own trouble
    assert gone([ok, dead, dead]) is True
    assert gone([dead, ok, dead]) is False                            # not in a row
    assert gone([dead, {"error": "RuntimeError: sandbox"}]) is False  # a failure of another kind is its own row
    assert gone([]) is False
    refused = {"llm_call_count": 0, "agent_error": "Sandbox execution error: litellm.InternalServerError: Connection error."}
    assert gone([ok, dead, refused]) is True
    prompt = {"llm_call_count": 0, "tool_call_count": 0, "agent_error": "Context variable not found: `hints`."}
    assert gone([ok, prompt, prompt]) is False                        # the server is alive: the submission's own fault


def test_a_rerun_keeps_each_tasks_place_in_the_seeded_order_of_the_whole_set(run):
    """The pre-registration reruns tasks a kernel did not run "with the same settings and order": among themselves
    they keep the order the seeded shuffle of the whole set gave them."""
    everything = [f"t{n}" for n in range(12)]
    full = run.seeded_order(everything, 20261110)
    assert sorted(full) == sorted(everything) and full != everything
    some = ["t3", "t7", "t9", "t0"]
    assert run.seeded_order(some, 20261110, of_set=everything) == [i for i in full if i in some]
    assert run.seeded_order(everything, 20261110, of_set=everything) == full
    with pytest.raises(SystemExit, match="not in the first run: zz"):
        run.seeded_order(["t3", "zz"], 20261110, of_set=everything)
    assert run.order_record(everything) == {"of_ids_count": 12, "of_ids_sha256": run.order_record(everything)["of_ids_sha256"]}
    assert len(run.order_record(everything)["of_ids_sha256"]) == 64 and run.order_record(some) != run.order_record(everything)


def test_a_batch_kernel_that_kaggle_refuses_stops_the_run_with_kaggles_own_words(run, tmp_path):
    """The rerun of November 11 was pushed with the weekly GPU allowance spent. Kaggle refused the kernel, and the
    runner went on to wait for a kernel that did not exist. A refusal ends the run and says why."""
    class Refusing:
        def kernels_push(self, folder, timeout=None):
            return type("Response", (), {"error": "Maximum weekly GPU quota of 30.00 hours reached."})()

    class Raising:
        def kernels_push(self, folder, timeout=None):
            raise RuntimeError("403 Client Error")

    class Accepting:
        def kernels_push(self, folder, timeout=None):
            return type("Response", (), {"error": ""})()

    with pytest.raises(SystemExit, match="someone/htlnlp-offrun-x: Kaggle refused the kernel: Maximum weekly GPU quota"):
        run.push_kernel(Refusing(), tmp_path, 60, "someone/htlnlp-offrun-x")
    with pytest.raises(SystemExit, match="403 Client Error"):
        run.push_kernel(Raising(), tmp_path, 60, "someone/htlnlp-offrun-x")
    assert run.push_kernel(Accepting(), tmp_path, 60, "someone/htlnlp-offrun-x") is None


def test_a_kernel_refused_for_the_gpu_quota_says_where_more_hours_come_from(run, tmp_path):
    """After that refusal the rerun went to Colab, and nobody had checked that a Colab subscription linked to the
    Kaggle account adds GPU hours on Kaggle itself (#698). The refusal now names that check; another refusal, which
    more hours would not cure, does not."""
    class OutOfHours:
        def kernels_push(self, folder, timeout=None):
            return type("Response", (), {"error": "Maximum weekly GPU quota of 30.00 hours reached."})()

    class TwoSessions:
        def kernels_push(self, folder, timeout=None):
            return type("Response", (), {"error": "You have reached the maximum of 2 concurrent GPU sessions."})()

    with pytest.raises(SystemExit) as out_of_hours:
        run.push_kernel(OutOfHours(), tmp_path, 60, "someone/htlnlp-offrun-x")
    said = str(out_of_hours.value)
    assert said.startswith("someone/htlnlp-offrun-x: Kaggle refused the kernel: Maximum weekly GPU quota")
    assert "Colab Pro or Pro+" in said and "kaggle/README.md" in said and "GPU hours" in said
    with pytest.raises(SystemExit) as two_sessions:
        run.push_kernel(TwoSessions(), tmp_path, 60, "someone/htlnlp-offrun-x")
    assert "Colab" not in str(two_sessions.value)


def test_a_context_needs_a_label_so_its_rows_never_join_another_runs_table(run):
    """Without a label a batch writes to the table of the run of November 10. A run with added context is a different
    condition: it must name its own table."""
    with pytest.raises(SystemExit, match="--context needs --label"):
        run.check_arm_options(label=None, context="contexts.jsonl", batch=True, development=False)
    with pytest.raises(SystemExit, match="need --batch"):
        run.check_arm_options(label="report", context="contexts.jsonl", batch=False, development=False)
    with pytest.raises(SystemExit, match="need --batch"):
        run.check_arm_options(label="report", context=None, batch=True, development=True)
    run.check_arm_options(label="report", context="contexts.jsonl", batch=True, development=False)
    run.check_arm_options(label="statement", context=None, batch=True, development=False)
    run.check_arm_options(label=None, context=None, batch=False, development=False)


def test_a_collection_can_reuse_output_already_downloaded(run, tmp_path):
    """Collecting again (new settings, a corrected note) need not download the kernel's output a second time."""
    assert run.reusable_output(tmp_path, True) is False              # nothing there yet
    (tmp_path / "result.json").write_text("{}")
    assert run.reusable_output(tmp_path, True) is True
    assert run.reusable_output(tmp_path, False) is False             # only when asked
