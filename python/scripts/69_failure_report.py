"""The failing test's report an agent can be given (028 AI7, #674).

This repository is test-first, so each task's failing test exists before its fix. Script 68 counted where that
test's report points; this builds the report itself, to give to an agent beside the task's statement:

- the tests that fail or cannot run, with the first line of each distinct error (pytest's own summary line), and
  how many tests fail that way;
- the package's public functions those tests called before failing: what the repository's OpenTelemetry spans
  record, since every public function is `@traced` (spec 014).

The report comes from the task's hidden test. It is the context a test-first workflow has before the fix, not a
benchmark condition, and a run that uses it says so.

    python scripts/69_failure_report.py --tasks <published tasks.jsonl> --snapshots <dir> --out-context <file>

Writes the reports to --out-context (JSON lines: instance_id, context_text), which must be outside the repository:
the text is rebuilt from the published dataset, never committed. Writes data/tasks/failure_report_shape.csv: ids
and counts, no text.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

HERE = Path(__file__).resolve().parent
OUT = TASKS_DIR / "failure_report_shape.csv"
COLUMNS = ["instance_id", "test_exit_code", "failing_test_count", "errored_test_count", "traced_function_count",
           "context_chars", "is_import_error"]
HEADER = "Failing test report (this repository's tests for the change, run on this commit before any fix):"
FUNCTIONS = ("Public functions these tests called before failing (what the repository's OpenTelemetry spans "
             "record): ")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tr = _load("68_trace_reach")


def failure_context(trace: dict, max_failures: int = 10, max_functions: int = 15,
                    max_message_chars: int = 240) -> str:
    """The report as text: one line per distinct error, with its first test and how many more fail the same way,
    then the public functions called. Short on purpose: a small model's context is its budget. Empty when no test
    failed."""
    messages = trace.get("failure_messages") or []
    if not messages:
        return ""
    groups: dict[tuple[str, str], list[str]] = {}
    for m in messages:
        groups.setdefault((m["kind_code"], m["message_text"]), []).append(m["test_id"])
    lines = [HEADER]
    for (kind, message), tests in list(groups.items())[:max_failures]:
        more = f" (and {len(tests) - 1} more tests with this error)" if len(tests) > 1 else ""
        lines.append(f"- {kind} python/{tests[0]}{more} - {message[:max_message_chars]}")
    if len(groups) > max_failures:
        lines.append(f"(and {len(groups) - max_failures} more distinct errors)")
    called = sorted(tr.public(set(trace.get("called") or [])))
    if called:
        more = f" (and {len(called) - max_functions} more)" if len(called) > max_functions else ""
        lines.append(FUNCTIONS + ", ".join(called[:max_functions]) + more)
    return "\n".join(lines)


def shape_row(instance_id: str, trace: dict, context: str) -> dict:
    """What is committed about one task's report: counts and booleans, never its text."""
    messages = trace.get("failure_messages") or []
    return {"instance_id": instance_id, "test_exit_code": trace.get("exit_status"),
            "failing_test_count": sum(m["kind_code"] == "FAILED" for m in messages),
            "errored_test_count": sum(m["kind_code"] == "ERROR" for m in messages),
            "traced_function_count": len(tr.public(set(trace.get("called") or []))),
            "context_chars": len(context),
            "is_import_error": any(m["message_text"].startswith(("ImportError", "ModuleNotFoundError"))
                                   for m in messages)}


def check_out_path(path: Path) -> None:
    """The report text never lands in the repository, where a commit could pick it up."""
    if Path(path).resolve().is_relative_to(REPO_ROOT.resolve()):
        raise SystemExit(f"--out-context {path}: write the report text outside the repository; only counts are committed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, required=True, help="the published tasks.jsonl")
    ap.add_argument("--snapshots", type=Path, required=True)
    ap.add_argument("--ids", help="comma-separated instance ids (default: every task)")
    ap.add_argument("--out-context", type=Path, required=True, help="where the report text goes (outside the repository)")
    ap.add_argument("--timeout", type=int, default=300, help="seconds a task's tests may run")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    check_out_path(a.out_context)
    tasks = {t["instance_id"]: t for t in map(json.loads, filter(str.strip, a.tasks.read_text().splitlines()))}
    ids = [i.strip() for i in a.ids.split(",") if i.strip()] if a.ids else sorted(tasks)
    missing = [i for i in ids if i not in tasks or not (a.snapshots / f"{i}.tgz").exists()]
    if missing:
        raise SystemExit(f"not in the tasks.jsonl given, or no snapshot: {', '.join(missing)}")

    def one(iid: str) -> tuple[dict, str]:
        trace = tr.run_task(tasks[iid], a.snapshots / f"{iid}.tgz", None, a.timeout, messages=True)
        context = failure_context(trace)
        row = shape_row(iid, trace, context)
        print(f"{iid}: exit {row['test_exit_code']}, failing {row['failing_test_count']}, errored "
              f"{row['errored_test_count']}, functions {row['traced_function_count']}, {row['context_chars']} chars",
              flush=True)
        return row, context

    with ThreadPoolExecutor(a.workers) as pool:
        done = list(pool.map(one, ids))
    rows = [row for row, _ in done]
    a.out_context.parent.mkdir(parents=True, exist_ok=True)
    a.out_context.write_text("".join(json.dumps({"instance_id": row["instance_id"], "context_text": context}) + "\n"
                                     for row, context in done if context))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=COLUMNS).sort_values("instance_id").to_csv(a.out, index=False)
    with_report = [r for r in rows if r["context_chars"]]
    print(json.dumps({"task_count": len(rows), "report_count": len(with_report),
                      "import_error_count": sum(r["is_import_error"] for r in rows),
                      "median_context_chars": statistics.median(r["context_chars"] for r in with_report)
                      if with_report else None,
                      "max_context_chars": max((r["context_chars"] for r in rows), default=0),
                      "no_report": [r["instance_id"] for r in rows if not r["context_chars"]]}, indent=1))
    print(f"-> {a.out} (counts); {a.out_context} (text, not committed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
