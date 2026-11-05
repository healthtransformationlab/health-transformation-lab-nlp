"""#535: a public Kaggle notebook that loads the coding-agent task set, on CPU, from the published layout."""

import contextlib
import io
import json
import subprocess
import sys
import tarfile

import numpy as np

from health_transformation_lab_nlp.paths import REPO_ROOT

NB = REPO_ROOT / "notebooks" / "agent_tasks_quickstart.ipynb"


def _layout(root):
    """The published layout, small: one task, its snapshot, graph and embeddings."""
    row = json.loads((REPO_ROOT / "data" / "tasks" / "tasks_sample.jsonl").read_text().splitlines()[0])
    root.mkdir(parents=True)
    (root / "tasks.jsonl").write_text(json.dumps(row) + "\n")
    name = f"{row['repo'].split('/')[-1]}_{row['base_commit']}"
    for d in ("snapshots", "graphs", "embeddings"):
        (root / d).mkdir(parents=True)
    src = root / "src"
    (src / "python").mkdir(parents=True)
    (src / "python" / "mod.py").write_text("def load():\n    return 1\n")
    with tarfile.open(root / "snapshots" / f"{row['instance_id']}.tgz", "w:gz") as tf:
        tf.add(src / "python", arcname="python")
    ids = ["pkg.mod.load", "pkg.mod.read", "pkg.other.plot"]
    graph = {"directed": True, "multigraph": True, "graph": {},
             "nodes": [{"id": i, "name": i, "text": f"def {i.split('.')[-1]}(): ..."} for i in ids],
             "edges": [{"source": ids[0], "target": ids[1], "type": "calls", "key": 0}]}
    (root / "graphs" / f"{name}.json").write_text(json.dumps(graph))
    vec = {ids[0]: [1.0, 0.0], ids[1]: [0.9, 0.1], ids[2]: [0.0, 1.0]}
    np.savez_compressed(root / "embeddings" / f"{name}.npz", **{k: np.asarray(v, np.float32) for k, v in vec.items()})
    return row


def test_the_notebook_reads_a_task_its_snapshot_graph_and_embeddings(monkeypatch, tmp_path):
    row = _layout(tmp_path / "ds")
    monkeypatch.setenv("AGENT_TASKS_DIR", str(tmp_path / "ds"))
    monkeypatch.chdir(tmp_path)
    ns, out = {}, io.StringIO()
    with contextlib.redirect_stdout(out):
        for cell in json.loads(NB.read_text())["cells"]:
            if cell["cell_type"] == "code":
                exec("".join(cell["source"]), ns)   # noqa: S102 - our own notebook
    printed = out.getvalue()
    assert ns["task"]["instance_id"] == row["instance_id"]
    assert (ns["workspace"] / "python" / "mod.py").exists()       # the snapshot unpacked
    assert len(ns["nodes"]) == 3 and len(ns["edges"]) == 1
    assert ns["nearest"][0][0] == "pkg.mod.read"                  # the closest other node to the symbol
    assert row["instance_id"] in printed and "diff --git" in printed


def test_the_notebook_is_saved_clean_and_says_where_the_tasks_come_from():
    text = NB.read_text()
    for s in ("not affiliated", "kaggle.com/datasets/jcblearning/health-transformation-lab-coding-agent-tasks",
              "github.com/healthtransformationlab/health-transformation-lab-nlp"):
        assert s in text, s
    assert all(not c.get("outputs") for c in json.loads(text)["cells"] if c["cell_type"] == "code")


def test_the_kaggle_kernel_attaches_the_task_set_and_needs_no_gpu(tmp_path):
    subprocess.run([sys.executable, str(REPO_ROOT / "kaggle" / "prepare_kernel.py"), "--job", "tasks-quickstart",
                    "--out", str(tmp_path / "k"), "--username", "someone"], check=True)
    meta = json.loads((tmp_path / "k" / "kernel-metadata.json").read_text())
    assert meta["id"] == "someone/coding-agent-tasks-quickstart"
    assert len(meta["title"]) <= 50   # #602: Kaggle refuses a longer kernel title with a bare 400
    assert meta["is_private"] is False and meta["enable_gpu"] is False and meta["enable_internet"] is False
    assert meta["dataset_sources"] == ["someone/health-transformation-lab-coding-agent-tasks"]
    assert (tmp_path / "k" / meta["code_file"]).read_text() == NB.read_text()


def test_the_task_set_workflow_publishes_the_notebook():
    import yaml
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "kaggle-publish-tasks.yml").read_text())
    steps = " ".join(s.get("run", "") for s in wf["jobs"]["publish"]["steps"])
    assert "--job tasks-quickstart" in steps and "kaggle kernels push -p build/tasks-quickstart" in steps
    assert '$KAGGLE_USERNAME/coding-agent-tasks-quickstart"' in steps   # polls the kernel it pushed
