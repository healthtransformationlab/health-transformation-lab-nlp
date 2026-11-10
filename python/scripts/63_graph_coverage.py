"""How much of each published task's fix its code graph reaches, and whether the graph leads there (spec 028, #659).

    python scripts/63_graph_coverage.py --published <the downloaded task set: tasks.jsonl, graphs/, snapshots/>

The graph shipped with a task holds the functions, classes and methods of the Python package at the task's base
commit (task_graph.build_graph). A data repository changes much else: scripts, notebooks, pipeline configuration,
documents. For each task this writes one row of data/tasks/graph_coverage.csv with two things.

Coverage: the files its reference patch changes, and how many of them are modules the graph has nodes for. A module
the patch adds is not in the base commit's graph, so it counts as outside it.

Localization: the graph nodes the fix edits (a changed line inside a function, class or method the base commit
already had), the nodes the task's statement names, and the fewest `calls` edges between the two. A graph tool
can walk from the statement to the fix only where that number exists. Naming is read from the text by a fixed
rule (named_nodes), so the counts are a lower bound on what a reader of the statement could work out.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import tarfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR
from health_transformation_lab_nlp.task_graph import (  # one definition of a node's name
    _Defs,
    module_name,
)

OUT = TASKS_DIR / "graph_coverage.csv"
COLUMNS = ["instance_id", "changed_file_count", "graphed_file_count", "is_fix_in_graph", "edited_node_count",
           "statement_node_count", "statement_to_fix_edge_count", "edited_node_text", "statement_node_text"]
SOURCE_ROOT = "python/"                                    # the package sits in python/ (task_graph's source root)
_HEADER = re.compile(r"(?m)^diff --git a/(\S+) b/")
_MODULE_FILE = re.compile(r"python/((?:\w+/)*\w+)\.py$")
_SAME_FILE = re.compile(r"diff --git a/(\S+) b/\1$")
_NOT_MODIFIED = ("new file mode", "deleted file mode", "rename from ", "copy from ")
_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,(\d+))? @@")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_]+")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_SPAN = re.compile(r"`([^`\n]+)`")
_REFERENCE = re.compile(r"((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*)(?:\(.*\))?")


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


def changed_runs(patch: str) -> dict[str, list[tuple[int, list[int]]]]:
    """For each file a patch modifies in place (not one it adds, deletes or renames): its runs of changed lines, each
    as (the old line just above the run, the old numbers of the lines the run removes; none when it only inserts)."""
    runs: dict[str, list[tuple[int, list[int]]]] = {}
    path, lines, i = None, (patch or "").split("\n"), 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith("diff --git "):
            path = m.group(1) if (m := _SAME_FILE.match(line)) else None
            if path:
                runs[path] = []
        elif path and line.startswith(_NOT_MODIFIED):
            del runs[path]
            path = None
        elif path and (m := _HUNK.match(line)):
            old_left, new_left = (1 if m.group(k) is None else int(m.group(k)) for k in (2, 3))
            old = int(m.group(1)) + (old_left == 0)   # "-k,0": the lines go in after old line k
            run = None
            while i < len(lines) and (old_left or new_left):
                mark = lines[i][:1]
                i += 1
                if mark in ("-", "+"):
                    if run is None:
                        run = (old - 1, [])
                        runs[path].append(run)
                    if mark == "-":
                        run[1].append(old)
                        old, old_left = old + 1, old_left - 1
                    else:
                        new_left -= 1
                elif mark != "\\":                    # a context line; "\ No newline at end of file" is neither
                    run, old, old_left, new_left = None, old + 1, old_left - 1, new_left - 1
    return runs


def edited_nodes(runs: list[tuple[int, list[int]]], source: str, module: str) -> set[str]:
    """The functions, classes and methods a file's changed runs fall in, by the graph's own names. A removed or
    replaced line counts for the innermost def that holds it. Lines that are only inserted count for the innermost
    def that holds both the line above and the line below, so new code after a def's last line is not an edit of it."""
    finder = _Defs(module)
    finder.visit(ast.parse(source))
    spans = sorted((node.end_lineno - node.lineno, node.lineno, node.end_lineno, qual)
                   for qual, node, _ in finder.found)   # shortest first: the innermost def comes first

    def holders(line: int) -> list[str]:   # every def that holds the line, innermost first
        return [qual for _, first, last, qual in spans if first <= line <= last]

    edited = set()
    for above, removed in runs:
        if removed:
            edited |= {h[0] for h in map(holders, removed) if h}
        else:
            below = holders(above + 1)
            edited |= set([q for q in holders(above) if q in below][:1])
    return edited


