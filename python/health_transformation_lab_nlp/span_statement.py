"""A coding-agent task statement written from a failing run's telemetry (spec 040 US1, #753).

One writer for every condition and both task sets, so the conditions differ only in what they include:

- `symptom`: the step's name and what a person would see without telemetry: it stopped with an error, or it
  finished but its output looks wrong.
- `span_names`: `symptom`, plus the function that failed, the data label, its rows in and out (spec 040 US6) and the
  error type. When nothing failed, the rows in and out of each step that counts them.
- `span_names_message`: `span_names`, plus the failing span's error message with every quoted value, path, file name
  and number masked, cut to 240 characters.

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

_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_PATH = re.compile(r"[\w.~:\-]*[\\/][\w.~\\/\-]*")
_FILE = re.compile(r"\b[\w\-]+\.(?:csv|tsv|py|json|jsonl|parquet|txt|ya?ml|xpt|md|ipynb|sql|r|zip|gz)\b", re.IGNORECASE)
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")


@traced
def read_spans(path: Path) -> list[dict]:
    """The spans in a span file, oldest first. Lines that are not spans (the file exporter's metrics batches) are
    skipped."""
    spans = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
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
    step = _step_name(spans)
    lines = [f"The {step} step stopped with an error." if failed
             else f"The {step} step finished, but its output looks wrong."]
    if condition == "symptom":
        return lines[0]

    label = next((s["attributes"]["data.label"] for s in spans if s.get("attributes", {}).get("data.label")), None)
    if failed:
        attrs = failed.get("attributes", {})
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
        message = (failed.get("status") or {}).get("description")
        if message:
            lines.append(f"Error message: {_mask(message)}")
    return "\n".join(lines)


def _ordered(spans: list[dict]) -> list[dict]:
    return sorted(spans, key=lambda s: (s.get("start_time") or "", s.get("name") or "",
                                        (s.get("context") or {}).get("span_id") or ""))


def _failed(span: dict) -> bool:
    return (span.get("status") or {}).get("status_code") == "ERROR"


def _depth(span: dict, parents: dict) -> int:
    depth, seen, parent = 0, set(), span.get("parent_id")
    while parent in parents and parent not in seen:
        seen.add(parent)
        depth += 1
        parent = parents[parent]
    return depth


def _innermost_failure(spans: list[dict]) -> dict | None:
    """The deepest span with status ERROR: an exception marks every span it passes through, so the deepest is where
    it was raised. Ties go to the one that started first."""
    parents = {(s.get("context") or {}).get("span_id"): s.get("parent_id") for s in spans}
    failures = [s for s in spans if _failed(s)]
    if not failures:
        return None
    deepest = max(_depth(s, parents) for s in failures)
    return next(s for s in failures if _depth(s, parents) == deepest)


def _step_name(spans: list[dict]) -> str:
    """The run's step: a script's run span (#712), else any span naming a pipeline step, else the outermost span,
    which stands for the step in runs older than the run spans."""
    for kind in ("script", None):
        for s in spans:
            attrs = s.get("attributes") or {}
            if attrs.get("pipeline.step") and (kind is None or attrs.get("pipeline.kind") == kind):
                return attrs["pipeline.step"]
    roots = [s for s in spans if not s.get("parent_id")]
    return (roots or spans)[0]["name"]


def _counts(span: dict) -> str:
    attrs = span.get("attributes") or {}
    parts = [f"{words} {attrs[key]}" for key, words in (("row_in_count", "rows in"), ("row_out_count", "rows out"))
             if isinstance(attrs.get(key), int)]
    return ", ".join(parts)


def _mask(message: str) -> str:
    """The error message with quoted values, paths, file names and numbers masked, cut to MAX_MESSAGE_CHARS."""
    text = _QUOTED.sub("<value>", " ".join(message.split()))
    text = _PATH.sub("<path>", text)
    text = _FILE.sub("<path>", text)
    text = _NUMBER.sub("<n>", text)
    return text[:MAX_MESSAGE_CHARS]
