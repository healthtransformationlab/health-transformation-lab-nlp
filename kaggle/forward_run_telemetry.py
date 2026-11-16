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


def task_attrs(result: dict, instance_id: str) -> dict:
    """The attributes of one task's span: numbers and short labels only."""
    verification = result.get("verification") or {}
    return {"instance_id": instance_id,
            "agent_seconds": float(result.get("agent_phase_seconds") or 0),
            "tool_call_count": int(result.get("tool_call_count") or 0),
            "is_patch_made": bool((result.get("patch") or "").strip()),
            "is_resolved": bool(isinstance(verification, dict) and verification.get("is_resolved")),
            "agent_error_code": _error_code(result.get("agent_error"))}


def _text(value) -> str:
    if value in (None, "None"):
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def step_attrs(step: dict, instance_id: str) -> dict:
    """The attributes of one trace step's span (full content only): what the model said, what it called, with what
    arguments, what came back, and what it cost."""
    calls = step.get("tool_calls") or []
    arguments = [c.get("arguments") for c in calls]
    metrics, extra = step.get("metrics") or {}, step.get("extra") or {}
    return {"instance_id": instance_id,
            "step_num": int(step.get("step_id") or 0),
            "source_name": str(step.get("source") or ""),
            "event_type_name": str(extra.get("event_type") or ""),
            "message_text": _text(step.get("message")),
            "tool_name": ", ".join(str(c.get("function_name") or "") for c in calls),
            "tool_call_count": len(calls),
            "arguments_text": _text(arguments[0] if len(arguments) == 1 else arguments) if calls else "",
            "output_text": _text((step.get("observation") or {}).get("content")),
            "prompt_token_count": int(metrics.get("prompt_tokens") or 0),
            "completion_token_count": int(metrics.get("completion_tokens") or 0),
            "cached_token_count": int(metrics.get("cached_tokens") or 0),
            "elapsed_seconds": float(extra.get("elapsed_s") or 0)}


def _ns(unix_seconds) -> int | None:
    try:
        return round(float(unix_seconds) * 1_000_000) * 1000 or None   # whole microseconds, as the span files keep
    except (TypeError, ValueError):
        return None


def _step_times(step: dict, fallback_ns: int) -> tuple[int, int]:
    """A step starts when the model answered and ends when its tool came back (or at once, without a tool)."""
    start = _ns((step.get("extra") or {}).get("timestamp")) or fallback_ns
    end = _ns(((step.get("observation") or {}).get("extra") or {}).get("timestamp")) or start
    return start, max(start, end)


def send_task_content(run_span, result: dict, task_dir: Path, common: dict) -> int:
    """One task in full: its `agent_task` span with the patch and the error text, and one `agent_step` span per step
    of each trace file under it. Returns the number of steps sent."""
    now = time.time_ns()
    start = _ns(result.get("started_unix")) or now
    end = max(start, _ns(result.get("ended_unix")) or start)
    task = telemetry.content_span("agent_task", start, end, parent=run_span, **common,
                                  **task_attrs(result, task_dir.name), patch_text=_text(result.get("patch")),
                                  agent_error_text=_text(result.get("agent_error")))
    sent = 0
    for trace_path in sorted(task_dir.glob("results/traces/*.json")):
        try:
            steps = json.loads(trace_path.read_text(encoding="utf-8", errors="replace")).get("steps") or []
        except ValueError:
            print(f"{task_dir.name}: {trace_path.name} is not JSON (a run cut off while writing it?): no steps sent")
            continue
        for step in steps:
            step_start, step_end = _step_times(step, start)
            telemetry.content_span("agent_step", step_start, step_end, parent=task, **common,
                                   **step_attrs(step, task_dir.name))
            sent += 1
    telemetry.flush()   # the batch processor keeps 2,048 spans; a whole run in full is more
    return sent


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
    if a.content:
        os.environ[telemetry.CONTENT_SETTING] = a.content
    content = telemetry.content_level()                # a value that is neither stops here, before any work
    results = sorted(a.results_dir.rglob("tasks/*/result.json"))
    if not results:
        sys.exit(f"no tasks/*/result.json under {a.results_dir}: is this a run's results dataset?")
    telemetry.setup()                                  # DENTAL_TELEMETRY; off by default
    common = {"run_label": a.label, "platform_name": a.platform, "forward_id": uuid.uuid4().hex[:12]}
    steps = 0
    with telemetry.pipeline_step("run_forward", **common, task_count=len(results),
                                 content_level_name=content) as run_span:
        for path in results:
            result = json.loads(path.read_text())
            if content == "full":
                steps += send_task_content(run_span, result, path.parent, common)
            else:
                with telemetry.pipeline_step("agent_task", **common, **task_attrs(result, path.parent.name)):
                    pass
    forwarded = sum(telemetry.forward_spans(p) for p in sorted(a.results_dir.rglob("telemetry.jsonl")))
    print(f"{a.label} ({a.platform}): {len(results)} tasks, {forwarded} agent spans forwarded; content {content}"
          f"{f', {steps} steps in full' if content == 'full' else ''}; telemetry {telemetry.active_exporter()}")
    _report(telemetry.flush())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
