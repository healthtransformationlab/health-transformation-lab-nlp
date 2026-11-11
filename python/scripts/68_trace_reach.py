"""Does the failing test's trace lead to the fix, where the statement does not? (028 AI6, #670)

This repository is test-first, so each task's failing test exists before its fix, and its run is what a CI failure
report, and the repository's own OpenTelemetry spans, record (every public function is `@traced`, spec 014). For each
published task whose fix edits an existing function or class (graph_coverage.csv), this unpacks its snapshot, adds
its test patch, runs the failing tests under scripts/_trace_plugin.py and counts:

- `is_edited_in_trace`: an edited node is among the package's public functions the tests called (what the spans
  record), and how many there were (`traced_node_count`: a hit in a large trace means less);
- `is_edited_on_traceback`: an edited node is on a failure's traceback; and the call edges from the traceback to one.

The trace uses the task's hidden test: it is the context a test-first workflow has, not a fair benchmark condition.

    python scripts/68_trace_reach.py --tasks <published tasks.jsonl> --snapshots <dir> --graphs <dir>

Writes data/tasks/trace_reach.csv (ids, counts, booleans; no text) and prints the counts beside the statement's.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import statistics
import subprocess
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp.paths import TASKS_DIR

HERE = Path(__file__).resolve().parent
OUT = TASKS_DIR / "trace_reach.csv"
COLUMNS = ["instance_id", "test_exit_code", "traced_node_count", "failure_frame_count", "is_edited_in_trace",
           "is_edited_on_traceback", "traceback_to_fix_edge_count", "is_import_error", "is_missing_name_added_by_fix",
           "is_error_module_changed_by_fix"]
_TEST_FILE = re.compile(r"(?m)^diff --git a/(python/tests/\S+\.py) b/")
_ADDED_NAME = re.compile(r"(?m)^\+\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)|^\+([A-Za-z_]\w*)\s*[:=]")
_CHANGED_FILE = re.compile(r"(?m)^diff --git a/python/(\S+)\.py b/")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gc = _load("63_graph_coverage")


def public(names: set[str]) -> set[str]:
    """The names the repository's spans record: every public function and method is `@traced`, so none with a part
    starting with an underscore (a private function, method or class)."""
    return {n for n in names if not any(part.startswith("_") for part in n.split("."))}


def trace_row(instance_id: str, trace: dict, graph: dict, edited: set[str]) -> dict:
    """One task's row from its trace: ids, counts and booleans only."""
    ids = {n["id"] for n in graph.get("nodes") or []}
    called = public(set(trace.get("called") or [])) & ids
    frames = public({f for failure in trace.get("failure_frames") or [] for f in failure}) & ids
    return {"instance_id": instance_id, "test_exit_code": trace.get("exit_status"), "traced_node_count": len(called),
            "failure_frame_count": len(frames), "is_edited_in_trace": bool(called & edited),
            "is_edited_on_traceback": bool(frames & edited),
            "traceback_to_fix_edge_count": gc.call_distance(frames, edited, graph) if frames else None}


def import_columns(trace: dict, patch: str) -> dict:
    """For a test that could not be imported: whether its missing name is one the reference fix defines, and whether
    its module is one the fix changes (the failure report then names what the statement may not)."""
    errors = trace.get("collection_errors") or []
    added = {a or b for a, b in _ADDED_NAME.findall(patch or "")}
    modules = {".".join(p for p in path.split("/") if p != "__init__") for path in _CHANGED_FILE.findall(patch or "")}
    return {"is_import_error": bool(errors),
            "is_missing_name_added_by_fix": any(e.get("missing_name") in added for e in errors),
            "is_error_module_changed_by_fix": any(e.get("module") in modules for e in errors)}


def summary(rows: list[dict], reached_by_statement: set[str]) -> dict:
    """How many tasks the trace and the traceback reach, how large the traces are, how many runs never ran a test,
    and what the failure report adds to the statement (by name, call edge or embedding search, the paper's 42), split
    by where the gain comes from: the trace (the functions the tests call, or a traceback) and the import errors (a
    test that cannot be imported, whose error names a name the fix adds or a module it changes). A task with several
    test files can be in both, so the two parts need not sum to the whole (028 BUG4, #672)."""
    traced = [r for r in rows if r["is_edited_in_trace"]]
    statement = set(reached_by_statement) & {r["instance_id"] for r in rows}
    by_trace = {r["instance_id"] for r in rows if r["is_edited_in_trace"] or r["is_edited_on_traceback"]}
    by_import = {r["instance_id"] for r in rows
                 if r.get("is_missing_name_added_by_fix") or r.get("is_error_module_changed_by_fix")}
    report = by_trace | by_import
    return {"task_count": len(rows), "trace_count": len(traced),
            "traceback_count": sum(bool(r["is_edited_on_traceback"]) for r in rows),
            "traceback_within_one_edge_count": sum(r["traceback_to_fix_edge_count"] is not None
                                                   and r["traceback_to_fix_edge_count"] <= 1 for r in rows),
            "trace_not_statement_count": len(by_trace - statement),
            "import_error_not_statement_count": len(by_import - statement),
            "report_count": len(report), "report_not_statement_count": len(report - statement),
            "statement_count": len(statement), "statement_or_report_count": len(statement | report),
            "median_traced_node_count": statistics.median([r["traced_node_count"] for r in rows]) if rows else None,
            "collection_error_count": sum(r["test_exit_code"] is None or r["test_exit_code"] >= 2 for r in rows),
            "import_error_count": sum(bool(r.get("is_import_error")) for r in rows),
            "missing_name_added_by_fix_count": sum(bool(r.get("is_missing_name_added_by_fix")) for r in rows),
            "error_module_changed_by_fix_count": sum(bool(r.get("is_error_module_changed_by_fix")) for r in rows)}


