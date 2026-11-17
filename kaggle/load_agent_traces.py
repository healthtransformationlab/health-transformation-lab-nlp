"""Load a finished coding-agent run into the Unity Catalog trace experiment (spec 041 US2, #857).

A Modal, Colab or Kaggle run leaves one folder per task (tasks/<id>/result.json and results/traces/*.json), the same
files kaggle/forward_run_telemetry.py sends to Azure. This writes one MLflow trace per task-run into the experiment
the bundle declares (databricks/resources/agent_traces.yml), whose traces are stored in
health_transformation_lab.ops_agent_trace:

    python kaggle/load_agent_traces.py <runs folder> --label devset-m31be-c1 --agent "ours 31B-e" --model gemma-4-31b

The trace's shape is plan.md's "What a trace looks like". MLflow groups its charts by span name, type, status and model:
- the root span (AGENT) is the task: the issue in; the outcome, the patch and the error out; OK when resolved;
- each model turn is an LLM span named "model turn": its message, its token use (mlflow.chat.tokenUsage), the model;
- each tool call is a TOOL span under its turn, named by the tool alone (read_file, edit_file, run_command, ...), ERROR
  when the tool reported an error (a failed edit), so the Tool calls tab counts calls and errors per tool.
A turn runs from the end of the previous step to when the model answered; its tool call from there to when the tool's
output came back.

Every text is scrubbed of secrets first (telemetry.scrub_value, ADR 0010). Every trace carries the tag trace_key, the
SHA-256 of run label, agent and task: a key already in the experiment is skipped, so loading a run twice writes it
once. Settings: DATABRICKS_HOST and DATABRICKS_TOKEN (the workspace), AGENT_TRACE_EXPERIMENT (default
/Shared/coding-agent-runs, the same in every environment; docs/telemetry.md).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forward_run_telemetry import _error, _error_code, _ns, _number, _steps   # read a run as the Azure forwarder does

from health_transformation_lab_nlp import telemetry

DEFAULT_EXPERIMENT = "/Shared/coding-agent-runs"   # databricks/resources/agent_traces.yml (a test holds them equal)
LABEL = re.compile(r"^[\w.-]+$")


def trace_key(run_label: str, agent_name: str, instance_id: str) -> str:
    return hashlib.sha256(f"{run_label}|{agent_name}|{instance_id}".encode()).hexdigest()


def _clean(value):
    """A trace value as MLflow will show it, scrubbed: JSON or a Python literal (how tool arguments are written) as a
    structure scrubbed leaf by leaf, anything else as scrubbed text."""
    if value in (None, "None"):
        return None
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in "{[":
            for parse in (json.loads, ast.literal_eval):
                try:
                    return telemetry.scrub_value(parse(text))
                except (ValueError, SyntaxError, MemoryError, RecursionError):
                    continue
        return telemetry.scrub(value)
    return telemetry.scrub_value(value)


def _when(step_or_obs) -> int | None:
    extra = step_or_obs.get("extra") if isinstance(step_or_obs, dict) else None
    if isinstance(extra, str):
        try:
            extra = ast.literal_eval(extra)
        except (ValueError, SyntaxError):
            extra = None
    return _ns(extra.get("timestamp")) if isinstance(extra, dict) else None


def _tool_name(obs) -> str:
    extra = obs.get("extra") if isinstance(obs, dict) else None
    return str(extra.get("tool_name") or "") if isinstance(extra, dict) else ""


def _is_tool_error(output) -> bool:
    return isinstance(output, dict) and output.get("status") == "error"


def _ended_code(result: dict) -> str:
    code = _error_code(_error(result))
    if code == "timeout":
        return "time_cap"
    if code != "none":
        return "error"
    budgets = result.get("budgets") if isinstance(result.get("budgets"), dict) else {}
    cap = _number(budgets.get("max_tool_calls"), int)
    return "call_cap" if cap and _number(result.get("tool_call_count"), int) >= cap else "ended_itself"


def _turns(steps: list[dict], start_ns: int, model_name: str | None) -> list[dict]:
    """One dict per model turn, each with its tool calls. A call's output is the turn's own observation or, for the
    second call on, the system step that follows the turn with that tool's name."""
    turns, prev = [], start_ns
    for i, step in enumerate(steps):
        if step.get("source") != "agent":
            if not isinstance(step.get("observation"), dict):          # the system prompt and the issue
                prev = max(prev, _when(step) or prev)
            continue
        answered = max(prev, _when(step) or prev)
        outputs = [step["observation"]] if isinstance(step.get("observation"), dict) else []
        for later in steps[i + 1:]:
            if later.get("source") == "agent":
                break
            if isinstance(later.get("observation"), dict):
                outputs.append(later["observation"])
        metrics = step.get("metrics") if isinstance(step.get("metrics"), dict) else {}
        num = _number(step.get("step_id"), int)
        attrs = {"step_num": num, "cached_token_count": _number(metrics.get("cached_tokens"), int)}
        if metrics:
            attrs["mlflow.chat.tokenUsage"] = {"input_tokens": _number(metrics.get("prompt_tokens"), int),
                                               "output_tokens": _number(metrics.get("completion_tokens"), int),
                                               "total_tokens": _number(metrics.get("total_tokens"), int)}
        if model_name:
            attrs["mlflow.llm.model"] = model_name
        tools, end = [], answered
        for call in [c for c in step.get("tool_calls") or [] if isinstance(c, dict)]:
            name = str(call.get("function_name") or "tool")
            match = next((o for o in outputs if _tool_name(o) == name), outputs[0] if outputs else None)
            if match is not None:
                outputs.remove(match)
            output = _clean(match.get("content")) if match else None
            came_back = max(answered, _when(match) or answered) if match else answered
            tools.append({"name": name, "inputs": _clean(call.get("arguments")), "outputs": output,
                          "attributes": {"step_num": num}, "is_ok": not _is_tool_error(output),
                          "start_ns": answered, "end_ns": came_back})
            end = max(end, came_back)
        turns.append({"name": "model turn", "inputs": None, "outputs": {"message": _clean(step.get("message"))},
                      "attributes": attrs, "start_ns": prev, "end_ns": answered, "tools": tools})
        prev = end
    return turns


