"""Embed every task's code graph, in the competition's format (spec 028 US4, T010, #355).

    python scripts/55_build_tasks.py --graphs   # first: data/tasks/graphs/<instance_id>.json
    python scripts/59_embed_graphs.py           # then: data/tasks/embeddings/<instance_id>.npz (git-ignored)
    python scripts/59_embed_graphs.py --limit 2

One .npz per graph, one float32 array of shape (256,) per node, keyed by node id, as the competition's
embeddings/ files are (checked by scripts/56_competition_check.py). Each node's source text is encoded with
EmbeddingGemma (google/embeddinggemma-300m), cut to its first 256 dimensions and renormalised. The competition
doesn't name its model, so parity with its vectors is unverified: same shape and type, not the same space.

Needs `pip install -e ".[tasks,embed]"` and HF_TOKEN: a Hugging Face token whose account has accepted the Gemma
licence on the model's page, with read access to gated repositories. CPU is enough (about 57,000 nodes).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np

from health_transformation_lab_nlp import task_graph as tg
from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.paths import REPO_ROOT

TASKS_DIR = REPO_ROOT / "data" / "tasks"
GRAPHS = TASKS_DIR / "graphs"            # git-ignored, from 55_build_tasks.py --graphs
EMBEDDINGS = TASKS_DIR / "embeddings"    # git-ignored
MAX_TOKENS = 512                         # long functions are cut; the start names and documents them


def check_settings() -> str:
    """AGENTS.md: the graphs, the token's shape, then one cheap authenticated call, before loading the model."""
    if not sorted(GRAPHS.glob("*.json")):
        sys.exit(f"no graphs in {GRAPHS.relative_to(REPO_ROOT)}: run scripts/55_build_tasks.py --graphs first")
    token = os.environ.get("HF_TOKEN", "")
    if not token.startswith("hf_"):
        sys.exit("HF_TOKEN is missing or not a Hugging Face token (they start hf_)")
    req = urllib.request.Request(f"https://huggingface.co/{tg.EMBED_MODEL}/resolve/main/config.json",
                                 method="HEAD", headers={"Authorization": f"Bearer {token}"})
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        hint = (" (accept the Gemma licence on the model's page, and give the token read access to gated repos)"
                if e.code in (401, 403) else "")
        sys.exit(f"HF_TOKEN can't read {tg.EMBED_MODEL}: HTTP {e.code}{hint}")
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"Hugging Face unreachable ({e})")
    return token


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="embed only the first N graphs (0: all)")
    ap.add_argument("--batch-size", type=int, default=32)
    a = ap.parse_args()
    token = check_settings()
    telemetry.setup()
    telemetry.start_script("59_embed_graphs", data_label="public")

    # the [embed] extra; heavy, so imported after the checks
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(tg.EMBED_MODEL, device="cpu", token=token)
    model.max_seq_length = MAX_TOKENS

    cache: dict[str, np.ndarray] = {}   # most functions are unchanged from one base commit to the next

    def encode(texts: list[str]) -> np.ndarray:
        new = list(dict.fromkeys(t for t in texts if t not in cache))
        if new:
            rows = model.encode(new, batch_size=a.batch_size, convert_to_numpy=True, normalize_embeddings=False)
            cache.update(zip(new, rows))
        return np.stack([cache[t] for t in texts])

    graphs = sorted(GRAPHS.glob("*.json"))[: a.limit or None]
    start, nodes = time.time(), 0
    for i, path in enumerate(graphs, 1):
        g = json.loads(path.read_text())
        vectors = tg.embed_graph(g, encode)
        tg.write_embeddings(vectors, EMBEDDINGS / f"{path.stem}.npz")   # overwritten whole: re-runnable
        nodes += len(vectors)
        print(f"{i}/{len(graphs)} {path.stem}: {len(vectors)} nodes, {len(cache)} distinct texts so far "
              f"({time.time() - start:.0f} s)", flush=True)
    size = sum(p.stat().st_size for p in EMBEDDINGS.glob("*.npz")) / 1e6
    print(f"{len(graphs)} embeddings -> {EMBEDDINGS.relative_to(REPO_ROOT)}; {nodes} nodes, {tg.EMBED_DIMS} float32 "
          f"each, {tg.EMBED_MODEL}; {len(cache)} distinct texts encoded; {size:.0f} MB in all. "
          "Parity with the competition's own model: unverified")
    telemetry.end_script()
    return 0


if __name__ == "__main__":
    sys.exit(main())
