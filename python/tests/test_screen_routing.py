"""Spec 028 (#664): what the baseline run would have cost and kept had only the tasks that pass the screen been sent
to the small model. A what-if on one run, not a new run."""
import importlib.util

import pandas as pd
import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT


@pytest.fixture(scope="module")
def routing():
    spec = importlib.util.spec_from_file_location(
        "screen_routing", REPO_ROOT / "python" / "scripts" / "66_screen_routing.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SCREEN = pd.DataFrame({"instance_id": ["a", "b", "c", "d"], "is_pass": [True, True, False, False]})
RUNS = pd.DataFrame({"instance_id": ["a", "b", "c", "z"], "is_resolved": [True, False, True, True],
                     "agent_seconds": [900.0, 900.0, 5400.0, 60.0]})


def test_the_run_is_split_into_tasks_that_pass_the_screen_and_tasks_that_fail_it(routing):
    table = routing.routing_table(SCREEN, RUNS).set_index("route_code")
    assert list(table.index) == ["pass", "fail", "all"]
    assert table.loc["pass"].to_dict() == {"attempted_count": 2, "resolved_count": 1, "agent_hours": 0.5,
                                           "agent_share_pct": 25.0, "agent_hours_per_resolved": 0.5}
    assert table.loc["fail", "attempted_count"] == 1 and table.loc["fail", "agent_share_pct"] == 75.0
    assert table.loc["all"].to_dict() == {"attempted_count": 3, "resolved_count": 2, "agent_hours": 2.0,
                                          "agent_share_pct": 100.0, "agent_hours_per_resolved": 1.0}


def test_a_task_that_was_never_run_or_is_not_screened_is_left_out(routing):
    table = routing.routing_table(SCREEN, RUNS).set_index("route_code")
    assert table.loc["all", "attempted_count"] == 3   # d was never run; z is not a published, screened task


def test_a_group_with_nothing_resolved_has_no_hours_per_fix(routing):
    runs = RUNS.assign(is_resolved=[True, False, False, True])
    table = routing.routing_table(SCREEN, runs).set_index("route_code")
    assert pd.isna(table.loc["fail", "agent_hours_per_resolved"])
