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
A full run (no --sample, --limit or --instance-ids) also drops the failures from the set (T007a, #502):
data/tasks/tasks_gated.jsonl (git-ignored) holds only the tasks that pass both gates, and is what gets published;
each failure is a row in tasks_excluded.csv (its earlier gate rows replaced, the other exclusions kept). Run it after
every 55_build_tasks.py, which rewrites tasks_excluded.csv without the gate rows.

    python scripts/57_gate_tasks.py --apply-only       # no gating: apply the committed task_gates.csv
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
GATED = TASKS_DIR / "tasks_gated.jsonl"       # git-ignored: the set that gets published (T007a)
EXCLUDED = TASKS_DIR / "tasks_excluded.csv"   # committed
MANIFEST = TASKS_DIR / "task_manifest.csv"    # committed, for each task's tier


def apply_gates(tasks: list[dict], gates: list[dict]) -> None:
    """Write the passing tasks to tasks_gated.jsonl and list the failures in tasks_excluded.csv (T007a, #502)."""
    tiers = pd.read_csv(MANIFEST, usecols=["instance_id", "tier_code"]).set_index("instance_id")["tier_code"].to_dict()
    kept = tgate.passing_tasks(tasks, gates)
    GATED.write_text("".join(json.dumps(t) + "\n" for t in kept))   # overwritten whole: re-runnable
    existing = pd.read_csv(EXCLUDED, keep_default_na=False).to_dict("records") if EXCLUDED.exists() else []
    dropped = tgate.gate_exclusions(gates, tiers)
    merged = tgate.merge_exclusions(existing, dropped)
    pd.DataFrame(merged, columns=["instance_id", "tier_code", "reason_text"]).to_csv(EXCLUDED, index=False)
    print(f"{len(kept)} of {len(tasks)} tasks -> {GATED.relative_to(REPO_ROOT)}; {len(dropped)} gate failure(s)"
          f" listed in {EXCLUDED.relative_to(REPO_ROOT)}" + (": " + ", ".join(d["instance_id"] for d in dropped)
                                                             if dropped else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="gate tasks_sample.jsonl instead of tasks.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="gate only the first N rows")
    ap.add_argument("--instance-ids", default="", help="comma-separated instance ids to gate")
    ap.add_argument("--timeout", type=int, default=tgate.DEFAULT_TIMEOUT, help="seconds per pytest run")
    ap.add_argument("--apply-only", action="store_true",
                    help="don't gate: apply the committed task_gates.csv to tasks.jsonl (T007a)")
    a = ap.parse_args()
    if a.apply_only and (a.sample or a.limit or a.instance_ids):
        sys.exit("--apply-only applies to the whole set: drop --sample, --limit and --instance-ids")
    if a.apply_only and not OUT.exists():
        sys.exit(f"missing {OUT.relative_to(REPO_ROOT)}: run scripts/57_gate_tasks.py without --apply-only first")
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

    if a.apply_only:
        gates = pd.read_csv(OUT, keep_default_na=False).to_dict("records")
        ungated = {t["instance_id"] for t in tasks} - {g["instance_id"] for g in gates}
        if ungated:   # a stale gate file would silently drop tasks
            sys.exit(f"{len(ungated)} task(s) have no gate row (e.g. {sorted(ungated)[0]}): gate them first")
        apply_gates(tasks, gates)
        telemetry.end_script()
        return 0

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
    if not (a.sample or a.limit or a.instance_ids):   # a partial run can't say which tasks the whole set keeps
        apply_gates(tasks, rows)
    telemetry.end_script()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
