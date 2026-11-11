"""The paper's graph-reach counts on the competition's own development set (028 AI5, #669).

Scripts 63 and 64 count, for our 93 tasks, how often a task's code graph leads from its statement to the code its fix
edits: by a name the statement gives, by call edges from one, or by embedding search over the graph's nodes, against
what a random ranking would give. This makes the same counts on the competition's 129 development tasks, with its
own graphs, so the claim no longer rests on one repository. Three things differ:

- The changed files at each base commit come from GitHub (the three repositories are public), not the snapshots,
  which are 21.5 GB; they are cached under --cache and never committed.
- A module may sit under `src/` or a folder that is not a package; the graph's own module names decide.
- The provided embeddings are not EmbeddingGemma document vectors, and the competition's search_similar_code takes a
  symbol, not text (HARNESS_README section 8). So embedding search is counted twice: (a) our method, EmbeddingGemma
  ranking every node against the statement, as the paper does; (b) the competition's tool, from each node the
  statement names to its nearest nodes under the provided embeddings.

    python scripts/67_devset_graph_reach.py --tasks <competition tasks.jsonl> --graphs <dir> --embeddings <dir> \\
        --cache <dir> [--checkpoint <dir>]

Embedding 129 graphs takes a few hours on a CPU: with --checkpoint a stopped run keeps its finished rows and node
vectors in that scratch folder and resumes from them.

Writes data/tasks/devset/devset_graph_reach.csv: ids, counts and ranks, no text from the competition.
"""

from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from health_transformation_lab_nlp import task_graph as tg
from health_transformation_lab_nlp.paths import TASKS_DIR

HERE = Path(__file__).resolve().parent
OUT = TASKS_DIR / "devset" / "devset_graph_reach.csv"
RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"
COLUMNS = ["instance_id", "graph_node_count", "changed_file_count", "graphed_file_count", "is_fix_in_graph",
           "edited_node_count", "statement_node_count", "statement_to_fix_edge_count", "edited_node_best_rank_num",
           "provided_edited_node_best_rank_num"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gc = _load("63_graph_coverage")
ss = _load("64_statement_search")


_HUNK_START = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def git_headers(patch: str) -> str:
    """The competition's plain unified diff (`--- a/` and `+++ b/`, no `diff --git` line; a new file only as an
    `@@ -0,0` hunk) in git's layout, which script 63 reads: each file gets its `diff --git` line, and a new or deleted
    one its mode line, so it is not taken for a file modified in place. A git-style patch comes back unchanged."""
    if not patch or re.search(r"(?m)^diff --git ", patch):
        return patch
    lines = patch.splitlines(keepends=True)
    out = []
    for i, line in enumerate(lines):
        if (line.startswith("--- ") and i + 2 < len(lines) and lines[i + 1].startswith("+++ ")
                and lines[i + 2].startswith("@@ ")):
            old, new = line[4:].strip().split("\t")[0], lines[i + 1][4:].strip().split("\t")[0]
            a, b = old.removeprefix("a/"), new.removeprefix("b/")
            hunk = _HUNK_START.match(lines[i + 2])
            old_empty = old == "/dev/null" or bool(hunk and hunk.group(1) == "0" and hunk.group(2) == "0")
            new_empty = new == "/dev/null" or bool(hunk and hunk.group(3) == "0" and hunk.group(4) == "0")
            a, b = (b if a == "/dev/null" else a), (a if b == "/dev/null" else b)
            out.append(f"diff --git a/{a} b/{b}\n")
            if old_empty:
                out.append("new file mode 100644\n")
            elif new_empty:
                out.append("deleted file mode 100644\n")
        out.append(line)
    return "".join(out)


def resolve_module(path: str, modules: set[str]) -> str | None:
    """The graph's name for a changed Python file: the longest dotted tail of its path that is one of the graph's
    modules (`src/pkg/models.py` and `pkg/models.py` are both `pkg.models`). None for anything else."""
    if not path.endswith(".py"):
        return None
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    for i in range(len(parts)):
        if (candidate := ".".join(parts[i:])) in modules:
            return candidate
    return None


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as r:   # noqa: S310 - a fixed https host
        return r.read().decode("utf-8")


def fetch_source(repo: str, commit: str, path: str, cache: Path, fetch=None) -> str:
    """A file at a base commit, from GitHub once, then from the cache."""
    local = Path(cache) / repo.replace("/", "__") / commit / path
    if local.exists():
        return local.read_text(encoding="utf-8")
    text = (fetch or _fetch)(RAW.format(repo=repo, commit=commit, path=path))
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(text, encoding="utf-8")
    return text


def edited_for(task: dict, graph: dict, sources: dict[str, str]) -> tuple[set[str], int, int]:
    """The nodes the reference fix edits (script 63's edited_nodes, by the graph's own names), and the counts of
    files it changes and of those that are graph modules."""
    ids = {n["id"] for n in graph.get("nodes") or []}
    modules = gc.graph_modules(graph)
    patch = git_headers(task.get("patch") or "")
    files = gc.changed_files(patch)
    graphed = [f for f in files if resolve_module(f, modules)]
    edited: set[str] = set()
    for path, runs in gc.changed_runs(patch).items():
        module = resolve_module(path, modules)
        if module and path in sources:
            edited |= gc.edited_nodes(runs, sources[path], module) & ids
    return edited, len(files), len(graphed)


def provided_rank(named: set[str], edited: set[str], vectors: dict[str, np.ndarray]) -> int | None:
    """The competition's search_similar_code from each node the statement names: where the closest edited node comes
    among that node's nearest nodes (1 is first; 0 when the statement names an edited node itself). None when the fix
    edits no node, or no named node has a vector to search from."""
    if not edited:
        return None
    if named & edited:
        return 0
    keys = list(vectors)
    index = {k: i for i, k in enumerate(keys)}
    matrix = np.stack([np.asarray(vectors[k], dtype=np.float64) for k in keys])
    matrix = matrix / np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12, None)
    best = None
    for node in sorted(named):
        if node not in index:
            continue
        order = [keys[j] for j in np.argsort(-(matrix @ matrix[index[node]]), kind="stable") if keys[j] != node]
        rank = next((pos for pos, k in enumerate(order, start=1) if k in edited), None)
        if rank is not None and (best is None or rank < best):
            best = rank
    return best


