"""The same tasks with and without added context, side by side (028 AI7, #674).

Reads the baseline arm's table (`..._swegemma_statement.csv`) and one other arm's (`..._swegemma_report.csv` or
`..._swegemma_graph.csv`, written by kaggle/official_agent_run.py --label), and writes
data/tasks/official_agent_runs/context_pairs_<arm>.csv: one row per task with both arms' verdicts and costs. Prints
the analysis the pre-registration names (specs/028-dataops-task-set/preregistration-*.md): each arm's resolved
count with its Wilson interval, the paired table, the exact McNemar test, two-sided, and the splits it only
describes. With --arm graph it also prints `graph` against `report` as a paired table, which the addendum describes
and does not test.

    python scripts/70_context_pairs.py --arm report
    python scripts/70_context_pairs.py --arm graph
    python scripts/70_context_pairs.py --arm graph --machine colab

`--machine colab` is addendum 2 (#687): both arms again, on one Colab GPU. It reads that pair's own tables
(`..._swegemma_colab-statement.csv`, `..._swegemma_colab-graph.csv`), writes `context_pairs_colab_graph.csv`, repeats
the test without any pair in which either side ran a command that reaches for the network, and sets each Colab arm
beside the Kaggle arm of the same text, which the addendum describes and does not test. No count is pooled across
machines.

`--arm report --machine colab` is addendum 3: the failing test's report as a third arm on the same Colab machine,
against the same baseline (`..._swegemma_colab-report.csv`, `context_pairs_colab_report.csv`). It also sets the
report arm beside the graph arm there, task by task, which is described and not tested.

`--machine colab-l4` is the same pair as a second notebook session made it at the same time, on an L4 (#687, the
comment of 03:25 UTC on November 12): unplanned, and described beside the registered pair. It reads
`..._swegemma_colab-statement-l4.csv` and `..._swegemma_colab-graph-l4.csv`, writes
`context_pairs_colab_l4_graph.csv`, and also sets each of its arms beside the registered pair's, task by task.

The report arm's context comes from each task's hidden test: what a test-first workflow has, not a benchmark
condition. The graph arm's comes from the statement and the graph alone.
"""

from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp.paths import TASKS_DIR
from health_transformation_lab_nlp.prevalence import wilson_ci

RUNS = TASKS_DIR / "official_agent_runs"
MODEL = "gemma-4-e4b-it-qat-w4a16-ct"
MEASURES = ["agent_patch_bytes", "tool_call_count", "graph_tool_call_count", "prompt_token_count",
            "output_token_count", "agent_seconds"]
FLAGS = {"report": ["is_import_error"], "graph": ["is_edited_node_listed", "is_node_named"]}
COMMON_FLAGS = ["is_screen_pass", "is_edit_task", "is_first_sample"]
SHAPES = {"report": "failure_report_shape.csv", "graph": "graph_context_shape.csv"}
# The Colab pair (addendum 2, #687) and what its tables' names end with. Two notebook sessions made it at the same
# time: the registered pair on an A100, and a second, unplanned one on an L4, kept apart.
COLAB = {"colab": "", "colab-l4": "-l4"}
FIRST = ("htlnlp_152,htlnlp_189,htlnlp_191,htlnlp_214,htlnlp_244,htlnlp_276,htlnlp_68,htlnlp_71,htlnlp_90,"
         "htlnlp_c95eedd3,htlnlp_cbc00f07,htlnlp_cc73f4cf,htlnlp_cf773377,htlnlp_pr21,htlnlp_pr28,htlnlp_pr31,"
         "htlnlp_pr34,htlnlp_pr37,htlnlp_pr47,htlnlp_pr54").split(",")   # the run of November 10


def mcnemar_exact(b: int, c: int) -> float:
    """The exact McNemar test, two-sided: a binomial test, at one half, on the discordant pairs (b one way, c the
    other). 1.0 when there are none."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def _value(v):
    return None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)


def pair_rows(ids: list[str], statement: pd.DataFrame, other: pd.DataFrame, flags: pd.DataFrame, arm: str) -> list[dict]:
    """One row per pre-registered task: both arms' verdicts and measures, and the task's flags for the splits. A task
    missing from an arm's table was not run in it: the row stays, with `is_pair_run` false. A measure's column is
    `<arm>_arm_<measure>`, so the graph arm's tool calls are not mistaken for calls to a graph tool."""
    arms = {"statement": statement.set_index("instance_id"), arm: other.set_index("instance_id")}
    flags = flags.set_index("instance_id")
    rows = []
    for iid in ids:
        ran = {name: iid in t.index for name, t in arms.items()}
        any_arm = next((t for name, t in arms.items() if ran[name]), None)
        row = {"instance_id": iid, "tier_code": any_arm.loc[iid, "tier_code"] if any_arm is not None else None}
        row.update({c: _value(flags.loc[iid, c]) if iid in flags.index else None for c in flags.columns})
        row["is_pair_run"] = all(ran.values())
        for name, t in arms.items():
            row[f"is_{name}_resolved"] = bool(t.loc[iid, "is_resolved"]) if ran[name] else None
        for m in MEASURES:
            for name, t in arms.items():
                row[f"{name}_arm_{m}"] = _value(t.loc[iid, m]) if ran[name] and m in t.columns else None
        rows.append(row)
    return rows


