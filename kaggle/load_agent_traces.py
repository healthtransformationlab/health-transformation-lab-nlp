"""Load a finished coding-agent run into the Unity Catalog trace experiment (spec 041 US2, #857).

A Modal, Colab or Kaggle run leaves one folder per task (tasks/<id>/result.json and results/traces/*.json), the same
files kaggle/forward_run_telemetry.py sends to Azure. This writes one MLflow trace per task-run into the experiment
the bundle declares (databricks/resources/agent_traces.yml), whose traces are stored in
health_transformation_lab.ops_agent_trace:

    python kaggle/load_agent_traces.py <runs folder> --label devset-m31be-c1 --agent "ours 31B-e" --model gemma-4-31b

The trace's shape is plan.md's "What a trace looks like". MLflow groups its charts by span name, type, status and model:
- the root span (AGENT) is the task: the issue in; the outcome, the patch and the error out; OK when resolved;
- each model turn is an LLM span named "model turn": its message, its token use (mlflow.chat.tokenUsage), the model;
- each tool call is a TOOL span beside its turn, named by the tool alone (read_file, edit_file, run_command, ...),
  ERROR when the tool reported an error (a failed edit), so the Tool calls tab counts calls and errors per tool.
Each span also carries OpenTelemetry's GenAI names (gen_ai.operation.name invoke_agent, chat or execute_tool;
gen_ai.tool.name; gen_ai.request.model; gen_ai.usage.input_tokens and output_tokens), which trace charts built on
OpenTelemetry read.
A turn runs from the end of the previous step to when the model answered; its tool call from there to when the tool's
output came back.

Every text is scrubbed of secrets first (telemetry.scrub_value, ADR 0010). Every trace carries the tag trace_key, the
SHA-256 of run label, agent and task. A reload deletes any existing trace with that key and writes again
(delete-then-append), so a run loaded twice leaves one trace per key (#899). Each written trace also carries
file_sha256 (of that task's result.json), loaded_ts and git_commit_sha. With --verdicts, the CPU verifier's result is
logged as a solved assessment. Settings: DATABRICKS_HOST and DATABRICKS_TOKEN (the workspace),
AGENT_TRACE_EXPERIMENT (default /Shared/coding-agent-runs, the same in every environment; docs/telemetry.md).
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


NO_TEST_SPEC = "missing test specification"


def _run_error(result: dict):
    """What stopped the run. The kernel's "Missing test specification" note says only that the kernel could not grade:
    our own repositories' tasks keep their tests out of the agent's bundle and are graded afterwards (#881, #894). It
    is never the run's error; the agent's own error, when there is one, comes first in `_error` anyway."""
    error = _error(result)
    if error not in (None, "None") and NO_TEST_SPEC in str(error).lower():
        return None
    return error


def _ended_code(result: dict) -> str:
    code = _error_code(_run_error(result))
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
        attrs = {"step_num": num, "cached_token_count": _number(metrics.get("cached_tokens"), int),
                 "gen_ai.operation.name": "chat"}
        if metrics:
            usage = {"input_tokens": _number(metrics.get("prompt_tokens"), int),
                     "output_tokens": _number(metrics.get("completion_tokens"), int),
                     "total_tokens": _number(metrics.get("total_tokens"), int)}
            attrs["mlflow.chat.tokenUsage"] = usage
            attrs["gen_ai.usage.input_tokens"] = usage["input_tokens"]
            attrs["gen_ai.usage.output_tokens"] = usage["output_tokens"]
        if model_name:
            attrs["mlflow.llm.model"] = model_name
            attrs["gen_ai.request.model"] = attrs["gen_ai.response.model"] = model_name
        tools, end = [], answered
        for call in [c for c in step.get("tool_calls") or [] if isinstance(c, dict)]:
            name = str(call.get("function_name") or "tool")
            match = next((o for o in outputs if _tool_name(o) == name), outputs[0] if outputs else None)
            if match is not None:
                outputs.remove(match)
            output = _clean(match.get("content")) if match else None
            came_back = max(answered, _when(match) or answered) if match else answered
            tools.append({"name": name, "inputs": _clean(call.get("arguments")), "outputs": output,
                          "attributes": {"step_num": num, "gen_ai.operation.name": "execute_tool",
                                         "gen_ai.tool.name": name},
                          "is_ok": not _is_tool_error(output),
                          "start_ns": answered, "end_ns": came_back})
            end = max(end, came_back)
        turns.append({"name": "model turn", "inputs": None, "outputs": {"message": _clean(step.get("message"))},
                      "attributes": attrs, "start_ns": prev, "end_ns": answered, "tools": tools})
        prev = end
    return turns


def read_verdicts(path: Path) -> dict[str, bool]:
    """instance_id -> resolved, from kaggle/official_verify.py's --out file (one JSON object per line; #881)."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[str(row["instance_id"])] = bool(row["resolved"])
    return out


def task_trace(task_dir: Path, run_label: str, agent_name: str, model_name: str | None = None,
               verdicts: dict[str, bool] | None = None) -> dict:
    """The trace of one task-run as plain data: {"tags", "root", "steps"}. Pure: reads the folder, writes nothing.
    With `verdicts` (read_verdicts), whether it was solved comes from the official verifier, not result.json: the
    kernel cannot grade this repository's own tasks ("Missing test specification", #881)."""
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
    if verdicts is not None:
        if iid not in verdicts:
            raise LookupError("no verdict")
        resolved, source = verdicts[iid], "official_verify"
    else:
        resolved, source = bool(verification.get("is_resolved")), "kernel"
    patch = str(result.get("patch") or "")
    outcome = "solved" if resolved else ("no_patch" if not patch.strip() else "patch_failed")
    ended = _ended_code(result)
    kernel_note = " ".join(str(result.get(k) or "") for k in ("error_text", "error")).lower()
    issue = next((s.get("message") for s in steps if s.get("source") == "user"), "") or ""
    system = next((s.get("message") for s in steps if s.get("source") == "system" and s.get("message")), "") or ""
    tags = {"trace_key": trace_key(run_label, agent_name, iid), "run_label": run_label, "agent_name": agent_name,
            "instance_id": iid, "repo_name": iid.rsplit("_", 1)[0], "outcome_code": outcome, "ended_code": ended,
            "is_resolved": str(resolved).lower(), "verdict_source_code": source,
            "kernel_grade_code": "no_test_spec" if NO_TEST_SPEC in kernel_note else "graded"}
    root = {"name": iid, "inputs": {"issue": telemetry.scrub(issue), "system_prompt": telemetry.scrub(system)},
            "outputs": {"outcome_code": outcome, "ended_code": ended, "patch": telemetry.scrub(patch),
                        "error_text": telemetry.scrub(str(_run_error(result) or ""))},
            "attributes": {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": agent_name,
                           "agent_seconds": _number(result.get("agent_phase_seconds")),
                           "tool_call_count": _number(result.get("tool_call_count"), int),
                           "llm_call_count": _number(result.get("llm_call_count"), int), "step_count": len(steps)},
            "start_ns": start, "end_ns": end, "is_ok": resolved}
    # CPU-verifier loads (#881, #899): attach solved so assessments are not empty for no_test_spec tasks.
    assessments = [{"name": "solved", "value": resolved}] if source == "official_verify" else []
    return {"tags": tags, "root": root, "steps": turns, "assessments": assessments}


def _commit() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _task_dirs(runs_dir: Path, run_label: str) -> list[Path]:
    """One folder per task id. A collected Colab run holds two copies of each task (colab_download/working/tasks and
    output/tasks): the graded output/tasks copy is taken (#913)."""
    base = runs_dir / run_label if (runs_dir / run_label).is_dir() else runs_dir
    by_id: dict[str, Path] = {}
    for p in sorted(base.rglob("tasks/*/result.json")):
        d, prev = p.parent, by_id.get(p.parent.name)
        if prev is None or (d.parent.parent.name == "output" and prev.parent.parent.name != "output"):
            by_id[d.name] = d
    return [by_id[k] for k in sorted(by_id)]


_PLAIN_ID = re.compile(r"[0-9A-Za-z_-]+")


def _bare_trace_id(trace_id: str) -> str:
    """The id the Unity Catalog tables hold: search_traces gives trace:/<catalog.schema.prefix>/<id>."""
    return str(trace_id).rsplit("/", 1)[-1].strip()


def delete_statements(table_prefix: str, trace_ids: list[str]) -> list[str]:
    """SQL that removes whole traces from a Unity Catalog trace location: their spans, and their annotations (the
    metadata, tags and assessments the trace_metadata view reads). MLflow's delete_traces can't delete a trace stored in
    Unity Catalog, as Databricks documents (#913); the logs table holds no rows for these traces and the metrics table
    isn't kept per trace."""
    ids = sorted({_bare_trace_id(t) for t in trace_ids})
    bad = [i for i in ids if not _PLAIN_ID.fullmatch(i)]
    if bad or not ids:
        raise ValueError(f"not a plain trace id: {bad or ids!r}")
    listed = ", ".join(f"'{i}'" for i in ids)
    return [f"delete from {table_prefix}_otel_spans where trace_id in ({listed})",
            f"delete from {table_prefix}_otel_annotations where target_id in ({listed})"]


def load_run(runs_dir: Path, run_label: str, agent_name: str, client, limit=None, dry_run=False,
             model_name: str | None = None, verdicts: dict[str, bool] | None = None) -> dict:
    """Build every task-run of one run, delete any existing traces with the same trace_key, then write (delete-then-
    append by trace_key, #899). Counts written, replaced, failed and unconfirmed (and, for a dry run, built)."""
    dirs = _task_dirs(Path(runs_dir), run_label)[:limit]
    batch = {"loaded_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_commit_sha": _commit()}
    todo, failed, seen, skipped_duplicate = [], 0, set(), 0
    for d in dirs:
        try:
            trace = task_trace(d, run_label, agent_name, model_name, verdicts)
        except LookupError:
            print(f"{d.name}: not loaded (no verdict)")
            failed += 1
            continue
        except (OSError, ValueError) as e:
            print(f"{d.name}: not loaded ({type(e).__name__})")
            failed += 1
            continue
        if trace["tags"]["trace_key"] in seen:  # the same task-run twice in one load (#913)
            skipped_duplicate += 1
            continue
        seen.add(trace["tags"]["trace_key"])
        result_path = d / "result.json"
        trace["tags"].update({**batch, "file_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest()})
        todo.append(trace)
    if dry_run:
        return {"written": 0, "skipped": 0, "failed": failed, "built": len(todo), "replaced": 0,
                "skipped_duplicate": skipped_duplicate}
    written, unconfirmed, replaced = 0, 0, 0
    if todo:
        keys = {t["tags"]["trace_key"] for t in todo}
        existing = client.existing_trace_ids(run_label)
        to_delete = [existing[k] for k in keys if k in existing]
        if to_delete:
            client.delete_keys(to_delete)
            replaced = len(to_delete)
        run_id = client.start_load(run_label, agent_name, {"model_name": model_name or "", **batch})
        for trace in todo:
            client.write(trace, source_run_id=run_id)
            written += 1
        client.end_load(run_id, {"task_count": len(dirs), "written_count": written, "replaced_count": replaced,
                                 "failed_count": failed,
                                 "solved_count": sum(t["tags"]["is_resolved"] == "true" for t in todo)})
        missing = client.confirm(run_label, keys)
        for key in sorted(missing):
            print(f"written but not found in the experiment: trace_key {key}")
        unconfirmed = len(missing)
    return {"written": written, "skipped": 0, "failed": failed, "unconfirmed": unconfirmed, "replaced": replaced,
            "skipped_duplicate": skipped_duplicate}


class MlflowTraceClient:
    """Writes to the experiment the bundle made. Never creates one: an experiment made here would store its traces in
    MLflow's default storage, not Unity Catalog. Traces reach Unity Catalog only once set_experiment is given the
    experiment's own trace location: started without it (only experiment_id on the span), MLflow dropped them with no
    error (November 17). confirm() checks afterwards that every trace written can be found."""

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
        mlflow.set_experiment(experiment_id=exp.experiment_id, trace_location=exp.trace_location)
        self.experiment_id = exp.experiment_id
        self.table_prefix = exp.trace_location.full_table_prefix  # catalog.schema.prefix of the trace tables
        self._ws = self._warehouse_id = None

    def existing_keys(self, run_label: str) -> set[str]:
        return set(self.existing_trace_ids(run_label))

    def existing_trace_ids(self, run_label: str) -> dict[str, str]:
        """trace_key -> trace_id for every trace of this run_label still in the experiment."""
        traces = self.mlflow.search_traces(locations=[self.experiment_id], return_type="list",
                                           filter_string=f"tags.run_label = '{run_label}'")
        return {t.info.tags["trace_key"]: t.info.trace_id for t in traces if t.info.tags.get("trace_key")}

    def delete_keys(self, trace_ids: list[str]) -> int:
        """Remove traces by id so a reload can append a fresh copy of the same trace_key (#899). The traces live in
        Unity Catalog, where MLflow's delete_traces rejects every id form (#913), so their rows are deleted by SQL
        through a warehouse (DATABRICKS_WAREHOUSE_ID, else the workspace's first). Returns the traces removed."""
        ids = sorted({_bare_trace_id(t) for t in trace_ids if t})
        if not ids:
            return 0
        for statement in delete_statements(self.table_prefix, ids):
            self._sql(statement)
        return len(ids)

    def _sql(self, statement: str) -> None:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.sql import StatementState
        if self._ws is None:
            self._ws = WorkspaceClient()
            self._warehouse_id = (os.environ.get("DATABRICKS_WAREHOUSE_ID") or "").strip() or next(
                iter(self._ws.warehouses.list())).id
        res = self._ws.statement_execution.execute_statement(statement=statement, warehouse_id=self._warehouse_id,
                                                             wait_timeout="50s")
        while res.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(2)
            res = self._ws.statement_execution.get_statement(res.statement_id)
        if res.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"{res.status.state}: {res.status.error.message if res.status.error else ''} "
                               f"in {statement[:120]}")

    def start_load(self, run_label: str, agent_name: str, params: dict) -> str:
        run = self.mlflow.start_run(experiment_id=self.experiment_id, run_name=f"{agent_name} | {run_label}")
        self.mlflow.set_tags({"run_label": run_label, "agent_name": agent_name, "is_simulated": "false"})
        self.mlflow.log_params({"agent_name": agent_name, "run_label": run_label, **params})
        return run.info.run_id

    def write(self, trace: dict, source_run_id: str | None = None) -> None:
        m, kind, r = self.mlflow, self.span_type, trace["root"]
        root = m.start_span_no_context(name=r["name"], span_type=kind.AGENT, inputs=r["inputs"], tags=trace["tags"],
                                       attributes=r["attributes"],
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
        tid = getattr(root, "trace_id", None) or getattr(root, "request_id", None)
        for assessment in trace.get("assessments") or []:
            m.log_feedback(trace_id=tid, name=assessment["name"], value=assessment["value"],
                           rationale="CPU verifier verdict" if assessment["name"] == "solved" else None)

    def end_load(self, run_id: str, metrics: dict) -> None:
        self.mlflow.log_metrics(metrics)
        self.mlflow.end_run()
        self.mlflow.flush_trace_async_logging()

    def confirm(self, run_label: str, keys: set[str], wait_seconds: int = 300) -> set[str]:
        """The keys written that the experiment still doesn't show after up to wait_seconds (traces reach the Delta
        tables a few seconds after they are flushed)."""
        missing, waited = set(keys), 0
        while missing:
            missing -= self.existing_keys(run_label)
            if not missing or waited >= wait_seconds:
                break
            time.sleep(15)
            waited += 15
        return missing


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("runs_dir", type=Path, help="the folder holding <label>/.../tasks/<id>/result.json")
    p.add_argument("--label", required=True, help="the run's label, e.g. devset-m31be-c1")
    p.add_argument("--agent", required=True, help="the agent's name, e.g. 'ours 31B-e'")
    p.add_argument("--model", default=None, help="the model's name on every model turn, e.g. gemma-4-31b")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true", help="build every trace and write none")
    p.add_argument("--verdicts", type=Path, default=None,
                   help="kaggle/official_verify.py's --out file: solved comes from it, not result.json (#881)")
    a = p.parse_args(argv)
    if not a.runs_dir.is_dir():
        sys.exit(f"runs folder {a.runs_dir} does not exist")
    if not LABEL.match(a.label):
        sys.exit(f"--label {a.label!r}: letters, digits, '.', '_' and '-' only")
    if not a.dry_run and not os.environ.get("DATABRICKS_HOST"):
        sys.exit("DATABRICKS_HOST is not set: the workspace to write to (and DATABRICKS_TOKEN)")
    client = None if a.dry_run else MlflowTraceClient(os.environ.get("AGENT_TRACE_EXPERIMENT") or DEFAULT_EXPERIMENT)
    verdicts = read_verdicts(a.verdicts) if a.verdicts else None
    counts = load_run(a.runs_dir, a.label, a.agent, client, limit=a.limit, dry_run=a.dry_run, model_name=a.model,
                      verdicts=verdicts)
    print(f"{a.label} ({a.agent}): {counts}")
    return 1 if counts["failed"] or counts.get("unconfirmed") else 0


if __name__ == "__main__":
    sys.exit(main())
