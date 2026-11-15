"""A coding-agent task statement written from a failing run's telemetry (spec 040 US1, #753).

One writer for every condition and both task sets, so the conditions differ only in what they include:

- `symptom`: the step's name and what a person would see without telemetry: it stopped with an error, or it
  finished but its output looks wrong.
- `span_names`: `symptom`, plus the function that failed, the data label, its rows in and out (spec 040 US6) and the
  error type. When nothing failed, the rows in and out of each step that counts them.
- `span_names_message`: `span_names`, plus the failing span's error message, masked: everything after its first
  `": "` (where Python and pandas print the value at fault, quoted or not), then every quoted value, path, file name
  and number in what is left, cut to 240 characters. A message that embeds a traceback is left out.

It reads the span file a run writes under `DENTAL_TELEMETRY=file` (one OpenTelemetry span a line, the SDK's own
JSON) and uses only each span's `name`, `parent_id`, `start_time`, `status` and the attributes `pipeline.step`,
`pipeline.kind`, `data.label`, `error.type`, `row_in_count` and `row_out_count`. Never an exception event: its stack
trace carries paths and source lines. The same spans, in any order, give the same text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .telemetry import traced

CONDITIONS = ("symptom", "span_names", "span_names_message")
MAX_MESSAGE_CHARS = 240                  # as 69_failure_report.py cuts an error line
MAX_COUNTED_STEPS = 10                   # a run that did not fail: at most this many counted steps are named

_TRACEBACK = "Traceback (most recent call last)"
# A quoted value: an apostrophe inside a word is text; a quote left open, as a cut message leaves it, runs
# to the end.
_QUOTED = re.compile(r"(?<!\w)'.*?(?:'(?!\w)|$)|\"[^\"]*(?:\"|$)")
_PATH = re.compile(r"[\w.~:\-]*[\\/][\w.~\\/\-]*")
_FILE = re.compile(r"\b[\w\-]+\.[A-Za-z][A-Za-z0-9]{0,4}\b")           # a bare file name, any short extension
_NUMBER = re.compile(r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")                 # also inside an identifier: V3437


@traced
def read_spans(path: Path) -> list[dict]:
    """The spans in a span file, oldest first. Lines that are not spans (the file exporter's metrics batches) are
    skipped."""
    spans = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line) if line.strip() else None
        except json.JSONDecodeError:              # a run killed mid-write leaves a cut-off last line
            continue
        if isinstance(item, dict) and "context" in item:
            spans.append(item)
    return _ordered(spans)


@traced
def write_statement(spans: list[dict], condition: str) -> str:
    """The task statement for one condition (`CONDITIONS`), from one failing run's spans."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown statement condition {condition!r}; expected one of {', '.join(CONDITIONS)}")
    if not spans:
        raise ValueError("no spans: a statement needs the spans of one run")
    spans = _ordered(spans)
    failed = _innermost_failure(spans)
    step = _step_name(spans, failed)
    lines = [f"The {step} step stopped with an error." if failed
             else f"The {step} step finished, but its output looks wrong."]
    if condition == "symptom":
        return lines[0]

    label = next((_attrs(s)["data.label"] for s in spans if _attrs(s).get("data.label")), None)
    if failed:
        attrs = _attrs(failed)
        lines.append(f"It failed in {failed['name']}.")
        if label:
            lines.append(f"Data label: {label}.")
        for key, words in (("row_in_count", "Rows in"), ("row_out_count", "Rows out")):
            if isinstance(attrs.get(key), int):
                lines.append(f"{words}: {attrs[key]}.")
        if attrs.get("error.type"):
            lines.append(f"Error type: {attrs['error.type']}.")
    else:
        if label:
            lines.append(f"Data label: {label}.")
        counted = [s for s in spans if _counts(s)][:MAX_COUNTED_STEPS]
        lines += [f"{s['name']}: {_counts(s)}." for s in counted]
    if condition == "span_names_message" and failed:
        message = _mask((failed.get("status") or {}).get("description") or "")
        if message:
            lines.append(f"Error message: {message}")
    return "\n".join(lines)


def _attrs(span: dict) -> dict:
    return span.get("attributes") or {}


def _ordered(spans: list[dict]) -> list[dict]:
    return sorted(spans, key=lambda s: (s.get("start_time") or "", s.get("name") or "",
                                        (s.get("context") or {}).get("span_id") or ""))


def _id(span: dict) -> str | None:
    return (span.get("context") or {}).get("span_id")


def _failed(span: dict) -> bool:
    return (span.get("status") or {}).get("status_code") == "ERROR"


def _last_ended(spans: list[dict]) -> dict:
    return max(spans, key=lambda s: (s.get("end_time") or "", s.get("start_time") or "", _id(s) or ""))


def _innermost_failure(spans: list[dict]) -> dict | None:
    """Where the exception that ended the run was raised. An exception marks every span it passes through, so follow
    the failed spans down from the outermost, taking at each level the failed child that ended last: a failure the
    code caught ends before the one that got through. None when no span failed."""
    by_id = {_id(s): s for s in spans}
    failures = [s for s in spans if _failed(s)]
    if not failures:
        return None
    top = [s for s in failures if not _failed(by_id.get(s.get("parent_id"), {}))]
    here, seen = _last_ended(top or failures), set()
    while _id(here) not in seen:
        seen.add(_id(here))
        children = [s for s in failures if s.get("parent_id") == _id(here) and s is not here]
        if not children:
            break
        here = _last_ended(children)
    return here


def _step_name(spans: list[dict], failed: dict | None) -> str:
    """The run's step: a script's run span (#712); else the pipeline step around the failure (the failing span or its
    nearest ancestor that names one), or the first named step when nothing failed; else the outermost span around the
    failure, which stands for the step in runs older than the run spans."""
    for s in spans:
        if _attrs(s).get("pipeline.step") and _attrs(s).get("pipeline.kind") == "script":
            return _attrs(s)["pipeline.step"]
    by_id = {_id(s): s for s in spans}
    chain, here, seen = [], failed, set()
    while here is not None and _id(here) not in seen:
        seen.add(_id(here))
        chain.append(here)
        here = by_id.get(here.get("parent_id"))
    for s in chain or spans:
        if _attrs(s).get("pipeline.step"):
            return _attrs(s)["pipeline.step"]
    if chain:
        return chain[-1]["name"]
    roots = [s for s in spans if not s.get("parent_id") or s.get("parent_id") not in by_id]
    return (roots or spans)[0]["name"]


def _counts(span: dict) -> str:
    attrs = _attrs(span)
    parts = [f"{words} {attrs[key]}" for key, words in (("row_in_count", "rows in"), ("row_out_count", "rows out"))
             if isinstance(attrs.get(key), int)]
    return ", ".join(parts)


def _mask(message: str) -> str | None:
    """The error message masked, or None when there is nothing safe to give. Everything after the first ": " is the
    value at fault (Python and pandas print it there, quoted or not); then quoted values, paths, bare file names and
    numbers in what is left. Cut to MAX_MESSAGE_CHARS. A message that embeds a traceback carries source lines and is
    left out."""
    text = " ".join(message.split())
    if not text or _TRACEBACK in text:
        return None
    head, colon, _ = text.partition(": ")
    text = head + (": <value>" if colon else "")
    text = _QUOTED.sub("<value>", text)
    text = _PATH.sub("<path>", text)
    text = _FILE.sub("<path>", text)
    text = _NUMBER.sub("<n>", text)
    return text[:MAX_MESSAGE_CHARS]
