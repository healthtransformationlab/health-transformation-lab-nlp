"""Spec 028 (#662): what the baseline's GPU time bought, split by whether the code graph leads to a task's fix."""
import importlib.util

import pandas as pd
import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT


@pytest.fixture(scope="module")
def cost():
    spec = importlib.util.spec_from_file_location(
        "cost_by_graph_reach", REPO_ROOT / "python" / "scripts" / "65_cost_by_graph_reach.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(**kw):
    base = {"is_fix_in_graph": True, "edited_node_count": 1, "statement_to_fix_edge_count": None,
            "edited_node_best_rank_num": None}
    return base | kw


def test_a_task_is_placed_by_the_first_thing_that_leads_to_its_fix(cost):
    assert cost.reach_code(_row(is_fix_in_graph=False, edited_node_count=0)) == "outside_graph"
    assert cost.reach_code(_row(edited_node_count=0)) == "no_existing_node"
    assert cost.reach_code(_row(statement_to_fix_edge_count=0, edited_node_best_rank_num=40)) == "named_or_called"
    assert cost.reach_code(_row(statement_to_fix_edge_count=3, edited_node_best_rank_num=2)) == "named_or_called"
    assert cost.reach_code(_row(edited_node_best_rank_num=10)) == "embedding_top10"
    assert cost.reach_code(_row(edited_node_best_rank_num=11)) == "unreached"


def test_the_table_has_every_kind_with_its_tasks_runs_and_agent_hours(cost):
    reach = pd.DataFrame({"instance_id": ["a", "b", "c", "d"],
                          "reach_code": ["named_or_called", "named_or_called", "outside_graph", "embedding_top10"]})
    runs = pd.DataFrame({"instance_id": ["a", "c", "z"], "is_resolved": [True, False, True],
                         "agent_seconds": [1800.0, 5400.0, 9000.0]})
    table = cost.cost_table(reach, runs).set_index("reach_code")
    assert list(table.index) == list(cost.REACH)                    # every kind, in the same order, even when empty
    assert table.loc["named_or_called"].to_dict() == {"task_count": 2, "attempted_count": 1, "resolved_count": 1,
                                                      "agent_hours": 0.5, "agent_share_pct": 25.0}
    assert table.loc["outside_graph", "agent_share_pct"] == 75.0 and table.loc["outside_graph", "resolved_count"] == 0
    assert table.loc["embedding_top10", "attempted_count"] == 0     # a task that was never run costs nothing
    assert table["attempted_count"].sum() == 2                      # run z is not a published task: left out


def test_a_run_with_no_recorded_time_stops_the_table(cost):
    reach = pd.DataFrame({"instance_id": ["a"], "reach_code": ["unreached"]})
    runs = pd.DataFrame({"instance_id": ["a"], "is_resolved": [False], "agent_seconds": [None]})
    with pytest.raises(SystemExit, match="agent_seconds"):
        cost.cost_table(reach, runs)
