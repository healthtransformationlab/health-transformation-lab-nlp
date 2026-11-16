"""Pipeline telemetry with OpenTelemetry (spec 014).

One switch, `DENTAL_TELEMETRY`, picks where traces, metrics and logs go:

    off      default: nothing leaves the process (tests, CI, laptops)
    console  print spans and metrics (debugging)
    azure    Azure Application Insights through the Azure Monitor OpenTelemetry distro;
             needs APPLICATIONINSIGHTS_CONNECTION_STRING (Databricks: secret scope `health_transformation_lab`,
             key `appinsights_connection_string`). Without it: off, with a warning, one stderr line naming the fix,
             and status() saying why (014 BUG1, #792); the daily digest carries it as a SEV3.
    otlp     any OpenTelemetry backend over OTLP (self-hosted Grafana Tempo/Loki, Jaeger, SigNoz);
             OTEL_EXPORTER_OTLP_ENDPOINT as usual
    memory   in-process, for tests
    file     one JSON line a span (and a metrics batch), to DENTAL_TELEMETRY_FILE: runs with no network, such as
             the coding agent on a Kaggle kernel (spec 014 US6); a later step sends the file on

Cost guards for the Azure free allowance (5 GB/month per billing account): the workspace daily cap
in infra/azure/main.tf (Terraform), `DENTAL_TELEMETRY_SAMPLING` (default 1.0: a batch run is a few hundred
spans, and a sampled-away failure is the one you needed), and only INFO and above from the package
logger. Telemetry never carries note text or row-level data: step names, counts, durations, rates
and error types only.

    from health_transformation_lab_nlp import telemetry
    telemetry.setup()                                   # from the environment
    with telemetry.pipeline_step("build_sites", data_label="synthetic", rows=len(v)):
        ...
    telemetry.record_value("data_quality.pass_rate", 0.97, check="cal_range")
    telemetry.annotate(output_token_count=64)           # numbers and short labels on the current function's span
"""

from __future__ import annotations

import atexit
import functools
import inspect
import itertools
import json
import importlib.util
import logging
import os
import re
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from opentelemetry import context, metrics, trace
from opentelemetry.trace import Status, StatusCode

SERVICE = "health-transformation-lab-nlp"                 # service.namespace: the code base
DATA_PRODUCT = "health_transformation_lab"          # service.name: the data product, as in the Databricks schemas
MAX_SPANS_PER_CALLER = int(os.environ.get("DENTAL_TELEMETRY_MAX_CALLS", "3"))
LEVELS = ("step", "call", "detail")         # DENTAL_TELEMETRY_LEVEL: how far down the call tree to trace
LEVELS_FILE = Path(__file__).with_name("telemetry_levels.yaml")
LOGGER = "health_transformation_lab_nlp"
EXPORTERS = ("off", "console", "azure", "otlp", "memory", "file")
LABEL_SUFFIXES = ("_name", "_code", "_id")   # annotate() keeps text only as a short label (AGENTS.md data names)
MAX_LABEL_CHARS = 64
AZURE_SETTING = "APPLICATIONINSIGHTS_CONNECTION_STRING"
CONTENT_SETTING = "DENTAL_TELEMETRY_CONTENT"   # a coding-agent run's own content on a span (spec 014 US9, ADR 0010)
CONTENT_LEVELS = ("labels", "full")           # labels: numbers and short labels, the default; full: text too, scrubbed
MAX_TEXT_CHARS = 8000                         # Application Insights: property value string length 8,192, and
#                                               64 KB an item (Azure Monitor service limits, read 2026-11-16)
REDACTED = "[REDACTED]"
SECRET_SCOPE, SECRET_KEY = "health_transformation_lab", "appinsights_connection_string"   # Databricks secret
REASONS = {                                 # why an asked-for exporter is off (status()["reason_text"] starts so)
    "no_connection_string": f"no connection string: {AZURE_SETTING} is not set",
    "malformed_connection_string": f"malformed connection string: {AZURE_SETTING} has no InstrumentationKey=...",
    "no_secret": "no secret",
    "no_file": "no file: DENTAL_TELEMETRY_FILE is not set",
    "no_azure_package": "no azure exporter: azure-monitor-opentelemetry is not installed",
}
log = logging.getLogger(LOGGER)


@dataclass(frozen=True)
class TelemetryConfig:
    exporter: str = "off"
    connection_string: str = field(default="", repr=False)
    sampling_ratio: float = 1.0
    environment: str = "dev"
    data_product_id: str = field(default_factory=lambda: os.environ.get("DENTAL_DATA_PRODUCT_ID", DATA_PRODUCT))
    level: str = field(default_factory=lambda: os.environ.get("DENTAL_TELEMETRY_LEVEL", "call").strip().lower())
    file_path: str = ""                     # DENTAL_TELEMETRY=file: one JSON line a span, for runs with no network

    def __post_init__(self):
        if self.exporter not in EXPORTERS:
            raise ValueError(f"DENTAL_TELEMETRY must be one of {EXPORTERS}")
        if not 0.0 <= self.sampling_ratio <= 1.0:
            raise ValueError("DENTAL_TELEMETRY_SAMPLING must be between 0 and 1")
        if self.level not in LEVELS:
            raise ValueError(f"DENTAL_TELEMETRY_LEVEL must be one of {LEVELS}")


def _clean(value: str) -> str:
    """Strip what shells and copy-paste add: whitespace, Windows line endings, surrounding quotes."""
    return value.strip().strip("\"'").strip()


def _looks_valid(connection_string: str) -> bool:
    """key=value pairs separated by ';', one of them InstrumentationKey (the Azure Monitor format)."""
    pairs = [p.split("=", 1) for p in connection_string.split(";") if p.strip()]
    return all(len(p) == 2 for p in pairs) and any(k.strip().lower() == "instrumentationkey" for k, _ in pairs)


