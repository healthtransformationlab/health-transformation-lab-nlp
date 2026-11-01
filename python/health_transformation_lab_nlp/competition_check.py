"""Compare spec 028's task set with the Gemma 4 Developer Agent competition's own files (#439).

    select_files       the competition files worth downloading: the harness guide, the Docker and sandbox setup, the
                       sample submission, any swegemma / adk-* wheel, and the smallest snapshot with its graph and
                       embedding (not the 22 GB whole)
    snapshot_layout    whether a snapshot .tgz has a root folder or its files at the root, and where `.git` is
    graph_summary      the keys the graph tools read, edge types and sample node ids
    embedding_summary  array count, shapes and dtypes of an embedding .npz
    compare_with_ours  MATCHES / DIFFERS / FOUND lines against the formats task_graph writes

The competition's format is documented on kaggle.com/competitions/gemma-4-developer-agent/data; nothing here
downloads or keeps its data beyond the run that calls it.
"""
from __future__ import annotations

import json
import re
import tarfile
from pathlib import Path

import numpy as np

from .telemetry import traced

COMPETITION = "gemma-4-developer-agent"
SMALL_FILES = ("HARNESS_README.md",)
SMALL_FOLDERS = ("docker/", "sandbox/", "sample_submission/")
HARNESS_WHEEL = re.compile(r"^wheels/(swegemma|adk[_-]submission|adk[_-]eval[_-]core)[-_].*\.whl$", re.IGNORECASE)
# what task_graph writes (spec 028 US4): files at the archive root (#452), these graph keys, 256 float32 per node
OUR_SNAPSHOT_ROOT = None
OUR_GRAPH_TOP = ["directed", "edges", "graph", "multigraph", "nodes"]
OUR_NODE_KEYS = ["id", "name", "text"]
OUR_EDGE_KEYS = ["key", "source", "target", "type"]
OUR_VECTOR = ("(256,)", "float32")


@traced
def select_files(listing: list[tuple[str, int]]) -> list[str]:
    """From (name, bytes) pairs, the files to download, sorted: the small files and folders, harness wheels, and the
    smallest snapshot with the graph and embedding of the same instance id."""
    names = {n for n, _ in listing}
    picked = {n for n in names if n in SMALL_FILES or n.startswith(SMALL_FOLDERS) or HARNESS_WHEEL.match(n)}
    snapshots = sorted(((size, n) for n, size in listing if n.startswith("snapshots/") and n.endswith(".tgz")))
    if snapshots:
        iid = Path(snapshots[0][1]).name.removesuffix(".tgz")
        picked |= {snapshots[0][1]} | {f for f in (f"graphs/{iid}.json", f"embeddings/{iid}.npz") if f in names}
    if not any(n.startswith("graphs/") for n in picked):   # only `<repo_short>_<base_commit>` copies listed (#452)
        pairs = sorted((size, n) for n, size in listing if n.startswith("graphs/") and n.endswith(".json")
                       and f"embeddings/{Path(n).stem}.npz" in names)
        if pairs:
            picked |= {pairs[0][1], f"embeddings/{Path(pairs[0][1]).stem}.npz"}
    return sorted(picked, key=lambda n: (n.split("/")[0] != "HARNESS_README.md", _order(n), n))


def _order(name: str) -> int:
    for i, prefix in enumerate(("HARNESS_README.md", "docker/", "sandbox/", "sample_submission/", "wheels/",
                                "snapshots/", "graphs/", "embeddings/")):
        if name.startswith(prefix):
            return i
    return 99


@traced
def snapshot_layout(tgz: Path) -> dict:
    """The archive's single root folder (None if files sit at the root), where `.git` is, and how many top-level
    entries there are under that root."""
    with tarfile.open(tgz) as t:
        names = [n for n in (m.name.removeprefix("./").rstrip("/") for m in t.getmembers()) if n and n != "."]
    tops = {n.split("/")[0] for n in names}
    root = next(iter(tops)) if len(tops) == 1 and any("/" in n for n in names) else None
    under = [n.split("/", 1)[1] for n in names if "/" in n] if root else names
    entries = {n.split("/")[0] for n in under if n}
    git = next((n for n in (f"{root}/.git" if root else ".git",) if any(x == n or x.startswith(n + "/")
                                                                       for x in names)), None)
    return {"root_folder": root, "git_dir": git, "entries": len(entries)}


@traced
def graph_summary(path: Path) -> dict:
    """Top-level keys, node and edge keys, edge types and the first node ids of a NetworkX node-link graph."""
    g = json.loads(Path(path).read_text())
    nodes, edges = g.get("nodes", []), g.get("edges", g.get("links", []))
    return {"top_keys": sorted(g), "node_keys": sorted({k for n in nodes for k in n}),
            "edge_keys": sorted({k for e in edges for k in e}), "edge_types": sorted({e.get("type") for e in edges
                                                                                       if e.get("type")}),
            "sample_ids": [n.get("id") for n in nodes[:3]], "nodes": len(nodes)}


@traced
def embedding_summary(path: Path) -> dict:
    """Array count, distinct shapes and dtypes, and the first keys of an .npz of per-node vectors."""
    with np.load(path) as z:
        keys = sorted(z.files)
        arrays = [z[k] for k in keys]
    return {"arrays": len(keys), "shapes": sorted({str(a.shape) for a in arrays}),
            "dtypes": sorted({str(a.dtype) for a in arrays}), "sample_keys": keys[:2]}


@traced
def compare_with_ours(theirs: dict) -> list[str]:
    """One line per check, starting MATCHES, DIFFERS, FOUND or MISSING, so the workflow log reads at a glance."""
    out = []
    s = theirs.get("snapshot")
    if s:
        same = s["root_folder"] == OUR_SNAPSHOT_ROOT
        ours = f"a {OUR_SNAPSHOT_ROOT}/ folder" if OUR_SNAPSHOT_ROOT else "files at the root"
        out.append(f"{'MATCHES' if same else 'DIFFERS'} snapshot root: theirs {s['root_folder'] or 'files at the root'}"
                   f" (.git at {s['git_dir']}), ours {ours}")
    g = theirs.get("graph")
    if g:
        same = (g["top_keys"], g["node_keys"], g["edge_keys"]) == (OUR_GRAPH_TOP, OUR_NODE_KEYS, OUR_EDGE_KEYS)
        out.append(f"{'MATCHES' if same else 'DIFFERS'} graph keys: top {g['top_keys']}, nodes {g['node_keys']}, "
                   f"edges {g['edge_keys']}; edge types {g['edge_types']}; sample ids {g['sample_ids']}")
    e = theirs.get("embedding")
    if e:
        same = e["shapes"] == [OUR_VECTOR[0]] and e["dtypes"] == [OUR_VECTOR[1]]
        out.append(f"{'MATCHES' if same else 'DIFFERS'} embeddings: {e['arrays']} arrays, shapes {e['shapes']}, "
                   f"dtypes {e['dtypes']}, sample keys {e['sample_keys']}")
    wheels = theirs.get("harness_wheels") or []
    out.append(f"FOUND swegemma: {', '.join(wheels)}" if any("swegemma" in w.lower() for w in wheels)
               else "MISSING swegemma: no swegemma wheel in wheels/ (see docker/Dockerfile.public)")
    return out
