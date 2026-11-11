"""Pipeline telemetry with OpenTelemetry (spec 014).

One switch, `DENTAL_TELEMETRY`, picks where traces, metrics and logs go:

    off      default: nothing leaves the process (tests, CI, laptops)
    console  print spans and metrics (debugging)
    azure    Azure Application Insights through the Azure Monitor OpenTelemetry distro;
             needs APPLICATIONINSIGHTS_CONNECTION_STRING (Databricks: secret scope `health_transformation_lab`,
             key `appinsights_connection_string`). Without it: a warning, then off.
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
import itertools
import json
import logging
import os
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
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
    file = None                             # the file exporter's open file


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
            provider.shutdown()
        except Exception:  # noqa: BLE001 - stopping telemetry never fails the run
            pass
    _State.providers = []
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
    if c.exporter == "azure" and not c.connection_string:
        log.warning("DENTAL_TELEMETRY=azure but APPLICATIONINSIGHTS_CONNECTION_STRING is not set: telemetry off")
        c = TelemetryConfig(exporter="off")
    elif c.exporter == "azure" and not _looks_valid(c.connection_string):   # never log the value itself
        log.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is not a valid Application Insights connection "
                    "string (expected InstrumentationKey=...;IngestionEndpoint=...): telemetry off")
        c = TelemetryConfig(exporter="off")
    if c.exporter == "file" and not c.file_path:
        log.warning("DENTAL_TELEMETRY=file but DENTAL_TELEMETRY_FILE is not set: telemetry off")
        c = TelemetryConfig(exporter="off")
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
        _State.tracer, _State.meter = trace.get_tracer(SERVICE), metrics.get_meter(SERVICE)
    _State.exporter = c.exporter
    return out


def active_exporter() -> str:
    return _State.exporter


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


def use_databricks_secret(dbutils, exporter: str = "azure", scope: str = "health_transformation_lab",
                          key: str = "appinsights_connection_string") -> str:
    """In a Databricks notebook: put the telemetry settings in the environment, where the scripts the
    notebook starts pick them up. A missing secret turns telemetry off; it never fails the job."""
    if exporter == "azure":
        try:
            os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = _clean(dbutils.secrets.get(scope, key))
        except Exception as e:  # noqa: BLE001  dbutils raises its own exception types
            log.warning("no secret %s/%s (%s): telemetry off", scope, key, type(e).__name__)
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
        if _State.profile is not None:
            return _profiled(name, fn, args, kwargs)
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
