"""Spec 028 US5, T011 (#356): the task set as a public Kaggle dataset, in the competition's own file names.

The competition names snapshots by instance id and graphs and embeddings by `<repo name>_<base_commit>` (checked
against all 129 of its tasks on Nov 3, 2026), and the harness looks graphs up by `task.repo`. Every test builds a
tiny task set in tmp_path; nothing here reads the git-ignored task files."""
import importlib.util
import json

import pandas as pd
import pytest

from health_transformation_lab_nlp import task_gate as tgate
from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("publish_tasks", REPO_ROOT / "kaggle" / "publish_tasks.py")
pt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pt)

REPO = "healthtransformationlab/health-transformation-lab-nlp"
BASE_A, BASE_B = "a" * 40, "b" * 40


def task(iid, base, statement="Fix the gate"):
    return {"instance_id": iid, "repo": REPO, "base_commit": base, "patch": "p", "test_patch": "t",
            "problem_statement": statement, "hints_text": "", "created_at": "2026-11-01T00:00:00Z"}


@pytest.fixture
def task_dir(tmp_path):
    d = tmp_path / "tasks"
    for sub in ("snapshots", "graphs", "embeddings", "wheels"):
        (d / sub).mkdir(parents=True)
    rows = [task("htlnlp_1", BASE_A), task("htlnlp_2", BASE_B), task("htlnlp_3", BASE_A)]   # 3 shares 1's base
    (d / "tasks_gated.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "tasks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows + [task("htlnlp_9", BASE_B)]))
    for r in rows + [task("htlnlp_9", BASE_B)]:
        (d / "snapshots" / f"{r['instance_id']}.tgz").write_bytes(b"tgz " + r["instance_id"].encode())
        (d / "graphs" / f"{r['instance_id']}.json").write_text(json.dumps({"nodes": [], "id": r["instance_id"]}))
        (d / "embeddings" / f"{r['instance_id']}.npz").write_bytes(b"npz " + r["instance_id"].encode())
    (d / "wheels" / "pandas-2.2.3-cp313-cp313-manylinux_2_17_x86_64.whl").write_bytes(b"wheel")
    gates = [{"instance_id": r["instance_id"], "is_valid": True, "reason_text": ""} for r in rows]
    gates.append({"instance_id": "htlnlp_9", "is_valid": False, "reason_text": "tests fail with the fix"})
    pd.DataFrame(gates, columns=tgate.GATE_COLUMNS).to_csv(d / "task_gates.csv", index=False)
    pd.DataFrame([{"instance_id": "htlnlp_9", "tier_code": "B",
                   "reason_text": tgate.GATE_EXCLUSION_PREFIX + "tests fail with the fix"}]) \
        .to_csv(d / "tasks_excluded.csv", index=False)
    return d


def test_graphs_and_embeddings_take_the_competitions_names():
    assert pt.code_index_name(REPO, BASE_A) == f"health-transformation-lab-nlp_{BASE_A}"


def test_the_set_is_the_gated_tasks_in_the_competitions_layout(task_dir):
    files = pt.files_of(task_dir)
    assert files["tasks.jsonl"] == task_dir / "tasks_gated.jsonl"      # never the ungated candidates
    assert set(files) == {
        "tasks.jsonl", "tasks_excluded.csv", "task_gates.csv",
        "snapshots/htlnlp_1.tgz", "snapshots/htlnlp_2.tgz", "snapshots/htlnlp_3.tgz",
        f"graphs/health-transformation-lab-nlp_{BASE_A}.json", f"graphs/health-transformation-lab-nlp_{BASE_B}.json",
        f"embeddings/health-transformation-lab-nlp_{BASE_A}.npz",
        f"embeddings/health-transformation-lab-nlp_{BASE_B}.npz"}
    assert not [f for f in files if "wheels" in f or "htlnlp_9" in f]   # no third-party wheels, no failed task


def test_a_base_shared_by_two_tasks_takes_the_first_tasks_graph(task_dir):
    files = pt.files_of(task_dir)
    assert files[f"graphs/health-transformation-lab-nlp_{BASE_A}.json"] == task_dir / "graphs" / "htlnlp_1.json"


