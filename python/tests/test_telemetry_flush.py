"""014 BUG2 (#801): spans sent to Azure are flushed, and every run says whether the export succeeded."""
import importlib.util
import logging
import sys
import types

import pytest
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import telemetry as tm

GOOD = "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://example.invalid/"


@pytest.fixture(autouse=True)
def _off_after(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    yield
    tm.setup(tm.TelemetryConfig(exporter="off"))


class FakeProvider:
    def __init__(self, ok=True):
        self.ok, self.flushed, self.stopped = ok, 0, 0

    def force_flush(self, timeout_millis=30000):
        self.flushed += 1
        return self.ok

    def shutdown(self):
        self.stopped += 1

    def get_tracer(self, *a, **k):
        return tm.trace.NoOpTracer()


def _fake_azure(monkeypatch, tp, mp):
    mod = types.ModuleType("azure.monitor.opentelemetry")
    mod.configure_azure_monitor = lambda **kw: None
    monkeypatch.setitem(sys.modules, "azure.monitor.opentelemetry", mod)
    monkeypatch.setattr(tm.trace, "get_tracer_provider", lambda: tp)
    monkeypatch.setattr(tm.metrics, "get_meter_provider", lambda: mp)


def test_flush_is_true_when_telemetry_is_off():
    tm.setup(tm.TelemetryConfig(exporter="off"))
    assert tm.flush() is True


def test_flush_is_true_after_a_memory_export():
    tm.setup(tm.TelemetryConfig(exporter="memory"))
    assert tm.flush() is True


def test_the_azure_providers_are_recorded_so_exit_flushes_them_without_stopping_the_global_ones(monkeypatch):
    tp, mp = FakeProvider(), FakeProvider()
    _fake_azure(monkeypatch, tp, mp)
    tm.setup(tm.TelemetryConfig(exporter="azure", connection_string=GOOD))
    assert tm.active_exporter() == "azure"
    assert tm.flush() is True and tp.flushed == 1
    tm._shutdown_providers()                          # what exit and the next setup() run
    assert tp.flushed == 2 and mp.flushed == 2
    assert tp.stopped == 0 and mp.stopped == 0        # global, set once: a later setup must still be able to send


def test_flush_reports_a_failed_export(monkeypatch):
    _fake_azure(monkeypatch, FakeProvider(ok=False), FakeProvider())
    tm.setup(tm.TelemetryConfig(exporter="azure", connection_string=GOOD))
    assert tm.flush() is False


def test_the_azure_exporters_warnings_reach_stderr(monkeypatch):
    _fake_azure(monkeypatch, FakeProvider(), FakeProvider())
    tm.setup(tm.TelemetryConfig(exporter="azure", connection_string=GOOD))
    log = logging.getLogger("azure.monitor.opentelemetry.exporter")
    assert any(isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr for h in log.handlers)
    assert log.getEffectiveLevel() <= logging.WARNING


@pytest.fixture
def sw():
    spec = importlib.util.spec_from_file_location("submission_watch", REPO_ROOT / "kaggle" / "submission_watch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_watcher_says_whether_the_export_succeeded(sw, capsys, monkeypatch):
    ok = types.SimpleNamespace(active_exporter=lambda: "azure", flush=lambda: True)
    bad = types.SimpleNamespace(active_exporter=lambda: "azure", flush=lambda: False)
    off = types.SimpleNamespace(active_exporter=lambda: "off", flush=lambda: True)
    sw.report_export(ok)
    sw.report_export(off)
    assert capsys.readouterr().out.strip().splitlines() == ["telemetry export: ok"]
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    sw.report_export(bad)
    out = capsys.readouterr()
    assert "telemetry export: FAILED" in out.out + out.err and "::warning" in out.out + out.err


def test_the_watcher_also_runs_when_the_ledger_changes_on_main():
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "leaderboard-watch.yml").read_text())
    on = wf.get("on", wf.get(True))
    assert on["push"]["branches"] == ["main"]
    assert "data/tasks/leaderboard_entries.csv" in on["push"]["paths"]
    assert "schedule" in on and "workflow_dispatch" in on
