"""Issue #478: CI runs the suite twice, once on the newest pandas (3) and once on the library versions of the
Databricks serverless environment the jobs run on (pandas 2). #476 failed only on pandas 2: CI was green while
Load Open Dental failed on dev."""
import re

import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

WF = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PINS = REPO_ROOT / "python" / "constraints" / "databricks_serverless.txt"


def _pins() -> dict[str, str]:
    lines = [ln.split("#")[0].strip() for ln in PINS.read_text().splitlines()]
    return dict(ln.split("==") for ln in lines if ln)


def _jobs() -> dict:
    return yaml.safe_load(WF.read_text())["jobs"]


def _runs(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in job["steps"])


def test_the_pins_are_the_serverless_environment_the_bundle_names():
    version = yaml.safe_load((REPO_ROOT / "databricks.yml").read_text())["variables"]["gpu_environment_version"]
    header = PINS.read_text()
    assert re.search(rf"environment version {version['default']}\b", header), "pins and bundle disagree"
    pins = _pins()
    assert pins["pandas"].startswith("2.") and pins["numpy"] and pins["pyarrow"] and pins["scikit-learn"]


def test_ci_runs_the_whole_suite_on_the_runtime_pins_and_on_the_newest_too():
    jobs = _jobs()
    newest, runtime = jobs["python"], jobs["python-databricks-runtime"]
    assert "constraints/" not in _runs(newest)                        # the pandas 3 job stays as it was
    assert "-c python/constraints/databricks_serverless.txt" in _runs(runtime)
    for job in (newest, runtime):                                     # the whole suite, not a subset,
        assert "cd python && pytest -q -n auto tests" in _runs(job)   # in parallel (pytest-xdist, #510)
    assert "if" not in runtime                                        # every PR, docs-only too, like python
    py = next(s["with"]["python-version"] for s in runtime["steps"] if "setup-python" in s.get("uses", ""))
    assert py == "3.12"                                               # serverless environment 4 is Python 3.12


def test_the_runtime_job_checks_it_got_the_pinned_pandas():
    run = _runs(_jobs()["python-databricks-runtime"])
    assert "pandas.__version__" in run and "numpy.__version__" in run
