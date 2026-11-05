"""The probe copy of the PerioBench task (#593): the same task file, pushed as `perio-bench-probe` on a few notes,
so a change can be checked on Kaggle for cents before a full run."""

import importlib.util

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("probe_task", REPO_ROOT / "kaggle" / "probe_task.py")
probe_task = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe_task)
TASK_FILE = REPO_ROOT / "kaggle" / "perio_bench_task.py"


def test_probe_is_the_task_under_another_slug_on_a_few_notes():
    text = TASK_FILE.read_text()
    probe = probe_task.make_probe(text, n=3)
    assert 'name="perio-bench-probe"' in probe and 'name="perio-bench"' not in probe
    assert 'n = "3"' in probe and "PERIO_BENCH_N" not in probe
    # everything else is the same file, so the probe tests exactly what a full run would push
    assert probe.replace('name="perio-bench-probe"', 'name="perio-bench"').replace('n = "3"', 'n = os.environ.get("PERIO_BENCH_N")') == text


def test_probe_fails_loudly_when_the_task_file_changes_shape():
    with pytest.raises(ValueError, match="once"):
        probe_task.make_probe("# %%\nprint('no task here')\n", n=3)


def test_the_workflow_offers_the_probe_and_never_publishes_it():
    wf = (REPO_ROOT / ".github" / "workflows" / "kaggle-benchmark.yml").read_text()
    assert "probe:" in wf and "kaggle/probe_task.py" in wf
    assert "inputs.action == 'publish' && !inputs.probe" in wf
