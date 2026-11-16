"""Send a finished development run's results to Application Insights (014 US8, #830).

A Modal, Colab or Kaggle run writes its per-task results (and, when built with --telemetry, the agent's spans in
telemetry.jsonl) into a private Kaggle results dataset. Agent sessions hold no secrets, so this runs in a GitHub
workflow with the dev environment's connection string ("Forward a development run's telemetry to Azure"):

    python kaggle/forward_run_telemetry.py <downloaded results dir> --label devset-m31b-d2 --platform modal

One run span `run_forward` (label, platform, task count) holds one `agent_task` span per task: instance id, agent
seconds, tool calls, whether a patch was made, whether it was resolved, and the error kind. Never task text or a
patch. telemetry.jsonl, when present, is forwarded too (telemetry.forward_spans). Off unless DENTAL_TELEMETRY is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
    a = ap.parse_args(argv)
    results = sorted(a.results_dir.rglob("tasks/*/result.json"))
    if not results:
        sys.exit(f"no tasks/*/result.json under {a.results_dir}: is this a run's results dataset?")
    telemetry.setup()                                  # DENTAL_TELEMETRY; off by default
    with telemetry.pipeline_step("run_forward", run_label=a.label, platform_name=a.platform,
                                 task_count=len(results)):
        for path in results:
            with telemetry.pipeline_step("agent_task", run_label=a.label, platform_name=a.platform,
                                         **task_attrs(json.loads(path.read_text()), path.parent.name)):
                pass
    forwarded = sum(telemetry.forward_spans(p) for p in sorted(a.results_dir.rglob("telemetry.jsonl")))
    print(f"{a.label} ({a.platform}): {len(results)} tasks, {forwarded} agent spans forwarded; "
          f"telemetry {telemetry.active_exporter()}")
    _report(telemetry.flush())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
