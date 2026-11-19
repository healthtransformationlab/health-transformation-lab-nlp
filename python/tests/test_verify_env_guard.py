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


def test_official_verify_refuses_a_resolve_total_when_a_module_is_missing():
    src = (REPO_ROOT / "kaggle" / "official_verify.py").read_text()
    assert "assert_no_missing_modules" in src and "SystemExit(2)" in src
    assert src.index("assert_no_missing_modules") < src.index('print(a.patch, "tasks"')
