"""How much of each published task's fix its code graph reaches (spec 028, #659).

    python scripts/63_graph_coverage.py --published <the downloaded task set: tasks.jsonl, graphs/>

The graph shipped with a task holds the functions, classes and methods of the Python package at the task's base
commit (task_graph.build_graph). A data repository changes much else: scripts, notebooks, pipeline configuration,
documents. For each task this counts the files its reference patch changes and how many of them are modules the
graph has nodes for, and writes data/tasks/graph_coverage.csv, one row per task. A module the patch adds is not in
the base commit's graph, so it counts as outside it.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

OUT = TASKS_DIR / "graph_coverage.csv"
COLUMNS = ["instance_id", "changed_file_count", "graphed_file_count", "is_fix_in_graph"]
_HEADER = re.compile(r"(?m)^diff --git a/(\S+) b/")
_MODULE_FILE = re.compile(r"python/((?:\w+/)*\w+)\.py$")   # the package sits in python/ (task_graph's source root)


def changed_files(patch: str) -> list[str]:
    """The files a unified git diff changes, in order."""
    return _HEADER.findall(patch or "")


def graph_modules(graph: dict) -> set[str]:
    """The modules that hold at least one node: the parent of every node whose parent is not itself a node (a
    method's parent is its class, a nested function's its function)."""
    ids = {n["id"] for n in graph.get("nodes") or []}
    return {i.rsplit(".", 1)[0] for i in ids if "." in i and i.rsplit(".", 1)[0] not in ids}


def coverage(task: dict, graph: dict) -> dict:
    """One task's row: files changed by its reference patch, and those that are modules of its graph."""
    modules = graph_modules(graph)
    files = changed_files(task.get("patch") or "")
    graphed = [f for f in files if (m := _MODULE_FILE.match(f)) and m.group(1).replace("/", ".") in modules]
    return {"instance_id": task["instance_id"], "changed_file_count": len(files), "graphed_file_count": len(graphed),
            "is_fix_in_graph": bool(graphed)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", type=Path, required=True, help="the task set as published (tasks.jsonl, graphs/)")
    a = ap.parse_args()
    tasks = [json.loads(line) for line in (a.published / "tasks.jsonl").read_text().splitlines() if line.strip()]
    rows = []
    for t in tasks:
        g = a.published / "graphs" / f"{t['repo'].split('/')[-1]}_{t['base_commit']}.json"
        if not g.exists():   # a required file: fail naming it
            raise SystemExit(f"no graph for {t['instance_id']}: {g}")
        rows.append(coverage(t, json.loads(g.read_text())))
    table = pd.DataFrame(rows, columns=COLUMNS).sort_values("instance_id")
    table.to_csv(OUT, index=False)   # overwritten whole: re-runnable
    inside = int(table["is_fix_in_graph"].sum())
    print(f"{len(table)} tasks: the reference patch changes a module of the graph in {inside}, none in "
          f"{len(table) - inside}; {int(table['graphed_file_count'].sum())} of {int(table['changed_file_count'].sum())} "
          f"changed files are graphed modules -> {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
