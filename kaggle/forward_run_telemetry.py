"""Send a finished development run's results to Application Insights (014 US8, #830).

A Modal, Colab or Kaggle run writes its per-task results (and, when built with --telemetry, the agent's spans in
telemetry.jsonl) into a private Kaggle results dataset. Agent sessions hold no secrets, so this runs in a GitHub
workflow with the dev environment's connection string ("Forward a development run's telemetry to Azure"):

    python kaggle/forward_run_telemetry.py <downloaded results dir> --label devset-m31b-d2 --platform modal

One run span `run_forward` (label, platform, task count) holds one `agent_task` span per task: instance id, agent
seconds, tool calls, whether a patch was made, whether it was resolved, and the error kind. Never task text or a
patch. telemetry.jsonl, when present, is forwarded too (telemetry.forward_spans). Off unless DENTAL_TELEMETRY is set.

With DENTAL_TELEMETRY_CONTENT=full, or --content full (014 US9, #850, ADR 0010), the run's own content goes too, so a
failed task can be read in Application Insights without a download: `agent_task` gains the patch and the agent's error
text, and each step of the task's trace (tasks/<id>/results/traces/*.json) is an `agent_step` span under it with the
step's message, its tool calls' names and arguments, the tool's output, the token counts and the times. Every text is
scrubbed of secrets, and a text longer than one property is continued in `agent_step_part` spans
(telemetry.content_span). Every span of one call carries the same `forward_id`: a run forwarded twice appends.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

from health_transformation_lab_nlp import telemetry


def _error_code(error) -> str:
    text = "" if error in (None, "None") else str(error).lower()
    if not text:
        return "none"
    return "timeout" if "timeout" in text else "other"


def _number(value, kind=float):
    """A count or a duration as a number; anything that isn't one is 0, so text in a numeric field never reaches an
    exception's message, a span's status or the workflow's public log."""
    try:
        number = kind(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return kind(0)
    return number if number == number and abs(number) != float("inf") else kind(0)


def _error(result: dict):
    """What stopped the task: the agent's own error, or the kernel's when the task failed outside the agent."""
    return result.get("agent_error") or result.get("error_text") or result.get("error")


def task_attrs(result: dict, instance_id: str) -> dict:
    """The attributes of one task's span: numbers and short labels only."""
    verification = result.get("verification") or {}
    return {"instance_id": instance_id,
            "agent_seconds": _number(result.get("agent_phase_seconds")),
            "tool_call_count": _number(result.get("tool_call_count"), int),
            "is_patch_made": bool(str(result.get("patch") or "").strip()),
            "is_resolved": bool(isinstance(verification, dict) and verification.get("is_resolved")),
            "agent_error_code": _error_code(_error(result))}


def _text(value) -> str:
    """Any value of a trace as text for a span. What is JSON (a tool call's arguments, a tool's output written as a
    JSON string) is scrubbed leaf by leaf before it is written out again: a secret between quotes is seen as it was
    typed, not behind JSON's escapes (telemetry.scrub_value). content_span scrubs the text once more."""
    if value in (None, "None"):
        return ""
    if isinstance(value, str):
        if value[:1] not in "{[":
            return value
        try:
            value = json.loads(value)
        except ValueError:
            return value
    return json.dumps(telemetry.scrub_value(value), ensure_ascii=False)


def step_attrs(step: dict, instance_id: str) -> dict:
    """The attributes of one trace step's span (full content only): what the model said, what it called, with what
    arguments, what came back, and what it cost."""
    calls = [c for c in step.get("tool_calls") or [] if isinstance(c, dict)]
    arguments = [c.get("arguments") for c in calls]
    observation = step.get("observation")
    metrics, extra = step.get("metrics") or {}, step.get("extra") or {}
    metrics, extra = (metrics if isinstance(metrics, dict) else {}), (extra if isinstance(extra, dict) else {})
    return {"instance_id": instance_id,
            "step_num": _number(step.get("step_id"), int),
            "source_name": str(step.get("source") or ""),
            "event_type_name": str(extra.get("event_type") or ""),
            "message_text": _text(step.get("message")),
            "tool_name": ", ".join(str(c.get("function_name") or "") for c in calls),
            "tool_call_count": len(calls),
            "arguments_text": _text(arguments[0] if len(arguments) == 1 else arguments) if calls else "",
            "output_text": _text(observation.get("content") if isinstance(observation, dict) else observation),
            "prompt_token_count": _number(metrics.get("prompt_tokens"), int),
            "completion_token_count": _number(metrics.get("completion_tokens"), int),
            "cached_token_count": _number(metrics.get("cached_tokens"), int),
            "elapsed_seconds": _number(extra.get("elapsed_s"))}


def _ns(unix_seconds) -> int | None:
    seconds = _number(unix_seconds)
    return round(seconds * 1_000_000) * 1000 if seconds > 0 else None   # whole microseconds, as the span files keep


def _step_times(step: dict, fallback_ns: int) -> tuple[int, int]:
    """A step starts when the model answered and ends when its tool came back (or at once, without a tool)."""
    extra, observation = step.get("extra"), step.get("observation")
    start = _ns(extra.get("timestamp") if isinstance(extra, dict) else None) or fallback_ns
    ended = (observation.get("extra") or {}) if isinstance(observation, dict) else {}
    end = _ns(ended.get("timestamp") if isinstance(ended, dict) else None) or start
    return start, max(start, end)


def _steps(task_dir: Path) -> list[dict]:
    """Every step of the task's trace files, in order; a file that isn't a trace is said and left out."""
    steps = []
    for trace_path in sorted(task_dir.glob("results/traces/*.json")):
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8", errors="replace"))
            found = trace.get("steps") if isinstance(trace, dict) else None
        except ValueError:
            found = None
        if not isinstance(found, list):
            print(f"{task_dir.name}: {trace_path.name} holds no steps (a run cut off while writing it?): none sent")
            continue
        steps += [s for s in found if isinstance(s, dict)]
    return steps


def send_task_content(run_span, result: dict, task_dir: Path, common: dict) -> tuple[int, bool]:
    """One task in full: its `agent_task` span with the patch and the error text, and one `agent_step` span per step
    of its trace under it. The task's times are the kernel's; without them, its first and last step's; without those,
    now. Returns the number of steps sent and whether the queue was sent on."""
    steps = _steps(task_dir)
    times = [t for step in steps for t in _step_times(step, 0) if t]
    start = _ns(result.get("started_unix")) or (min(times) if times else time.time_ns())
    end = max(start, _ns(result.get("ended_unix")) or (max(times) if times else start))
    task = telemetry.content_span("agent_task", start, end, parent=run_span, **common,
                                  **task_attrs(result, task_dir.name), patch_text=_text(result.get("patch")),
                                  agent_error_text=_text(_error(result)))
    sent = 0
    for step in steps:
        step_start, step_end = _step_times(step, start)
        span = telemetry.content_span("agent_step", step_start, step_end, parent=task, **common,
                                      **step_attrs(step, task_dir.name))
        sent += span is not None        # nothing is sent with the exporter off
    return sent, telemetry.flush()      # the batch processor keeps 2,048 spans; a whole run in full is more


def _report(ok: bool) -> None:
    if telemetry.active_exporter() == "off":
        return
    if ok:
        print("telemetry export: ok")
        return
    line = "telemetry export: FAILED (the spans did not reach the backend; the exporter's warnings are above)"
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning title=telemetry export::{line}")
    print(line, file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results_dir", type=Path)
    ap.add_argument("--label", required=True, help="the run's label, e.g. devset-m31b-d2")
    ap.add_argument("--platform", required=True, choices=("modal", "colab", "kaggle"))
    ap.add_argument("--content", choices=telemetry.CONTENT_LEVELS,
                    help=f"labels: numbers and short labels only; full: each step's text too, secrets taken out "
                         f"(default: {telemetry.CONTENT_SETTING}, else labels)")
    a = ap.parse_args(argv)
    before = os.environ.get(telemetry.CONTENT_SETTING)
    if a.content:
        os.environ[telemetry.CONTENT_SETTING] = a.content   # content_span reads the setting; put back below
    try:
        return _forward(a)
    finally:
        if a.content:
            os.environ.pop(telemetry.CONTENT_SETTING, None)
            if before is not None:
                os.environ[telemetry.CONTENT_SETTING] = before


def _forward(a) -> int:
    content = telemetry.content_level()                # a value that is neither stops here, before any work
    results = sorted(a.results_dir.rglob("tasks/*/result.json"))
    if not results:
        sys.exit(f"no tasks/*/result.json under {a.results_dir}: is this a run's results dataset?")
    telemetry.setup()                                  # DENTAL_TELEMETRY; off by default
    common = {"run_label": a.label, "platform_name": a.platform, "forward_id": uuid.uuid4().hex[:12]}
    steps, skipped, sent_on = 0, [], True
    with telemetry.pipeline_step("run_forward", **common, task_count=len(results),
                                 content_level_name=content) as run_span:
        for path in results:
            try:                                       # one odd file costs its own task, not the rest of the run
                result = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                if not isinstance(result, dict):
                    raise ValueError("result.json is not an object")
                if content == "full":
                    count, ok = send_task_content(run_span, result, path.parent, common)
                    steps, sent_on = steps + count, sent_on and ok
                else:
                    with telemetry.pipeline_step("agent_task", **common, **task_attrs(result, path.parent.name)):
                        pass
            except Exception as e:  # noqa: BLE001 - the kind is said, never the message: it can quote the file
                skipped.append(path.parent.name)
                print(f"{path.parent.name}: skipped ({type(e).__name__})")
    forwarded = sum(telemetry.forward_spans(p, extra=common) for p in sorted(a.results_dir.rglob("telemetry.jsonl")))
    print(f"{a.label} ({a.platform}): {len(results) - len(skipped)} of {len(results)} tasks, {forwarded} agent spans "
          f"forwarded; content {content}{f', {steps} steps in full' if content == 'full' else ''}; "
          f"telemetry {telemetry.active_exporter()}")
    if skipped and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning title=tasks skipped::{len(skipped)} task(s) could not be read: {', '.join(skipped[:20])}")
    _report(telemetry.flush() and sent_on)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