def package_of(root: Path) -> str | None:
    """The package a snapshot holds under python/, whatever it was called at that commit (it was renamed partway
    through the repository's history): the first folder there with an __init__.py that is not tests or scripts."""
    base = Path(root) / "python"
    if not base.is_dir():
        return None
    names = sorted(p.name for p in base.iterdir()
                   if (p / "__init__.py").exists() and p.name not in ("tests", "scripts"))
    return names[0] if names else None


def run_task(task: dict, snapshot: Path, package: str | None, timeout: int, messages: bool = False) -> dict:
    """Unpack the snapshot, add the test patch, run its test files under the plugin; the trace, or the exit status
    when no trace was written. `package` None finds it in the snapshot; `messages` also keeps the first line of each
    failure's error (028 AI7, #674)."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "repo"
        root.mkdir()
        with tarfile.open(snapshot) as t:
            t.extractall(root, filter="data")
        applied = subprocess.run(["git", "-c", "safe.directory=*", "apply", "--whitespace=nowarn", "-"], cwd=root,
                                 input=task.get("test_patch") or "", text=True, capture_output=True)
        if applied.returncode != 0:
            return {"called": [], "failure_frames": [], "exit_status": None}
        files = sorted({f.removeprefix("python/") for f in _TEST_FILE.findall(task.get("test_patch") or "")
                        if (root / f).exists()})
        if not files:   # never the whole suite: a task without a Python test file of its own has no trace here
            return {"called": [], "failure_frames": [], "exit_status": None}
        package = package or package_of(root) or ""
        out = Path(d) / "trace.json"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "DENTAL_TELEMETRY"))}
        env.update(PYTHONPATH=f"{root / 'python'}{os.pathsep}{HERE}", TRACE_PACKAGE=package, TRACE_OUT=str(out),
                   DENTAL_TELEMETRY="off", **({"TRACE_MESSAGES": "1", "TRACE_ROOT": str(root)} if messages else {}))
        try:
            # a report (messages) goes on past a file that cannot be imported, to list every failing test
            more = ["--continue-on-collection-errors"] if messages else []
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "_trace_plugin",
                                *more, *files], cwd=root / "python", env=env, capture_output=True, text=True,
                               timeout=timeout)
            status = r.returncode
        except subprocess.TimeoutExpired:
            status = None
        return json.loads(out.read_text()) if out.exists() else {"called": [], "failure_frames": [],
                                                                  "exit_status": status}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, required=True, help="the published tasks.jsonl")
    ap.add_argument("--snapshots", type=Path, required=True)
    ap.add_argument("--graphs", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=300, help="seconds a task's tests may run")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    tasks = {t["instance_id"]: t for t in map(json.loads, filter(str.strip, a.tasks.read_text().splitlines()))}
    coverage = pd.read_csv(TASKS_DIR / "graph_coverage.csv").fillna({"edited_node_text": ""})
    search = pd.read_csv(TASKS_DIR / "statement_search.csv")
    edits = {r.instance_id: set(filter(None, r.edited_node_text.split(";")))
             for r in coverage.itertuples() if r.edited_node_count > 0}
    reached = ({r.instance_id for r in coverage.itertuples() if pd.notna(r.statement_to_fix_edge_count)}
               | {r.instance_id for r in search.itertuples() if pd.notna(r.edited_node_best_rank_num)
                  and r.edited_node_best_rank_num <= 10})

    def one(iid: str) -> dict:
        task = tasks[iid]
        graph_file = next((p for p in (a.graphs / f"{iid}.json",
                                       a.graphs / f"{task['repo'].split('/')[-1]}_{task['base_commit']}.json")
                           if p.exists()), None)
        graph = json.loads(graph_file.read_text()) if graph_file else {"nodes": [], "edges": []}
        package = next(iter(edits[iid])).split(".")[0]
        trace = run_task(task, a.snapshots / f"{iid}.tgz", package, a.timeout)
        row = {**trace_row(iid, trace, graph, edits[iid]), **import_columns(trace, task.get("patch") or "")}
        print(f"{iid}: exit {row['test_exit_code']}, traced {row['traced_node_count']}, in trace "
              f"{row['is_edited_in_trace']}, on traceback {row['is_edited_on_traceback']}", flush=True)
        return row

    with ThreadPoolExecutor(a.workers) as pool:
        rows = list(pool.map(one, sorted(edits)))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=COLUMNS).sort_values("instance_id").to_csv(a.out, index=False)
    print(json.dumps(summary(rows, reached), indent=1))
    print(f"statement (name, call edge or embedding search, first ten): {len(reached & set(edits))} of {len(edits)}")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
