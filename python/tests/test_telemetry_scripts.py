"""Spec 014 US1: every pipeline step is traced. The library's functions are all @traced
(test_telemetry_calls.py), but their spans go nowhere unless the script that runs them calls
telemetry.setup(), and they have no run span to nest under without telemetry.start_script(). The same
holds for the Databricks jobs: a notebook passes the telemetry switch to the code it runs only if the
job gives it one."""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "python" / "scripts"
JOBS = REPO / "databricks" / "resources" / "jobs.yml"

# Files in python/scripts that aren't pipeline scripts, with the reason.
NOT_PIPELINE_SCRIPTS = {
    "_trace_plugin.py": "a pytest plugin loaded by 68_trace_reach.py, not a script that is run",
}
START = re.compile(r'telemetry\.start_script\(\s*"(?P<name>[^"]+)"')


def test_every_script_sets_up_telemetry_and_starts_a_run_span_named_for_itself():
    missing, misnamed = [], []
    for f in sorted(SCRIPTS.glob("*.py")):
        if f.name in NOT_PIPELINE_SCRIPTS:
            continue
        text = f.read_text()
        names = START.findall(text)
        if "telemetry.setup()" not in text or not names:
            missing.append(f.name)
        elif f.stem not in names:
            misnamed.append(f"{f.name}: {names}")
    assert not missing, f"call telemetry.setup() and telemetry.start_script(...) in: {missing}"
    assert not misnamed, f"start_script must be given the script's own name: {misnamed}"


def test_every_script_labels_its_data():
    unlabelled = [f.name for f in sorted(SCRIPTS.glob("*.py"))
                  if f.name not in NOT_PIPELINE_SCRIPTS
                  and "start_script(" in f.read_text()
                  and not re.search(r"start_script\([^)]*data_label=", f.read_text(), re.DOTALL)]
    assert not unlabelled, f"give start_script a data_label (synthetic, public or simulated) in: {unlabelled}"


def _python_notebook_tasks():
    jobs = yaml.safe_load(JOBS.read_text())["resources"]["jobs"]
    for job_name, job in jobs.items():
        for task in job.get("tasks", []):
            nb = task.get("notebook_task")
            if nb and nb["notebook_path"].endswith(".py"):     # a SQL notebook can't run the Python tracer
                yield job_name, task["task_key"], nb


def test_every_python_job_task_passes_the_telemetry_switch():
    missing = [f"{job}.{key}" for job, key, nb in _python_notebook_tasks()
               if (nb.get("base_parameters") or {}).get("telemetry") != "${var.telemetry_exporter}"]
    assert not missing, f"pass telemetry: ${{var.telemetry_exporter}} to: {missing}"


def test_every_python_job_notebook_reads_the_switch_and_the_secret():
    missing = []
    for job, key, nb in _python_notebook_tasks():
        text = (JOBS.parent / nb["notebook_path"]).resolve().read_text()
        if 'dbutils.widgets.text("telemetry"' not in text or "telemetry.use_databricks_secret(" not in text:
            missing.append(f"{job}.{key}: {nb['notebook_path']}")
    assert not missing, f"read the telemetry widget and call telemetry.use_databricks_secret in: {missing}"