def config_from_env() -> TelemetryConfig:
    return TelemetryConfig(exporter=os.environ.get("DENTAL_TELEMETRY", "off").strip().lower() or "off",
                           connection_string=_clean(os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")),
                           sampling_ratio=float(os.environ.get("DENTAL_TELEMETRY_SAMPLING", "1.0")),
                           environment=os.environ.get("DENTAL_ENVIRONMENT", "dev"),
                           file_path=os.environ.get("DENTAL_TELEMETRY_FILE", "").strip())


class _State:
    exporter = "off"
    tracer: trace.Tracer = trace.NoOpTracer()
    meter: metrics.Meter = metrics.NoOpMeter(SERVICE)
    instruments: ClassVar[dict] = {}
    calls: ClassVar[dict] = {}
    header: ClassVar[dict] = {}
    level = LEVELS.index("call")
    profile = None                          # dict while telemetry.profile() is running
    script = None
    providers: ClassVar[list] = []          # the SDK providers setup() made, shut down (flushed) by the next setup
    providers_global = False                # azure: the process's global providers, flushed but never shut down here
    file = None                             # the file exporter's open file
    status: ClassVar[dict] = {"asked_exporter_name": "off", "active_exporter_name": "off", "reason_text": ""}
    pending: ClassVar[dict] = {}            # use_databricks_secret found no secret: the next setup() keeps saying so


_annotatable: ContextVar = ContextVar("dental_annotatable_span", default=None)   # the span annotate() writes on


def _header(c: TelemetryConfig) -> dict:
    """The common header on every span and log line, so one shared Application Insights resource can be
    filtered by data product and environment (as cdh-lava-core does with service and cloud-role names)."""
    return {"data_product_id": c.data_product_id, "environment": c.environment, "service.namespace": SERVICE}


def _resource(c: TelemetryConfig):
    import socket

    from opentelemetry.sdk.resources import Resource
    return Resource.create({"service.name": c.data_product_id, "service.namespace": SERVICE,
                            "service.instance.id": socket.gethostname(), "deployment.environment": c.environment})


def _header_processor():
    from opentelemetry.sdk.trace import SpanProcessor

    class HeaderProcessor(SpanProcessor):
        def on_start(self, span, parent_context=None):
            span.set_attributes(_State.header)

    return HeaderProcessor()


def _sdk_providers(c: TelemetryConfig, span_exporter, metric_exporter):
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    tp = TracerProvider(resource=_resource(c), sampler=ParentBased(TraceIdRatioBased(c.sampling_ratio)),
                        shutdown_on_exit=False)
    tp.add_span_processor(_header_processor())
    simple = c.exporter in ("memory", "console", "file")      # a file is written as each span ends: a crash loses none
    tp.add_span_processor((SimpleSpanProcessor if simple else BatchSpanProcessor)(span_exporter))
    readers = [PeriodicExportingMetricReader(metric_exporter)] if metric_exporter is not None else []
    mp = MeterProvider(resource=_resource(c), metric_readers=readers, shutdown_on_exit=False)
    _State.providers = [tp, mp]
    return tp.get_tracer(SERVICE), mp.get_meter(SERVICE)


def _json_line(item) -> str:
    return item.to_json(indent=None) + "\n"


def _shutdown_providers() -> None:
    """Flush and stop the providers setup() made, then close the file exporter's file (at the next setup, and at
    exit, after the run span has ended)."""
    for provider in _State.providers:
        try:
            if getattr(_State, "providers_global", False):
                provider.force_flush()     # azure: global providers, flushed, left running (#801)
            else:
                provider.shutdown()
        except Exception:  # noqa: BLE001 - stopping telemetry never fails the run
            pass
    _State.providers = []
    _State.providers_global = False
    if _State.file is not None:
        _State.file.close()
        _State.file = None


atexit.register(_shutdown_providers)


def setup(config: TelemetryConfig | None = None):
    """Configure telemetry. Returns the in-memory span exporter for exporter='memory', else None."""
    c = config or config_from_env()
    _shutdown_providers()
    _State.instruments, _State.calls = {}, {}
    _State.header = _header(c)
    _State.level = LEVELS.index(c.level)
    logging.getLogger(LOGGER).setLevel(logging.INFO)
    out = None
    asked, reason = c.exporter, ""
    if c.exporter == "azure" and not c.connection_string:
        log.warning("DENTAL_TELEMETRY=azure but APPLICATIONINSIGHTS_CONNECTION_STRING is not set: telemetry off")
        reason = REASONS["no_connection_string"]
        c = TelemetryConfig(exporter="off")
    elif c.exporter == "azure" and not _looks_valid(c.connection_string):   # never log the value itself
        log.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is not a valid Application Insights connection "
                    "string (expected InstrumentationKey=...;IngestionEndpoint=...): telemetry off")
        reason = REASONS["malformed_connection_string"]
        c = TelemetryConfig(exporter="off")
    if c.exporter == "azure" and not _azure_exporter_installed():   # optional: never fails a pipeline (#822)
        log.warning("DENTAL_TELEMETRY=azure but azure-monitor-opentelemetry is not installed: telemetry off")
        reason = REASONS["no_azure_package"]
        c = TelemetryConfig(exporter="off")
    if c.exporter == "file" and not c.file_path:
        log.warning("DENTAL_TELEMETRY=file but DENTAL_TELEMETRY_FILE is not set: telemetry off")
        reason = REASONS["no_file"]
        c = TelemetryConfig(exporter="off")
    pending, _State.pending = _State.pending, {}
    if asked == "off" and pending:          # use_databricks_secret asked for an exporter and found no secret
        asked, reason = pending["asked_exporter_name"], pending["reason_text"]
    _set_status(asked, c.exporter, reason, announce=not pending)
    if c.exporter == "off":
        _State.tracer, _State.meter = trace.NoOpTracer(), metrics.NoOpMeter(SERVICE)
    elif c.exporter == "memory":
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        out = InMemorySpanExporter()
        _State.tracer, _State.meter = _sdk_providers(c, out, None)
    elif c.exporter == "console":
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        _State.tracer, _State.meter = _sdk_providers(c, ConsoleSpanExporter(), ConsoleMetricExporter())
    elif c.exporter == "file":
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        path = Path(c.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _State.file = path.open("w", encoding="utf-8")         # one file a run: a rerun replaces it, never appends
        _State.tracer, _State.meter = _sdk_providers(c, ConsoleSpanExporter(out=_State.file, formatter=_json_line),
                                                     ConsoleMetricExporter(out=_State.file, formatter=_json_line))
    elif c.exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        _State.tracer, _State.meter = _sdk_providers(c, OTLPSpanExporter(), OTLPMetricExporter())
    else:                                                      # azure
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=c.connection_string, sampling_ratio=c.sampling_ratio,
                                enable_live_metrics=True, logger_name=LOGGER, resource=_resource(c),
                                span_processors=[_header_processor()])
        # Recorded like the other exporters' providers, so flush() and exit send what is queued (014 BUG2, #801):
        # without this a short script's spans sat in the batch queue and never reached Application Insights.
        # They are the process's global providers, set once: flushed at the next setup and at exit, never shut down
        # here, or a later setup's spans would go to a stopped provider (the SDK shuts them down at exit itself).
        _State.providers = [trace.get_tracer_provider(), metrics.get_meter_provider()]
        _State.providers_global = True
        _azure_warnings_to_stderr()
        _State.tracer, _State.meter = trace.get_tracer(SERVICE), metrics.get_meter(SERVICE)
    _State.exporter = c.exporter
    return out


