"""Spec 041 US3 (#858): fallback notebook copies traces when a run folder is gone.

US3's main path reloads run folders with kaggle/load_agent_traces.py (plan.md Order step 3).
This notebook is only for a source experiment that still has traces whose folders are missing.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / "databricks/notebooks/15_migrate_agent_traces.py"


def _src() -> str:
    assert NOTEBOOK.is_file(), f"missing {NOTEBOOK.relative_to(ROOT)}"
    return NOTEBOOK.read_text()


def test_notebook_declares_the_contract_widgets():
    text = _src()
    assert 'widgets.text("source_experiment_id"' in text
    assert 'widgets.text("target_experiment_name"' in text
    assert "/Shared/coding-agent-runs" in text


def test_notebook_installs_databricks_agents_for_migrate():
    text = _src()
    assert re.search(r"databricks-agents\s*>=\s*1\.10\.1", text), text
    assert "migrate_traces_to_uc" in text or "migrations.migrate_traces_to_uc" in text


def test_notebook_never_deletes_the_source_experiment():
    text = _src().lower()
    for banned in ("delete_experiment", "experiments.delete", "trash the source", "drop experiment"):
        assert banned not in text, banned


def test_count_table_is_delete_then_append_by_run_id():
    text = _src()
    assert "trace_migration_check" in text
    assert "ops_agent_trace" in text
    # delete-then-append by run_id (idempotent writes)
    assert re.search(r"delete\s+from\s+.*trace_migration_check", text, re.I)
    assert "run_id" in text and "run_ts" in text and "git_commit_sha" in text
    for col in (
        "experiment_id",
        "experiment_name",
        "assessment_name",
        "trace_count",
        "assessment_count",
    ):
        assert col in text, col