def task_trace(task_dir: Path, run_label: str, agent_name: str, model_name: str | None = None) -> dict:
    """The trace of one task-run as plain data: {"tags", "root", "steps"}. Pure: reads the folder, writes nothing."""
    result = json.loads((task_dir / "result.json").read_text(encoding="utf-8", errors="replace"))
    if not isinstance(result, dict):
        raise ValueError("result.json is not an object")
    iid = task_dir.name
    steps = _steps(task_dir)
    stamps = [t for s in steps for t in (_when(s), _when(s.get("observation"))) if t]
    start = _ns(result.get("started_unix")) or (min(stamps) if stamps else time.time_ns())
    turns = _turns(steps, start, model_name)
    last = max([start, *stamps, *(c["end_ns"] for t in turns for c in t["tools"])])
    end = max(_ns(result.get("ended_unix")) or last, last)
    verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
    resolved = bool(verification.get("is_resolved"))
    patch = str(result.get("patch") or "")
    outcome = "solved" if resolved else ("no_patch" if not patch.strip() else "patch_failed")
    ended = _ended_code(result)
    issue = next((s.get("message") for s in steps if s.get("source") == "user"), "") or ""
    system = next((s.get("message") for s in steps if s.get("source") == "system" and s.get("message")), "") or ""
    tags = {"trace_key": trace_key(run_label, agent_name, iid), "run_label": run_label, "agent_name": agent_name,
            "instance_id": iid, "repo_name": iid.rsplit("_", 1)[0], "outcome_code": outcome, "ended_code": ended,
            "is_resolved": str(resolved).lower()}
    root = {"name": iid, "inputs": {"issue": telemetry.scrub(issue), "system_prompt": telemetry.scrub(system)},
            "outputs": {"outcome_code": outcome, "ended_code": ended, "patch": telemetry.scrub(patch),
                        "error_text": telemetry.scrub(str(_error(result) or ""))},
            "attributes": {"agent_seconds": _number(result.get("agent_phase_seconds")),
                           "tool_call_count": _number(result.get("tool_call_count"), int),
                           "llm_call_count": _number(result.get("llm_call_count"), int), "step_count": len(steps)},
            "start_ns": start, "end_ns": end, "is_ok": resolved}
    return {"tags": tags, "root": root, "steps": turns}


def _commit() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _task_dirs(runs_dir: Path, run_label: str) -> list[Path]:
    base = runs_dir / run_label if (runs_dir / run_label).is_dir() else runs_dir
    return sorted(p.parent for p in base.rglob("tasks/*/result.json"))


def load_run(runs_dir: Path, run_label: str, agent_name: str, client, limit=None, dry_run=False,
             model_name: str | None = None) -> dict:
    """Write each task-run of one run whose trace_key is not in the experiment yet. Counts written, skipped and failed
    (and, for a dry run, built)."""
    dirs = _task_dirs(Path(runs_dir), run_label)[:limit]
    have = set() if dry_run else client.existing_keys(run_label)
    batch = {"loaded_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_commit_sha": _commit()}
    todo, failed, skipped = [], 0, 0
    for d in dirs:
        if trace_key(run_label, agent_name, d.name) in have:
            skipped += 1
            continue
        try:
            trace = task_trace(d, run_label, agent_name, model_name)
        except (OSError, ValueError) as e:
            print(f"{d.name}: not loaded ({type(e).__name__})")
            failed += 1
            continue
        trace["tags"].update(batch)
        todo.append(trace)
    if dry_run:
        return {"written": 0, "skipped": 0, "failed": failed, "built": len(todo)}
    written = 0
    if todo:
        run_id = client.start_load(run_label, agent_name, {"model_name": model_name or "", **batch})
        for trace in todo:
            client.write(trace, source_run_id=run_id)
            written += 1
        client.end_load(run_id, {"task_count": len(dirs), "written_count": written, "skipped_count": skipped,
                                 "failed_count": failed,
                                 "solved_count": sum(t["tags"]["is_resolved"] == "true" for t in todo)})
    return {"written": written, "skipped": skipped, "failed": failed}