AZURE_EXPORTER_LOGGER = "azure.monitor.opentelemetry.exporter"


def _azure_exporter_installed() -> bool:
    """Whether the Azure Monitor exporter can be imported (the azure extra). A module already in sys.modules counts as
    import would count it (None there means it cannot be imported)."""
    name = "azure.monitor.opentelemetry"
    if name in sys.modules:
        return sys.modules[name] is not None
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _azure_warnings_to_stderr() -> None:
    """A rejected or failed export is logged by the Azure exporter; print its warnings and errors, once (#801)."""
    log = logging.getLogger(AZURE_EXPORTER_LOGGER)
    if not any(getattr(h, "_htl_stderr", False) for h in log.handlers):
        h = logging.StreamHandler(sys.stderr)
        h._htl_stderr = True
        h.setLevel(logging.WARNING)
        log.addHandler(h)
    if log.level == logging.NOTSET or log.level > logging.WARNING:
        log.setLevel(logging.WARNING)


def flush(timeout_millis: int = 10000) -> bool:
    """Send what is queued now and say whether every provider's flush succeeded (014 BUG2, #801). True when
    telemetry is off. A provider without force_flush (the SDK's no-op default) counts as nothing to send."""
    ok = True
    for provider in _State.providers:
        fn = getattr(provider, "force_flush", None)
        if fn is None:
            continue
        try:
            ok = bool(fn(timeout_millis=timeout_millis)) and ok
        except Exception:  # noqa: BLE001 - a failed flush is reported, never raised
            ok = False
    return ok


def active_exporter() -> str:
    return _State.exporter


def status() -> dict:
    """What the last setup() was asked for, what is on, and why they differ (014 BUG1, #792): `asked_exporter_name`,
    `active_exporter_name`, `reason_text` (empty when they agree). Names and reasons only, never a secret's value.
    A missing Databricks secret (use_databricks_secret) shows here at once and through the next setup()."""
    return dict(_State.status)


def fix_text(reason_text: str) -> str:
    """The fix for a reason status() gives: what to create or set, by name."""
    if reason_text.startswith(REASONS["no_file"]):
        return "set DENTAL_TELEMETRY_FILE to the span file's path"
    if reason_text.startswith(REASONS["no_azure_package"]):
        return 'install the azure extra: pip install "health-transformation-lab-nlp[azure]" (in a notebook, %pip install -e ../../python[azure])'
    if reason_text.startswith(REASONS["malformed_connection_string"]):
        return ("put the resource's own connection string (InstrumentationKey=...;IngestionEndpoint=..., from "
                f"terraform -chdir=infra/azure output -raw connection_string) in {AZURE_SETTING} or the Databricks "
                f"secret {SECRET_SCOPE}/{SECRET_KEY}")
    return ("create the Application Insights resource with infra/azure (terraform -chdir=infra/azure apply), then put "
            f"its connection string in {AZURE_SETTING} or the Databricks secret {SECRET_SCOPE}/{SECRET_KEY}")


def _set_status(asked: str, active: str, reason: str, announce: bool = True) -> None:
    """Record the outcome; when asked and active differ, say so on one stderr line (a workflow warning annotation
    under GitHub Actions), so it shows in a job's output, not only in a log. Telemetry stays optional: no raise."""
    _State.status = {"asked_exporter_name": asked, "active_exporter_name": active,
                     "reason_text": reason if asked != active else ""}
    if asked == active or not announce:
        return
    line = (f"telemetry off: DENTAL_TELEMETRY={asked} was asked but telemetry is {active} ({reason}). "
            f"Fix: {fix_text(reason)}. Until then no spans reach the backend; the daily digest carries it as a SEV3.")
    prefix = "::warning title=telemetry off::" if os.environ.get("GITHUB_ACTIONS", "").lower() == "true" else ""
    print(prefix + line, file=sys.stderr, flush=True)


def _instrument(kind: str, name: str, unit: str = ""):
    key = (kind, name)
    if key not in _State.instruments:
        make = {"histogram": _State.meter.create_histogram, "counter": _State.meter.create_counter}[kind]
        _State.instruments[key] = make(name, unit=unit)
    return _State.instruments[key]


def record_value(name: str, value: float, **attrs) -> None:
    """A measured value (pass rate, rows, AUROC) as a histogram point with attributes."""
    _instrument("histogram", name).record(value, attributes=attrs)