def reach_row(task: dict, graph: dict, sources: dict[str, str], provided: dict | None = None,
              query: np.ndarray | None = None, ours: dict | None = None) -> dict:
    """One task's row: ids, counts and ranks only."""
    edited, files, graphed = edited_for(task, graph, sources)
    ids = {n["id"] for n in graph.get("nodes") or []}
    named = gc.named_nodes((task.get("problem_statement") or "") + "\n" + (task.get("hints_text") or ""), ids)
    return {"instance_id": task["instance_id"], "graph_node_count": len(ids), "changed_file_count": files,
            "graphed_file_count": graphed, "is_fix_in_graph": graphed > 0, "edited_node_count": len(edited),
            "statement_node_count": len(named),
            "statement_to_fix_edge_count": gc.call_distance(named, edited, graph) if edited else None,
            "edited_node_best_rank_num": ss.best_rank(query, ours, edited) if (
                query is not None and ours and edited) else None,
            "provided_edited_node_best_rank_num": provided_rank(named, edited, provided) if provided else None}


def _present(v) -> bool:
    return v is not None and not (isinstance(v, float) and np.isnan(v))


def summary(rows: list[dict]) -> dict:
    """The paper's partition: the fix outside the graph, in it but editing no existing node, or editing one; of the
    last, reached by a name, by call edges, by embedding search (first one and first ten), by any of the three, and
    by the competition's own tool beyond what the statement names (its rank 0 is a named edited node, a find the tool
    did not make) and beyond names and call edges; and what a random ranking would give."""
    edit = [r for r in rows if r["edited_node_count"] > 0]

    def top(r, col, k):
        return _present(r[col]) and r[col] <= k

    def chance(k):
        return sum(ss.chance_top(int(r["graph_node_count"]), int(r["edited_node_count"]), k) for r in edit)

    return {"task_count": len(rows), "outside_graph_count": sum(not r["is_fix_in_graph"] for r in rows),
            "no_existing_node_count": sum(bool(r["is_fix_in_graph"]) and r["edited_node_count"] == 0 for r in rows),
            "edit_node_count": len(edit),
            "named_count": sum(_present(r["statement_to_fix_edge_count"]) and r["statement_to_fix_edge_count"] == 0
                               for r in edit),
            "called_count": sum(_present(r["statement_to_fix_edge_count"]) and r["statement_to_fix_edge_count"] > 0
                                for r in edit),
            "embedding_top1_count": sum(top(r, "edited_node_best_rank_num", 1) for r in edit),
            "embedding_top5_count": sum(top(r, "edited_node_best_rank_num", 5) for r in edit),
            "embedding_top10_count": sum(top(r, "edited_node_best_rank_num", 10) for r in edit),
            "reached_count": sum(_present(r["statement_to_fix_edge_count"]) or top(r, "edited_node_best_rank_num", 10)
                                 for r in edit),
            "provided_top10_beyond_named_count": sum(top(r, "provided_edited_node_best_rank_num", 10)
                                                     and r["provided_edited_node_best_rank_num"] > 0 for r in edit),
            "provided_top10_beyond_name_or_call_count": sum(top(r, "provided_edited_node_best_rank_num", 10)
                                                            and not _present(r["statement_to_fix_edge_count"])
                                                            for r in edit),
            "chance_top1": chance(1), "chance_top5": chance(5), "chance_top10": chance(10)}


