"""Spec 025 US2: the quickstart notebook runs on the published files, from either platform's layout, and its
baseline scores what the leaderboard's tfidf_logreg does."""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys

import pandas as pd
import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

NB = REPO_ROOT / "notebooks" / "perio_bench_quickstart.ipynb"


def _run(monkeypatch, root):
    monkeypatch.setenv("PERIO_BENCH_DIR", str(root))
    ns, out = {}, io.StringIO()
    with contextlib.redirect_stdout(out):
        for cell in json.loads(NB.read_text())["cells"]:
            if cell["cell_type"] == "code":
                exec("".join(cell["source"]), ns)   # noqa: S102 - our own notebook
    return ns, out.getvalue()


def _publish(platform, tmp_path, name):
    script = REPO_ROOT / platform / "publish.py"
    args = [sys.executable, str(script), "--dataset", name, "--out", str(tmp_path / name), "--commit", "abc1234"]
    if platform == "kaggle":
        args += ["--username", "someone"]
    subprocess.run(args, check=True, capture_output=True)


@pytest.mark.parametrize("platform", ["huggingface", "kaggle"])
def test_the_notebook_runs_on_each_platforms_layout(monkeypatch, tmp_path, platform):
    for name in ("notes", "results"):
        _publish(platform, tmp_path, name)
    ns, printed = _run(monkeypatch, tmp_path)
    assert len(ns["train"]) == 3016 and len(ns["test"]) == 223     # the #467 build
    board = pd.read_csv(REPO_ROOT / "data" / "datasets" / "ladder" / "ladder_vs_truth.csv").set_index("method")
    ref = board.loc["tfidf_logreg"]
    assert ref.acc_lo <= ns["accuracy"] <= ref.acc_hi           # the same method scores as published
    assert "on synthetic notes" in printed and "your baseline" in printed
    assert "synthetic review notes" in printed                   # the leaderboard table is labelled too


def test_the_notebook_says_synthetic_and_links_both_platforms():
    text = NB.read_text()
    for s in ("Everything here is synthetic", "not affiliated", "huggingface.co/datasets/healthtransformationlab",
              "kaggle.com/datasets/jcblearning/perio-bench-notes"):
        assert s in text, s
    assert all(not c.get("outputs") for c in json.loads(text)["cells"] if c["cell_type"] == "code")   # saved clean


def test_kaggle_quickstart_kernel_attaches_both_datasets_and_needs_no_gpu(tmp_path):
    spec = importlib.util.spec_from_file_location("prepare_kernel", REPO_ROOT / "kaggle" / "prepare_kernel.py")
    sys.path.insert(0, str(REPO_ROOT / "kaggle"))
    pk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pk)
    subprocess.run([sys.executable, str(REPO_ROOT / "kaggle" / "prepare_kernel.py"), "--job", "quickstart",
                    "--out", str(tmp_path / "k"), "--username", "someone"], check=True)
    meta = json.loads((tmp_path / "k" / "kernel-metadata.json").read_text())
    assert meta["id"] == "someone/perio-bench-quickstart" and meta["is_private"] is False
    assert meta["enable_gpu"] is False and meta["enable_internet"] is False
    assert meta["dataset_sources"] == ["someone/perio-bench-notes", "someone/perio-bench-results"]
    assert (tmp_path / "k" / meta["code_file"]).read_text() == NB.read_text()
