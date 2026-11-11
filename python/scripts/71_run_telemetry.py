"""What a kernel's spans and GPU samples say about each task (036 US2, #569; 028 AI4, #668).

A batch kernel run with --telemetry keeps the agent framework's OpenTelemetry spans (numbers and short labels only)
and samples its GPUs. This rolls them up beside the run's table:

- `<table>_task_sections.csv`: one row per task and code section, with the section's self time (a span's time
  less its children's, so each second of a task is counted once), its span count and its tokens;
- `<table>_sections.csv`: the same over all tasks, with each section's share of the time;
- `<table>_gpu.csv`: one row per task with its seconds, GPU-hours, mean utilization, peak memory, energy, and an
  estimated cost when ops/cost_settings.yaml declares a price for that GPU. Kaggle's GPUs are free: the cost is
  what the same GPU time would cost on a cloud, never anything paid.

    python scripts/71_run_telemetry.py --output <the kernel's output folder> --summary <run_summary.json> \\
        --table data/tasks/official_agent_runs/<table>.csv

Names, counts and seconds only: no prompt, reply, path or task text.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

TASK_SPAN = "official_agent_kernel.task"
SECTION_COLUMNS = ["instance_id", "section_name", "span_count", "self_seconds", "input_token_count",
                   "output_token_count"]
ROLLUP_COLUMNS = ["section_name", "task_count", "span_count", "self_seconds", "time_share_pct", "input_token_count",
                  "output_token_count"]
GPU_COLUMNS = ["instance_id", "task_seconds", "gpu_count", "gpu_hours", "avg_gpu_utilization_pct",
               "max_gpu_memory_used_mb", "gpu_energy_wh", "estimated_cost_usd", "price_basis_text"]
PRICE_KEYS = {"Tesla T4": "t4_usd_per_gpu_hour", "NVIDIA L4": "l4_usd_per_gpu_hour"}


def section_of(name: str) -> str:
    """The code section a span belongs to, by its name."""
    if name.startswith("generate_content") or name == "call_llm":
        return "model call"
    if name.startswith("execute_tool "):
        return "tool " + name.split(" ", 1)[1]
    if name.startswith("invoke_agent "):
        return "agent " + name.split(" ", 1)[1]
    if name.startswith("compact_events"):
        return "context compaction"
    if name == TASK_SPAN:
        return "harness"
    if name == "invocation":
        return "agent loop"
    return "other"


def _seconds(span: dict) -> float:
    start, end = (datetime.fromisoformat(span[k].replace("Z", "+00:00")) for k in ("start_time", "end_time"))
    return (end - start).total_seconds()


def task_sections(spans: list[dict]) -> list[dict]:
    """One row per task and section: self time (the span's seconds less its direct children's), spans and tokens. A
    model call is two spans (`call_llm` around `generate_content`) and is counted once; its tokens come from the
    inner one. A span belongs to the task whose span is its root."""
    by_id = {s["context"]["span_id"]: s for s in spans}
    child_seconds: dict[str, float] = defaultdict(float)
    for s in spans:
        if s.get("parent_id") in by_id:
            child_seconds[s["parent_id"]] += _seconds(s)

    def task_of(s: dict) -> str | None:
        for _ in range(64):
            if s["name"] == TASK_SPAN:
                return (s.get("attributes") or {}).get("instance_id")
            s = by_id.get(s.get("parent_id"))
            if s is None:
                return None
        return None

    rows: dict[tuple[str, str], dict] = {}
    for s in spans:
        iid = task_of(s)
        if iid is None:
            continue
        section = section_of(s["name"])
        row = rows.setdefault((iid, section), {"instance_id": iid, "section_name": section, "span_count": 0,
                                               "self_seconds": 0.0, "input_token_count": 0, "output_token_count": 0})
        row["self_seconds"] += max(0.0, _seconds(s) - child_seconds[s["context"]["span_id"]])
        row["span_count"] += 0 if s["name"].startswith("generate_content") else 1
        attributes = s.get("attributes") or {}
        row["input_token_count"] += int(attributes.get("gen_ai.usage.input_tokens") or 0)
        row["output_token_count"] += int(attributes.get("gen_ai.usage.output_tokens") or 0)
    return [dict(r, self_seconds=round(r["self_seconds"], 3)) for _, r in sorted(rows.items())]


def rollup(rows: list[dict]) -> list[dict]:
    """Each section over all tasks, with its share of all the time, largest first."""
    total = sum(r["self_seconds"] for r in rows) or 1.0
    out: dict[str, dict] = {}
    for r in rows:
        o = out.setdefault(r["section_name"], {"section_name": r["section_name"], "tasks": set(), "span_count": 0,
                                               "self_seconds": 0.0, "input_token_count": 0, "output_token_count": 0})
        o["tasks"].add(r["instance_id"])
        for k in ("span_count", "self_seconds", "input_token_count", "output_token_count"):
            o[k] += r[k]
    return [{"section_name": o["section_name"], "task_count": len(o["tasks"]), "span_count": o["span_count"],
             "self_seconds": round(o["self_seconds"], 1), "time_share_pct": round(100 * o["self_seconds"] / total, 2),
             "input_token_count": o["input_token_count"], "output_token_count": o["output_token_count"]}
            for o in sorted(out.values(), key=lambda o: -o["self_seconds"])]


def gpu_rows(gpu: dict, task_seconds: dict, gpu_count: int, usd_per_gpu_hour: float | None,
             price_basis_text: str) -> list[dict]:
    """One row per task: its time on the GPUs as GPU-hours, what the samples say, and the estimate."""
    rows = []
    for iid in sorted(gpu):
        g, seconds = gpu[iid], task_seconds.get(iid)
        hours = round(seconds * gpu_count / 3600, 4) if seconds is not None else None
        rows.append({"instance_id": iid, "task_seconds": seconds, "gpu_count": gpu_count, "gpu_hours": hours,
                     "avg_gpu_utilization_pct": g.get("avg_gpu_utilization_pct"),
                     "max_gpu_memory_used_mb": g.get("max_gpu_memory_used_mb"), "gpu_energy_wh": g.get("gpu_energy_wh"),
                     "estimated_cost_usd": round(hours * usd_per_gpu_hour, 4)
                     if hours is not None and usd_per_gpu_hour is not None else None,
                     "price_basis_text": price_basis_text})
    return rows


def declared_price(gpu_name: str | None) -> tuple[float | None, str]:
    """The declared price of one hour of this GPU and where it comes from, or none with the reason."""
    settings = yaml.safe_load((REPO_ROOT / "ops" / "cost_settings.yaml").read_text())
    entry = settings.get(PRICE_KEYS.get(gpu_name or "", ""))
    if not entry:
        return None, f"no price declared for {gpu_name} in ops/cost_settings.yaml; Kaggle's GPUs are free"
    return float(entry["value"]), (f"estimate: {entry['value']} USD per {gpu_name} GPU-hour ({entry['source']}, read "
                                   f"{entry['read_date']}); Kaggle's GPUs are free")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True, help="the kernel's output folder (telemetry.jsonl)")
    ap.add_argument("--summary", type=Path, required=True, help="the run's run_summary.json (its GPU readings)")
    ap.add_argument("--table", type=Path, required=True, help="the run's committed table; the new ones sit beside it")
    a = ap.parse_args()
    spans = [json.loads(line) for line in (a.output / "telemetry.jsonl").read_text().splitlines() if line.strip()]
    sections = task_sections(spans)
    table = pd.read_csv(a.table)
    known = set(table.instance_id)
    sections = [r for r in sections if r["instance_id"] in known]
    stem = a.table.with_suffix("")
    pd.DataFrame(sections, columns=SECTION_COLUMNS).to_csv(f"{stem}_task_sections.csv", index=False)
    roll = rollup(sections)
    pd.DataFrame(roll, columns=ROLLUP_COLUMNS).to_csv(f"{stem}_sections.csv", index=False)
    seconds = {(s.get("attributes") or {}).get("instance_id"): round(_seconds(s), 1) for s in spans if s["name"] == TASK_SPAN}
    gpu = {i: g for i, g in (json.loads(a.summary.read_text()).get("gpu") or {}).items() if i in known}
    name = table.gpu_name.dropna().iloc[0] if table.gpu_name.notna().any() else None
    count = int(table.gpu_count.dropna().iloc[0]) if table.gpu_count.notna().any() else 0
    price, basis = declared_price(name)
    rows = gpu_rows(gpu, seconds, count, price, basis)
    pd.DataFrame(rows, columns=GPU_COLUMNS).to_csv(f"{stem}_gpu.csv", index=False)
    print(pd.DataFrame(roll, columns=ROLLUP_COLUMNS).to_string(index=False))
    g = pd.DataFrame(rows, columns=GPU_COLUMNS)
    print(json.dumps({"task_count": len(g), "gpu_hours": round(float(g.gpu_hours.sum()), 2),
                      "gpu_energy_wh": round(float(g.gpu_energy_wh.sum()), 1),
                      "avg_gpu_utilization_pct": round(float(g.avg_gpu_utilization_pct.mean()), 1),
                      "median_task_seconds": float(g.task_seconds.median()), "price_basis_text": basis}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