def summary(rows: list[dict], arm: str, flags: list[str]) -> dict:
    """The pre-registered analysis over the pairs both arms ran, and each split it only describes: for a flag, the
    pairs where it is true and where it is false (a pair with no value for it is in neither)."""
    pairs = [r for r in rows if r["is_pair_run"]]
    n = len(pairs)
    key = f"is_{arm}_resolved"

    def counts(sel: list[dict]) -> dict:
        return {"pair_count": len(sel), "statement_resolved_count": sum(bool(r["is_statement_resolved"]) for r in sel),
                f"{arm}_resolved_count": sum(bool(r[key]) for r in sel)}

    s_only = sum(bool(r["is_statement_resolved"]) and not r[key] for r in pairs)
    o_only = sum(bool(r[key]) and not r["is_statement_resolved"] for r in pairs)
    both = sum(bool(r["is_statement_resolved"]) and bool(r[key]) for r in pairs)
    p = mcnemar_exact(s_only, o_only)

    def pct(k: int) -> list[float]:
        return [round(100 * v, 1) for v in wilson_ci(k, n)] if n else [None, None]

    return {"arm_name": arm, "pair_count": n, "left_out_count": len(rows) - n,
            "statement_resolved_count": both + s_only, f"{arm}_resolved_count": both + o_only,
            "statement_wilson_pct": pct(both + s_only), f"{arm}_wilson_pct": pct(both + o_only),
            "both_count": both, "statement_only_count": s_only, f"{arm}_only_count": o_only,
            "neither_count": n - both - s_only - o_only, "mcnemar_exact_p": p, "is_difference_claimed": p < 0.05,
            "splits": {f: {"yes": counts([r for r in pairs if r.get(f) is True]),
                           "no": counts([r for r in pairs if r.get(f) is False])} for f in flags}}


def arm_cross(ids: list[str], a_table: pd.DataFrame, b_table: pd.DataFrame, a: str, b: str) -> dict:
    """Two added arms side by side over the tasks both ran: a paired table the addendum only describes, so no test."""
    ra, rb = a_table.set_index("instance_id").is_resolved, b_table.set_index("instance_id").is_resolved
    ran = [i for i in ids if i in ra.index and i in rb.index]
    both = sum(bool(ra[i]) and bool(rb[i]) for i in ran)
    a_only = sum(bool(ra[i]) and not rb[i] for i in ran)
    b_only = sum(bool(rb[i]) and not ra[i] for i in ran)
    return {"pair_count": len(ran), "left_out_count": len(ids) - len(ran), "both_count": both,
            f"{a}_only_count": a_only, f"{b}_only_count": b_only, "neither_count": len(ran) - both - a_only - b_only}


def table_names(machine: str, arm: str) -> tuple[str, str, str]:
    """The baseline table's label, the arm's, and the pairs file: for the Kaggle arms (the first plan and addendum 1),
    or for the Colab arms (addenda 2 and 3, #687), whose tables are their own."""
    if machine in COLAB:
        end = COLAB[machine]   # "" for the registered session's arms, "-l4" for the second session's
        if arm != "graph" and end:
            raise SystemExit("the second session did not make the report arm: on Colab it was registered on the A100 "
                             "session alone (addendum 3)")
        return f"colab-statement{end}", f"colab-{arm}{end}", f"context_pairs_colab{end.replace('-', '_')}_{arm}.csv"
    return "statement", arm, f"context_pairs_{arm}.csv"


def network_ids(settings: Path) -> list[str]:
    """The tasks of a Colab arm in which the agent ran a command that reaches for the network, from the audit in the
    arm's settings file. None for an arm with no audit (a Kaggle kernel has no network) or no settings file yet."""
    if not Path(settings).exists():
        return []
    return list((json.loads(Path(settings).read_text()).get("network_audit") or {}).get("instance_ids") or [])


def without_network(rows: list[dict], reached: dict[str, list[str]]) -> list[dict]:
    """The pairs in which neither side reached for the network: the addendum's sensitivity analysis."""
    out = {i for ids in reached.values() for i in ids}
    return [r for r in rows if r["instance_id"] not in out]


