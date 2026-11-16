"""Spec 014: pipeline telemetry (OpenTelemetry; Azure Application Insights via the Azure Monitor distro)."""

import logging
import sys

import pytest

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import telemetry as tm


@pytest.fixture
def mem():
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    yield exporter
    tm.setup(tm.TelemetryConfig(exporter="off"))


def test_config_from_env_defaults_to_off(monkeypatch):
    for k in ("DENTAL_TELEMETRY", "APPLICATIONINSIGHTS_CONNECTION_STRING", "DENTAL_TELEMETRY_SAMPLING"):
        monkeypatch.delenv(k, raising=False)
    c = tm.config_from_env()
    assert c.exporter == "off" and c.sampling_ratio == 1.0


def test_config_from_env_reads_exporter_sampling_and_connection_string(monkeypatch):
    monkeypatch.setenv("DENTAL_TELEMETRY", "azure")
    monkeypatch.setenv("DENTAL_TELEMETRY_SAMPLING", "0.25")
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=00000000-0000-0000-0000-000000000000")
    c = tm.config_from_env()
    assert (c.exporter, c.sampling_ratio) == ("azure", 0.25) and c.connection_string.startswith("InstrumentationKey=")


def test_bad_settings_are_errors():
    with pytest.raises(ValueError):
        tm.TelemetryConfig(exporter="datadog")
    with pytest.raises(ValueError):
        tm.TelemetryConfig(sampling_ratio=1.5)


def test_step_span_carries_name_label_and_counts(mem):
    with tm.pipeline_step("build_sites", data_label="synthetic", rows=3437):
        pass
    (span,) = mem.get_finished_spans()
    assert span.name == "build_sites"
    assert span.attributes["pipeline.step"] == "build_sites"
    assert span.attributes["data.label"] == "synthetic" and span.attributes["rows"] == 3437
    assert span.status.is_ok


def test_failure_is_recorded_on_the_span_and_re_raised(mem):
    with pytest.raises(RuntimeError, match="GPU"), tm.pipeline_step("encoder_gpu"):
        raise RuntimeError("failed to start within 900 seconds: no GPU available")
    (span,) = mem.get_finished_spans()
    assert not span.status.is_ok
    assert span.attributes["error.type"] == "RuntimeError"
    assert any(e.name == "exception" for e in span.events)


def test_nested_steps_share_one_trace(mem):
    with tm.pipeline_step("data_quality"), tm.pipeline_step("transitions"):
        pass
    inner, outer = mem.get_finished_spans()
    assert inner.context.trace_id == outer.context.trace_id and inner.parent.span_id == outer.context.span_id


def test_metric_helpers_do_not_fail_when_telemetry_is_off():
    tm.setup(tm.TelemetryConfig(exporter="off"))
    tm.record_value("data_quality.pass_rate", 0.97, check="cal_range")
    with tm.pipeline_step("noop"):
        pass


def test_azure_without_connection_string_warns_and_turns_off(caplog):
    with caplog.at_level(logging.WARNING):
        assert tm.setup(tm.TelemetryConfig(exporter="azure", connection_string="")) is None
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" in caplog.text
    assert tm.active_exporter() == "off"


def test_azure_uses_the_distro_with_sampling_live_metrics_and_the_package_logger(monkeypatch):
    pytest.importorskip("azure.monitor.opentelemetry")
    import azure.monitor.opentelemetry as distro
    seen = {}
    monkeypatch.setattr(distro, "configure_azure_monitor", lambda **kw: seen.update(kw))
    tm.setup(tm.TelemetryConfig(exporter="azure", connection_string="InstrumentationKey=x", sampling_ratio=0.5))
    assert seen["connection_string"] == "InstrumentationKey=x" and seen["sampling_ratio"] == 0.5
    assert seen["enable_live_metrics"] is True and seen["logger_name"] == "health_transformation_lab_nlp"
    assert seen["resource"].attributes["service.name"] == "health_transformation_lab"           # the data product
    assert seen["resource"].attributes["service.namespace"] == "health-transformation-lab-nlp"
    assert len(seen["span_processors"]) == 1                                         # the common header
    assert logging.getLogger("health_transformation_lab_nlp").level == logging.INFO          # no DEBUG shipped
    tm.setup(tm.TelemetryConfig(exporter="off"))


