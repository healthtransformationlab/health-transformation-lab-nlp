"""Graph-guided retrieval, done for the agent before it starts (028 AI7, #674: the graph arm).

Scripts 63 and 64 counted how often a task's code graph leads from its statement to its fix. Those are counts. The
agent itself asks a graph tool in about one tool call in twenty on these tasks, so whether the graph helps it has
stayed untested. This builds, for each task, what the graph says about its statement:

- the functions and classes the statement names (script 63's rule);
- the nodes one `calls` edge from those, either way;
- the ten nodes nearest the statement by embedding search (script 64's method: EmbeddingGemma's query prompt
  against the published node vectors).

Each with the file that holds it. It is built from the statement, the graph and the embeddings alone: never from
the reference patch or the tests. So, unlike the failing test's report (script 69), it is a condition a deployed
agent could have, and a run that uses it is a benchmark condition.

    python scripts/72_graph_context.py --published <the downloaded task set> --out-context <file>

Writes the text to --out-context (JSON lines: instance_id, context_text), outside the repository, and
data/tasks/graph_context_shape.csv: counts, and whether an edited node was among those listed (from
graph_coverage.csv; that column is for reading the run afterwards and is never given to the agent).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

from health_transformation_lab_nlp.paths import TASKS_DIR

HERE = Path(__file__).resolve().parent
OUT = TASKS_DIR / "graph_context_shape.csv"
COLUMNS = ["instance_id", "named_node_count", "neighbour_node_count", "similar_node_count", "context_chars",
           "is_edited_node_listed"]
HEADER = "Graph retrieval for this issue (computed from the issue text and this repository's code graph alone):"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gc = _load("63_graph_coverage")
ss = _load("64_statement_search")
fr = _load("69_failure_report")


def top_nodes(query: np.ndarray, vectors: dict[str, np.ndarray], k: int) -> list[str]:
    """The k node ids nearest the query by cosine similarity, nearest first (ties in the vectors' own order)."""
    if not vectors:
        return []
    ids = list(vectors)
    scores = np.stack([vectors[i] for i in ids]).astype(np.float64) @ np.asarray(query, dtype=np.float64)
    return [ids[j] for j in np.argsort(-scores, kind="stable")[:k]]


def neighbours(named: set[str], graph: dict, limit: int) -> list[str]:
    """The nodes one `calls` edge from a named node, in either direction, that are not named themselves."""
    found = set()
    for e in graph.get("edges") or []:
        if e.get("type", "calls") != "calls":
            continue
        if e["source"] in named:
            found.add(e["target"])
        if e["target"] in named:
            found.add(e["source"])
    return sorted(found - set(named))[:limit]


def node_path(node_id: str, modules: set[str]) -> str | None:
    """The file that holds a node: its longest module prefix as a path under python/."""
    parts = node_id.split(".")
    for n in range(len(parts) - 1, 0, -1):
        if ".".join(parts[:n]) in modules:
            return "python/" + "/".join(parts[:n]) + ".py"
    return None


def _show(node_id: str, modules: set[str]) -> str:
    path = node_path(node_id, modules)
    return f"{node_id} ({path})" if path else node_id


def graph_context(named: list[str], near: list[str], similar: list[str], modules: set[str]) -> str:
    """The retrieval as text. Nothing here comes from the fix or the tests. Empty when the graph gave nothing."""
    if not (named or similar):
        return ""
    lines = [HEADER]
    if named:
        lines.append("Named in the issue: " + "; ".join(_show(n, modules) for n in named))
    if near:
        lines.append("One call away from those: " + "; ".join(_show(n, modules) for n in near))
    if similar:
        lines.append("Nearest to the issue text by embedding search:")
        lines += [f"{rank}. {_show(n, modules)}" for rank, n in enumerate(similar, start=1)]
    return "\n".join(lines)


def context_or_empty(context: str) -> str:
    """Every task of the arm gets the retrieval's answer; for a graph with no nodes the answer is that it has none."""
    return context or HEADER + "\nThe code graph at this commit holds no functions or classes."


def shape_row(instance_id: str, named: list[str], near: list[str], similar: list[str], context: str,
              edited: set[str]) -> dict:
    """What is committed about one task's context: counts, and whether a node the fix edits was listed (blank when
    the fix edits no node). The last is read from the answer and is for the analysis only."""
    listed = set(named) | set(near) | set(similar)
    return {"instance_id": instance_id, "named_node_count": len(named), "neighbour_node_count": len(near),
            "similar_node_count": len(similar), "context_chars": len(context),
            "is_edited_node_listed": bool(listed & edited) if edited else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", type=Path, required=True, help="the task set as published (tasks.jsonl, graphs/, embeddings/)")
    ap.add_argument("--out-context", type=Path, required=True, help="where the text goes (outside the repository)")
    ap.add_argument("--max-named", type=int, default=5)
    ap.add_argument("--max-neighbours", type=int, default=8)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    fr.check_out_path(a.out_context)
    coverage = pd.read_csv(TASKS_DIR / "graph_coverage.csv", keep_default_na=False).set_index("instance_id")
    tasks = [json.loads(line) for line in (a.published / "tasks.jsonl").read_text().splitlines() if line.strip()]
    texts = [(t.get("problem_statement") or "") + "\n" + (t.get("hints_text") or "") for t in tasks]
    queries = ss.unit_rows(ss.load_query_encoder()(texts))
    rows, contexts = [], []
    for t, text, query in zip(tasks, texts, queries):
        stem = f"{t['repo'].split('/')[-1]}_{t['base_commit']}"
        graph = json.loads((a.published / "graphs" / f"{stem}.json").read_text())
        with np.load(a.published / "embeddings" / f"{stem}.npz") as z:
            vectors = {k: z[k] for k in z.files}
        ids = {n["id"] for n in graph.get("nodes") or []}
        named = sorted(gc.named_nodes(text, ids))[:a.max_named]
        near = neighbours(set(named), graph, a.max_neighbours)
        similar = top_nodes(query, vectors, a.top)
        context = context_or_empty(graph_context(named, near, similar, gc.graph_modules(graph)))
        edited = {e for e in str(coverage.loc[t["instance_id"], "edited_node_text"]).split(";") if e}
        rows.append(shape_row(t["instance_id"], named, near, similar, context, edited))
        contexts.append({"instance_id": t["instance_id"], "context_text": context})
    a.out_context.parent.mkdir(parents=True, exist_ok=True)
    a.out_context.write_text("".join(json.dumps(c) + "\n" for c in contexts if c["context_text"]))
    table = pd.DataFrame(rows, columns=COLUMNS).sort_values("instance_id")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(a.out, index=False)
    edit = table[table.is_edited_node_listed.notna()]
    print(json.dumps({"task_count": len(table), "context_count": int((table.context_chars > 0).sum()),
                      "names_a_node_count": int((table.named_node_count > 0).sum()),
                      "median_context_chars": float(statistics.median(table.context_chars)),
                      "max_context_chars": int(table.context_chars.max()),
                      "edit_task_count": len(edit), "edited_node_listed_count": int(edit.is_edited_node_listed.astype(bool).sum()),
                      "empty_graph": list(table.instance_id[table.similar_node_count == 0])}, indent=1))
    print(f"-> {a.out} (counts); {a.out_context} (text, not committed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
