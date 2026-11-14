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
NOTEBOOKS = REPO / "databricks" / "notebooks"
# Notebooks that run the package's code in their own process: besides passing the switch on, they set telemetry
# up, open a run span named for themselves and end it themselves (a notebook's process may not run atexit).
IN_PROCESS_NOTEBOOKS = ["01_run_benchmark", "07_judge_scorecard", "10_load_results", "11_migrate_gold_names",
                        "12_load_open_dental", "13_pipeline_doctor", "14_pipeline_digest"]
# Scripts whose data isn't the default synthetic, or is simulated only in a dry-run mode: the text their label
# must contain.
LABEL_MUST_SAY = {
    "32_maccrobat_deid.py": '"public"',
    "33_maccrobat_phi_tagger.py": '"public"',
    "34_phi_tagger_regex.py": '"public"',
    "43_simulated_grader.py": '"simulated"',
    "14_benchmark_cost.py": '"--simulate-missing"',
    "15_judge.py": 'a.backend == "simulated"',
}


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


def _start_call(text: str) -> str:
    m = re.search(r"telemetry\.start_script\((?:[^()]|\([^()]*\))*\)", text)
    return m.group(0) if m else ""


def test_public_and_simulated_scripts_say_so_in_their_label():
    wrong = [f"{name}: {_start_call((SCRIPTS / name).read_text())!r}" for name, must in LABEL_MUST_SAY.items()
             if must not in _start_call((SCRIPTS / name).read_text())]
    assert not wrong, f"these labels don't match the data the script reads: {wrong}"


def test_no_label_tests_a_flag_the_script_does_not_have():
    wrong = []
    for f in sorted(SCRIPTS.glob("*.py")):
        text = f.read_text()
        for flag in re.findall(r'"(--[a-z-]+)" in sys\.argv', _start_call(text)):
            if f'"{flag}"' not in text.replace(_start_call(text), ""):
                wrong.append(f"{f.name}: {flag}")
    assert not wrong, f"the label tests a flag the script never declares: {wrong}"


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


def test_in_process_notebooks_set_up_start_and_end_their_own_run_span():
    missing = []
    for stem in IN_PROCESS_NOTEBOOKS:
        text = (NOTEBOOKS / f"{stem}.py").read_text()
        for needed in ("telemetry.setup()", f'telemetry.start_script("{stem}"', "telemetry.end_script()"):
            if needed not in text:
                missing.append(f"{stem}: {needed}")
    assert not missing, f"missing in the in-process notebooks: {missing}"