def _keep(key: str, value) -> bool:
    """Numbers and booleans; text only as a short label, a key ending _name, _code or _id."""
    if isinstance(value, (bool, int, float)):
        return True
    return isinstance(value, str) and key.endswith(LABEL_SUFFIXES) and len(value) <= MAX_LABEL_CHARS


def annotate(**attrs) -> None:
    """Measured values on the span of the function this is called from: tokens, seconds, counts, a tool's name
    (spec 014 US6). Text is kept only as a short label (a key ending _name, _code or _id, at most 64 characters), so a
    prompt, a reply, a command or a patch can't reach a span. When that function made no span (telemetry off, its
    level, or past DENTAL_TELEMETRY_MAX_CALLS), nothing is written: never onto the caller's span."""
    if _State.exporter == "off":
        return
    span = _annotatable.get()
    if span is None or not span.is_recording():
        return
    span.set_attributes({k: v for k, v in attrs.items() if _keep(k, v)})


def content_level() -> str:
    """`DENTAL_TELEMETRY_CONTENT`: `labels` (the default) or `full`. Any other value stops the caller at once, naming
    the setting (AGENTS.md, "Check settings before doing work")."""
    value = os.environ.get(CONTENT_SETTING, "").strip().lower() or CONTENT_LEVELS[0]
    if value not in CONTENT_LEVELS:
        raise SystemExit(f"{CONTENT_SETTING} is {value!r}: it takes {' or '.join(CONTENT_LEVELS)}")
    return value


_B = r"(?<![A-Za-z0-9])"                       # a token shape starts where no letter or digit runs into it
_TOKEN_SHAPES = re.compile(_B + r"(?:" + "|".join((
    r"KGAT_[A-Za-z0-9]{16,}",                                                # Kaggle
    r"hf_[A-Za-z0-9]{20,}",                                                  # Hugging Face
    r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",          # GitHub
    r"sk-(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{20,}",                            # sk- API keys (a digit somewhere)
    r"[sr]k_(?:live|test)_[A-Za-z0-9]{16,}",                                 # Stripe-style
    r"A[KS]IA[0-9A-Z]{16}",                                                  # AWS access key ids
    r"dapi[0-9a-f]{32}",                                                     # Databricks
    r"AIza[0-9A-Za-z_-]{30,}",                                               # Google
    r"xox[abprs]-[A-Za-z0-9-]{10,}",                                         # Slack
    r"pypi-[A-Za-z0-9_-]{20,}", r"glpat-[A-Za-z0-9_-]{16,}", r"npm_[A-Za-z0-9]{30,}",
    r"a[ks]-[A-Za-z0-9]{20,}",                                               # Modal token id and secret
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",           # a JSON web token
)) + r")")
_PEM = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)", re.S)
_TELLING = (r"(?:pass(?:word|wd|phrase)|\bpwd\b|secret|token|api_?key|private_?key|instrumentation_?key"
            r"|credentials?|\bauth\b|\bkey\b)")
_Q = r"""(?P<q>\\?["'])"""                     # a quote, as written or as JSON escapes it
_QUOTED_VALUE = r"(?P<v>(?:(?!(?P=q))[^\n]){4,}?)(?P=q)"
_RULES = (   # (pattern with groups keep and v, which values it redacts: "any", "unless_ordinary" or "if_mixed")
    # a quoted value given to a telling name: NAME = "v", "NAME": "v", NAME["X"] = "v", getenv("NAME", "v")
    (re.compile(rf"""(?i)(?P<keep>{_TELLING}[A-Za-z0-9_]{{0,40}}(?:\\?["'])?\]?\s*[:=,]\s*[bruf]{{0,2}}{_Q}){_QUOTED_VALUE}"""),
     "unless_ordinary"),
    (re.compile(rf"""(?i)(?P<keep>\bauth\s*=\s*\(\s*\\?["'][^"'\\\n]*\\?["']\s*,\s*{_Q}){_QUOTED_VALUE}"""), "any"),
    # NAME=value with no quotes, the name in capitals: a shell line, a .env file, printenv's output
    (re.compile(r"""(?P<keep>(?<![A-Za-z0-9_])[A-Z0-9_]{0,40}(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS)"""
                r"""[A-Z0-9_]{0,40}=)(?P<v>[^\s"'\\&;]{4,})"""), "unless_ordinary"),
    # name: value or name = value without quotes (YAML, ini, .netrc), only when the value mixes letters and digits
    (re.compile(r"""(?i)(?P<keep>(?<![A-Za-z0-9_])[A-Za-z0-9_]{0,40}(?:password|passwd|secret|token|api_?key)"""
                r"""[A-Za-z0-9_]{0,20}(?:\s*[:=]\s*|\s+))(?P<v>[^\s"'\\#,)(]{6,})"""), "if_mixed"),
    # command-line options and logins
    (re.compile(r"""(?i)(?P<keep>--?(?:password|passwd|token|api[-_]?key|secret|access[-_]?token|auth[-_]?token)"""
                r"""(?:=|\s+))(?P<v>[^\s"'\\-][^\s"'\\]{3,})"""), "unless_ordinary"),
    (re.compile(r"""(?P<keep>(?:\s-u|--user)\s+[^\s:"'\\]+:)(?P<v>[^\s"'\\]+)"""), "any"),
    (re.compile(r"""(?P<keep>\bmysql\b[^\n|;&]*?\s-p)(?P<v>[^\s"'\\]+)"""), "any"),
    (re.compile(r"""(?P<keep>\bdocker\s+login\b[^\n|;&]*?\s-p\s+)(?P<v>[^\s"'\\]+)"""), "any"),
    # headers
    (re.compile(r"""(?i)(?P<keep>authorization(?:\\?["'])?\s*[:=]\s*(?:\\?["'])?\s*(?:basic|bearer|token)\s+)"""
                r"""(?P<v>(?=[^\s"'\\]*\d)[^\s"'\\]{6,})"""), "any"),
    (re.compile(r"""(?i)(?P<keep>\bbearer\s+)(?P<v>(?=[A-Za-z0-9._~+/=-]*\d)[A-Za-z0-9._~+/=-]{8,})"""), "any"),
    (re.compile(r"""(?i)(?P<keep>(?:x-api-key|x-auth-token|private-token|api-key)(?:\\?["'])?\s*[:=]\s*(?:\\?["'])?\s*)"""
                r"""(?P<v>[^\s"'\\]{6,})"""), "unless_ordinary"),
    (re.compile(r"""(?P<keep>(?:^|[\s"'])(?:Set-)?Cookie(?:\\?["'])?:\s*(?:\\?["'])?)(?P<v>[^\n"'\\]*=[^\n"'\\]{4,})""",
                re.M), "any"),
    # URLs: scheme://user:password@host, and a secret in the query string
    (re.compile(r"""(?P<keep>[A-Za-z][A-Za-z0-9+.-]{1,20}://[^\s/:@"'\\]+:)(?P<v>[^\s/@"'\\]+)(?=@)"""), "any"),
    (re.compile(r"""(?i)(?P<keep>[?&](?:api[-_]?key|access[-_]?token|token|sig|signature|password|secret|key)=)"""
                r"""(?P<v>[^&\s"'\\#]{6,})"""), "unless_ordinary"),
    # Azure connection strings
    (re.compile(r"""(?i)(?P<keep>(?:InstrumentationKey|AccountKey|SharedAccessKey|SharedAccessSignature)=)"""
                r"""(?P<v>[^;\s"'\\]+)"""), "any"),
)
_SECRET_ENV = re.compile(r"(?i)(?:^|_)(?:key|token|secret|password|passwd|credentials?)(?:$|_)|connection_string")
_PLAIN_WORDS = re.compile(r"[A-Za-z]+(?:[-_.][A-Za-z]+)*")


