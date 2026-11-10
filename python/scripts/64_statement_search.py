"""Does embedding search find a task's fix? (spec 028, #662)

    python scripts/64_statement_search.py --published <the downloaded task set: tasks.jsonl, embeddings/>

The task set publishes one embedding per graph node (task_graph.embed_graph: EmbeddingGemma's document prompt, cut to
256 dimensions, renormalised). The agent's `search_similar_code` tool ranks nodes by similarity to a query. This
embeds each task's statement and hints with the same model's query prompt, ranks the task's nodes by cosine
similarity, and records the best rank of a node its reference patch edits (data/tasks/graph_coverage.csv, #659).

It is a count from the published files, not an agent run: it says where the edited code sits in the ranking a tool
could return, not that a model asks for the ranking or uses it. Writes data/tasks/statement_search.csv, one row per
task. Needs the gated model (HF_TOKEN) and about three minutes on a CPU.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from health_transformation_lab_nlp import task_graph as tg
from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

COVERAGE = TASKS_DIR / "graph_coverage.csv"
OUT = TASKS_DIR / "statement_search.csv"
COLUMNS = ["instance_id", "graph_node_count", "edited_node_count", "edited_node_best_rank_num", "is_named_or_called"]


def unit_rows(raw: np.ndarray, dims: int = tg.EMBED_DIMS) -> np.ndarray:
    """Each row cut to `dims` and scaled to length 1, as the published node vectors are."""
    cut = np.asarray(raw, dtype=np.float64)[:, :dims]
    norms = np.linalg.norm(cut, axis=1, keepdims=True)
    return np.divide(cut, norms, out=np.zeros_like(cut), where=norms > 0)


def best_rank(query: np.ndarray, vectors: dict[str, np.ndarray], edited: set[str]) -> int | None:
    """Where the closest edited node comes when every node is ranked by cosine similarity to the query (1 is first).
    None when the fix edits no node or the graph has none. An edited node with no vector is an error."""
    if not edited or not vectors:
        return None
    if missing := sorted(edited - set(vectors)):
        raise SystemExit(f"no embedding for {', '.join(missing[:3])}")
    ids = list(vectors)
    scores = np.stack([vectors[i] for i in ids]).astype(np.float64) @ np.asarray(query, dtype=np.float64)
    order = np.argsort(-scores, kind="stable")
    position = {ids[j]: rank for rank, j in enumerate(order, start=1)}
    return min(position[e] for e in edited)


def top_counts(rows: list[dict]) -> dict[str, dict[str, int]]:
    """How many tasks have an edited node first, in the first five and in the first ten: for every task with an
    edited node, and for those where neither a name nor a call edge led to the fix."""
    def count(sel: list[dict]) -> dict[str, int]:
        ranks = [r["edited_node_best_rank_num"] for r in sel]
        return {"tasks": len(ranks), "top1": sum(k <= 1 for k in ranks), "top5": sum(k <= 5 for k in ranks),
                "top10": sum(k <= 10 for k in ranks)}
    ranked = [r for r in rows if r["edited_node_best_rank_num"] is not None]
    return {"all": count(ranked), "missed": count([r for r in ranked if not r["is_named_or_called"]])}


def load_query_encoder():
    """EmbeddingGemma at the revision the node vectors were made with, as a texts -> (n, 768) function using the
    model's query prompt. A missing token fails here, before any work."""
    if not os.environ.get("HF_TOKEN"):
        sys.exit("HF_TOKEN is not set: the embedding model is gated (ops/secrets_register.yaml, Hugging Face read token)")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(tg.EMBED_MODEL, revision=tg.EMBED_REVISION, device="cpu")
    return lambda texts: model.encode_query(texts, batch_size=4, convert_to_numpy=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", type=Path, required=True, help="the task set as published (tasks.jsonl, embeddings/)")
    a = ap.parse_args()
    if not COVERAGE.exists():   # a required file: fail naming it
        sys.exit(f"{COVERAGE.relative_to(REPO_ROOT)} is missing: run scripts/63_graph_coverage.py first")
    coverage = pd.read_csv(COVERAGE, keep_default_na=False).set_index("instance_id")
    tasks = [json.loads(line) for line in (a.published / "tasks.jsonl").read_text().splitlines() if line.strip()]
    encode = load_query_encoder()
    queries = unit_rows(encode([(t.get("problem_statement") or "") + "\n" + (t.get("hints_text") or "") for t in tasks]))
    rows = []
    for t, query in zip(tasks, queries):
        npz = a.published / "embeddings" / f"{t['repo'].split('/')[-1]}_{t['base_commit']}.npz"
        if not npz.exists():
            sys.exit(f"no embeddings for {t['instance_id']}: {npz}")
        with np.load(npz) as z:
            vectors = {k: z[k] for k in z.files}
        c = coverage.loc[t["instance_id"]]
        edited = {e for e in str(c["edited_node_text"]).split(";") if e}
        rows.append({"instance_id": t["instance_id"], "graph_node_count": len(vectors), "edited_node_count": len(edited),
                     "edited_node_best_rank_num": best_rank(query, vectors, edited),
                     "is_named_or_called": str(c["statement_to_fix_edge_count"]) != ""})
    table = pd.DataFrame(rows, columns=COLUMNS).sort_values("instance_id")
    table["edited_node_best_rank_num"] = table["edited_node_best_rank_num"].astype("Int64")   # blank: no edited node
    table.to_csv(OUT, index=False)   # overwritten whole: re-runnable
    n = top_counts(rows)
    ranked = table.dropna(subset=["edited_node_best_rank_num"])
    print(f"{len(table)} tasks, {n['all']['tasks']} with an edited node (median graph {int(ranked['graph_node_count'].median())} "
          f"nodes, median best rank {int(ranked['edited_node_best_rank_num'].median())}): an edited node is first in "
          f"{n['all']['top1']}, in the first five in {n['all']['top5']}, in the first ten in {n['all']['top10']}")
    print(f"of the {n['missed']['tasks']} where neither a name nor a call edge leads to the fix: first in "
          f"{n['missed']['top1']}, first five in {n['missed']['top5']}, first ten in {n['missed']['top10']} "
          f"-> {OUT.relative_to(REPO_ROOT)}")
    print("A count from the published files, not an agent run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
