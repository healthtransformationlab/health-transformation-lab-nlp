"""014 BUG1 (#792): telemetry asked for Azure turned itself off with only a log warning, for weeks. Telemetry stays
optional (a missing connection string never fails a job), but being off when it was asked for is now visible: a
status, one stderr line (a workflow annotation under GitHub Actions), and a SEV3 in the daily digest; the secrets
register's Databricks-scope entries are checked to exist. No Databricks, Azure or network here."""

import pandas as pd
import pytest

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import digests as dg
from health_transformation_lab_nlp import telemetry as tm
from health_transformation_lab_nlp.paths import REPO_ROOT

SECRET = "InstrumentationKey=11111111-2222-3333-4444-555555555555;IngestionEndpoint=https://x/"
STATUS_KEYS = {"asked_exporter_name", "active_exporter_name", "reason_text"}


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    yield
    tm.setup(tm.TelemetryConfig(exporter="off"))


class _Secrets:
    def __init__(self, store):
        self.store = store

    def get(self, scope, key):
        if (scope, key) not in self.store:
            raise ValueError(f"Secret does not exist with scope: {scope} and key: {key}")
        return self.store[(scope, key)]


class _Dbutils:
    def __init__(self, store):
        self.secrets = _Secrets(store)


# --- telemetry.status() and the stderr line ---------------------------------------------------------------------------

def test_status_says_what_was_asked_what_is_on_and_why_without_the_secret():
    tm.setup(tm.TelemetryConfig(exporter="azure", connection_string=""))
    s = tm.status()
    assert STATUS_KEYS <= set(s)
    assert (s["asked_exporter_name"], s["active_exporter_name"]) == ("azure", "off")
    assert "no connection string" in s["reason_text"]


def test_status_names_a_malformed_connection_string_and_never_holds_its_value():
    bad = "Warning: No outputs found"
    tm.setup(tm.TelemetryConfig(exporter="azure", connection_string=bad))
    s = tm.status()
    assert s["active_exporter_name"] == "off" and "malformed connection string" in s["reason_text"]
    assert bad not in str(s)


def test_status_when_asked_and_active_agree_has_no_reason():
    tm.setup(tm.TelemetryConfig(exporter="memory"))
    assert tm.status() == {**tm.status(), "asked_exporter_name": "memory", "active_exporter_name": "memory",
                           "reason_text": ""}
    tm.setup(tm.TelemetryConfig(exporter="off"))
    s = tm.status()
    assert (s["asked_exporter_name"], s["active_exporter_name"], s["reason_text"]) == ("off", "off", "")


def test_a_missing_databricks_secret_shows_in_the_status_after_setup(monkeypatch):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("DENTAL_TELEMETRY", raising=False)
    assert tm.use_databricks_secret(_Dbutils({}), "azure") == "off"          # still never fails the job
    assert tm.status()["asked_exporter_name"] == "azure" and "no secret" in tm.status()["reason_text"]
    tm.setup()                                                               # from the environment: off
    s = tm.status()
    assert (s["asked_exporter_name"], s["active_exporter_name"]) == ("azure", "off")
    assert "no secret" in s["reason_text"] and "appinsights_connection_string" in s["reason_text"]
    tm.setup()                                                               # a later setup starts clean
    assert tm.status()["asked_exporter_name"] == "off"


def test_setup_carries_on_and_prints_one_stderr_line_naming_setting_reason_and_fix(capsys):
    assert tm.setup(tm.TelemetryConfig(exporter="azure", connection_string="")) is None
    assert tm.active_exporter() == "off"
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1
    line = err[0]
    assert "DENTAL_TELEMETRY=azure" in line and "APPLICATIONINSIGHTS_CONNECTION_STRING" in line
    assert "no connection string" in line and "infra/azure" in line
    assert "health_transformation_lab/appinsights_connection_string" in line and "SEV3" in line
    assert not line.startswith("::warning")