def _ordinary(value: str) -> bool:
    """A value that reads as a name, a path or a sentence, not a secret: letters only (`bearer`, `new_password`,
    `X-API-Key`, `bert-base-uncased`), a path or a placeholder (`/token`, `<mask>`, `{token}`, `$TOKEN`), three or
    more words, or a small number. A password that is one plain word passes as ordinary: the price of readable code."""
    if value == REDACTED or value[:1] in "/<{$.~%" or len(value.split()) >= 3:
        return True
    if value.isdigit() and len(value) <= 6:
        return True
    return len(value) <= 24 and _PLAIN_WORDS.fullmatch(value) is not None


def _mixed(value: str) -> bool:
    return any(c.isdigit() for c in value) and any(c.isalpha() for c in value)


def _redact(match, which: str) -> str:
    value = match.group("v")
    if which == "unless_ordinary" and _ordinary(value) or which == "if_mixed" and not _mixed(value):
        return match.group(0)
    tail = match.group(0)[match.end("v") - match.start(0):]
    return match.group("keep") + REDACTED + tail


def scrub(text: str) -> str:
    """`text` with secrets replaced by `[REDACTED]` (spec 014 US9, ADR 0010). It knows shapes, not secrets:

    - token shapes (Kaggle, Hugging Face, GitHub, `sk-`, AWS, Databricks, Google, Slack, PyPI, GitLab, npm, Modal,
      JSON web tokens) and private-key blocks;
    - a value given to a telling name (`password`, `secret`, `token`, `api_key`, `private_key`, `credentials`, `auth`,
      `key`): quoted in code or JSON, as written or JSON-escaped; unquoted after a NAME in capitals (`export`, `.env`,
      `printenv`); unquoted in YAML, ini or .netrc when it mixes letters and digits;
    - `--password`/`--token` options, `curl -u`, `mysql -p`, `docker login -p`;
    - `Authorization`, `Bearer`, `X-API-Key` and `Cookie` headers;
    - `scheme://user:password@host`, a secret in a query string, and an Azure connection string's key;
    - the value of any of this process's environment variables whose name says it is a secret (the forwarder runs
      with the Kaggle token and the connection string in its environment).

    Ordinary code stays readable: `password: str`, `password=form.password`, `"token_type": "bearer"`. What it cannot
    know is a secret in a shape it has no rule for under a name that doesn't tell; docs/telemetry.md lists the gaps."""
    for name, value in os.environ.items():
        if len(value) >= 12 and _SECRET_ENV.search(name):
            for form in {value, json.dumps(value)[1:-1]}:
                if form in text:
                    text = text.replace(form, REDACTED)
    text = _PEM.sub(REDACTED, text)
    text = _TOKEN_SHAPES.sub(REDACTED, text)
    for pattern, which in _RULES:
        text = pattern.sub(functools.partial(_redact, which=which), text)
    return text


