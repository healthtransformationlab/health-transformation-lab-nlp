"""014 BUG3 (#809): keepalive dispatches leaderboard-watch when GitHub's schedule goes quiet."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
import yaml

from health_transformation_lab_nlp import digests as dg
from health_transformation_lab_nlp.paths import REPO_ROOT

ROOT = REPO_ROOT
KEEPALIVE_WF = ROOT / ".github" / "workflows" / "leaderboard-watch-keepalive.yml"
KEEPALIVE_PY = ROOT / ".github" / "scripts" / "leaderboard_watch_keepalive.py"
WATCH_WF = ROOT / ".github" / "workflows" / "leaderboard-watch.yml"
TELEMETRY = ROOT / "docs" / "telemetry.md"


def test_keepalive_workflow_and_script_exist_and_dispatch_the_watch():
    assert KEEPALIVE_WF.is_file() and KEEPALIVE_PY.is_file()
    wf = yaml.safe_load(KEEPALIVE_WF.read_text())
    on = wf.get("on", wf.get(True))
    assert "workflow_dispatch" in on and on.get("schedule")
    text = KEEPALIVE_WF.read_text() + KEEPALIVE_PY.read_text()
    assert "leaderboard-watch.yml" in text or "Watch the competition's leaderboard entries" in text
    assert "workflow run" in text or "gh api" in text
    assert "actions: write" in KEEPALIVE_WF.read_text() or "actions:write" in KEEPALIVE_WF.read_text().replace(" ", "")


def test_docs_name_the_schedule_and_the_keepalive_fallback():
    text = TELEMETRY.read_text()
    assert "leaderboard-watch.yml" in text and "keepalive" in text.lower()
    assert "workflow_dispatch" in text or "dispatches" in text.lower()


def test_hours_since_and_should_dispatch(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("lb_keepalive", KEEPALIVE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    now = datetime(2026, 11, 21, 18, 0, tzinfo=UTC)
    recent = (now - timedelta(hours=2)).isoformat()
    assert mod.hours_since(recent, now) == pytest.approx(2.0)
    assert not mod.should_dispatch(2.0)
    assert mod.should_dispatch(4.0)
    assert not mod.is_stale_alert(5.0)
    assert mod.is_stale_alert(6.0)


def test_leaderboard_watch_alerts_sev3_when_last_finished_over_six_hours():
    now = pd.Timestamp("2026-11-21 18:00:00", tz="UTC")
    fresh = dg.leaderboard_watch_alerts(now - pd.Timedelta(hours=2), now=now)
    assert fresh == []
    stale = dg.leaderboard_watch_alerts(now - pd.Timedelta(hours=7), now=now)
    assert len(stale) == 1
    row = stale[0]
    assert row["severity_code"] == "SEV3"
    assert row["subject_name"] == "leaderboard watch"
    assert "6" in row["evidence_text"] or "7" in row["evidence_text"]
    assert row["recommended_action_code"] == "investigate"
    assert dg.leaderboard_watch_alerts(None, now=now) == []  # unknown: don't invent a page


def test_watch_workflow_clears_local_stale_marker_and_digest_reads_the_file():
    assert "leaderboard_watch_stale.json" in WATCH_WF.read_text()
    assert "leaderboard_watch_stale_file_alerts" in (
        ROOT / "databricks" / "notebooks" / "14_pipeline_digest.py"
    ).read_text()


def test_stale_file_alerts_match_leaderboard_watch_alerts(tmp_path):
    now = pd.Timestamp("2026-11-21 18:00:00", tz="UTC")
    path = tmp_path / "leaderboard_watch_stale.json"
    path.write_text(json.dumps({
        "last_finished_ts": (now - pd.Timedelta(hours=8)).isoformat(),
        "stale_hours": 8,
        "severity_code": "SEV3",
    }), encoding="utf-8")
    a = dg.leaderboard_watch_stale_file_alerts(path, now=now)
    assert len(a) == 1 and a[0]["subject_name"] == "leaderboard watch"
    assert dg.leaderboard_watch_stale_file_alerts(tmp_path / "missing.json", now=now) == []
