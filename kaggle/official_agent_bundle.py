"""One task's inputs for the competition's own evaluator on a Kaggle GPU, and nothing that holds its answer
(spec 028 US5, T011b, #636).

The layout is the one the evaluator reads (the competition's dataset layout), for a single task:

    official_task.json   which task this is, and any budget the run overrides
    tasks.jsonl          one row: the fields the prompt uses. No `patch`, no `test_patch`
    snapshots/<instance_id>.tgz              the published snapshot: base_commit as one commit
    graphs/<repo name>_<base_commit>.json    the task's code graph, when there is one
    embeddings/<repo name>_<base_commit>.npz its embeddings, when there are
    submission/          the agent: agent.yaml, eval_config.yaml, prompts/, sub_agents/, configs/, skills/, adapters/

On Kaggle anything the agent runs can read every attached file (kaggle/agent_bundle.py says how that was probed), so
each task runs alone beside this bundle. The evaluator's verification needs the tests; they are not here, so the
patch is verified afterwards with the evaluator's own verify_task on the published files (kaggle/official_verify.py).

    build(task, snapshot, graph, embedding, submission_dir, out, username)   the folder, with dataset-metadata.json
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

TASK_FIELDS = ("instance_id", "repo", "base_commit", "problem_statement", "hints_text", "created_at")
SUBMISSION_ENTRIES = ("agent.yaml", "eval_config.yaml", "eval_config.yml", "prompts", "sub_agents", "configs",
                      "skills", "adapters")



def _check_snapshot(snapshot: Path) -> None:
    """A bundle carries base_commit alone: one commit, nothing unreachable (as kaggle/agent_bundle.py checks). The
    unpacked files may belong to the user that built the archive, so git is told the folder is safe to read."""
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(snapshot) as t:
            t.extractall(d, filter="tar")
        run = lambda *a: subprocess.run(["git", "-c", f"safe.directory={d}", "-c", "safe.directory=*", *a], cwd=d,
                                        capture_output=True, text=True, check=True).stdout
        commits = int(run("rev-list", "--all", "--count").strip() or 0)
        loose = run("fsck", "--unreachable", "--no-reflogs").strip()
        if commits != 1 or loose:
            raise SystemExit(f"{snapshot.name}: its .git holds {commits} commit(s)"
                             f"{' and unreachable objects' if loose else ''}; a bundle carries base_commit alone")


def slug(instance_id: str) -> str:
    return "htlnlp-official-" + re.sub(r"[^a-z0-9]+", "-", instance_id.lower()).strip("-")


def code_index_name(repo: str, base_commit: str) -> str:
    """The competition's name for a graph or embedding file: `<repo name>_<base_commit>`."""
    return f"{repo.split('/')[-1]}_{base_commit}"


def build(task: dict, snapshot: Path, graph: Path | None, embedding: Path | None, submission_dir: Path, out: Path,
          username: str = "jcblearning", budget_overrides: dict | None = None) -> Path:
    submission_dir = Path(submission_dir)
    if not (submission_dir / "agent.yaml").is_file():
        raise SystemExit(f"{submission_dir} has no agent.yaml: not a submission folder")
    _check_snapshot(Path(snapshot))
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "snapshots").mkdir(parents=True)
    row = {k: task.get(k, "") for k in TASK_FIELDS}
    (out / "tasks.jsonl").write_text(json.dumps(row) + "\n")
    (out / "official_task.json").write_text(json.dumps(
        {"instance_id": task["instance_id"], "budget_overrides": budget_overrides or {}}, indent=1) + "\n")
    shutil.copyfile(snapshot, out / "snapshots" / f"{task['instance_id']}.tgz")
    stem = code_index_name(task["repo"], task["base_commit"])
    for src, folder, ext in ((graph, "graphs", ".json"), (embedding, "embeddings", ".npz")):
        if src and Path(src).exists():
            (out / folder).mkdir(exist_ok=True)
            shutil.copyfile(src, out / folder / f"{stem}{ext}")
    (out / "submission").mkdir()
    for name in SUBMISSION_ENTRIES:
        src = submission_dir / name
        if src.is_dir():
            shutil.copytree(src, out / "submission" / name)
        elif src.is_file():
            shutil.copyfile(src, out / "submission" / name)
    (out / "dataset-metadata.json").write_text(json.dumps({
        "title": f"htlnlp official input {task['instance_id']}"[:50], "id": f"{username}/{slug(task['instance_id'])}",
        "licenses": [{"name": "CC-BY-4.0"}]}, indent=1) + "\n")
    return out


if __name__ == "__main__":
    sys.exit("used by kaggle/official_agent_run.py")