def scrub_value(value):
    """`value` (what `json.loads` gives: dicts, lists, text, numbers) with every text in it scrubbed, and any text
    stored under a telling key (`password`, `token`, `client_secret`, `private_key`, `auth`, `key`, ...) redacted
    unless it reads as ordinary. Scrubbing before `json.dumps` sees the text as it was written, quotes and newlines
    unescaped; `content_span` scrubs the result once more."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if isinstance(item, str) and _TELLING_KEY.search(str(key)) and not _ordinary(item):
                out[key] = REDACTED
            else:
                out[key] = scrub_value(item)
        return out
    if isinstance(value, list):
        return [scrub_value(item) for item in value]
    return scrub(value) if isinstance(value, str) else value


_TELLING_KEY = re.compile(rf"(?i){_TELLING}")


def text_parts(text: str, size: int = MAX_TEXT_CHARS) -> list[str]:
    """`text` cut into pieces of at most `size` characters, in order; joined, they are the text. Always one or more."""
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def content_span(name: str, start_ns: int, end_ns: int, parent=None, **attrs):
    """One finished span that may hold text: the only way a prompt, a command, a tool's output or a patch reaches a
    span, and only for a coding-agent run's own content (spec 014 US9, ADR 0010), never dental records. Numbers and
    booleans are kept as they are. Every text value is scrubbed (`scrub`); one longer than MAX_TEXT_CHARS keeps its
    first part on the span with `<key>_part_count`, and each further part is a child span `<name>_part` with
    `field_name`, `part_num`, `part_text` and the span's own numbers and short labels. `parent` is a span (ended or
    not) or None for a new trace. Returns the span; sends nothing, and returns None, unless content_level() is `full`
    and an exporter is set up."""
    if _State.exporter == "off" or content_level() != "full":
        return None
    base, more = {}, []
    for key, value in attrs.items():
        if isinstance(value, (bool, int, float)):
            base[key] = value
        elif isinstance(value, str):
            first, *rest = text_parts(scrub(value))
            base[key] = first
            if rest:
                base[f"{key}_part_count"] = 1 + len(rest)
                more += [(key, num, part) for num, part in enumerate(rest, start=2)]
    ctx = trace.set_span_in_context(parent) if parent is not None else context.Context()
    span = _State.tracer.start_span(name, context=ctx, attributes=base, start_time=start_ns)
    labels = {k: v for k, v in base.items() if not k.endswith("_text") and (not isinstance(v, str) or _keep_label(v))}
    for key, num, part in more:
        child = _State.tracer.start_span(f"{name}_part", context=trace.set_span_in_context(span), start_time=start_ns,
                                         attributes={**labels, "field_name": key, "part_num": num, "part_text": part})
        child.end(end_time=end_ns)
    span.end(end_time=end_ns)
    return span


def _keep_label(value: str) -> bool:
    return len(value) <= MAX_LABEL_CHARS


def _record_failure(span, name: str, e: BaseException) -> None:
    span.set_attribute("error.type", type(e).__name__)
    span.record_exception(e)
    span.set_status(Status(StatusCode.ERROR, str(e)[:500]))
    _instrument("counter", "pipeline.step.failures").add(1, {"pipeline.step": name, "error.type": type(e).__name__})
    log.error("step %s failed: %s: %s", name, type(e).__name__, str(e)[:500])


@contextmanager
def pipeline_step(name: str, **attrs):
    """A span for one pipeline step; on failure the error is recorded, counted and re-raised."""
    base = {"pipeline.step": name, **{("data.label" if k == "data_label" else k): v for k, v in attrs.items()}}
    start = time.perf_counter()
    with _State.tracer.start_as_current_span(name, attributes=base, record_exception=False,
                                             set_status_on_exception=False) as span:
        token = _annotatable.set(span)
        try:
            yield span
        except Exception as e:
            _record_failure(span, name, e)
            raise
        finally:
            _annotatable.reset(token)
            _instrument("histogram", "pipeline.step.duration", "s").record(
                time.perf_counter() - start, {"pipeline.step": name})


def start_script(name: str, **attrs) -> None:
    """One call at the top of a script: a run-level span that every pipeline_step nests under, ended at
    exit; an uncaught error is recorded on it (through sys.excepthook) before Python prints it."""
    end_script()
    span = _State.tracer.start_span(name, attributes={"pipeline.step": name, "pipeline.kind": "script",
                                                      **{("data.label" if k == "data_label" else k): v
                                                         for k, v in attrs.items()}})
    token = context.attach(trace.set_span_in_context(span))
    marked = _annotatable.set(span)
    prev = sys.excepthook

    def hook(etype, value, tb):
        if _State.script is not None and _State.script[0] is span:
            _record_failure(span, name, value)
            end_script()
        prev(etype, value, tb)

    _State.script = (span, token, prev, time.perf_counter(), name, marked)
    sys.excepthook = hook
    atexit.register(end_script)


def end_script() -> None:
    """End the run span (idempotent) and put the previous excepthook back."""
    if _State.script is None:
        return
    span, token, prev, start, name, marked = _State.script
    _State.script = None
    try:
        _annotatable.reset(marked)
    except ValueError:         # ended from another context (an excepthook, atexit): nothing to put back there
        _annotatable.set(None)
    sys.excepthook = prev
    _instrument("histogram", "pipeline.step.duration", "s").record(time.perf_counter() - start,
                                                                   {"pipeline.step": name})
    span.end()
    context.detach(token)      # OpenTelemetry logs, never raises, if the context already moved on


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_KINDS = {k.name: k for k in trace.SpanKind}


def _iso_ns(text: str) -> int:
    """A span file's time ("2026-11-15T02:18:52.813000Z", microseconds) as nanoseconds since the epoch, exactly."""
    t = datetime.fromisoformat(text)
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (t - _EPOCH) // timedelta(microseconds=1) * 1000


def _forwardable(value) -> bool:
    """What a forwarded span keeps: numbers, booleans, lists of them, and text only as a short label (at most
    MAX_LABEL_CHARS), so a file written by other code (the agent framework's spans) can't carry text to Azure."""
    if isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, list):
        return all(isinstance(v, (bool, int, float)) for v in value)
    return isinstance(value, str) and len(value) <= MAX_LABEL_CHARS


def _read_spans(path: Path) -> list[dict]:
    """The span lines of a telemetry.jsonl: metrics batches and a line cut off by a machine that stopped are left out."""
    spans = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and "context" in item and "start_time" in item and "end_time" in item:
            spans.append(item)
    return spans