def load_done(path: Path) -> dict[str, dict]:
    """The rows a stopped run already made, by task id; a last line cut off mid-write is dropped."""
    done = {}
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[row["instance_id"]] = row
    return done


def append_row(path: Path, row: dict) -> None:
    """Keep one finished row (a checkpoint for this run only; the table is written whole at the end)."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=lambda v: v.item() if hasattr(v, "item") else str(v)) + "\n")


class TextCache(dict):
    """text -> unit vector for task_graph.embed_graph, held by each text's SHA-256 so it can be saved and loaded
    without the text (a restart then embeds only what it has not seen)."""

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def __contains__(self, text) -> bool:
        return dict.__contains__(self, self._key(text))

    def __getitem__(self, text):
        return dict.__getitem__(self, self._key(text))

    def __setitem__(self, text, vector) -> None:
        dict.__setitem__(self, self._key(text), vector)

    def update(self, pairs) -> None:
        for text, vector in pairs:
            self[text] = vector

    def save(self, path: Path) -> None:
        tmp = Path(path).with_suffix(".tmp.npz")
        np.savez(tmp, **dict(self.items()))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "TextCache":
        cache = cls()
        if Path(path).exists():
            with np.load(path) as z:
                for key in z.files:
                    dict.__setitem__(cache, key, z[key])
        return cache


def _document_encoder():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(tg.EMBED_MODEL, revision=tg.EMBED_REVISION, device="cpu")
    return lambda texts: model.encode_document(texts, batch_size=16, convert_to_numpy=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, required=True, help="the competition's tasks.jsonl (never committed)")
    ap.add_argument("--graphs", type=Path, required=True)
    ap.add_argument("--embeddings", type=Path, required=True, help="the competition's provided embeddings")
    ap.add_argument("--cache", type=Path, required=True, help="where the files read from GitHub are kept")
    ap.add_argument("--no-ours", action="store_true", help="skip EmbeddingGemma (method a)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--checkpoint", type=Path, help="a scratch folder for finished rows and node vectors, so a stopped "
                    "run resumes where it stopped (never committed)")
    a = ap.parse_args()
    if not a.no_ours and not os.environ.get("HF_TOKEN"):
        sys.exit("HF_TOKEN is not set: the embedding model is gated (ops/secrets_register.yaml, Hugging Face read token)")
    tasks = [json.loads(line) for line in a.tasks.read_text().splitlines() if line.strip()]
    query_encoder = None if a.no_ours else ss.load_query_encoder()
    doc_encoder = None if a.no_ours else _document_encoder()
    rows_path = vec_path = None
    if a.checkpoint:
        a.checkpoint.mkdir(parents=True, exist_ok=True)
        rows_path = a.checkpoint / ("rows_no_ours.jsonl" if a.no_ours else "rows.jsonl")
        vec_path = a.checkpoint / "vectors.npz"
    done = load_done(rows_path) if rows_path else {}
    cache = TextCache.load(vec_path) if vec_path else TextCache()
    rows, missing = [], []
    for n, task in enumerate(tasks, start=1):
        if task["instance_id"] in done:
            rows.append(done[task["instance_id"]])
            continue
        stem = f"{task['repo'].split('/')[-1]}_{task['base_commit']}"
        gpath, epath = a.graphs / f"{stem}.json", a.embeddings / f"{stem}.npz"
        if not gpath.exists():
            missing.append(task["instance_id"])
            continue
        graph = json.loads(gpath.read_text())
        modules = gc.graph_modules(graph)
        sources = {p: fetch_source(task["repo"], task["base_commit"], p, a.cache)
                   for p in gc.changed_runs(git_headers(task.get("patch") or "")) if resolve_module(p, modules)}
        provided = dict(np.load(epath)) if epath.exists() else None
        query = ours = None
        if query_encoder is not None:
            text = (task.get("problem_statement") or "") + "\n" + (task.get("hints_text") or "")
            query = ss.unit_rows(query_encoder([text]))[0]
            ours = tg.embed_graph(graph, doc_encoder, cache=cache)
        rows.append(reach_row(task, graph, sources, provided, query, ours))
        if rows_path:
            append_row(rows_path, rows[-1])
            if ours is not None:
                cache.save(vec_path)
        print(f"[{n}/{len(tasks)}] {task['instance_id']}: edited {rows[-1]['edited_node_count']}, "
              f"rank {rows[-1]['edited_node_best_rank_num']}, provided {rows[-1]['provided_edited_node_best_rank_num']}",
              flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows, columns=COLUMNS).sort_values("instance_id")
    for column in ("statement_to_fix_edge_count", "edited_node_best_rank_num", "provided_edited_node_best_rank_num"):
        table[column] = table[column].astype("Int64")   # whole numbers; blank where there is none
    table.to_csv(a.out, index=False)
    s = summary(rows)
    print(json.dumps(s, indent=1))
    print(f"no graph for {len(missing)}: {', '.join(missing) or 'none'}")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
