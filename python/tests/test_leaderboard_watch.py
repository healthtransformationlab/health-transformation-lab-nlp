"""Spec 014 US7 (#791): the competition's leaderboard entries are watched, and the GPU runs' spans reach Azure.

An entry runs on Kaggle's machines with no code of ours, so it can't be traced; what can be seen is its status,
score and dates. kaggle/submission_watch.py keeps them in a ledger (one row per entry) and sends one span per status
change. All of it is checked here without the network."""
import csv
import importlib.util
import re
from types import SimpleNamespace

import pytest
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import telemetry as tm

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "leaderboard-watch.yml"
LEDGER = REPO_ROOT / "data" / "tasks" / "leaderboard_entries.csv"
COLUMNS = ["ref", "description", "submitted_ts", "status", "public_score", "first_seen_ts", "completed_ts",
           "finished_ts", "scoring_hours", "wall_hours", "final_status_text", "agent_commit_sha"]


@pytest.fixture(scope="module")
def sw():
    spec = importlib.util.spec_from_file_location("submission_watch", REPO_ROOT / "kaggle" / "submission_watch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sub(ref, status, score="", description="entry", submitted="2026-11-15T02:18:52Z"):
    return {"ref": str(ref), "description": description, "submitted_ts": submitted, "status": status,
            "public_score": score}


# ---- entry_rows ---------------------------------------------------------------------------------------------------

def test_a_new_entry_is_recorded_when_first_seen(sw):
    (row,) = sw.entry_rows([_sub(1, "complete", "0.05", "entry 1: E4B, main 9c9cd3a = the lean prompt")], [],
                           "2026-11-15T10:00:00Z")
    assert list(row) == COLUMNS
    assert row["first_seen_ts"] == "2026-11-15T10:00:00Z" and row["public_score"] == "0.05"
    assert row["completed_ts"] == "" and row["finished_ts"] == "" and row["wall_hours"] == ""
    assert row["final_status_text"] == "0.05"
    assert row["agent_commit_sha"] == "9c9cd3a"


def test_an_entry_seen_pending_then_complete_gets_its_completion_time_and_wall_hours(sw):
    first = sw.entry_rows([_sub(4, "pending")], [], "2026-11-15T04:00:00Z")
    (row,) = sw.entry_rows([_sub(4, "complete", "0.04")], first, "2026-11-15T10:18:52Z")
    assert row["first_seen_ts"] == "2026-11-15T04:00:00Z" and row["finished_ts"] == "2026-11-15T10:18:52Z"
    assert row["completed_ts"] == row["finished_ts"]
    assert float(row["wall_hours"]) == pytest.approx(8.0)
    assert row["scoring_hours"] == row["wall_hours"]
    assert row["final_status_text"] == "0.04"
    (again,) = sw.entry_rows([_sub(4, "complete", "0.04")], [row], "2026-11-15T12:00:00Z")
    assert again == row                                                       # a rerun changes nothing


def test_a_runtime_exceedance_is_notebook_timeout_and_sets_finished_ts(sw):
    first = sw.entry_rows([_sub(7, "pending", submitted="2026-11-19T18:00:00Z")], [],
                          "2026-11-19T18:00:00Z")
    timed_out = {**_sub(7, "error", submitted="2026-11-19T18:00:00Z"), "error_description":
                 "Your submission notebook exceeded the allowed runtime. Review the competition's Code Requirements."}
    (row,) = sw.entry_rows([timed_out], first, "2026-11-20T16:00:00Z")
    assert row["status"] == "error"
    assert row["finished_ts"] == "2026-11-20T16:00:00Z"
    assert row["final_status_text"] == "Notebook Timeout"
    assert float(row["wall_hours"]) == pytest.approx(22.0)


def test_one_row_per_entry_and_entries_missing_from_the_list_are_kept(sw):
    ledger = sw.entry_rows([_sub(1, "complete", "0.05"), _sub(2, "pending")], [], "2026-11-15T04:00:00Z")
    rows = sw.entry_rows([_sub(1, "complete", "0.05"), _sub(1, "complete", "0.05")], ledger, "2026-11-15T06:00:00Z")
    assert [r["ref"] for r in rows] == ["1", "2"]
    assert rows[1]["status"] == "pending"


@pytest.mark.parametrize(("description", "sha"), [
    ("entry 5: E4B, main 9c9cd3a = lean prompt", "9c9cd3a"),
    ("entry 4: E4B, localize-first prompt (PR 98), main 76bc6d6; dev set 4/23", "76bc6d6"),
    ("entry 1: one agent, E4B, answer cap 6144, 4.5 min", ""),
    ("main branch, 4.5 min", ""),
    ("main " + "a" * 40, "a" * 40),
])
def test_the_agent_commit_is_read_from_the_description_when_it_names_one(sw, description, sha):
    (row,) = sw.entry_rows([_sub(1, "pending", description=description)], [], "2026-11-15T04:00:00Z")
    assert row["agent_commit_sha"] == sha


# ---- status_changes -----------------------------------------------------------------------------------------------

def test_status_changes_lists_new_entries_and_changed_statuses_only(sw):
    old = sw.entry_rows([_sub(1, "complete", "0.05"), _sub(2, "pending")], [], "2026-11-15T04:00:00Z")
    new = sw.entry_rows([_sub(1, "complete", "0.05"), _sub(2, "error"), _sub(3, "pending")], old,
                        "2026-11-15T06:00:00Z")
    changes = sw.status_changes(old, new)
    assert [(c["ref"], c["previous_status"], c["status"]) for c in changes] == [("2", "pending", "error"),
                                                                                 ("3", "", "pending")]
    assert sw.status_changes(new, new) == []


# ---- main, with a stand-in for the Kaggle API --------------------------------------------------------------------

class FakeApi:
    def __init__(self, listed, by_ref):
        self.listed, self.by_ref, self.looked_up = listed, by_ref, []

    def authenticate(self):
        pass

    def competition_submissions(self, competition, **kwargs):
        assert competition == "gemma-4-developer-agent"
        return self.listed

    def get_submission(self, ref):
        self.looked_up.append(int(ref))
        return self.by_ref[int(ref)]


def _api_sub(ref, status, score, description, date="2026-11-15 02:18:52.813000", error_description=None):
    from datetime import datetime
    return SimpleNamespace(ref=ref, description=description, date=datetime.fromisoformat(date),
                           status=SimpleNamespace(name=status), public_score=score,
                           error_description=error_description)


@pytest.fixture
def mem(monkeypatch):
    real = tm.setup
    holder = {}

    def setup(config=None):
        holder["exporter"] = real(tm.TelemetryConfig(exporter="memory"))
        return holder["exporter"]

    monkeypatch.setattr(tm, "setup", setup)
    monkeypatch.setenv("KAGGLE_API_TOKEN", "not-a-real-token")
    yield holder
    real(tm.TelemetryConfig(exporter="off"))


def _run(sw, monkeypatch, api, ledger, now="2026-11-15T10:00:00Z"):
    monkeypatch.setattr(sw, "make_api", lambda: api)
    monkeypatch.setattr(sw, "now_ts", lambda: now)
    return sw.main(["--competition", "gemma-4-developer-agent", "--ledger", str(ledger)])


def test_main_looks_up_hidden_pending_entries_writes_the_ledger_and_sends_a_span_per_change(sw, monkeypatch, mem,
                                                                                              tmp_path):
    ledger = tmp_path / "leaderboard_entries.csv"
    with ledger.open("w", newline="") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        w.writerow({**dict.fromkeys(COLUMNS, ""), "ref": "4", "status": "pending", "description": "entry 4",
                    "submitted_ts": "2026-11-15T02:18:52Z", "first_seen_ts": "2026-11-15T04:00:00Z"})
    api = FakeApi([_api_sub(1, "COMPLETE", "0.05", "entry 1", "2026-11-13 01:09:18.787000")],
                  {4: _api_sub(4, "COMPLETE", "0.04", "entry 4, main 76bc6d6")})
    assert _run(sw, monkeypatch, api, ledger) == 0
    assert api.looked_up == [4]                         # the list hides pending entries: looked up by ref
    rows = list(csv.DictReader(ledger.open()))
    assert [r["ref"] for r in rows] == ["1", "4"] and list(rows[0]) == COLUMNS
    assert rows[1]["status"] == "complete" and rows[1]["finished_ts"] == "2026-11-15T10:00:00Z"
    assert rows[1]["wall_hours"] != "" and rows[1]["final_status_text"] == "0.04"
    assert rows[0]["submitted_ts"] == "2026-11-13T01:09:18Z"
    spans = [s for s in mem["exporter"].get_finished_spans() if s.name == "leaderboard_entry"]
    assert sorted((s.attributes["submission_ref_id"], s.attributes["status_code"]) for s in spans) == [
        ("1", "complete"), ("4", "complete")]
    assert {s.attributes["public_score_ratio"] for s in spans} == {0.05, 0.04}
    values = {str(v) for s in spans for v in s.attributes.values()}
    assert not values & {"entry 1", "entry 4, main 76bc6d6"}                       # no description on a span
    run = [s for s in mem["exporter"].get_finished_spans() if s.name == "submission_watch"]
    assert len(run) == 1 and all(s.parent.span_id == run[0].context.span_id for s in spans)

    before = ledger.read_text()
    mem["exporter"].clear()
    assert _run(sw, monkeypatch, api, ledger, now="2026-11-15T12:00:00Z") == 0
    assert ledger.read_text() == before                 # idempotent: overwritten with the same rows
    assert not [s for s in mem["exporter"].get_finished_spans() if s.name == "leaderboard_entry"]


def test_an_entry_in_error_ends_the_run_non_zero_after_the_ledger_is_written(sw, monkeypatch, mem, tmp_path, capsys):
    ledger = tmp_path / "leaderboard_entries.csv"
    api = FakeApi([_api_sub(7, "ERROR", None, "entry 7")], {})
    assert _run(sw, monkeypatch, api, ledger) != 0
    assert next(iter(csv.DictReader(ledger.open())))["status"] == "error"
    assert "7" in capsys.readouterr().err


def test_without_a_kaggle_token_it_stops_at_once_naming_it(sw, monkeypatch, tmp_path):
    for name in ("KAGGLE_API_TOKEN", "KAGGLE_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sw, "make_api", lambda: pytest.fail("no API call without a token"))
    with pytest.raises(SystemExit, match="KAGGLE_API_TOKEN"):
        sw.main(["--competition", "gemma-4-developer-agent", "--ledger", str(tmp_path / "l.csv")])


def test_the_script_sets_up_telemetry_and_labels_its_run_span(sw):
    text = (REPO_ROOT / "kaggle" / "submission_watch.py").read_text()
    assert "telemetry.setup()" in text
    assert re.search(r'telemetry\.start_script\(\s*"submission_watch",[^)]*data_label=', text)


# ---- the committed ledger -----------------------------------------------------------------------------------------

def test_the_ledger_holds_one_row_per_entry_so_far(sw):
    rows = sw.read_ledger(LEDGER)
    assert rows and list(rows[0]) == COLUMNS
    refs = [r["ref"] for r in rows]
    assert len(refs) == len(set(refs))
    assert {"58290615", "58333590", "58364801"} <= set(refs)
    assert {r["status"] for r in rows} <= {"pending", "complete", "error"}


# ---- the workflow -------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def wf():
    return yaml.safe_load(WORKFLOW.read_text())


def test_the_workflow_runs_every_two_hours_and_on_demand_in_dev(wf):
    on = wf.get("on", wf.get(True))
    assert {"cron": "0 */2 * * *"} in on["schedule"] and "workflow_dispatch" in on
    (job,) = wf["jobs"].values()
    assert job["environment"] == "dev"
    assert job["permissions"] == {"contents": "write", "pull-requests": "write"}


def test_the_workflow_passes_the_token_and_the_connection_string_by_name(wf):
    text = WORKFLOW.read_text()
    assert "secrets.KAGGLE_API_TOKEN" in text and "secrets.APPINSIGHTS_CONNECTION_STRING" in text
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" in text and "DENTAL_TELEMETRY=azure" in text
    assert "::warning::" in text                         # missing: a warning, telemetry off, the ledger still updated
    assert "python kaggle/submission_watch.py --competition gemma-4-developer-agent " \
           "--ledger data/tasks/leaderboard_entries.csv" in text
    assert '"kaggle==2.2.5" six' in text and "-e \"./python[azure]\"" in text


def test_the_ledger_goes_to_a_results_branch_and_a_pull_request_even_when_an_entry_is_in_error(wf):
    (job,) = wf["jobs"].values()
    steps = job["steps"]
    text = WORKFLOW.read_text()
    assert "kaggle-results/leaderboard-entries-${{ github.run_id }}" in text and "gh pr create" in text
    watch = next(s for s in steps if "submission_watch.py" in s.get("run", ""))
    pr = next(s for s in steps if "gh pr create" in s.get("run", ""))
    fail = steps[-1]
    assert steps.index(watch) < steps.index(pr) < steps.index(fail)
    assert watch.get("id") and "GITHUB_OUTPUT" in watch["run"]
    assert "!cancelled()" in pr.get("if", "")
    assert watch["id"] in fail["if"] and "exit 1" in fail["run"]


# ---- the register and the spec ------------------------------------------------------------------------------------

def test_the_register_lists_the_github_connection_string_secret():
    entries = yaml.safe_load((REPO_ROOT / "ops" / "secrets_register.yaml").read_text())["credentials"]
    hit = [e for e in entries if "APPINSIGHTS_CONNECTION_STRING" in str(e.get("stored_in", ""))]
    assert hit and "dev" in hit[0]["stored_in"] and str(hit[0]["expires"]) == "never"
    assert "leaderboard-watch.yml" in hit[0]["used_by"]


def test_spec_014_names_the_story_and_has_a_plan():
    spec = (REPO_ROOT / "specs" / "014-telemetry" / "spec.md").read_text()
    assert re.search(r"^### US7 - .*#791$", spec, re.MULTILINE)
    plan = (REPO_ROOT / "specs" / "014-telemetry" / "plan.md").read_text()
    for name in ("submission_watch.py", "forward_spans", "leaderboard-watch.yml", "leaderboard_entry",
                 "APPINSIGHTS_CONNECTION_STRING"):
        assert name in plan, name