def forward_spans(path: Path, extra: dict | None = None) -> int:
    """Send the spans of a telemetry.jsonl (the `file` exporter's layout, or the Kaggle bundle's and kernel's, which
    are the same) through the exporter setup() configured, and return how many were sent (spec 014 US7, #791). Each
    keeps its own start and end time, kind, status and attributes (numbers and short labels only); a child keeps its
    parent, under new span ids, and a span whose parent isn't in the file starts its own trace. `extra` is added to
    every span (the forwarding's `run_label` and `forward_id`), under the same rule: numbers and short labels. With
    the exporter off, or no file, nothing is sent."""
    path = Path(path)
    if _State.exporter == "off":
        return 0
    if not path.is_file():
        log.warning("no span file at %s: nothing to forward", path.name)
        return 0
    spans = sorted(_read_spans(path), key=lambda s: _iso_ns(s["start_time"]))
    by_id = {str(s["context"].get("span_id")): s for s in spans}
    made: dict[str, trace.Span] = {}

    def start(s: dict, depth: int = 0) -> trace.Span:
        sid = str(s["context"].get("span_id"))
        if sid in made:
            return made[sid]
        parent = by_id.get(str(s.get("parent_id")))
        if parent is not None and parent is not s and depth < 64:
            ctx = trace.set_span_in_context(start(parent, depth + 1))
        else:
            ctx = context.Context()                            # a root: its own trace, not the caller's
        attrs = {k: v for k, v in {**(extra or {}), **(s.get("attributes") or {})}.items() if _forwardable(v)}
        kind = _KINDS.get(str(s.get("kind", "")).rsplit(".", 1)[-1], trace.SpanKind.INTERNAL)
        made[sid] = _State.tracer.start_span(s.get("name") or "span", context=ctx, kind=kind, attributes=attrs,
                                             start_time=_iso_ns(s["start_time"]))
        return made[sid]

    for s in spans:
        start(s)
    for s in reversed(spans):                                  # children end first, as they did
        span = made[str(s["context"].get("span_id"))]
        status = (s.get("status") or {}).get("status_code", "UNSET")
        if status == "ERROR":
            span.set_status(Status(StatusCode.ERROR, str((s.get("status") or {}).get("description") or "")[:64]))
        elif status == "OK":
            span.set_status(Status(StatusCode.OK))
        span.end(end_time=_iso_ns(s["end_time"]))
    for provider in _State.providers or [trace.get_tracer_provider()]:   # sent now, not at exit (azure: global)
        flush = getattr(provider, "force_flush", None)
        if flush is not None and hasattr(provider, "get_tracer"):
            flush()
    return len(made)


def use_databricks_secret(dbutils, exporter: str = "azure", scope: str = SECRET_SCOPE, key: str = SECRET_KEY) -> str:
    """In a Databricks notebook: put the telemetry settings in the environment, where the scripts the
    notebook starts pick them up. A missing secret turns telemetry off; it never fails the job."""
    _State.pending = {}
    if exporter == "azure":
        try:
            os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = _clean(dbutils.secrets.get(scope, key))
        except Exception as e:  # noqa: BLE001  dbutils raises its own exception types
            log.warning("no secret %s/%s (%s): telemetry off", scope, key, type(e).__name__)
            reason = f"{REASONS['no_secret']}: the Databricks secret {scope}/{key} is not there ({type(e).__name__})"
            _set_status("azure", "off", reason)
            _State.pending = dict(_State.status)
            exporter = "off"
    os.environ["DENTAL_TELEMETRY"] = exporter
    return exporter


class _HeaderLogger(logging.LoggerAdapter):
    """Log lines carry the common header and the calling function (customDimensions in App Insights)."""

    def process(self, msg, kwargs):
        kwargs["extra"] = {**_State.header, **self.extra, **kwargs.get("extra", {})}
        return msg, kwargs


@contextmanager
def trace_call(name: str, level: str = "call", **attrs):
    """`with telemetry.trace_call("module.function") as log:` - one span per call with the common header,
    and a logger that carries it (cdh-lava-core's `with tracer.start_as_current_span(...)` pattern).
    A function called more than MAX_SPANS_PER_CALLER times under the same parent span stops making spans
    and is only counted (`function.calls`), so hot loops can't flood the ingestion allowance."""
    logger = _HeaderLogger(log, {"function": name})
    if _State.exporter == "off" or LEVELS.index(level) > _State.level:
        token = _annotatable.set(None)
        try:
            yield logger
        finally:
            _annotatable.reset(token)
        return
    parent = trace.get_current_span().get_span_context().span_id
    key = (parent, name)
    if len(_State.calls) > 50_000:
        _State.calls.clear()
    n = _State.calls[key] = _State.calls.get(key, 0) + 1
    if n > MAX_SPANS_PER_CALLER:
        _instrument("counter", "function.calls").add(1, {"code.function": name})
        token = _annotatable.set(None)
        try:
            yield logger
        except Exception as e:
            _instrument("counter", "pipeline.step.failures").add(1, {"pipeline.step": name,
                                                                      "error.type": type(e).__name__})
            raise
        finally:
            _annotatable.reset(token)
        return
    with _State.tracer.start_as_current_span(name, attributes=attrs, record_exception=False,
                                             set_status_on_exception=False) as span:
        token = _annotatable.set(span)
        try:
            yield logger
        except Exception as e:
            _record_failure(span, name, e)
            raise
        finally:
            _annotatable.reset(token)


def traced(fn):
    """Decorator form of trace_call for every public function: the body runs inside
    `with trace_call("<module>.<function>")`. The function's level comes from telemetry_levels.yaml
    (default `call`); below DENTAL_TELEMETRY_LEVEL, or with telemetry off, it is a direct call."""
    module = fn.__module__.rsplit(".", 1)[-1]
    qual = fn.__qualname__.split(".<locals>.")[-1]
    name = f"{module}.{qual}"
    level = function_levels().get(name, "call")
    rank = LEVELS.index(level)
    attrs = {"code.function": fn.__name__, "code.namespace": fn.__module__, "telemetry.level": level}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if _State.profile is not None:              # no span: nothing may annotate the caller's
            token = _annotatable.set(None)
            try:
                return _profiled(name, fn, args, kwargs)
            finally:
                _annotatable.reset(token)
        if _State.exporter == "off":
            return fn(*args, **kwargs)
        if rank > _State.level:
            token = _annotatable.set(None)
            try:
                return fn(*args, **kwargs)
            finally:
                _annotatable.reset(token)
        with trace_call(name, level, **attrs):
            return fn(*args, **kwargs)

    wrapper.__traced__ = True
    return wrapper