def task_flags(arm: str) -> pd.DataFrame:
    """Each task's flags for the splits: the screen's verdict, whether its fix edits code the graph holds, whether it
    was in the run of November 10, and what the arm's own shape table says of its context."""
    screen = pd.read_csv(TASKS_DIR / "screening" / "agent_screen_all.csv", usecols=["instance_id", "is_pass"])
    cover = pd.read_csv(TASKS_DIR / "graph_coverage.csv", usecols=["instance_id", "edited_node_count"])
    shape = pd.read_csv(TASKS_DIR / SHAPES[arm])
    out = screen.rename(columns={"is_pass": "is_screen_pass"}).merge(cover, on="instance_id", how="outer")
    out["is_edit_task"] = out.edited_node_count > 0
    out["is_first_sample"] = out.instance_id.isin(FIRST)
    if arm == "graph":
        shape["is_node_named"] = shape.named_node_count > 0
    keep = ["instance_id", "context_chars"] + [f for f in FLAGS[arm] if f in shape.columns]
    out = out.merge(shape[keep], on="instance_id", how="left").drop(columns=["edited_node_count"])
    for f in FLAGS[arm] + COMMON_FLAGS:   # true, false, or no value: never a number or a string
        out[f] = out[f].map(lambda v: None if pd.isna(v) else bool(v)).astype(object)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(SHAPES), help="the arm to set beside the statement arm")
    ap.add_argument("--ids", help="the pre-registered ids, comma-separated (default: every published task)")
    ap.add_argument("--machine", choices=("kaggle", *COLAB), default="kaggle",
                    help="colab: the pair run again on one Colab GPU (addendum 2, #687), from its own tables; "
                         "colab-l4: the same pair as a second session made it on an L4, described beside it")
    a = ap.parse_args()
    base, label, out_name = table_names(a.machine, a.arm)
    statement = pd.read_csv(RUNS / f"{MODEL}_swegemma_{base}.csv")
    other = pd.read_csv(RUNS / f"{MODEL}_swegemma_{label}.csv")
    flags = task_flags(a.arm)
    ids = [i.strip() for i in a.ids.split(",") if i.strip()] if a.ids else sorted(flags.instance_id)
    rows = pair_rows(ids, statement, other, flags, a.arm)
    out = RUNS / out_name
    frame = pd.DataFrame(rows)
    frame.to_csv(out, index=False)
    s = summary(rows, a.arm, FLAGS[a.arm] + COMMON_FLAGS)
    pairs = frame[frame.is_pair_run]
    means = {f"{name}_arm_{m}": round(float(pairs[f"{name}_arm_{m}"].mean()), 1) for m in MEASURES
             for name in ("statement", a.arm) if len(pairs) and pairs[f"{name}_arm_{m}"].notna().any()}
    extra = {}
    report_table = RUNS / f"{MODEL}_swegemma_report.csv"
    if a.machine == "kaggle" and a.arm == "graph" and report_table.exists():   # addendum 1: described only
        extra["graph_against_report"] = arm_cross(ids, pd.read_csv(report_table), other, "report", "graph")
    if a.machine in COLAB:
        reached = {name: network_ids(RUNS / f"{MODEL}_swegemma_{lab}_settings.json")
                   for name, lab in (("statement", base), (a.arm, label))}
        extra["network"] = {"instance_ids": reached,
                            "without_those_pairs": summary(without_network(rows, reached), a.arm, [])}
        for name, table in (("statement", statement), (a.arm, other)):   # each arm beside Kaggle's: described only
            kaggle = RUNS / f"{MODEL}_swegemma_{name}.csv"
            if kaggle.exists():
                extra[f"{name}_on_kaggle_and_on_colab"] = arm_cross(ids, pd.read_csv(kaggle), table, "kaggle", "colab")
        graph_here = RUNS / f"{MODEL}_swegemma_colab-graph.csv"
        if a.machine == "colab" and a.arm == "report" and graph_here.exists():   # addendum 3: described only
            extra["report_against_graph_on_colab"] = arm_cross(ids, pd.read_csv(graph_here), other, "graph", "report")
        for name, table in (("statement", statement), (a.arm, other)):
            first = RUNS / f"{MODEL}_swegemma_colab-{name}.csv"   # the registered pair's arm of the same text
            if a.machine != "colab" and first.exists():           # the two machines, task by task: described only
                extra[f"{name}_on_the_a100_and_on_the_l4"] = arm_cross(ids, pd.read_csv(first), table, "a100", "l4")
    print(json.dumps({**s, "means": means, **extra}, indent=1))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
