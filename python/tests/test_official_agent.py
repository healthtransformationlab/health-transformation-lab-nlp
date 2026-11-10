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
    row = run.row_for(result, verdict, tier="A", kernel_url="https://k", session_seconds=900.0)
    assert list(row) == run.COLUMNS
    assert row["is_resolved"] is True and row["agent_patch_bytes"] == 19 and row["tier_code"] == "A"
    assert row["harness_name"].startswith("swegemma 0.2.11") and row["gpu_count"] == 4 and row["gpu_name"] == "NVIDIA L4"
    assert row["max_time_minutes"] == 5.0 and row["max_output_tokens"] == 16384 and row["thinking_budget"] == 4096
    failed = run.row_for({"instance_id": "htlnlp_7", "error": "RuntimeError: no GPU"}, None, tier="A", kernel_url="k",
                         session_seconds=60.0)
    assert failed["is_resolved"] is False and failed["reason_text"] == "kernel failed" and "no GPU" in failed["error_text"]