def test_under_github_actions_the_line_is_a_warning_annotation(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    tm.setup(tm.TelemetryConfig(exporter="azure", connection_string="abc;def"))
    (line,) = capsys.readouterr().err.strip().splitlines()
    assert line.startswith("::warning") and "malformed connection string" in line and "abc;def" not in line


def test_no_line_when_nothing_was_asked_or_it_is_on(capsys):
    tm.setup(tm.TelemetryConfig(exporter="off"))
    tm.setup(tm.TelemetryConfig(exporter="memory"))
    assert capsys.readouterr().err == ""


def test_the_missing_secret_line_is_printed_once_not_again_by_setup(monkeypatch, capsys):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    tm.use_databricks_secret(_Dbutils({}), "azure")
    tm.setup()
    (line,) = capsys.readouterr().err.strip().splitlines()
    assert "no secret" in line and "health_transformation_lab/appinsights_connection_string" in line


def test_a_found_secret_leaves_no_trace_of_its_value(monkeypatch, capsys):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    tm.use_databricks_secret(_Dbutils({("health_transformation_lab", "appinsights_connection_string"): SECRET}), "off")
    assert SECRET not in str(tm.status()) and capsys.readouterr().err == ""


# --- digests.telemetry_alerts ----------------------------------------------------------------------------------------

def _status(pipeline, asked="azure", active="off", reason="no connection string: APPLICATIONINSIGHTS_CONNECTION_STRING is not set"):
    return {"pipeline_name": pipeline, "asked_exporter_name": asked, "active_exporter_name": active,
            "reason_text": reason}


def test_telemetry_off_when_asked_is_a_sev3_per_pipeline_with_owner_and_fix():
    out = dg.telemetry_alerts([_status("study_benchmark"), _status("pipeline_digest"),
                               _status("study_benchmark"),                          # the same pipeline once
                               _status("ok_job", active="azure", reason=""), _status("quiet", "off", "off", "")])
    assert isinstance(out, list) and len(out) == 2
    assert all(set(a) == set(dg.ALERT_COLUMNS) for a in out)
    assert {a["pipeline_name"] for a in out} == {"study_benchmark", "pipeline_digest"}
    a = out[0]
    assert a["severity_code"] == "SEV3" and a["owner_name"] == "repo owner"
    assert a["recommended_action_code"] == "fix_setting" and a["predicted_failure_class_code"] == "config"
    assert "infra/azure" in a["evidence_text"] and "no connection string" in a["evidence_text"]
    assert len({a["subject_name"] for a in out}) == 1                               # one problem, counted


def test_the_daily_digest_shows_telemetry_off_once_with_a_count():
    alerts = pd.DataFrame(dg.telemetry_alerts([_status("a"), _status("b"), _status("c")]), columns=dg.ALERT_COLUMNS)
    items, messages = dg.build(alerts, "daily", "2026-11-15", previous=None)
    assert len(items) == 1 and int(items.iloc[0]["alert_count"]) == 3
    assert items.iloc[0]["pipeline_names_text"] == "a, b, c"
    assert "infra/azure" in messages.iloc[0]["message_text"]


def test_no_statuses_no_alerts():
    assert dg.telemetry_alerts([]) == []


# --- digests.register_alerts ----------------------------------------------------------------------------------------

def _register():
    import yaml
    return yaml.safe_load((REPO_ROOT / "ops" / "secrets_register.yaml").read_text())


def test_a_registered_scope_secret_missing_from_the_scope_is_a_sev3():
    out = dg.register_alerts(_register(), {"hf_token"})
    names = {a["subject_name"] for a in out}
    assert "Application Insights connection string" in names and "Hugging Face token" not in names
    a = next(a for a in out if a["subject_name"] == "Application Insights connection string")
    assert set(a) == set(dg.ALERT_COLUMNS)
    assert (a["severity_code"], a["subject_kind_code"], a["owner_name"]) == ("SEV3", "credential", "repo owner")
    assert a["recommended_action_code"] == "fix_setting"
    assert "appinsights_connection_string" in a["evidence_text"] and "health_transformation_lab" in a["evidence_text"]


def test_every_registered_scope_secret_present_means_no_alert():
    assert dg.register_alerts(_register(), {"hf_token", "appinsights_connection_string"}) == []


def test_only_entries_stored_in_the_databricks_scope_are_checked():
    reg = {"credentials": [
        {"name": "gh", "stored_in": "your laptop only", "owner": "repo owner"},
        {"name": "other scope", "stored_in": "Databricks secret scope elsewhere, key k", "owner": "repo owner"},
        {"name": "two", "stored_in": "Databricks secret scope health_transformation_lab, key a; Kaggle secret X",
         "owner": "someone"}]}
    out = dg.register_alerts(reg, set())
    assert [(a["subject_name"], a["owner_name"]) for a in out] == [("two", "someone")]


# --- the digest notebook and the docs --------------------------------------------------------------------------------

def test_the_daily_digest_notebook_includes_both_and_lists_the_scope_by_name_only():
    src = (REPO_ROOT / "databricks" / "notebooks" / "14_pipeline_digest.py").read_text()
    assert "digests.telemetry_alerts(" in src and "telemetry.status()" in src
    assert "digests.register_alerts(" in src and 'dbutils.secrets.list("health_transformation_lab")' in src
    assert "secrets.get(" not in src.replace("use_databricks_secret", "")


def test_the_telemetry_doc_says_off_is_a_sev3_in_the_daily_digest():
    doc = (REPO_ROOT / "docs" / "telemetry.md").read_text()
    assert "SEV3" in doc and "daily digest" in doc and "telemetry.status()" in doc
    assert "register_alerts" in doc
