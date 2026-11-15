"""The Kaggle account's weekly GPU hours (#772): read before and after every GPU run, so the cost of a run is known
and the week isn't spent in a day."""

import importlib.util
from datetime import datetime, timedelta
from types import SimpleNamespace

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("gpu_quota", REPO_ROOT / "kaggle" / "gpu_quota.py")
gpu_quota = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gpu_quota)


def _response(used_hours: float, allowed_hours: float):
    return SimpleNamespace(
        quota_refresh_time=datetime(2026, 11, 21),  # noqa: DTZ001  Kaggle returns a naive UTC time
        gpu_quota=SimpleNamespace(time_used=timedelta(hours=used_hours), total_time_allowed=timedelta(hours=allowed_hours)))


def test_summarize_gives_hours_used_allowed_left_and_the_refresh():
    s = gpu_quota.summarize(_response(32.34, 60))
    assert s == {"gpu_hours_used": 32.34, "gpu_hours_allowed": 60.0, "gpu_hours_left": 27.66,
                 "refresh_ts": "2026-11-21T00:00:00"}


def test_the_line_printed_is_the_one_the_readme_shows():
    assert gpu_quota.line(gpu_quota.summarize(_response(32.34, 60))) == \
        "gpu_hours used 32.34 allowed 60.00 left 27.66 refresh 2026-11-21T00:00:00 UTC"


def test_agents_md_and_the_readme_carry_the_rationing_rules():
    agents = (REPO_ROOT / "AGENTS.md").read_text()
    readme = (REPO_ROOT / "kaggle" / "README.md").read_text()
    assert "kaggle/gpu_quota.py" in agents and "kaggle/gpu_quota.py" in readme
    assert "one gpu run at a time" in agents.lower()
    assert "reserve" in agents


def test_agents_md_sends_development_set_mechanism_runs_to_colab():
    """#787: once a development-set batch can run on Colab (#780), AGENTS.md no longer keeps it on Kaggle."""
    agents = (REPO_ROOT / "AGENTS.md").read_text()
    assert "development-set run stays on Kaggle" not in agents
    assert "--source competition --batch --competition gemma-4-developer-agent --label" in agents


def test_agents_md_records_the_gpu_decisions():
    """#797: the decisions of November 15 are in ADR 0007, and AGENTS.md's rules cite it."""
    agents = (REPO_ROOT / "AGENTS.md").read_text()
    adr = REPO_ROOT / "docs" / "adr" / "0007-gpu-hours-are-a-reserve-and-score-questions-go-to-the-leaderboard.md"
    assert adr.exists() and "0007" in (REPO_ROOT / "docs" / "adr" / "README.md").read_text()
    assert "ADR 0007" in agents
    assert "owner's explicit yes" in agents
    assert "recorded traces" in agents
