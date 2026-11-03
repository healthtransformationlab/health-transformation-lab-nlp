"""Build the spec 028 task set as a Kaggle dataset folder and, with --upload, publish it public (T011, #356).
Used by .github/workflows/kaggle-publish-tasks.yml, after 55_build_tasks.py and a full 57_gate_tasks.py run.

    python kaggle/publish_tasks.py --out build/tasks --username <kaggle user> --commit <sha> [--upload --message ...]

The layout is the Gemma 4 Developer Agent competition's, checked against all 129 of its tasks (Nov 3, 2026):
`tasks.jsonl`, `snapshots/<instance_id>.tgz`, and `graphs/` and `embeddings/` named `<repo name>_<base_commit>`
(the harness finds them by `task.repo`; ours are built per instance id, so they are renamed here, one per base).
Only the gated set goes: `tasks_gated.jsonl` becomes `tasks.jsonl`, never the ungated candidates. No wheels:
they are third-party packages under their own licences (the card says how to download them). check() refuses a
task that didn't pass the gate, a task missing a file, and any row or graph naming the organisation CLAUDE.md forbids.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))
sys.path.insert(0, str(HERE))

import publish  # kaggle/publish.py: the same upload, create-public-then-version

from health_transformation_lab_nlp import task_mine as tm
from health_transformation_lab_nlp.paths import TASKS_DIR

SLUG = "health-transformation-lab-coding-agent-tasks"
TITLE = "Coding-Agent Tasks from a Data Pipeline Repo"
SUBTITLE = "Real issues, patches and tests in the Gemma 4 Developer Agent dataset layout"
KEYWORDS = ["programming", "software", "python"]


def code_index_name(repo: str, base_commit: str) -> str:
    """The competition's name for a graph or embedding file: `<repo name>_<base_commit>`."""
    return f"{repo.split('/')[-1]}_{base_commit}"


def _rows(task_dir: Path) -> list[dict]:
    src = task_dir / "tasks_gated.jsonl"
    if not src.exists() or not src.read_text().strip():
        raise SystemExit(f"no gated set at {src}: run scripts/57_gate_tasks.py (a full run) after 55_build_tasks.py")
    return [json.loads(line) for line in src.read_text().splitlines() if line.strip()]


def files_of(task_dir: Path) -> dict:
    """{path in the dataset: source file}, in a stable order. A base shared by tasks keeps the first task's graph."""
    rows = _rows(task_dir)
    out = {"tasks.jsonl": task_dir / "tasks_gated.jsonl", "tasks_excluded.csv": task_dir / "tasks_excluded.csv",
           "task_gates.csv": task_dir / "task_gates.csv"}
    for r in rows:
        out[f"snapshots/{r['instance_id']}.tgz"] = task_dir / "snapshots" / f"{r['instance_id']}.tgz"
    for r in rows:
        name = code_index_name(r["repo"], r["base_commit"])
        out.setdefault(f"graphs/{name}.json", task_dir / "graphs" / f"{r['instance_id']}.json")
        out.setdefault(f"embeddings/{name}.npz", task_dir / "embeddings" / f"{r['instance_id']}.npz")
    return out


def check(task_dir: Path) -> None:
    """Refuse what must not be published: a task that didn't pass both gates, a missing file, the organisation."""
    rows = _rows(task_dir)
    gates = pd.read_csv(task_dir / "task_gates.csv", keep_default_na=False)
    valid = set(gates.loc[gates["is_valid"].astype(str) == "True", "instance_id"])
    failed = [r["instance_id"] for r in rows if r["instance_id"] not in valid]
    if failed:
        raise SystemExit(f"{len(failed)} task(s) in the set didn't pass both gates: {', '.join(failed[:5])}")
    missing = [dest for dest, src in files_of(task_dir).items() if not src.exists()]
    if missing:
        raise SystemExit(f"{len(missing)} file(s) missing, e.g. {missing[0]}: build them with 55_build_tasks.py "
                         "--snapshots N --graphs --embeddings")
    named = [r["instance_id"] for r in rows if tm.names_org(json.dumps(r))]
    named += [dest for dest, src in files_of(task_dir).items()   # graph node text is unredacted source (PR #515)
              if dest.startswith("graphs/") and tm.names_org(src.read_text())]
    if named:   # CLAUDE.md: nothing published names it (#435)
        raise SystemExit(f"{len(named)} row(s) or graph(s) name the organisation CLAUDE.md forbids: "
                         f"{', '.join(named[:5])}")


def card(task_dir: Path, commit: str) -> str:
    files = files_of(task_dir)
    folders = {}
    for dest, src in files.items():
        top = dest.split("/")[0] if "/" in dest else dest
        n, size = folders.get(top, (0, 0))
        folders[top] = (n + 1, size + src.stat().st_size)
    table = "\n".join(f"| `{top}` | {n} | {size / 1e6:.1f} MB |" for top, (n, size) in folders.items())
    n_tasks = len(_rows(task_dir))
    return ((HERE / "cards" / "tasks.md").read_text().rstrip()
            + f"\n\n## Contents\n\n{n_tasks} tasks.\n\n| Path | Files | Size |\n|---|---|---|\n" + table
            + f"\n\nPublished from commit `{commit}` of the repository.\n")


def build(task_dir: Path, out: Path, username: str, commit: str) -> dict:
    check(task_dir)
    if out.exists():
        shutil.rmtree(out)
    for dest, src in files_of(task_dir).items():
        (out / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out / dest)
    meta = {"title": TITLE, "subtitle": SUBTITLE, "id": f"{username}/{SLUG}", "licenses": [{"name": "CC-BY-4.0"}],
            "keywords": KEYWORDS, "description": card(task_dir, commit)}
    (out / "dataset-metadata.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks-dir", type=Path, default=TASKS_DIR)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--username", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--upload", action="store_true", help="publish it (needs Kaggle credentials)")
    ap.add_argument("--message", default="Update from the repository")
    a = ap.parse_args()
    meta = build(a.tasks_dir, a.out, a.username, a.commit)
    files = files_of(a.tasks_dir)
    size = sum(p.stat().st_size for p in a.out.rglob("*") if p.is_file())
    print(f"prepared {meta['id']}: {len(_rows(a.tasks_dir))} tasks, {len(files)} files, {size / 1e9:.2f} GB "
          f"at {a.commit[:12]}")
    if a.upload:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        publish.upload(a.out, meta["id"], f"{a.message} ({a.commit[:12]})", api)


if __name__ == "__main__":
    main()
