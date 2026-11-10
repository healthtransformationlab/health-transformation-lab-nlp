"""What the baseline run would have cost and kept had only screened tasks gone to the small model (spec 028, #664).

    python scripts/66_screen_routing.py

Joins the automated screen of all 93 tasks (data/tasks/screening/agent_screen_all.csv) to the Gemma 4 E4B run table
(data/tasks/agent_runs/gemma-4-e4b-it_kaggle.csv, each task's latest run) and splits the run by the screen's
verdict: tasks run, tasks resolved, the agent's hours and the hours per resolved task. Writes
data/tasks/screening/screen_routing.csv with three rows (pass, fail, all).

It is a what-if on one run: the model ran every task, and this says what the tasks that pass the screen cost and
gave. The screen reads a task's tests, so as a rule for what to send to a model it fits a test-first workflow,
where the failing test exists before the fix is tried. An AI reviewer's screen, this repository's harness, the tight
limits, cheapest tasks first. No model is needed.
"""

from __future__ import annotations

import pandas as pd

from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

SCREEN = TASKS_DIR / "screening" / "agent_screen_all.csv"
RUNS = TASKS_DIR / "agent_runs" / "gemma-4-e4b-it_kaggle.csv"
OUT = TASKS_DIR / "screening" / "screen_routing.csv"
COLUMNS = ["route_code", "attempted_count", "resolved_count", "agent_hours", "agent_share_pct", "agent_hours_per_resolved"]


def routing_table(screen: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """Three rows: the run's tasks that pass the screen, those that fail it, and all of them. Only tasks that are
    both screened and run count. `agent_hours_per_resolved` is blank where nothing was resolved."""
    ran = screen[["instance_id", "is_pass"]].merge(runs[["instance_id", "is_resolved", "agent_seconds"]], on="instance_id")
    if ran["agent_seconds"].isna().any():
        raise SystemExit("a run has no agent_seconds: " + ", ".join(ran[ran["agent_seconds"].isna()]["instance_id"]))
    total = ran["agent_seconds"].sum()
    rows = []
    for code, sel in (("pass", ran[ran["is_pass"].astype(bool)]), ("fail", ran[~ran["is_pass"].astype(bool)]), ("all", ran)):
        resolved = int(sel["is_resolved"].astype(bool).sum())
        hours = float(sel["agent_seconds"].sum()) / 3600
        rows.append({"route_code": code, "attempted_count": len(sel), "resolved_count": resolved,
                     "agent_hours": round(hours, 2), "agent_share_pct": round(100 * hours * 3600 / total, 1) if total else 0.0,
                     "agent_hours_per_resolved": round(hours / resolved, 2) if resolved else None})
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> int:
    for path in (SCREEN, RUNS):   # required files: fail naming the missing one
        if not path.exists():
            raise SystemExit(f"{path.relative_to(REPO_ROOT)} is missing")
    table = routing_table(pd.read_csv(SCREEN), pd.read_csv(RUNS))
    table.to_csv(OUT, index=False)   # overwritten whole: re-runnable
    print(table.to_string(index=False))
    print(f"-> {OUT.relative_to(REPO_ROOT)}. A what-if on one run of this repository's harness, not a new run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
