"""028 US7 (#847): before a Colab tab is opened, what it would run, and whether a tab that looked disconnected is still
running (kaggle/colab_status.py)."""
import datetime as dt
import importlib.util

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("colab_status", REPO_ROOT / "kaggle" / "colab_status.py")
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)
NOW = dt.datetime(2026, 11, 16, 15, 20, tzinfo=dt.timezone.utc)


def _session(note, minutes_ago, sid="s1"):
    ts = (NOW - dt.timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"session_id": sid, "note_text": note, "uploaded_ts": ts}


def test_each_state():
    assert cs.state_of(_session("finished, kernel exit 0", 600), NOW) == "finished"
    assert cs.state_of(_session("still running", 5), NOW) == "running"
    assert cs.state_of(_session("started", 12), NOW) == "running"
    assert cs.state_of(_session("still running", 45), NOW) == "stale", "no upload for 20 minutes: the tab has dropped"
    assert cs.state_of(None, NOW) == "not started"


def test_next_run_skips_finished_and_other_gpus_and_waits_on_a_running_one():
    runs = [{"label": "devset-e4b-tests", "gpu": "L4"}, {"label": "devset-31b-d2", "gpu": "A100"},
            {"label": "devset-e4b-all", "gpu": "L4"}, {"label": "any-gpu-try2"}]
    sessions = {"devset-e4b-tests": _session("finished, kernel exit 0", 600),
                "devset-31b-d2": _session("still running", 900)}
    rows = cs.status_rows(runs, lambda label: sessions.get(label), NOW)
    assert [r["state"] for r in rows] == ["finished", "stale", "not started", "not started"]
    assert cs.next_run(rows, "L4") == "devset-e4b-all", "a new L4 tab skips the finished run and makes the next L4 one"
    assert cs.next_run(rows, "A100") == "devset-31b-d2", "a stale run is made again (it resumes from its upload)"
    sessions["devset-e4b-all"] = _session("still running", 3)
    rows = cs.status_rows(runs, lambda label: sessions.get(label), NOW)
    assert cs.next_run(rows, "L4") == "any-gpu-try2", "a running run is not made twice; one that names no GPU is next"
    sessions["any-gpu"] = _session("finished, kernel exit 0", 30)
    rows = cs.status_rows(runs, lambda label: sessions.get(label), NOW)
    assert rows[3]["label"] == "any-gpu-try2" and rows[3]["state"] == "finished", "a -try<n> label reads its run's results"
    assert cs.next_run(rows, "L4") is None


def test_the_lines_name_the_state_and_the_next_run():
    rows = cs.status_rows([{"label": "devset-e4b-tests", "gpu": "L4"}],
                          lambda label: _session("finished, kernel exit 0", 600, "20261116T031111Z-9a623c73"), NOW)
    text = cs.render(rows, "L4")
    assert "devset-e4b-tests" in text and "finished" in text and "20261116T031111Z-9a623c73" in text
    assert text.rstrip().endswith("next on L4: nothing")
