"""Spec 036 US2 (#569): what each coding-agent task costs, and a cap on a run's share of the Kaggle GPU allowance.
Kaggle counts a session's time against the weekly allowance, whatever its GPUs; a cloud bills GPU-hours (session time
by GPU count). The price and the allowance are declared once, with their source and date, and every cost they give
is an estimate."""
import pytest

from health_transformation_lab_nlp import agent_cost as ac
from health_transformation_lab_nlp.paths import REPO_ROOT

S = {"kaggle_weekly_allowance_hours": {"value": 30.0, "source": "s", "read_date": "2026-11-04"},
     "t4_usd_per_gpu_hour": {"value": 0.69, "source": "s", "read_date": "2026-11-04"}}


def test_the_declared_settings_load_with_their_sources():
    s = ac.load_settings()
    for key in ("kaggle_weekly_allowance_hours", "t4_usd_per_gpu_hour"):
        assert s[key]["value"] > 0 and s[key]["source"].startswith("http") and s[key]["read_date"]


@pytest.mark.parametrize("bad", [{"value": 0, "source": "x", "read_date": "d"}, {"value": 1, "read_date": "d"},
                                 {"value": 1, "source": "x"}])
def test_a_setting_without_a_value_source_or_date_is_refused(tmp_path, bad):
    p = tmp_path / "cost.yaml"
    import yaml
    p.write_text(yaml.safe_dump({**S, "t4_usd_per_gpu_hour": bad}))
    with pytest.raises(SystemExit, match="t4_usd_per_gpu_hour"):
        ac.load_settings(p)


def test_a_task_costs_its_session_time_against_the_allowance_and_gpu_hours_at_the_price():
    c = ac.task_cost(session_seconds=1800, gpu_count=2, settings=S)
    assert c["session_seconds"] == 1800 and c["gpu_count"] == 2
    assert c["allowance_hours"] == 0.5 and c["kaggle_allowance_ratio"] == pytest.approx(0.5 / 30)
    assert c["gpu_hours"] == 1.0 and c["estimated_cost_usd"] == pytest.approx(0.69)
    assert c["price_basis_text"] == "estimate: 0.69 USD per T4 GPU-hour (s, read 2026-11-04); Kaggle's GPUs are free"


def test_a_task_with_no_session_time_has_no_cost():
    c = ac.task_cost(session_seconds=None, gpu_count=2, settings=S)
    assert c["gpu_hours"] is None and c["estimated_cost_usd"] is None


def test_expected_time_comes_from_earlier_runs_else_their_median_else_the_default():
    past = {"a": 600.0, "b": 900.0, "c": 1200.0}
    assert ac.expected_seconds("b", past) == 900.0
    assert ac.expected_seconds("new", past) == 900.0            # median of what ran
    assert ac.expected_seconds("new", {}) == ac.DEFAULT_SECONDS


def test_the_cap_takes_the_cheapest_first_and_stops_before_passing_it():
    expected = {"big": 3600.0, "small": 600.0, "mid": 1800.0}
    run, left = ac.plan_under_cap(["big", "small", "mid"], expected, cap_hours=0.75)
    assert run == ["small", "mid"] and left == ["big"]          # 0.17 h + 0.5 h fits; + 1 h would pass 0.75
    run, left = ac.plan_under_cap(["big", "small"], expected, cap_hours=0.75, used_hours=0.7)
    assert run == [] and left == ["small", "big"]


def test_no_cap_runs_everything_cheapest_first():
    run, left = ac.plan_under_cap(["b", "a"], {"a": 1.0, "b": 2.0}, cap_hours=None)
    assert run == ["a", "b"] and left == []


def test_settings_file_is_where_agents_md_says_settings_live():
    assert (REPO_ROOT / "ops" / "cost_settings.yaml").exists()
