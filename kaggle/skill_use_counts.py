"""Per-task counts of the edit-fallback scripts' use, read from a run's traces (028 AI17, #812).

The skill (gemma-developer-agent `skills/edit-fallback`) installs `find.py` and `edit.py` to /tmp/h with one
`run_skill_script` call. This reads each task's trace in a collected run (`<results>/working/tasks/<id>/results/
traces/*.json`, with `result.json` beside it) and counts, per task: the install call and whether it passed arguments;
`find.py` calls and whether the next file read was one `find.py` listed; `edit.py` calls by the first outcome it
printed; `edit_file`'s "not found" and "occurs N times" failures; tool calls and the agent's seconds. It reads
tool names, commands and outcomes only, never a file's contents into the table.

usage: python kaggle/skill_use_counts.py <collected results folder> <out.csv>
"""
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

COLUMNS = ["instance_id", "install_call_count", "install_with_args_count", "find_call_count",
           "find_then_listed_read_count", "edit_script_call_count", "edit_applied_count", "edit_nothing_written_count",
           "edit_already_done_count", "edit_occurs_count", "edit_file_not_found_count", "edit_file_ambiguous_count",
           "tool_call_count", "task_seconds"]
ARG_KEYS = ("args", "short_options", "positional_args")


def _calls(trace: dict) -> list[tuple[str, dict, str]]:
    """(tool name, arguments, the tool's output as text) for every tool call, in order."""
    calls = []
    for step in trace.get("steps", []):
        out = (step.get("observation") or {}).get("content", "")
        out = out if isinstance(out, str) else json.dumps(out)
        for call in step.get("tool_calls") or []:
            calls.append((call.get("function_name") or "", call.get("arguments") or {}, out))
    return calls


def _edit_outcome(out: str) -> str | None:
    """edit.py's outcome, from what it printed; None when it never ran (not installed) or printed none of them."""
    if re.search(r"occurs at lines", out):
        return "edit_occurs_count"
    if "already in the file" in out:
        return "edit_already_done_count"
    if "NOTHING WRITTEN" in out:
        return "edit_nothing_written_count"
    if re.search(r"^written: ", out, re.M) or '"written: ' in out or "\\nwritten: " in out:
        return "edit_applied_count"
    return None


def count_task(task_dir: Path) -> dict:
    """One row of COLUMNS for the task whose collected folder is `task_dir`."""
    task_dir = Path(task_dir)
    trace = json.loads(Path(glob.glob(str(task_dir / "results" / "traces" / "*.json"))[0]).read_text())
    result = json.loads((task_dir / "result.json").read_text())
    calls = _calls(trace)
    row = dict.fromkeys(COLUMNS, 0)
    row["instance_id"] = task_dir.name
    for i, (name, args, out) in enumerate(calls):
        command = args.get("command", "") if isinstance(args, dict) else ""
        if name == "run_skill_script":
            row["install_call_count"] += 1
            row["install_with_args_count"] += any(k in args for k in ARG_KEYS)
        elif name == "run_command" and "find.py" in command:
            row["find_call_count"] += 1
            read = next((a for n, a, _ in calls[i + 1:] if n == "read_file"), None)
            path = str((read or {}).get("filepath") or "").removeprefix("/workspace/").lstrip("/")
            row["find_then_listed_read_count"] += bool(path) and path in out
        elif name == "run_command" and "edit.py" in command:
            row["edit_script_call_count"] += 1
            outcome = _edit_outcome(out)
            if outcome:
                row[outcome] += 1
        elif name == "edit_file":
            if "not found" in out:
                row["edit_file_not_found_count"] += 1
            elif re.search(r"occurs \d+ times", out):
                row["edit_file_ambiguous_count"] += 1
    row["tool_call_count"] = len(calls)
    row["task_seconds"] = round(float(result.get("agent_phase_seconds") or 0), 1)
    return row


def main(results: str, out: str) -> int:
    rows = [count_task(Path(d)) for d in sorted(glob.glob(os.path.join(results, "working", "tasks", "*")))]
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} tasks -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
