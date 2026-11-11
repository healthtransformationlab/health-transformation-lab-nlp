"""The same tasks with and without a failing test's report, side by side (028 AI7, #674).

Reads the two arms' tables (`..._swegemma_statement.csv` and `..._swegemma_report.csv`, written by
kaggle/official_agent_run.py --label), and writes data/tasks/official_agent_runs/context_pairs.csv: one row per task
with both arms' verdicts and costs. Prints the analysis the pre-registration names
(specs/028-dataops-task-set/preregistration-failing-test-report.md): each arm's resolved count with its Wilson
interval, the paired table, and the exact McNemar test, two-sided.

    python scripts/70_context_pairs.py --ids <the pre-registered ids, comma-separated> --first <the first 20>

The report comes from each task's hidden test: the context a test-first workflow has, not a benchmark condition.
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
OUT = RUNS / "context_pairs.csv"
MEASURES = ["agent_patch_bytes", "tool_call_count", "graph_tool_call_count", "prompt_token_count",
            "output_token_count", "agent_seconds"]
COLUMNS = (["instance_id", "tier_code", "is_first_sample", "is_import_error", "is_screen_pass", "context_chars",
            "is_pair_run", "is_statement_resolved", "is_report_resolved"]
           + [f"{arm}_{m}" for m in MEASURES for arm in ("statement", "report")])


def mcnemar_exact(b: int, c: int) -> float:
    """The exact McNemar test, two-sided: a binomial test, at one half, on the discordant pairs (b one way, c the
    other). 1.0 when there are none."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def _value(v):
    return None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)


def pair_rows(ids: list[str], statement: pd.DataFrame, report: pd.DataFrame, shape: pd.DataFrame,
              screen: pd.DataFrame, first: set[str]) -> list[dict]:
    """One row per pre-registered task: both arms' verdicts and measures, and what the splits need. A task missing
    from an arm's table was not run in it: the row stays, with `is_pair_run` false."""
    arms = {"statement": statement.set_index("instance_id"), "report": report.set_index("instance_id")}
    shape, screen = shape.set_index("instance_id"), screen.set_index("instance_id")
    rows = []
    for iid in ids:
        ran = {arm: iid in t.index for arm, t in arms.items()}
        any_arm = next((t for arm, t in arms.items() if ran[arm]), None)
        row = {"instance_id": iid, "tier_code": any_arm.loc[iid, "tier_code"] if any_arm is not None else None,
               "is_first_sample": iid in first,
               "is_import_error": bool(shape.loc[iid, "is_import_error"]) if iid in shape.index else None,
               "is_screen_pass": bool(screen.loc[iid, "is_pass"]) if iid in screen.index else None,
               "context_chars": _value(shape.loc[iid, "context_chars"]) if iid in shape.index else None,
               "is_pair_run": all(ran.values())}
        for arm, t in arms.items():
            row[f"is_{arm}_resolved"] = bool(t.loc[iid, "is_resolved"]) if ran[arm] else None
        for m in MEASURES:
            for arm, t in arms.items():
                row[f"{arm}_{m}"] = _value(t.loc[iid, m]) if ran[arm] and m in t.columns else None
        rows.append(row)
    return rows


def _of(rows: list[dict]) -> str:
    return f"{sum(bool(r['is_report_resolved']) for r in rows)} of {len(rows)}"


def summary(rows: list[dict]) -> dict:
    """The pre-registered analysis over the pairs both arms ran, and the splits it only describes."""
    pairs = [r for r in rows if r["is_pair_run"]]
    n = len(pairs)
    s_only = sum(bool(r["is_statement_resolved"]) and not r["is_report_resolved"] for r in pairs)
    r_only = sum(bool(r["is_report_resolved"]) and not r["is_statement_resolved"] for r in pairs)
    both = sum(bool(r["is_statement_resolved"]) and bool(r["is_report_resolved"]) for r in pairs)
    p = mcnemar_exact(s_only, r_only)

    def pct(k: int) -> list[float]:
        return [round(100 * v, 1) for v in wilson_ci(k, n)] if n else [None, None]

    return {"pair_count": n, "left_out_count": len(rows) - n,
            "statement_resolved_count": both + s_only, "report_resolved_count": both + r_only,
            "statement_wilson_pct": pct(both + s_only), "report_wilson_pct": pct(both + r_only),
            "both_count": both, "statement_only_count": s_only, "report_only_count": r_only,
            "neither_count": n - both - s_only - r_only, "mcnemar_exact_p": p, "is_difference_claimed": p < 0.05,
            "report_resolved_with_import_error": _of([r for r in pairs if r["is_import_error"]]),
            "report_resolved_without_import_error": _of([r for r in pairs if not r["is_import_error"]]),
            "report_resolved_screen_pass": _of([r for r in pairs if r["is_screen_pass"]]),
            "report_resolved_screen_fail": _of([r for r in pairs if not r["is_screen_pass"]]),
            "report_resolved_first_sample": _of([r for r in pairs if r["is_first_sample"]]),
            "report_resolved_added_sample": _of([r for r in pairs if not r["is_first_sample"]])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="the pre-registered ids, comma-separated")
    ap.add_argument("--first", required=True, help="the ids of the first sample (the run of November 10)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    ids = [i.strip() for i in a.ids.split(",") if i.strip()]
    first = {i.strip() for i in a.first.split(",") if i.strip()}
    statement = pd.read_csv(RUNS / f"{MODEL}_swegemma_statement.csv")
    report = pd.read_csv(RUNS / f"{MODEL}_swegemma_report.csv")
    rows = pair_rows(ids, statement, report, pd.read_csv(TASKS_DIR / "failure_report_shape.csv"),
                     pd.read_csv(TASKS_DIR / "screening" / "agent_screen_all.csv"), first)
    pd.DataFrame(rows, columns=COLUMNS).to_csv(a.out, index=False)
    s = summary(rows)
    pairs = pd.DataFrame([r for r in rows if r["is_pair_run"]], columns=COLUMNS)
    means = {f"{arm}_{m}": round(float(pairs[f"{arm}_{m}"].mean()), 1) for m in MEASURES for arm in ("statement", "report")
             if len(pairs) and pairs[f"{arm}_{m}"].notna().any()}
    print(json.dumps({**s, "means": means}, indent=1))
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