def test_the_built_folder_holds_exactly_the_set_and_a_cc_by_card(task_dir, tmp_path):
    out = tmp_path / "out"
    meta = pt.build(task_dir, out, "someone", "abc1234")
    built = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert built == set(pt.files_of(task_dir)) | {"dataset-metadata.json"}
    assert [json.loads(line)["instance_id"] for line in (out / "tasks.jsonl").read_text().splitlines()] \
        == ["htlnlp_1", "htlnlp_2", "htlnlp_3"]
    assert meta["licenses"] == [{"name": "CC-BY-4.0"}]
    owner, slug = meta["id"].split("/")
    assert owner == "someone" and 6 <= len(slug) <= 50 and slug == slug.lower()
    assert 6 <= len(meta["title"]) <= 50 and 20 <= len(meta["subtitle"]) <= 80
    card = meta["description"].lower()
    for words in ("not affiliated", "cc by 4.0", "github.com/healthtransformationlab/health-transformation-lab-nlp",
                  "abc1234", "3 tasks", "embeddinggemma", "wheels"):
        assert words in card, words
    assert json.loads((out / "dataset-metadata.json").read_text()) == meta


def test_a_second_build_replaces_the_first(task_dir, tmp_path):
    out = tmp_path / "out"
    pt.build(task_dir, out, "someone", "abc1234")
    (out / "stale.txt").write_text("x")
    pt.build(task_dir, out, "someone", "abc1234")
    assert not (out / "stale.txt").exists()


def test_refuses_without_a_gated_set(task_dir):
    (task_dir / "tasks_gated.jsonl").unlink()
    with pytest.raises(SystemExit, match="57_gate_tasks.py"):
        pt.check(task_dir)


def test_refuses_a_task_that_did_not_pass_the_gate(task_dir):
    rows = [json.loads(line) for line in (task_dir / "tasks_gated.jsonl").read_text().splitlines()]
    rows.append(task("htlnlp_9", BASE_B))
    (task_dir / "tasks_gated.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(SystemExit, match="htlnlp_9"):
        pt.check(task_dir)


@pytest.mark.parametrize("missing", ["snapshots/htlnlp_2.tgz", "graphs/htlnlp_2.json", "embeddings/htlnlp_1.npz"])
def test_refuses_a_task_missing_a_file(task_dir, missing):
    (task_dir / missing).unlink()
    with pytest.raises(SystemExit, match="missing"):
        pt.check(task_dir)


def test_refuses_a_row_naming_the_forbidden_organisation(task_dir, monkeypatch):
    monkeypatch.setattr(pt.tm, "names_org", lambda text: "Fix the gate" in (text or ""))
    with pytest.raises(SystemExit, match="organisation"):
        pt.check(task_dir)


def test_build_checks_first_and_writes_nothing_on_a_refusal(task_dir, tmp_path):
    (task_dir / "graphs" / "htlnlp_2.json").unlink()
    with pytest.raises(SystemExit):
        pt.build(task_dir, tmp_path / "out", "someone", "abc1234")
    assert not (tmp_path / "out").exists()


def test_the_workflow_builds_gates_then_publishes_from_full_history():
    import yaml
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "kaggle-publish-tasks.yml").read_text())
    steps = wf["jobs"]["publish"]["steps"]
    assert steps[0]["with"]["fetch-depth"] == 0                       # every base commit is snapshotted
    assert steps[1]["with"]["python-version"] == "3.13"               # the competition sandbox's Python
    runs = [s.get("run", "") for s in steps]
    build = next(i for i, r in enumerate(runs) if "55_build_tasks.py" in r)
    gate = next(i for i, r in enumerate(runs) if "57_gate_tasks.py" in r)
    pub = next(i for i, r in enumerate(runs) if "publish_tasks.py" in r)
    assert build < gate < pub
    assert all(f in runs[build] for f in ("--snapshots", "--graphs", "--embeddings"))
    assert not any(f in runs[gate] for f in ("--sample", "--limit", "--instance-ids"))   # only a full run publishes
    assert "--upload" in runs[pub] and "pipefail" in runs[pub]
    check = next(i for i, r in enumerate(runs) if "authenticate()" in r)
    assert check < build                                              # the credential is checked before the work
