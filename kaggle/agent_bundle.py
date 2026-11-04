"""One task's inputs for the Gemma agent on a Kaggle GPU, and nothing that holds its answer (spec 035 US2, #544).

On Kaggle every attached file is readable by anything the agent runs, and neither namespaces nor a second user can
hide one (probed Nov 2026). The task set's later snapshots hold earlier tasks' fixes, and this repository's code is
later than every task. So each task runs alone, in its own kernel, beside a private dataset holding only:

    task.json       the fields the prompt uses (TASK_FIELDS): no reference patch, no tests
    snapshot.tgz    the files at base_commit, as one commit (refused if its .git holds more)
    graph.json, embedding.npz   the task's code graph and embeddings, when there are
    agent.json      the submission's instruction, declared tools, budget and model settings
    htl_agent/      agent_harness.py, gemma_agent.py, task_gate.py and a telemetry stub: no task changes them
                    (touched_shipped), and they need nothing else from the package

    build(task, snapshot, graph, embedding, out, instruction, tools, budget)  the folder, with dataset-metadata.json
    touched_shipped(task)   the shipped files a task's patch or tests change; must be none
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent / "python" / "health_transformation_lab_nlp"
SHIPPED = ("agent_harness.py", "gemma_agent.py", "task_gate.py")
TASK_FIELDS = {"instance_id", "repo", "base_commit", "problem_statement", "hints_text"}
TELEMETRY_STUB = '''"""Stand-in for health_transformation_lab_nlp.telemetry on Kaggle: no spans, nothing exported."""


def traced(fn):
    return fn
'''


def slug(instance_id: str) -> str:
    return "htlnlp-agent-" + re.sub(r"[^a-z0-9]+", "-", instance_id.lower()).strip("-")


def touched_shipped(task: dict) -> list[str]:
    paths = re.findall(r"(?m)^diff --git a/(\S+)", (task.get("patch") or "") + (task.get("test_patch") or ""))
    shipped = {f"python/health_transformation_lab_nlp/{f}" for f in SHIPPED}
    return sorted(set(paths) & shipped)


def _check_snapshot(snapshot: Path) -> None:
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(snapshot) as t:
            t.extractall(d, filter="tar")
        run = lambda *a: subprocess.run(["git", *a], cwd=d, capture_output=True, text=True, check=True).stdout
        commits = int(run("rev-list", "--all", "--count").strip() or 0)
        loose = run("fsck", "--unreachable", "--no-reflogs").strip()
        if commits != 1 or loose:
            raise SystemExit(f"{snapshot.name}: its .git holds {commits} commit(s)"
                             f"{' and unreachable objects' if loose else ''}; a bundle carries base_commit alone")


def build(task: dict, snapshot: Path, graph: Path | None, embedding: Path | None, out: Path, instruction: str,
          tools: list[str], budget, username: str = "jcblearning", model: dict | None = None) -> Path:
    if touched_shipped(task):
        raise SystemExit(f"{task['instance_id']} changes {touched_shipped(task)}, which the bundle ships")
    _check_snapshot(Path(snapshot))
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "htl_agent").mkdir(parents=True)
    for f in SHIPPED:
        shutil.copyfile(PKG / f, out / "htl_agent" / f)
    (out / "htl_agent" / "__init__.py").write_text('"""The harness, as shipped beside one task (kaggle/agent_bundle.py)."""\n')
    (out / "htl_agent" / "telemetry.py").write_text(TELEMETRY_STUB)
    (out / "task.json").write_text(json.dumps({k: task.get(k) for k in sorted(TASK_FIELDS)}, indent=1) + "\n")
    shutil.copyfile(snapshot, out / "snapshot.tgz")
    for src, name in ((graph, "graph.json"), (embedding, "embedding.npz")):
        if src and Path(src).exists():
            shutil.copyfile(src, out / name)
    (out / "agent.json").write_text(json.dumps({"instruction": instruction, "tools": tools, "budget": asdict(budget),
                                                "model": model or {}}, indent=1) + "\n")
    (out / "dataset-metadata.json").write_text(json.dumps({
        "title": f"htlnlp agent input {task['instance_id']}"[:50], "id": f"{username}/{slug(task['instance_id'])}",
        "licenses": [{"name": "CC-BY-4.0"}]}, indent=1) + "\n")
    return out


if __name__ == "__main__":
    sys.exit("used by python/scripts/60_kaggle_agent.py")