def test_script_span_covers_the_run_and_records_a_crash(mem):
    import sys
    tm.start_script("20_data_quality", data_label="synthetic")
    with tm.pipeline_step("checks"):
        pass
    err = ValueError("visits_structured.csv: column rec_max_cal_mm missing")
    sys.excepthook(type(err), err, None)                     # what Python calls on an uncaught error
    spans = {s.name: s for s in mem.get_finished_spans()}
    assert set(spans) == {"checks", "20_data_quality"}
    run = spans["20_data_quality"]
    assert spans["checks"].parent.span_id == run.context.span_id
    assert not run.status.is_ok and run.attributes["error.type"] == "ValueError"
    assert run.attributes["pipeline.kind"] == "script"


def test_script_span_ends_ok_when_the_script_finishes(mem):
    tm.start_script("22_build_sites")
    tm.end_script()
    tm.end_script()                                           # second call is a no-op (atexit after explicit end)
    (run,) = mem.get_finished_spans()
    assert run.status.is_ok or run.status.status_code.name == "UNSET"


class _FakeSecrets:
    def __init__(self, store):
        self.store = store

    def get(self, scope, key):
        if (scope, key) not in self.store:
            raise ValueError(f"Secret does not exist with scope: {scope} and key: {key}")
        return self.store[(scope, key)]


class _FakeDbutils:
    def __init__(self, store):
        self.secrets = _FakeSecrets(store)


def test_databricks_secret_sets_the_environment_child_scripts_inherit(monkeypatch):
    for k in ("DENTAL_TELEMETRY", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        monkeypatch.delenv(k, raising=False)
    dbu = _FakeDbutils({("health_transformation_lab", "appinsights_connection_string"): "InstrumentationKey=abc"})
    assert tm.use_databricks_secret(dbu, "azure") == "azure"
    import os
    assert os.environ["DENTAL_TELEMETRY"] == "azure"
    assert os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] == "InstrumentationKey=abc"


def test_missing_databricks_secret_turns_telemetry_off_not_the_job(monkeypatch, caplog):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    with caplog.at_level(logging.WARNING):
        assert tm.use_databricks_secret(_FakeDbutils({}), "azure") == "off"
    import os
    assert os.environ["DENTAL_TELEMETRY"] == "off" and "appinsights_connection_string" in caplog.text


def test_connection_string_from_env_loses_stray_quotes_and_line_endings(monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", '"InstrumentationKey=abc;IngestionEndpoint=https://x/"\r\n')
    assert tm.config_from_env().connection_string == "InstrumentationKey=abc;IngestionEndpoint=https://x/"


@pytest.mark.parametrize("bad", ["Warning: No outputs found", "abc;def", "╷\n│ Error: Output not found"])
def test_malformed_connection_string_warns_and_turns_off_instead_of_crashing(bad, caplog):
    with caplog.at_level(logging.WARNING):
        assert tm.setup(tm.TelemetryConfig(exporter="azure", connection_string=bad)) is None
    assert tm.active_exporter() == "off"
    assert "not a valid" in caplog.text and bad not in caplog.text      # the value is never logged


def test_a_missing_azure_package_turns_telemetry_off_instead_of_failing_the_pipeline(monkeypatch, caplog, capsys):
    """#822: on Databricks the azure extra was not installed; once a valid connection string arrived, setup() raised
    ModuleNotFoundError and Load results failed. Telemetry is optional: it turns off, says why and how to fix it."""
    for name in ("azure.monitor.opentelemetry", "azure.monitor", "azure"):
        monkeypatch.setitem(sys.modules, name, None)      # import of any of them now raises ImportError
    good = "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://x.example/"
    with caplog.at_level(logging.WARNING):
        assert tm.setup(tm.TelemetryConfig(exporter="azure", connection_string=good)) is None
    assert tm.active_exporter() == "off"
    status = tm.status()
    assert status["asked_exporter_name"] == "azure" and status["reason_text"].startswith(tm.REASONS["no_azure_package"])
    err = capsys.readouterr().err
    assert 'pip install "health-transformation-lab-nlp[azure]"' in err and good not in err + caplog.text
