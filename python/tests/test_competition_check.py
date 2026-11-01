"""Issue #439: pick the competition's small files, and compare its snapshot, graph and embedding formats with ours."""
import io
import json
import tarfile

import numpy as np

from health_transformation_lab_nlp import competition_check as cc

LISTING = [("HARNESS_README.md", 57_000), ("tasks.jsonl", 9_000_000), ("docker/Dockerfile.public", 2_000),
           ("docker/imp.py", 900), ("sandbox/setup.py", 8_000), ("sample_submission/agent.yaml", 700),
           ("wheels/rich-13.7.1-py3-none-any.whl", 240_000), ("wheels/swegemma-0.3.0-py3-none-any.whl", 400_000),
           ("wheels/adk_submission-0.2.0-py3-none-any.whl", 90_000),
           ("snapshots/fastapi_11194.tgz", 40_000_000), ("snapshots/httpx_3672.tgz", 3_000_000),
           ("graphs/httpx_3672.json", 2_000_000), ("graphs/httpx_abc.json", 2_000_000),
           ("graphs/fastapi_11194.json", 9_000_000), ("embeddings/httpx_3672.npz", 1_000_000),
           ("embeddings/fastapi_11194.npz", 5_000_000)]


def test_only_the_small_files_and_the_smallest_task_are_picked():
    picked = cc.select_files(LISTING)
    assert picked == ["HARNESS_README.md", "docker/Dockerfile.public", "docker/imp.py", "sandbox/setup.py",
                      "sample_submission/agent.yaml", "wheels/adk_submission-0.2.0-py3-none-any.whl",
                      "wheels/swegemma-0.3.0-py3-none-any.whl", "snapshots/httpx_3672.tgz",
                      "graphs/httpx_3672.json", "embeddings/httpx_3672.npz"]
    assert "tasks.jsonl" not in picked and "wheels/rich-13.7.1-py3-none-any.whl" not in picked


def _tgz(path, names):
    with tarfile.open(path, "w:gz") as t:
        for n in names:
            data = b"x"
            info = tarfile.TarInfo(n)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))


def test_snapshot_layout_tells_a_root_folder_from_files_at_the_root(tmp_path):
    _tgz(tmp_path / "a.tgz", ["workspace/.git/HEAD", "workspace/httpx/__init__.py"])
    _tgz(tmp_path / "b.tgz", [".git/HEAD", "httpx/__init__.py", "README.md"])
    a, b = cc.snapshot_layout(tmp_path / "a.tgz"), cc.snapshot_layout(tmp_path / "b.tgz")
    assert a == {"root_folder": "workspace", "git_dir": "workspace/.git", "entries": 2}
    assert b == {"root_folder": None, "git_dir": ".git", "entries": 3}


def test_graph_summary_reports_the_keys_the_tools_read(tmp_path):
    g = {"directed": True, "multigraph": True, "graph": {}, "nodes": [{"id": "httpx._api.get", "name": "httpx._api.get",
         "text": "def get(): ..."}], "edges": [{"source": "httpx._api.get", "target": "httpx._api.request",
                                               "type": "calls", "key": 0}]}
    (tmp_path / "g.json").write_text(json.dumps(g))
    s = cc.graph_summary(tmp_path / "g.json")
    assert s["top_keys"] == ["directed", "edges", "graph", "multigraph", "nodes"]
    assert s["node_keys"] == ["id", "name", "text"] and s["edge_keys"] == ["key", "source", "target", "type"]
    assert s["edge_types"] == ["calls"] and s["sample_ids"] == ["httpx._api.get"] and s["nodes"] == 1


def test_embedding_summary_reports_vector_length_and_type(tmp_path):
    np.savez_compressed(tmp_path / "e.npz", **{"httpx._api.get": np.zeros(256, "float32"),
                                               "httpx._api.request": np.ones(256, "float32")})
    assert cc.embedding_summary(tmp_path / "e.npz") == {"arrays": 2, "shapes": ["(256,)"], "dtypes": ["float32"],
                                                        "sample_keys": ["httpx._api.get", "httpx._api.request"]}


def test_the_report_compares_with_our_formats():
    theirs = {"snapshot": {"root_folder": None, "git_dir": ".git", "entries": 3},
              "graph": {"top_keys": ["directed", "edges", "graph", "multigraph", "nodes"],
                        "node_keys": ["id", "name", "text"], "edge_keys": ["key", "source", "target", "type"],
                        "edge_types": ["calls"], "sample_ids": ["httpx._api.get"], "nodes": 1},
              "embedding": {"arrays": 2, "shapes": ["(256,)"], "dtypes": ["float32"], "sample_keys": ["a"]},
              "harness_wheels": ["wheels/swegemma-0.3.0-py3-none-any.whl"]}
    lines = cc.compare_with_ours(theirs)
    assert any(line.startswith("DIFFERS snapshot root") for line in lines)        # ours has a workspace/ folder
    assert any(line.startswith("MATCHES graph keys") for line in lines)
    assert any(line.startswith("MATCHES embeddings") for line in lines)
    assert any(line.startswith("FOUND swegemma") for line in lines)


def test_the_workflow_installs_six_with_kaggle():
    """kaggle 2.2.5 imports six without declaring it (#450)."""
    from health_transformation_lab_nlp.paths import REPO_ROOT
    wf = (REPO_ROOT / ".github/workflows/kaggle-competition-check.yml").read_text()
    line = next(x for x in wf.splitlines() if "pip install" in x and "kaggle==" in x)
    assert "six" in line.split()
