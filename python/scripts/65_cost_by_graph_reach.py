"""What the baseline's GPU time bought, split by whether the code graph leads to a task's fix (spec 028, #662).

    python scripts/65_cost_by_graph_reach.py

Joins three committed tables: data/tasks/graph_coverage.csv (63_graph_coverage.py), data/tasks/statement_search.csv
(64_statement_search.py) and the Gemma 4 E4B run table (data/tasks/agent_runs/gemma-4-e4b-it_kaggle.csv, each
task's latest run). Each published task gets one kind, by the first thing that leads from its statement to its fix:

    outside_graph      the reference patch touches no module the graph covers
    no_existing_node   it touches one, but edits no function, class or method the base commit already had
    named_or_called    the statement names an edited node, or call edges lead to one from a node it names
    embedding_top10    neither, but an edited node is in the first ten by embedding similarity to the statement
    unreached          a node is edited and none of the three leads to it

Writes data/tasks/cost_by_graph_reach.csv, one row per kind: tasks, tasks run, tasks resolved, the hours the agent
ran on them and the share of those hours. Cost is the agent's own time (`agent_seconds`: the model's turns and its
tool calls, on two T4 GPUs), which every run records; the session's GPU-hours are missing for the three earliest
runs. The run table is of this repository's harness under the tight limits, cheapest tasks first, so the split
describes that run; it is not an estimate of what any task must cost. No model is needed.
"""

from __future__ import annotations

import pandas as pd

from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

COVERAGE = TASKS_DIR / "graph_coverage.csv"
SEARCH = TASKS_DIR / "statement_search.csv"
RUNS = TASKS_DIR / "agent_runs" / "gemma-4-e4b-it_kaggle.csv"
OUT = TASKS_DIR / "cost_by_graph_reach.csv"
REACH = ("outside_graph", "no_existing_node", "named_or_called", "embedding_top10", "unreached")
COLUMNS = ["reach_code", "task_count", "attempted_count", "resolved_count", "agent_hours", "agent_share_pct"]
TOP = 10


def reach_code(row) -> str:
    """One task's kind (see the module docstring), from its coverage and search columns."""
    if not row["is_fix_in_graph"]:
        return "outside_graph"
    if not row["edited_node_count"]:
        return "no_existing_node"
    if not pd.isna(row["statement_to_fix_edge_count"]):
        return "named_or_called"
    if not pd.isna(row["edited_node_best_rank_num"]) and row["edited_node_best_rank_num"] <= TOP:
        return "embedding_top10"
    return "unreached"


def cost_table(reach: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """One row per kind: published tasks of that kind, those the run attempted, those it resolved, the hours the
    agent ran on them and their share of the agent's hours on published tasks. A run of a task that is not
    published is left out; a run with no recorded time is an error."""
    joined = reach.merge(runs[["instance_id", "is_resolved", "agent_seconds"]], on="instance_id", how="left", indicator=True)
    ran_all = joined[joined["_merge"] == "both"]
    if ran_all["agent_seconds"].isna().any():
        raise SystemExit("a run has no agent_seconds: " + ", ".join(ran_all[ran_all["agent_seconds"].isna()]["instance_id"]))
    total = ran_all["agent_seconds"].sum()
    rows = []
    for code in REACH:
        sel = joined[joined["reach_code"] == code]
        ran = sel[sel["_merge"] == "both"]
        seconds = float(ran["agent_seconds"].sum())
        rows.append({"reach_code": code, "task_count": len(sel), "attempted_count": len(ran),
                     "resolved_count": int(ran["is_resolved"].astype(bool).sum()), "agent_hours": round(seconds / 3600, 2),
                     "agent_share_pct": round(100 * seconds / total, 1) if total else 0.0})
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> int:
    for path in (COVERAGE, SEARCH, RUNS):   # required files: fail naming the missing one
        if not path.exists():
            raise SystemExit(f"{path.relative_to(REPO_ROOT)} is missing")
    tasks = pd.read_csv(COVERAGE).merge(pd.read_csv(SEARCH)[["instance_id", "edited_node_best_rank_num"]], on="instance_id")
    tasks["reach_code"] = tasks.apply(reach_code, axis=1)
    table = cost_table(tasks[["instance_id", "reach_code"]], pd.read_csv(RUNS))
    table.to_csv(OUT, index=False)   # overwritten whole: re-runnable
    print(table.to_string(index=False))
    print(f"{int(table['attempted_count'].sum())} published tasks run, {int(table['resolved_count'].sum())} resolved, "
          f"{table['agent_hours'].sum():.2f} hours of agent time on two T4s -> {OUT.relative_to(REPO_ROOT)}")
    print("This repository's harness under the tight limits, cheapest tasks first; not the competition's evaluator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