class MlflowTraceClient:
    """Writes to the experiment the bundle made. Never creates one: an experiment made here would store its traces in
    MLflow's default storage, not Unity Catalog."""

    def __init__(self, experiment_name: str):
        import mlflow
        from mlflow.entities import SpanType
        self.mlflow, self.span_type = mlflow, SpanType
        mlflow.set_tracking_uri("databricks")
        exp = mlflow.get_experiment_by_name(experiment_name)
        if exp is None:
            sys.exit(f"{experiment_name} does not exist: deploy the bundle first (databricks/resources/agent_traces.yml)")
        if getattr(exp, "trace_location", None) is None:
            sys.exit(f"{experiment_name} has no Unity Catalog trace location: it was not made by the bundle")
        self.experiment_id = exp.experiment_id

    def existing_keys(self, run_label: str) -> set[str]:
        traces = self.mlflow.search_traces(locations=[self.experiment_id], return_type="list",
                                           filter_string=f"tags.run_label = '{run_label}'")
        return {t.info.tags.get("trace_key") for t in traces} - {None}

    def start_load(self, run_label: str, agent_name: str, params: dict) -> str:
        run = self.mlflow.start_run(experiment_id=self.experiment_id, run_name=f"{agent_name} | {run_label}")
        self.mlflow.set_tags({"run_label": run_label, "agent_name": agent_name, "is_simulated": "false"})
        self.mlflow.log_params({"agent_name": agent_name, "run_label": run_label, **params})
        return run.info.run_id

    def write(self, trace: dict, source_run_id: str | None = None) -> None:
        m, kind, r = self.mlflow, self.span_type, trace["root"]
        root = m.start_span_no_context(name=r["name"], span_type=kind.AGENT, inputs=r["inputs"], tags=trace["tags"],
                                       attributes=r["attributes"], experiment_id=self.experiment_id,
                                       metadata={"mlflow.sourceRun": source_run_id} if source_run_id else None,
                                       start_time_ns=r["start_ns"])
        clamp = lambda ns: min(max(ns, r["start_ns"]), r["end_ns"])
        for turn in trace["steps"]:
            span = m.start_span_no_context(name=turn["name"], span_type=kind.LLM, parent_span=root,
                                           inputs=turn["inputs"], attributes=turn["attributes"],
                                           start_time_ns=clamp(turn["start_ns"]))
            span.end(outputs=turn["outputs"], end_time_ns=clamp(turn["end_ns"]))
            for tool in turn["tools"]:
                child = m.start_span_no_context(name=tool["name"], span_type=kind.TOOL, parent_span=root,
                                                inputs=tool["inputs"], attributes=tool["attributes"],
                                                start_time_ns=clamp(tool["start_ns"]))
                child.end(outputs=tool["outputs"], status="OK" if tool["is_ok"] else "ERROR",
                          end_time_ns=clamp(tool["end_ns"]))
        root.end(outputs=r["outputs"], status="OK" if r["is_ok"] else "ERROR", end_time_ns=r["end_ns"])

    def end_load(self, run_id: str, metrics: dict) -> None:
        self.mlflow.log_metrics(metrics)
        self.mlflow.end_run()
        self.mlflow.flush_trace_async_logging()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("runs_dir", type=Path, help="the folder holding <label>/.../tasks/<id>/result.json")
    p.add_argument("--label", required=True, help="the run's label, e.g. devset-m31be-c1")
    p.add_argument("--agent", required=True, help="the agent's name, e.g. 'ours 31B-e'")
    p.add_argument("--model", default=None, help="the model's name on every model turn, e.g. gemma-4-31b")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true", help="build every trace and write none")
    a = p.parse_args(argv)
    if not a.runs_dir.is_dir():
        sys.exit(f"runs folder {a.runs_dir} does not exist")
    if not LABEL.match(a.label):
        sys.exit(f"--label {a.label!r}: letters, digits, '.', '_' and '-' only")
    if not a.dry_run and not os.environ.get("DATABRICKS_HOST"):
        sys.exit("DATABRICKS_HOST is not set: the workspace to write to (and DATABRICKS_TOKEN)")
    client = None if a.dry_run else MlflowTraceClient(os.environ.get("AGENT_TRACE_EXPERIMENT") or DEFAULT_EXPERIMENT)
    counts = load_run(a.runs_dir, a.label, a.agent, client, limit=a.limit, dry_run=a.dry_run, model_name=a.model)
    print(f"{a.label} ({a.agent}): {counts}")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
