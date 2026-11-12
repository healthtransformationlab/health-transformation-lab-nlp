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
    flags = pd.DataFrame({"instance_id": ["a", "b", "c"], "is_import_error": [True, False, False],
                          "is_screen_pass": [False, True, False], "context_chars": [300, 900, 500]})
    rows = cp.pair_rows(["a", "b", "c"], statement, report, flags, arm="report")
    assert [r["instance_id"] for r in rows] == ["a", "b", "c"]
    a, _, c = rows
    assert (a["is_statement_resolved"], a["is_report_resolved"], a["is_pair_run"]) == (False, True, True)
    assert (a["is_import_error"], a["is_screen_pass"], a["context_chars"]) == (True, False, 300)
    assert (a["statement_arm_agent_patch_bytes"], a["report_arm_agent_patch_bytes"]) == (10, 40)
    assert c["is_pair_run"] is False and c["is_report_resolved"] is None
    assert all(not isinstance(v, str) or k in ("instance_id", "tier_code") for r in rows for k, v in r.items())
    graph = cp.pair_rows(["a"], statement, report, flags, arm="graph")[0]    # the arm names its own columns
    assert graph["is_graph_resolved"] is True and "is_report_resolved" not in graph
    # the graph arm's tool calls, and its calls to a graph tool, are two columns that cannot be mistaken for each other
    assert (graph["graph_arm_tool_call_count"], graph["graph_arm_graph_tool_call_count"]) == (5, 1)
    assert "graph_tool_call_count" not in graph


def test_the_summary_counts_each_arm_the_discordant_pairs_what_was_left_out_and_each_split(cp):
    rows = ([dict(instance_id=f"h{n}", is_pair_run=True, is_statement_resolved=False, is_report_resolved=True,
                  is_import_error=n < 2, is_screen_pass=False) for n in range(6)]
            + [dict(instance_id="s", is_pair_run=True, is_statement_resolved=True, is_report_resolved=True,
                    is_import_error=False, is_screen_pass=True),
               dict(instance_id="n", is_pair_run=True, is_statement_resolved=False, is_report_resolved=False,
                    is_import_error=False, is_screen_pass=None),
               dict(instance_id="x", is_pair_run=False, is_statement_resolved=True, is_report_resolved=None,
                    is_import_error=False, is_screen_pass=False)])
    s = cp.summary(rows, arm="report", flags=["is_import_error", "is_screen_pass"])
    assert (s["pair_count"], s["left_out_count"]) == (8, 1)
    assert (s["statement_resolved_count"], s["report_resolved_count"]) == (1, 7)
    assert (s["both_count"], s["statement_only_count"], s["report_only_count"], s["neither_count"]) == (1, 0, 6, 1)
    assert s["mcnemar_exact_p"] == pytest.approx(0.03125) and s["is_difference_claimed"] is True
    assert s["report_wilson_pct"] == [pytest.approx(52.9, abs=0.1), pytest.approx(97.8, abs=0.1)]
    assert s["splits"]["is_import_error"] == {"yes": {"pair_count": 2, "statement_resolved_count": 0, "report_resolved_count": 2},
                                              "no": {"pair_count": 6, "statement_resolved_count": 1, "report_resolved_count": 5}}
    assert s["splits"]["is_screen_pass"]["yes"] == {"pair_count": 1, "statement_resolved_count": 1, "report_resolved_count": 1}
    assert s["splits"]["is_screen_pass"]["no"]["pair_count"] == 6        # a pair with no flag is in neither part


def test_two_added_arms_are_set_side_by_side_over_the_tasks_both_ran(cp):
    """The addendum's `graph` against `report`: described as a paired table, never tested."""
    report = _arm([("a", True, 40), ("b", True, 20), ("c", False, 0)])                  # d was not reached
    graph = _arm([("a", True, 40), ("b", False, 20), ("c", False, 0), ("d", True, 9)])
    out = cp.arm_cross(["a", "b", "c", "d"], report, graph, "report", "graph")
    assert out == {"pair_count": 3, "left_out_count": 1, "both_count": 1, "report_only_count": 1,
                   "graph_only_count": 0, "neither_count": 1}
    assert "mcnemar_exact_p" not in out


def test_the_colab_pair_reads_its_own_tables_and_writes_its_own_file(cp):
    """Addendum 2 (#687): both arms again on one Colab GPU. Its tables are never pooled with the Kaggle arms'."""
    assert cp.table_names("kaggle", "graph") == ("statement", "graph", "context_pairs_graph.csv")
    assert cp.table_names("kaggle", "report") == ("statement", "report", "context_pairs_report.csv")
    assert cp.table_names("colab", "graph") == ("colab-statement", "colab-graph", "context_pairs_colab_graph.csv")
    # a second notebook session made the same pair at the same time on another GPU (#687): its tables are its own too
    assert cp.table_names("colab-l4", "graph") == ("colab-statement-l4", "colab-graph-l4",
                                                    "context_pairs_colab_l4_graph.csv")
    with pytest.raises(SystemExit, match="did not make the report arm"):
        cp.table_names("colab-l4", "report")                       # the second session made the pair only
    # addendum 3: the failing test's report as a third arm on the same machine, beside the same baseline
    assert cp.table_names("colab", "report") == ("colab-statement", "colab-report", "context_pairs_colab_report.csv")


def test_the_sensitivity_analysis_leaves_out_a_pair_in_which_either_side_reached_for_the_network(cp, tmp_path):
    """Nothing blocks the network at a Colab machine's edge, so the plan repeats its test without any pair in which
    either side ran a command that reaches for it."""
    rows = [dict(instance_id=i, is_pair_run=True, is_statement_resolved=False, is_graph_resolved=True) for i in "abc"]
    kept = cp.without_network(rows, {"statement": ["a"], "graph": ["c", "zz"]})
    assert [r["instance_id"] for r in kept] == ["b"]
    assert cp.without_network(rows, {"statement": [], "graph": []}) == rows
    settings = tmp_path / "arm_settings.json"
    settings.write_text('{"network_audit": {"command_count": 9, "network_command_count": 2, "instance_ids": ["a", "c"]}}')
    assert cp.network_ids(settings) == ["a", "c"]
    assert cp.network_ids(tmp_path / "none.json") == []                      # an arm with no settings file yet
    (tmp_path / "kaggle_settings.json").write_text('{"kernel": {"internet": false}}')
    assert cp.network_ids(tmp_path / "kaggle_settings.json") == []           # a Kaggle arm: no audit, nothing to read
