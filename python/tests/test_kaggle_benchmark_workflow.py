"""The "Run PerioBench on Kaggle Benchmarks" workflow (.github/workflows/kaggle-benchmark.yml). Runs without the
Kaggle Benchmarks SDK, unlike test_kbench.py, so CI always checks it."""

import re
from pathlib import PurePosixPath

import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "kaggle-benchmark.yml"


def test_kaggle_b_init_has_a_folder_for_its_example_file():
    # issue #364: build/ is gitignored, so a fresh runner has none and `kaggle b init` failed with Errno 2
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["benchmark"]["steps"]
    runs = [s["run"] for s in steps if "kaggle b init" in s.get("run", "")]
    assert runs
    for run in runs:
        init = run.index("kaggle b init")
        target = re.search(r"--example-file\s+(\S+)", run[init:]).group(1)
        folder = str(PurePosixPath(target).parent)
        assert folder == "." or re.search(rf"mkdir -p (\S+ )*{re.escape(folder)}\b", run[:init]), \
            f"create {folder}/ before `kaggle b init` writes {target}"
