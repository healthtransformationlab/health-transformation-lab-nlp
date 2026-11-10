"""The Gemma agent at fuller settings on a Colab GPU (spec 035 US2, #656): the same one-task bundles as Kaggle, a
notebook that runs them one at a time, and the patches scored here in the sandbox.

    python scripts/62_colab_agent.py bundles --ids <id,...> --agent-dir ~/gemma-developer-agent --published <dir>
    # then open kaggle/colab_agent.ipynb in Colab (A100), Run all; it versions jcblearning/htlnlp-colab-results
    python scripts/62_colab_agent.py score --published <dir>

`--published` is the downloaded task set (jcblearning/health-transformation-lab-coding-agent-tasks): its tasks.jsonl,
snapshots, graphs and embeddings, the files the paper's 93 tasks were verified on. Each bundle is a private dataset
`htlnlp-colab-<id>` holding that task alone (kaggle/agent_bundle.py: no reference patch, no tests, one commit), so the
notebook never has two tasks' files at once. Rows go to data/tasks/agent_reruns/<model>_larger_budget.csv: each
task's run under the tight limits (its row in agent_runs/<model>_kaggle.csv) beside its run here, with the calls to
the graph tools counted from the transcript. Not to agent_runs/: that folder feeds fact_agent_task_run and the Kaggle
allowance check, and a Colab run is neither. Measured with this repository's harness, NOT the competition's evaluator.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import agent_harness as ah
from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

_spec = importlib.util.spec_from_file_location("kaggle_agent", Path(__file__).resolve().parent / "60_kaggle_agent.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

USER = "jcblearning"
RESULTS = f"{USER}/htlnlp-colab-results"
MODEL = "gemma-4-e4b-it"
# The submission's settings where one card allows them (gemma-developer-agent configs/: 16,384 output tokens,
# thinking on) and the rulebook's 100 calls, 500 turns, 300 s a command; 20 minutes a task (not the rulebook's 60) so
# 48 tasks fit in Colab Pro+'s 24 hours. The notebook sets max_context from the card's memory.
BUDGET = ah.Budget(tool_calls=100, time_minutes=20.0, turns=500, command_timeout=300)
MODEL_CFG = {"variant": MODEL, "max_new_tokens": 16384, "thinking": True, "reuse_cache": True}


PAIRED = TASKS_DIR / "agent_reruns" / f"{MODEL}_larger_budget.csv"
PAIRED_COLUMNS = ["instance_id", "tier_code", "tight_run_ts", "is_tight_resolved", "tight_patch_bytes",
                  "tight_tool_call_count", "larger_run_ts", "is_larger_resolved", "larger_patch_bytes",
                  "larger_tool_call_count", "larger_graph_tool_call_count", "larger_max_output_token_count",
                  "larger_over_context_turn_count", "larger_task_seconds", "larger_reason_text", "larger_gpu_name"]


def graph_tool_calls(history: list[dict]) -> int:
    """Calls to the three graph tools in a run's transcript."""
    return sum(((c.get("function") or c).get("name") in ah.GRAPH_TOOLS)
               for m in history or [] for c in m.get("tool_calls") or [])


def paired_row(row: dict, result: dict, tight: dict, tier_code: str) -> dict:
    """One task: its run under the tight limits beside its run with the larger budget."""
    outs = [t.get("output_tokens", 0) for t in result.get("turns") or []]
    return {"instance_id": row["instance_id"], "tier_code": tier_code,
            "tight_run_ts": tight.get("run_ts"), "is_tight_resolved": bool(tight.get("is_resolved")),
            "tight_patch_bytes": int(tight.get("agent_patch_bytes") or 0),
            "tight_tool_call_count": int(tight.get("tool_call_count") or 0),
            "larger_run_ts": result.get("finished_ts") or row.get("run_ts"),   # when it ran, not when it was scored
            "is_larger_resolved": bool(row.get("is_resolved")),
            "larger_patch_bytes": int(row.get("agent_patch_bytes") or 0),
            "larger_tool_call_count": int(row.get("tool_call_count") or 0),
            "larger_graph_tool_call_count": graph_tool_calls(result.get("history") or []),
            "larger_max_output_token_count": max(outs, default=0),
            # turns the model could not take: the prompt was past the context that fits on the card
            "larger_over_context_turn_count": sum(bool(t.get("over_context")) for t in result.get("turns") or []),
            "larger_task_seconds": result.get("task_seconds"), "larger_reason_text": row.get("reason_text"),
            "larger_gpu_name": ", ".join(result.get("gpus") or [])}


