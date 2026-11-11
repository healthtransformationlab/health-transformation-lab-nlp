"""028 AI7 (#674): the same tasks with and without a failing test's report, set side by side. The paired table holds
ids, counts and booleans; the test is the exact McNemar test the pre-registration names; a pair with a side that did
not run leaves the test and is counted."""
import importlib.util

import pandas as pd
import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT


@pytest.fixture(scope="module")
def cp():
    spec = importlib.util.spec_from_file_location("context_pairs", REPO_ROOT / "python" / "scripts" / "70_context_pairs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_exact_mcnemar_test_is_a_binomial_test_on_the_discordant_pairs(cp):
    assert cp.mcnemar_exact(0, 0) == 1.0                       # nothing discordant: nothing to tell apart
    assert cp.mcnemar_exact(0, 5) == pytest.approx(0.0625)     # 2 x 0.5^5
    assert cp.mcnemar_exact(0, 6) == pytest.approx(0.03125)    # the fewest one-way pairs that reach p < 0.05
    assert cp.mcnemar_exact(6, 0) == pytest.approx(0.03125)    # two-sided
    assert cp.mcnemar_exact(1, 7) == pytest.approx(2 * (1 + 8) / 256)
    assert cp.mcnemar_exact(3, 3) == 1.0


def _arm(rows):
    return pd.DataFrame([{"instance_id": i, "tier_code": "A", "is_resolved": r, "agent_patch_bytes": b,
                          "tool_call_count": 5, "graph_tool_call_count": 1, "prompt_token_count": 1000,
                          "output_token_count": 100, "agent_seconds": 60.0} for i, r, b in rows])


def test_each_task_is_one_row_with_both_arms_and_a_task_missing_from_an_arm_is_kept_as_not_run(cp):
    statement = _arm([("a", False, 10), ("b", False, 0), ("c", True, 30)])
    report = _arm([("a", True, 40), ("b", False, 20)])                       # c was not reached in this arm
    shape = pd.DataFrame({"instance_id": ["a", "b", "c"], "is_import_error": [True, False, False],
                          "context_chars": [300, 900, 500]})
    screen = pd.DataFrame({"instance_id": ["a", "b", "c"], "is_pass": [False, True, False]})
    rows = cp.pair_rows(["a", "b", "c"], statement, report, shape, screen, first={"a", "b"})
    assert [r["instance_id"] for r in rows] == ["a", "b", "c"]
    a, _, c = rows
    assert (a["is_statement_resolved"], a["is_report_resolved"], a["is_pair_run"]) == (False, True, True)
    assert (a["is_import_error"], a["is_screen_pass"], a["is_first_sample"], a["context_chars"]) == (True, False, True, 300)
    assert c["is_pair_run"] is False and c["is_report_resolved"] is None and c["is_first_sample"] is False
    assert all(not isinstance(v, str) or k in ("instance_id", "tier_code") for r in rows for k, v in r.items())


def test_the_summary_counts_each_arm_the_discordant_pairs_and_what_was_left_out(cp):
    rows = ([dict(instance_id=f"h{n}", is_pair_run=True, is_statement_resolved=False, is_report_resolved=True,
                  is_import_error=n < 2, is_screen_pass=False, is_first_sample=True) for n in range(6)]
            + [dict(instance_id="s", is_pair_run=True, is_statement_resolved=True, is_report_resolved=True,
                    is_import_error=False, is_screen_pass=True, is_first_sample=False),
               dict(instance_id="n", is_pair_run=True, is_statement_resolved=False, is_report_resolved=False,
                    is_import_error=False, is_screen_pass=False, is_first_sample=False),
               dict(instance_id="x", is_pair_run=False, is_statement_resolved=True, is_report_resolved=None,
                    is_import_error=False, is_screen_pass=False, is_first_sample=False)])
    s = cp.summary(rows)
    assert (s["pair_count"], s["left_out_count"]) == (8, 1)
    assert (s["statement_resolved_count"], s["report_resolved_count"]) == (1, 7)
    assert (s["both_count"], s["statement_only_count"], s["report_only_count"], s["neither_count"]) == (1, 0, 6, 1)
    assert s["mcnemar_exact_p"] == pytest.approx(0.03125) and s["is_difference_claimed"] is True
    assert s["report_wilson_pct"] == [pytest.approx(52.9, abs=0.1), pytest.approx(97.8, abs=0.1)]
    assert s["report_resolved_with_import_error"] == "2 of 2" and s["report_resolved_without_import_error"] == "5 of 6"
