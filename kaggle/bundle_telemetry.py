"""Telemetry for the coding agent on a Kaggle kernel (spec 014 US6, #666), shipped as htl_agent/telemetry.py.

The package's own telemetry module can't go in the bundle: tasks change it, and a fix the agent could read beside its
task would be its answer (kaggle/agent_bundle.py). Kaggle kernels also run with internet off, on an image that may not
have the tracing SDK. So this is a small stand-in with the same calls (traced, annotate, setup, start_script,
end_script, active_exporter). It uses the standard library only, is off unless DENTAL_TELEMETRY=file and
DENTAL_TELEMETRY_FILE are set, and writes one JSON line a span in the layout the package's `file` exporter writes,
children first, so one reader handles both. A span carries numbers and short labels only (annotate), never a prompt,
a reply, a command or a patch; an error is recorded by its type, never its message.
"""
from __future__ import annotations

import functools
import json
import os
import secrets
import socket
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone

SERVICE = "health-transformation-lab-nlp"        # as the package's telemetry.SERVICE
DATA_PRODUCT = "health_transformation_lab"       # as the package's telemetry.DATA_PRODUCT
LABEL_SUFFIXES = ("_name", "_code", "_id")       # text is kept only as a short label, as the package keeps it
MAX_LABEL_CHARS = 64
MAX_SPANS_PER_CALLER = int(os.environ.get("DENTAL_TELEMETRY_MAX_CALLS", "1000"))   # a file costs nothing to ingest

_current: ContextVar = ContextVar("htl_bundle_span", default=None)   # the span annotate() writes on


class _State:
    file = None
    header: dict = {}
    resource: dict = {}
    script = None
    calls: dict = {}


def _iso(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _keep(key: str, value) -> bool:
    """Numbers and booleans; text only as a short label, a key ending _name, _code or _id."""
    if isinstance(value, (bool, int, float)):
        return True
    return isinstance(value, str) and key.endswith(LABEL_SUFFIXES) and len(value) <= MAX_LABEL_CHARS


class _Span:
    def __init__(self, name: str, attributes: dict, parent: _Span | None):
        self.name, self.parent = name, parent
        self.trace_id = parent.trace_id if parent is not None else "0x" + secrets.token_hex(16)
        self.span_id = "0x" + secrets.token_hex(8)
        self.start = time.time_ns()
        self.attributes = {**_State.header, **attributes}
        self.status = {"status_code": "UNSET"}

    def fail(self, error: BaseException) -> None:
        self.status = {"status_code": "ERROR", "description": type(error).__name__}
        self.attributes["error.type"] = type(error).__name__

    def end(self) -> None:
        if _State.file is None:
            return
        line = {"name": self.name,
                "context": {"trace_id": self.trace_id, "span_id": self.span_id, "trace_state": "[]"},
                "kind": "SpanKind.INTERNAL", "parent_id": self.parent.span_id if self.parent is not None else None,
                "start_time": _iso(self.start), "end_time": _iso(time.time_ns()), "status": self.status,
                "attributes": self.attributes, "events": [], "links": [],
                "resource": {"attributes": _State.resource, "schema_url": ""}}
        _State.file.write(json.dumps(line, default=str) + "\n")
        _State.file.flush()                       # a kernel that dies keeps every span that ended


def setup() -> None:
    """From the environment, as the package's setup() does: DENTAL_TELEMETRY=file and DENTAL_TELEMETRY_FILE, else off."""
    end_script()
    if _State.file is not None:
        _State.file.close()
        _State.file = None
    _State.calls = {}
    if os.environ.get("DENTAL_TELEMETRY", "off").strip().lower() != "file":
        return
    path = os.environ.get("DENTAL_TELEMETRY_FILE", "").strip()
    if not path:
        print("DENTAL_TELEMETRY=file but DENTAL_TELEMETRY_FILE is not set: telemetry off", file=sys.stderr)
        return
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    _State.file = open(path, "w", encoding="utf-8")       # one file a run: a rerun replaces it, never appends
    environment = os.environ.get("DENTAL_ENVIRONMENT", "dev")
    product = os.environ.get("DENTAL_DATA_PRODUCT_ID", DATA_PRODUCT)
    _State.header = {"data_product_id": product, "environment": environment, "service.namespace": SERVICE}
    _State.resource = {"service.name": product, "service.namespace": SERVICE,
                       "service.instance.id": socket.gethostname(), "deployment.environment": environment}


def active_exporter() -> str:
    return "file" if _State.file is not None else "off"


def annotate(**attrs) -> None:
    """Numbers and short labels on the span of the function this is called from; nothing when it made no span."""
    span = _current.get()
    if span is None or _State.file is None:
        return
    span.attributes.update({k: v for k, v in attrs.items() if _keep(k, v)})


def traced(fn):
    """One span a call, named <module>.<function> as the package names it."""
    module = fn.__module__.rsplit(".", 1)[-1]
    name = f"{module}.{fn.__qualname__.split('.<locals>.')[-1]}"
    attrs = {"code.function": fn.__name__, "code.namespace": fn.__module__, "telemetry.level": "call"}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if _State.file is None:
            return fn(*args, **kwargs)
        parent = _current.get()
        key = (parent.span_id if parent is not None else None, name)
        n = _State.calls[key] = _State.calls.get(key, 0) + 1
        if n > MAX_SPANS_PER_CALLER:
            token = _current.set(None)
            try:
                return fn(*args, **kwargs)
            finally:
                _current.reset(token)
        span = _Span(name, dict(attrs), parent)
        token = _current.set(span)
        try:
            return fn(*args, **kwargs)
        except BaseException as e:
            span.fail(e)
            raise
        finally:
            _current.reset(token)
            span.end()

    wrapper.__traced__ = True
    return wrapper


def start_script(name: str, **attrs) -> None:
    """The run's span, which every traced call nests under until end_script()."""
    end_script()
    if _State.file is None:
        return
    span = _Span(name, {"pipeline.step": name, "pipeline.kind": "script",
                        **{k: v for k, v in attrs.items() if _keep(k, v)}}, None)
    _State.script = (span, _current.set(span))


def end_script() -> None:
    """End the run's span (idempotent)."""
    if _State.script is None:
        return
    span, token = _State.script
    _State.script = None
    try:
        _current.reset(token)
    except ValueError:                    # ended from another context: nothing to put back there
        _current.set(None)
    span.end()