def colab_slug(instance_id: str) -> str:
    return runner.bundle.slug(instance_id).replace("htlnlp-agent-", "htlnlp-colab-", 1)


def _tasks(published: Path) -> dict:
    return {t["instance_id"]: t for t in map(json.loads, filter(str.strip, (published / "tasks.jsonl").read_text()
                                                                     .splitlines()))}


def bundles(a) -> int:
    from kaggle.api.kaggle_api_extended import KaggleApi
    tasks = _tasks(a.published)
    ids = [i.strip() for i in a.ids.split(",") if i.strip()]
    missing = [i for i in ids if i not in tasks]
    if missing:
        sys.exit(f"not in the published tasks.jsonl: {', '.join(missing)}")
    instruction, tools, _, unsupported = runner.run_agent.agent_config(a.agent_dir)
    runner.check_graphs([tasks[i] for i in ids], a.published / "graphs", a.published / "embeddings", tools)
    api = KaggleApi()
    api.authenticate()
    for n, iid in enumerate(ids, 1):
        task = tasks[iid]
        with tempfile.TemporaryDirectory() as tmp:
            out = runner.bundle.build(task, a.published / "snapshots" / f"{iid}.tgz",
                                      *runner.graph_files(task, a.published / "graphs", a.published / "embeddings"),
                                      Path(tmp) / "bundle", instruction, tools, BUDGET, USER, MODEL_CFG)
            meta = json.loads((out / "dataset-metadata.json").read_text())
            meta.update(id=f"{USER}/{colab_slug(iid)}", title=f"htlnlp colab input {iid}"[:50])
            (out / "dataset-metadata.json").write_text(json.dumps(meta, indent=1) + "\n")
            print(f"[{n}/{len(ids)}] {iid} -> {meta['id']} (private)", flush=True)
            runner._upload_bundle(api, out, meta["id"])
    (a.out / "colab_ids.txt").write_text(",".join(ids) + "\n")
    print(f"left out (not supported by this harness): {', '.join(unsupported) or 'none'}")
    return 0


def score(a) -> int:
    from kaggle.api.kaggle_api_extended import KaggleApi
    tasks = _tasks(a.published)
    tight = pd.read_csv(TASKS_DIR / "agent_runs" / f"{MODEL}_kaggle.csv").set_index("instance_id")
    tiers = pd.read_csv(TASKS_DIR / "task_manifest.csv", usecols=["instance_id", "tier_code"]).set_index("instance_id")
    api = KaggleApi()
    api.authenticate()
    got = Path(tempfile.mkdtemp())
    api.dataset_download_files(RESULTS, path=str(got), unzip=True, quiet=True)
    rows = []
    for f in sorted(got.glob("*.json")):
        result = json.loads(f.read_text())
        iid = result.get("instance_id") or f.stem
        settings = {"name": MODEL, "model": {**MODEL_CFG, **(result.get("settings") or {})},
                    "budget": BUDGET.__dict__}
        work = got / "score" / iid
        shutil.rmtree(work, ignore_errors=True)
        row = runner.row_for(tasks[iid], result, a.published / "snapshots" / f"{iid}.tgz", work,
                             f"https://www.kaggle.com/datasets/{RESULTS}", settings)
        rows.append(paired_row(row, result, tight.loc[iid].to_dict(), tiers["tier_code"].get(iid)))
        print(f"{iid}: {'resolved' if row['is_resolved'] else row.get('reason_text')}", flush=True)
    table = pd.DataFrame(rows, columns=PAIRED_COLUMNS).sort_values("instance_id")
    PAIRED.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(PAIRED, index=False)   # overwritten whole: re-runnable
    print(f"\n{len(table)} tasks: larger budget resolved {int(table['is_larger_resolved'].sum())}, tight limits "
          f"{int(table['is_tight_resolved'].sum())}; graph-tool calls {int(table['larger_graph_tool_call_count'].sum())} of "
          f"{int(table['larger_tool_call_count'].sum())} -> {PAIRED.relative_to(REPO_ROOT)}\n{ah.HARNESS_NOTE}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bundles")
    b.add_argument("--ids", required=True)
    b.add_argument("--agent-dir", type=Path, required=True)
    b.add_argument("--published", type=Path, required=True)
    b.add_argument("--out", type=Path, default=Path("."))
    s = sub.add_parser("score")
    s.add_argument("--published", type=Path, required=True)
    a = ap.parse_args()
    return bundles(a) if a.cmd == "bundles" else score(a)


if __name__ == "__main__":
    raise SystemExit(main())