ROW_COUNTED: set[str] = set()   # "<module>.<function>" of each step that records its rows (spec 040 US6, #758)


def _row_count(value) -> int | None:
    """Rows in a table (a DataFrame or Series: its first dimension), or in a dict of tables (their sum). None for
    anything else, so a step that reads or writes no table records no count."""
    shape = getattr(value, "shape", None)
    if shape:
        return int(shape[0])
    if isinstance(value, dict) and value and all(getattr(v, "shape", None) for v in value.values()):
        return int(sum(v.shape[0] for v in value.values()))
    return None


def counts_rows(fn):
    """Record the rows a table step reads and writes on its own span (spec 040 US6, #758): `row_in_count` from its
    first argument, `row_out_count` from what it returns (the first item of a tuple). A filter that drops rows shows
    up only as these two numbers. Put it directly under `@traced`, so `annotate` reaches that function's span.
    `row_in_count` is written before the body runs, so a step that fails still says how many rows it was given.
    Counts only, never a row's values; with telemetry off, `annotate` writes nothing and the step is unchanged."""
    if getattr(fn, "__traced__", False):
        raise TypeError(f"put @counts_rows directly under @traced, not above it ({fn.__qualname__}): above it, the "
                        "counts would land on the caller's span")
    first = next(iter(inspect.signature(fn).parameters), None)
    module = fn.__module__.rsplit(".", 1)[-1]
    ROW_COUNTED.add(f"{module}.{fn.__qualname__.split('.<locals>.')[-1]}")

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        rows_in = _row_count(args[0] if args else kwargs.get(first))
        if rows_in is not None:
            annotate(row_in_count=rows_in)
        out = fn(*args, **kwargs)
        rows_out = _row_count(out[0] if isinstance(out, tuple) and out else out)
        if rows_out is not None:
            annotate(row_out_count=rows_out)
        return out

    return wrapper


# ---- levels: measured, kept in telemetry_levels.yaml (scripts/39_telemetry_levels.py) -------------

_LEVEL_CACHE: dict | None = None
_parent: ContextVar[int] = ContextVar("dental_traced_parent", default=0)   # id of the enclosing call
_call_ids = itertools.count(1)


def function_levels() -> dict:
    """{"module.function": level} from telemetry_levels.yaml (read once)."""
    global _LEVEL_CACHE
    if _LEVEL_CACHE is None:
        import yaml
        data = yaml.safe_load(LEVELS_FILE.read_text()) if LEVELS_FILE.exists() else {}
        _LEVEL_CACHE = {k: v["level"] for k, v in (data or {}).items()}
    return _LEVEL_CACHE


def _profiled(name, fn, args, kwargs):
    parent = _parent.get()
    token = _parent.set(next(_call_ids))
    start = time.perf_counter()
    try:
        return fn(*args, **kwargs)
    finally:
        _parent.reset(token)
        p = _State.profile
        p["time"][name] += time.perf_counter() - start
        p["calls"][(parent, name)] += 1


def _summarize(p: dict) -> dict:
    per_name: dict = defaultdict(list)
    for (_, name), n in p["calls"].items():
        per_name[name].append(n)
    return {name: {"calls": sum(c), "total_ms": 1000 * p["time"][name], "max_calls_per_parent": max(c)}
            for name, c in per_name.items()}


def merge_profiles(rows: list[dict]) -> dict:
    """Combine profiles from several processes: calls and time add up, calls per parent take the max."""
    out: dict = {}
    for row in rows:
        for name, s in row.items():
            o = out.setdefault(name, {"calls": 0, "total_ms": 0.0, "max_calls_per_parent": 0})
            o["calls"] += s["calls"]
            o["total_ms"] += s["total_ms"]
            o["max_calls_per_parent"] = max(o["max_calls_per_parent"], s["max_calls_per_parent"])
    for o in out.values():
        o["mean_ms"] = o["total_ms"] / o["calls"]
    return out


@contextmanager
def profile():
    """Count every @traced call (whatever the exporter or level): calls, time, and calls per parent call.
    Yields a dict filled when the block ends: {name: {calls, mean_ms, max_calls_per_parent}}."""
    _State.profile = {"time": defaultdict(float), "calls": defaultdict(int)}
    out: dict = {}
    try:
        yield out
    finally:
        p, _State.profile = _State.profile, None
        out.update(merge_profiles([_summarize(p)]))


def _profile_from_env() -> None:
    """DENTAL_TELEMETRY_PROFILE=<file>: profile this whole process and append its summary to the file at
    exit (scripts/39_telemetry_levels.py runs each pipeline in its own process, as CI does)."""
    path = os.environ.get("DENTAL_TELEMETRY_PROFILE")
    if not path:
        return
    _State.profile = {"time": defaultdict(float), "calls": defaultdict(int)}

    def dump():
        if _State.profile is not None:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(_summarize(_State.profile)) + "\n")

    atexit.register(dump)


def classify(stats: dict, max_calls_per_parent: int = 20, min_ms: float = 0.5) -> dict:
    """`detail` for functions called more than max_calls_per_parent times under one parent call, or cheap
    (< min_ms per call) and called that often in total: tracing them costs more than it tells. Else `call`."""
    out = {}
    for name, s in sorted(stats.items()):
        hot = s["max_calls_per_parent"] > max_calls_per_parent
        cheap = s["mean_ms"] < min_ms and s["calls"] > max_calls_per_parent
        why = f"{s['max_calls_per_parent']} calls per parent, {s['calls']} in total, {s['mean_ms']:.3f} ms per call"
        out[name] = {"level": "detail" if hot or cheap else "call", "reason": why}
    return out


def merge_levels(old: dict, new: dict) -> dict:
    """New measurements win, except entries marked `manual: true` (hand-edited) and functions this run
    didn't reach (their old level stays)."""
    merged = {**old}
    for name, v in new.items():
        if not (old.get(name) or {}).get("manual"):
            merged[name] = v
    return dict(sorted(merged.items()))


_profile_from_env()
