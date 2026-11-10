"""#508: the wiring in scripts/57_gate_tasks.py (T007a): the apply step and the --apply-only guards. The package
functions it calls are tested in test_task_gate.py; here the script runs against a tiny task set in tmp_path."""
import importlib.util
import json
import sys

import pandas as pd
import pytest

from health_transformation_lab_nlp import task_gate as tgate
from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("gate_tasks", REPO_ROOT / "python" / "scripts" / "57_gate_tasks.py")
gate_tasks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate_tasks)

TASKS = [{"instance_id": "htlnlp_1"}, {"instance_id": "htlnlp_2"}]
GATES = [{"instance_id": "htlnlp_1", "is_valid": True, "reason_text": ""},
         {"instance_id": "htlnlp_2", "is_valid": False, "reason_text": "tests fail with the fix"}]
OTHER = {"instance_id": "htlnlp_91", "tier_code": "A", "reason_text": "names the organisation (#435)"}


@pytest.fixture
def task_dir(tmp_path, monkeypatch):
    d = tmp_path / "data" / "tasks"
    d.mkdir(parents=True)
    names = {"TASKS": "tasks.jsonl", "SAMPLE": "tasks_sample.jsonl", "OUT": "task_gates.csv",
             "GATED": "tasks_gated.jsonl", "EXCLUDED": "tasks_excluded.csv", "MANIFEST": "task_manifest.csv",
             "VERIFIED": "official_verifier/swegemma_verification.csv"}   # absent unless a test writes it
    for attr, name in names.items():
        monkeypatch.setattr(gate_tasks, attr, d / name)
    monkeypatch.setattr(gate_tasks, "REPO_ROOT", tmp_path)
    (d / "tasks.jsonl").write_text("".join(json.dumps(t) + "\n" for t in TASKS))
    pd.DataFrame(GATES, columns=tgate.GATE_COLUMNS).to_csv(d / "task_gates.csv", index=False)
    pd.DataFrame([{"instance_id": "htlnlp_1", "tier_code": "A"}, {"instance_id": "htlnlp_2", "tier_code": "B"}]) \
        .to_csv(d / "task_manifest.csv", index=False)
    pd.DataFrame([OTHER]).to_csv(d / "tasks_excluded.csv", index=False)
    return d


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["57_gate_tasks.py", *args])
    return gate_tasks.main()


def test_apply_writes_the_passing_tasks_and_lists_the_failure(task_dir):
    gate_tasks.apply_gates(TASKS, GATES)
    assert [json.loads(line)["instance_id"] for line in (task_dir / "tasks_gated.jsonl").read_text().splitlines()] \
        == ["htlnlp_1"]
    excluded = pd.read_csv(task_dir / "tasks_excluded.csv").to_dict("records")
    assert excluded == [{"instance_id": "htlnlp_2", "tier_code": "B",
                         "reason_text": tgate.GATE_EXCLUSION_PREFIX + "tests fail with the fix"}, OTHER]


def test_apply_only_is_idempotent(task_dir, monkeypatch):
    assert run(monkeypatch, "--apply-only") == 0
    first = {p.name: p.read_bytes() for p in task_dir.iterdir()}
    assert run(monkeypatch, "--apply-only") == 0
    assert {p.name: p.read_bytes() for p in task_dir.iterdir()} == first
    assert "tasks_gated.jsonl" in first


@pytest.mark.parametrize("extra", [["--sample"], ["--limit", "1"], ["--instance-ids", "htlnlp_1"]])
def test_apply_only_refuses_a_partial_run(task_dir, monkeypatch, extra):
    with pytest.raises(SystemExit, match="whole set"):
        run(monkeypatch, "--apply-only", *extra)
    assert not (task_dir / "tasks_gated.jsonl").exists()


def test_apply_only_refuses_a_gate_file_missing_a_task(task_dir, monkeypatch):
    pd.DataFrame(GATES[:1], columns=tgate.GATE_COLUMNS).to_csv(task_dir / "task_gates.csv", index=False)
    with pytest.raises(SystemExit, match="no gate row"):
        run(monkeypatch, "--apply-only")
    assert not (task_dir / "tasks_gated.jsonl").exists()


def test_apply_only_needs_the_gate_file(task_dir, monkeypatch):
    (task_dir / "task_gates.csv").unlink()
    with pytest.raises(SystemExit, match="missing"):
        run(monkeypatch, "--apply-only")


def test_apply_leaves_out_tasks_the_competitions_evaluator_has_not_verified(task_dir):   # spec 028 US6, #641
    tasks = TASKS + [{"instance_id": "htlnlp_3"}]
    gates = GATES + [{"instance_id": "htlnlp_3", "is_valid": True, "reason_text": ""}]
    (task_dir / "official_verifier").mkdir()
    pd.DataFrame([{"instance_id": "htlnlp_1", "patch_source_code": "reference", "is_resolved": True, "reason_text": ""},
                  {"instance_id": "htlnlp_1", "patch_source_code": "empty", "is_resolved": False, "reason_text": ""},
                  {"instance_id": "htlnlp_3", "patch_source_code": "reference", "is_resolved": False,
                   "reason_text": "tests read withheld files"},
                  {"instance_id": "htlnlp_3", "patch_source_code": "empty", "is_resolved": False, "reason_text": ""}]) \
        .to_csv(task_dir / "official_verifier" / "swegemma_verification.csv", index=False)
    gate_tasks.apply_gates(tasks, gates)
    assert [json.loads(line)["instance_id"] for line in (task_dir / "tasks_gated.jsonl").read_text().splitlines()] \
        == ["htlnlp_1"]
    reasons = pd.read_csv(task_dir / "tasks_excluded.csv").set_index("instance_id")["reason_text"].to_dict()
    assert reasons["htlnlp_2"].startswith(tgate.GATE_EXCLUSION_PREFIX)           # our gate's reason is kept
    assert reasons["htlnlp_3"] == (tgate.EVALUATOR_EXCLUSION_PREFIX
                                   + "it does not resolve the reference patch: tests read withheld files")
    assert "htlnlp_91" in reasons
