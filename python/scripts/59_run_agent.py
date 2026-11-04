"""Run an agent over the task set with our re-implementation of the competition's documented harness (spec 035).

    python scripts/59_run_agent.py --model oracle                      # the 3 committed sample tasks
    python scripts/59_run_agent.py --model null --tasks ../data/tasks/tasks_gated.jsonl
    python scripts/59_run_agent.py --model oracle --agent-dir ~/gemma-developer-agent   # its prompt, tools, budgets

--model oracle replays each task's reference patch (should resolve every task) and --model null submits nothing
(should resolve none): calibration runs, named calib:oracle and calib:null, that prove the runner before a real
model is scored (spec 035 US2). The workspace comes from --snapshots (the published .tgz files) when given, or
else from this repository's own history (needs the full history: git fetch --unshallow origin).

Writes data/tasks/agent_runs/<model>_<tasks file>.csv (one row per task, agent_harness.RUN_COLUMNS) and prints the
resolution rate. Every number is measured with this repository's harness, NOT the competition's evaluator.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import yaml

from health_transformation_lab_nlp import agent_harness as ah
from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

OUT_DIR = TASKS_DIR / "agent_runs"
MODELS = {"oracle": ah.OracleModel, "null": ah.NullModel}


def _include_loader(base: Path):
    class Loader(yaml.SafeLoader):
        pass

    def include(loader, node):
        path = base / loader.construct_scalar(node)
        return path.read_text() if path.suffix in (".md", ".txt") else yaml.safe_load(path.read_text())

    Loader.add_constructor("!include", include)
    return Loader


def agent_config(agent_dir: Path | None) -> tuple[str, list[str], ah.Budget, list[str]]:
    """The root agent's instruction and declared tools, and the budgets, from a submission folder. Tools the
    runner doesn't have (agent_tool sub-agents, skills) are returned as not supported."""
    if agent_dir is None:
        return "", ah.ALL_TOOLS, ah.Budget(), []
    cfg = yaml.load((agent_dir / "agent.yaml").read_text(), Loader=_include_loader(agent_dir))
    tools, unsupported = [], []
    for t in cfg.get("tools") or []:
        (tools if isinstance(t, str) and t in ah.ALL_TOOLS else unsupported).append(t if isinstance(t, str)
                                                                                    else next(iter(t)))
    unsupported += [f"skill:{s}" for s in cfg.get("skills") or []]
    ev = agent_dir / "eval_config.yaml"
    budget = ah.Budget.from_eval_config(ev) if ev.exists() else ah.Budget()
    return cfg.get("instruction") or "", tools, budget, unsupported


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=sorted(MODELS))
    ap.add_argument("--tasks", type=Path, default=TASKS_DIR / "tasks_sample.jsonl")
    ap.add_argument("--agent-dir", type=Path, help="a submission folder (agent.yaml, eval_config.yaml)")
    ap.add_argument("--snapshots", type=Path, help="folder of <instance_id>.tgz; default: this repo's history")
    ap.add_argument("--graphs", type=Path, default=TASKS_DIR / "graphs")
    ap.add_argument("--embeddings", type=Path, default=TASKS_DIR / "embeddings")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sandbox", choices=["auto", "required", "off"],
                    help="default: required for a real model, auto for a calib: model (spec 035)")
    a = ap.parse_args()
    calib = MODELS[a.model].name.startswith("calib:")
    sandbox = a.sandbox or ("auto" if calib else "required")
    if sandbox != "required" and not calib:
        sys.exit("a real model runs only in the sandbox: it could otherwise read this repository and the host's secrets")
    if not a.tasks.exists():   # check inputs before any work (AGENTS.md, configuration)
        sys.exit(f"missing {a.tasks}: run scripts/55_build_tasks.py, or use the committed tasks_sample.jsonl")
    if a.agent_dir and not (a.agent_dir / "agent.yaml").exists():
        sys.exit(f"--agent-dir {a.agent_dir}: no agent.yaml")
    telemetry.setup()
    telemetry.start_script("59_run_agent", data_label="public")

    instruction, tools, budget, unsupported = agent_config(a.agent_dir)
    print(f"sandbox: {sandbox} ({'namespaces available' if ah.Sandbox.available() else 'no namespaces here'})")
    if unsupported:
        print(f"not supported by this harness, left out: {', '.join(unsupported)}")
    tasks = [json.loads(line) for line in a.tasks.read_text().splitlines() if line.strip()]
    if a.limit:
        tasks = tasks[: a.limit]
    rows = []
    for i, task in enumerate(tasks, 1):
        source = (a.snapshots / f"{task['instance_id']}.tgz") if a.snapshots else REPO_ROOT
        graph = ah.load_graph(task, a.graphs, a.embeddings)
        work = ah.workspace_tmp()
        try:
            row = ah.run_task(task, source, MODELS[a.model](), budget, work, instruction, tools, graph, sandbox)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        rows.append(row)
        print(f"[{i}/{len(tasks)}] {row['instance_id']}: {'resolved' if row['is_resolved'] else row['reason_text']}",
              flush=True)

    out = pd.DataFrame(rows, columns=ah.RUN_COLUMNS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{a.model}_{a.tasks.stem}.csv"
    out.to_csv(path, index=False)   # overwritten whole: re-runnable
    rate = out["is_resolved"].mean() if len(out) else 0.0
    print(f"\n{int(out['is_resolved'].sum())} of {len(out)} resolved ({rate:.0%}) with {MODELS[a.model].name} -> "
          f"{path.relative_to(REPO_ROOT)}\n{ah.HARNESS_NOTE}")
    telemetry.end_script()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
