"""Run the competition's own verification (swegemma.harness.verification.verify_task, unmodified) on a task set
with a chosen patch per task: empty ("null"), the reference patch ("oracle"), or patches from a JSONL file.

The Evaluator is built exactly as the swegemma command line builds it (subprocess sandbox), so the sandbox manager
and limits are the official ones. Only the source of the patch differs: the command line can run the agent or use an
empty patch (--skip-agent-patch); this calls the same verify_task with a given patch.
"""
import argparse, asyncio, json, os, sys, time
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
from swegemma.cli import _build_cli_model_registry
from swegemma.config import EvalConfig
from swegemma.deduplication import resolve_task_snapshot_paths
from swegemma.evaluate import Evaluator
from swegemma.harness.verification import verify_task
from swegemma.models import load_tasks

ap = argparse.ArgumentParser()
ap.add_argument("--tasks", type=Path, required=True)
ap.add_argument("--snapshots-dir", type=Path, required=True)
ap.add_argument("--submission-dir", type=Path, required=True)
ap.add_argument("--results-dir", type=Path, required=True)
ap.add_argument("--patch", choices=["null", "oracle", "file"], required=True)
ap.add_argument("--patch-file", type=Path, help="JSONL of {instance_id, patch} for --patch file")
ap.add_argument("--task-ids", nargs="*")
ap.add_argument("--concurrency", type=int, default=3)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()

config = EvalConfig(tasks_path=a.tasks, snapshots_dir=a.snapshots_dir, results_dir=a.results_dir,
                    submission_dir=a.submission_dir,
                    models=_build_cli_model_registry(submission_dir=a.submission_dir, models_yaml_path=None),
                    sandbox="subprocess", skip_agent_patch=(a.patch == "null"), display_mode="quiet")
ev = Evaluator(config)
tasks = load_tasks(a.tasks)
if a.task_ids:
    tasks = [t for t in tasks if t.instance_id in set(a.task_ids)]
given = {}
if a.patch == "file":
    given = {json.loads(l)["instance_id"]: json.loads(l)["patch"] for l in a.patch_file.read_text().splitlines() if l.strip()}
    tasks = [t for t in tasks if t.instance_id in given]

async def one(task, sem):
    async with sem:
        snap, base, pp = resolve_task_snapshot_paths(config.snapshots_dir, task.instance_id, task.repo)
        patch = "" if a.patch == "null" else (task.patch if a.patch == "oracle" else given[task.instance_id])
        t0 = time.perf_counter()
        try:
            r = await verify_task(ev.docker, config, task, snap, base_snapshot_path=base, patch_path=pp,
                                  agent_patch=patch, start_time=t0)
            out = r.test_output or ""
            row = {"instance_id": task.instance_id, "patch_kind": a.patch, "resolved": bool(r.resolved),
                   "test_exit_code": r.test_exit_code, "error": r.error, "seconds": round(time.perf_counter() - t0, 1),
                   "output_tail": out[-int(os.environ.get("TAIL", "1500")):]}
        except Exception as e:  # a setup failure is a row too
            row = {"instance_id": task.instance_id, "patch_kind": a.patch, "resolved": False, "test_exit_code": None,
                   "error": f"{type(e).__name__}: {e}"[:400], "seconds": round(time.perf_counter() - t0, 1), "output_tail": ""}
        return row

async def main():
    sem = asyncio.Semaphore(a.concurrency)
    rows = await asyncio.gather(*(one(t, sem) for t in tasks))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r) + "\n" for r in sorted(rows, key=lambda r: r["instance_id"])))
    print(a.patch, "tasks", len(rows), "resolved", sum(r["resolved"] for r in rows))

asyncio.run(main())
