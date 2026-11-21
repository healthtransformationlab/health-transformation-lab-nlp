"""A missing module in a verdict is an environment fault, not an agent fail (#883)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "verify_env_guard", REPO_ROOT / "kaggle" / "verify_env_guard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_task_package_the_reference_can_import_is_an_ordinary_fail():
    g = _load()
    rows = [{
        "instance_id": "onav_47c8b791_schema_guard",
        "resolved": False,
        "error": None,
        "output_tail": "ModuleNotFoundError: No module named 'scrapers'",
    }]
    oracle = {"onav_47c8b791_schema_guard": {
        "instance_id": "onav_47c8b791_schema_guard",
        "resolved": True,
        "error": None,
        "output_tail": "1 passed",
    }}
    assert g.environment_faults(rows, oracle) == []
    g.assert_no_missing_modules(rows, oracle_by_id=oracle)


def test_a_verdict_with_no_module_named_is_an_environment_fault():
    g = _load()
    rows = [
        {"instance_id": "htlnlp_111", "resolved": True, "error": None, "output_tail": "6 passed"},
        {
            "instance_id": "htlnlp_226",
            "resolved": False,
            "error": None,
            "output_tail": "ModuleNotFoundError: No module named 'sklearn'",
        },
    ]
    assert g.missing_module_instance_ids(rows) == ["htlnlp_226"]
    with pytest.raises(g.MissingModuleError, match="htlnlp_226") as caught:
        g.assert_no_missing_modules(rows)
    assert "environment" in str(caught.value).lower()
    assert "ordinary failure" in str(caught.value).lower()


def test_a_clean_verdict_set_is_not_an_environment_fault():
    g = _load()
    rows = [
        {"instance_id": "htlnlp_111", "resolved": True, "error": None, "output_tail": "ok"},
        {"instance_id": "htlnlp_174", "resolved": False, "error": None, "output_tail": "1 failed"},
        {"instance_id": "htlnlp_178", "resolved": False, "error": "TimeoutError: ran out of time", "output_tail": ""},
    ]
    assert g.missing_module_instance_ids(rows) == []
    g.assert_no_missing_modules(rows)


def test_no_module_named_in_the_error_field_counts_too():
    g = _load()
    rows = [{"instance_id": "a", "resolved": False, "error": "No module named 'pytest'", "output_tail": ""}]
    assert g.missing_module_instance_ids(rows) == ["a"]


def test_a_module_the_reference_also_cannot_import_is_an_environment_fault():
    g = _load()
    rows = [{
        "instance_id": "htlnlp_226",
        "resolved": False,
        "error": None,
        "output_tail": "ModuleNotFoundError: No module named 'sklearn'",
    }]
    oracle = {"htlnlp_226": {
        "instance_id": "htlnlp_226",
        "resolved": False,
        "error": None,
        "output_tail": "ModuleNotFoundError: No module named 'sklearn'",
    }}
    assert g.environment_faults(rows, oracle) == [("htlnlp_226", "sklearn")]
    with pytest.raises(g.MissingModuleError, match="sklearn"):
        g.assert_no_missing_modules(rows, oracle_by_id=oracle)


def test_pytest_is_an_environment_fault_without_a_reference_verdict():
    g = _load()
    rows = [{"instance_id": "a", "resolved": False, "error": "No module named 'pytest'", "output_tail": ""}]
    assert g.environment_faults(rows, {}) == [("a", "pytest")]


def test_official_verify_refuses_an_oracle_total_when_a_module_is_missing():
    src = (REPO_ROOT / "kaggle" / "official_verify.py").read_text()
    gate = src.index('if a.patch == "oracle"')
    check = src.index("assert_no_missing_modules")
    printed = src.index('print(a.patch, "tasks"')
    assert gate < check < printed and "SystemExit(2)" in src


def test_the_collector_checks_the_reference_before_it_prints_a_resolve_count():
    src = (REPO_ROOT / "kaggle" / "official_agent_run.py").read_text()
    batch = src[src.index("def run_batch("):src.index("\ndef main(")]
    main = src[src.index("def main("):]
    assert batch.index("_refuse_missing_modules(") < batch.index("of {len(table)} resolved")
    assert main.index("require_launch_imports()") < main.index("run_batch(")