def named_nodes(text: str, node_ids: set[str]) -> set[str]:
    """The graph nodes a task's text names. A node is named when the last part of its id is a whole identifier in the
    text that could hardly be an ordinary word (five characters or more, with an underscore or a capital), or when
    an inline code span is exactly that name, optionally called, optionally qualified (`calc.add()`). Code blocks
    are not spans. A plain word such as `add` outside backticks names nothing."""
    words = set(_IDENTIFIER.findall(text))
    references = {m.group(1) for span in _SPAN.findall(_FENCE.sub("\n", text))
                  if (m := _REFERENCE.fullmatch(span.strip()))}
    named = set()
    for node_id in node_ids:
        last = node_id.rsplit(".", 1)[-1]
        by_word = last in words and len(last) >= 5 and ("_" in last or last != last.lower())
        by_span = any(r == last or (r.endswith("." + last) and ("." + node_id).endswith("." + r)) for r in references)
        if by_word or by_span:
            named.add(node_id)
    return named


def call_distance(named: set[str], edited: set[str], graph: dict) -> int | None:
    """The fewest `calls` edges, followed in either direction, from a named node to an edited one: 0 when the text
    names an edited node; None when it names none, the fix edits none, or no path joins them."""
    if not named or not edited:
        return None
    if named & edited:
        return 0
    near: dict[str, set[str]] = defaultdict(set)
    for e in graph.get("edges") or []:
        if e.get("type") == "calls":
            near[e["source"]].add(e["target"])
            near[e["target"]].add(e["source"])
    seen, frontier, steps = set(named), set(named), 0
    while frontier:
        steps += 1
        frontier = {v for u in frontier for v in near[u]} - seen
        if frontier & edited:
            return steps
        seen |= frontier
    return None


def localization(task: dict, graph: dict, sources: dict[str, str]) -> dict:
    """One task's localization columns. `sources` holds the base commit's text of the graphed modules the patch
    modifies (base_sources)."""
    ids = {n["id"] for n in graph.get("nodes") or []}
    edited: set[str] = set()
    for path, runs in changed_runs(task.get("patch") or "").items():
        if path in sources:
            edited |= edited_nodes(runs, sources[path], module_name(path, SOURCE_ROOT)) & ids
    named = named_nodes((task.get("problem_statement") or "") + "\n" + (task.get("hints_text") or ""), ids)
    return {"edited_node_count": len(edited), "statement_node_count": len(named),
            "statement_to_fix_edge_count": call_distance(named, edited, graph),
            "edited_node_text": ";".join(sorted(edited)), "statement_node_text": ";".join(sorted(named))}


def base_sources(snapshot: Path, paths: set[str]) -> dict[str, str]:
    """The named files as a task's snapshot holds them (the tree at its base commit). A file the snapshot lacks is
    an error: the patch says it modifies it."""
    found: dict[str, str] = {}
    if paths:
        with tarfile.open(snapshot, "r:gz") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                if name in paths and member.isfile():
                    found[name] = archive.extractfile(member).read().decode("utf-8")
    if missing := sorted(paths - set(found)):
        raise SystemExit(f"{snapshot.name} has no {', '.join(missing)}")
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", type=Path, required=True,
                    help="the task set as published (tasks.jsonl, graphs/, snapshots/)")
    a = ap.parse_args()
    tasks = [json.loads(line) for line in (a.published / "tasks.jsonl").read_text().splitlines() if line.strip()]
    rows = []
    for t in tasks:
        g = a.published / "graphs" / f"{t['repo'].split('/')[-1]}_{t['base_commit']}.json"
        if not g.exists():   # a required file: fail naming it
            raise SystemExit(f"no graph for {t['instance_id']}: {g}")
        graph = json.loads(g.read_text())
        modules = graph_modules(graph)
        modified = {f for f in changed_runs(t.get("patch") or "")
                    if (m := _MODULE_FILE.match(f)) and m.group(1).replace("/", ".") in modules}
        sources = base_sources(a.published / "snapshots" / f"{t['instance_id']}.tgz", modified)
        rows.append(coverage(t, graph) | localization(t, graph, sources))
    table = pd.DataFrame(rows, columns=COLUMNS).sort_values("instance_id")
    table["statement_to_fix_edge_count"] = table["statement_to_fix_edge_count"].astype("Int64")   # blank: no path
    table.to_csv(OUT, index=False)   # overwritten whole: re-runnable
    inside = int(table["is_fix_in_graph"].sum())
    print(f"{len(table)} tasks: the reference patch changes a module of the graph in {inside}, none in "
          f"{len(table) - inside}; {int(table['graphed_file_count'].sum())} of {int(table['changed_file_count'].sum())} "
          f"changed files are graphed modules -> {OUT.relative_to(REPO_ROOT)}")
    edits = table[table["edited_node_count"] > 0]
    steps = edits["statement_to_fix_edge_count"]
    print(f"the fix edits a node of the graph in {len(edits)}: the statement names an edited node in "
          f"{int((steps == 0).sum())}, call edges join a named node to an edited one in {int((steps > 0).sum())} more, "
          f"and nothing joins them in {int(steps.isna().sum())} (the statement names no node in "
          f"{int((edits['statement_node_count'] == 0).sum())} of those)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
