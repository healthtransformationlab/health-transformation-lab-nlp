"""Gate every task in the task set with our own fail-to-pass check (spec 028, US3, T007, #453).

    python scripts/57_gate_tasks.py                    # every row of data/tasks/tasks.jsonl -> task_gates.csv
    python scripts/57_gate_tasks.py --sample           # the committed tasks_sample.jsonl instead
    python scripts/57_gate_tasks.py --limit 5          # the first 5 rows
    python scripts/57_gate_tasks.py --instance-ids htlnlp_143,htlnlp_200

The competition's evaluator (`swegemma eval --skip-agent-patch`) isn't distributed (#449), so
`task_gate.gate_task` follows the harness's documented verification: the target tests fail with `test_patch`
alone at `base_commit`, and pass with `patch` (protected files stripped) plus `test_patch`.

Runs with THIS environment's Python and packages, not the competition's sandbox image: a dependency that differs
can change a verdict. Official swegemma scoring happens only on Kaggle (US5, #356).

Writes data/tasks/task_gates.csv (committed, overwritten whole, one row per gated task) and prints counts.
Needs tasks.jsonl from scripts/55_build_tasks.py (git-ignored) and the full git history, since every base commit
is checked out in a temporary worktree.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

import pandas as pd

from health_transformation_lab_nlp import task_gate as tgate
from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.paths import REPO_ROOT

TASKS_DIR = REPO_ROOT / "data" / "tasks"
TASKS = TASKS_DIR / "tasks.jsonl"             # git-ignored, from 55_build_tasks.py
SAMPLE = TASKS_DIR / "tasks_sample.jsonl"     # committed, 3 rows
OUT = TASKS_DIR / "task_gates.csv"            # committed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="gate tasks_sample.jsonl instead of tasks.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="gate only the first N rows")
    ap.add_argument("--instance-ids", default="", help="comma-separated instance ids to gate")
    ap.add_argument("--timeout", type=int, default=tgate.DEFAULT_TIMEOUT, help="seconds per pytest run")
    a = ap.parse_args()
    src = SAMPLE if a.sample else TASKS
    if not src.exists():   # check inputs before any work (AGENTS.md, configuration)
        sys.exit(f"missing {src.relative_to(REPO_ROOT)}: run scripts/55_build_tasks.py first, or pass --sample")
    if a.timeout <= 0:
        sys.exit("--timeout must be positive")
    telemetry.setup()
    telemetry.start_script("57_gate_tasks", data_label="public")

    tasks = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
    if a.instance_ids:
        wanted = {s.strip() for s in a.instance_ids.split(",") if s.strip()}
        unknown = wanted - {t["instance_id"] for t in tasks}
        if unknown:
            sys.exit(f"unknown instance id(s): {', '.join(sorted(unknown))}")
        tasks = [t for t in tasks if t["instance_id"] in wanted]
    if a.limit:
        tasks = tasks[: a.limit]

    rows = []
    for i, task in enumerate(tasks, 1):
        row = tgate.gate_task(task, REPO_ROOT, timeout=a.timeout)
        rows.append(row)
        print(f"[{i}/{len(tasks)}] {row['instance_id']}: {'valid' if row['is_valid'] else row['reason_text']}",
              flush=True)

    out = pd.DataFrame(rows, columns=tgate.GATE_COLUMNS).sort_values("instance_id")
    for c in ["before_exit_code", "after_exit_code", "after_passed_count", "after_failed_count", "after_error_count"]:
        out[c] = out[c].astype("Int64")
    out.to_csv(OUT, index=False)   # overwritten whole: re-runnable
    valid = int(out["is_valid"].sum())
    print(f"\n{valid} of {len(out)} tasks pass both gates ({src.name}); wrote {OUT.relative_to(REPO_ROOT)}")
    reasons = Counter(r for text in out["reason_text"] if text for r in text.split("; "))
    for reason, n in reasons.most_common():
        print(f"  {n:4d}  {reason}")
    telemetry.end_script()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
