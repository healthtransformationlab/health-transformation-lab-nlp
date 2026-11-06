"""Run the Gemma agent on Kaggle GPUs, one task per kernel, and verify each patch here in the sandbox (spec 035 US2).

    python scripts/60_kaggle_agent.py --ids htlnlp_170,htlnlp_143,htlnlp_174 \\
        --agent-dir ~/gemma-developer-agent --snapshots ../data/tasks/snapshots

For each task: kaggle/agent_bundle.py builds a private dataset holding that task alone (no reference patch, no
tests, a one-commit snapshot); a private kernel (kaggle/agent_kernel.py, internet off, GPU) runs the agent beside
it and the model; its patch comes back and agent_harness.score_patch verifies it in the sandbox. On Kaggle nothing
can hide one attached file from the agent, so a kernel never carries a second task.

Each run uses a Kaggle GPU (the weekly allowance is shared: AGENTS.md, Branches and issues 6). Rows go to
data/tasks/agent_runs/<model>_kaggle.csv, merged by instance_id so a rerun replaces its task's row; the settings
each ran with are in <model>_kaggle_settings.json. Every number is measured with this repository's harness on
Kaggle's GPUs, NOT the competition's evaluator.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import agent_cost as ac
from health_transformation_lab_nlp import agent_harness as ah
from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

_spec = importlib.util.spec_from_file_location("run_agent", Path(__file__).resolve().parent / "59_run_agent.py")
run_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_agent)
_spec = importlib.util.spec_from_file_location("agent_bundle", REPO_ROOT / "kaggle" / "agent_bundle.py")
bundle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bundle)

OUT_DIR = TASKS_DIR / "agent_runs"
MODELS = {"gemma-4-e4b-it": "google/gemma-4/transformers/gemma-4-e4b-it/1"}
EXTRA = ["kaggle_kernel_url", "time_minutes", "max_new_tokens", "is_thinking", "is_cache_reused", "max_prompt_tokens",
         "prompt_token_count", "prefill_token_count", "output_token_count", "model_seconds", "load_seconds",
         "run_ts", "script_seconds", "session_seconds", "gpu_count", "allowance_hours", "kaggle_allowance_ratio", "gpu_hours",
         "estimated_cost_usd", "price_basis_text", "error_text"]   # the cost columns: spec 036 US2 (#569)
POLL_SECONDS, MAX_WAIT_SECONDS = 30, 4 * 3600
UPLOAD_TRIES, UPLOAD_RETRY_SECONDS = 4, 60


def kernel_slug(instance_id: str) -> str:
    """Not the dataset's slug: Kaggle refuses a kernel with the same slug as one of the owner's datasets (409)."""
    return bundle.slug(instance_id).replace("htlnlp-agent-", "htlnlp-run-", 1)


def kernel_metadata(username: str, slug: str, model_source: str) -> dict:
    """Private, GPU, internet off, and exactly one dataset: this task's bundle (slug is the bundle's)."""
    kslug = slug.replace("htlnlp-agent-", "htlnlp-run-", 1)
    return {"id": f"{username}/{kslug}", "title": kslug.replace("-", " "), "code_file": "agent_kernel.py",
            "language": "python",
            "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_tpu": False,
            "enable_internet": False, "dataset_sources": [f"{username}/{slug}"], "competition_sources": [],
            "kernel_sources": [], "model_sources": [model_source]}


def merge_rows(path: Path, rows: list[dict]) -> pd.DataFrame:
    """The table with these tasks' rows replaced (re-runnable), sorted by instance_id."""
    cols = ah.RUN_COLUMNS + EXTRA
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=cols)
    new = pd.DataFrame(rows, columns=cols)
    keep = old[~old["instance_id"].isin(new["instance_id"])]
    out = pd.concat([keep, new], ignore_index=True) if len(keep) else new
    return out.sort_values("instance_id").reset_index(drop=True)[cols]


def _wait_dataset(api, ref: str) -> None:
    for _ in range(MAX_WAIT_SECONDS // POLL_SECONDS):
        try:
            if str(api.dataset_status(ref)).lower().endswith("ready"):
                return
        except Exception:  # noqa: BLE001 - not listed yet
            pass
        time.sleep(POLL_SECONDS)
    raise SystemExit(f"{ref}: not ready after {MAX_WAIT_SECONDS} s")


def _upload_bundle(api, folder: Path, ref: str) -> None:
    try:
        api.dataset_status(ref)
        exists = True
    except Exception:  # noqa: BLE001 - a missing dataset is an HTTP error here
        exists = False
    for attempt in range(UPLOAD_TRIES):   # Kaggle sometimes drops a create (HTTP 499): it passes on a retry (#615)
        try:
            r = (api.dataset_create_version(str(folder), "This task's bundle", dir_mode="zip") if exists
                 else api.dataset_create_new(str(folder), public=False, dir_mode="zip"))
            break
        except Exception as e:  # noqa: BLE001 - the client raises plain HTTP errors
            if attempt == UPLOAD_TRIES - 1:
                raise
            print(f"upload of {ref} failed ({e}); trying again in {UPLOAD_RETRY_SECONDS} s", flush=True)
            time.sleep(UPLOAD_RETRY_SECONDS)
    if r is None or str(r.status).lower() != "ok":
        raise SystemExit(f"Kaggle refused {ref}: {getattr(r, 'error', None)}")
    time.sleep(10)
    _wait_dataset(api, ref)


def _run_kernel(api, folder: Path | None, ref: str, out: Path, max_seconds: int) -> dict:
    """Push (unless folder is None: collect a run already going) and wait. Kaggle stops the run at max_seconds, so
    a stuck kernel can't use up the GPU allowance."""
    if folder is not None:
        api.kernels_push(str(folder), timeout=str(max_seconds))
    status = ""
    for _ in range(MAX_WAIT_SECONDS // POLL_SECONDS):
        time.sleep(POLL_SECONDS)
        try:
            status = str(api.kernels_status(ref).status).lower()
        except Exception:  # noqa: BLE001 - a blip; the next poll tells
            continue
        if any(s in status for s in ("complete", "error", "cancel")):
            break
    out.mkdir(parents=True, exist_ok=True)
    api.kernels_output(ref, str(out), force=True)
    res = out / "result.json"
    if not res.exists():
        return {"error": f"kernel ended {status or 'without a status'} and wrote no result.json"}
    return json.loads(res.read_text())


def _script_seconds(result: dict) -> float | None:
    try:
        start, end = (pd.Timestamp(result[k]) for k in ("started_ts", "finished_ts"))
        return round((end - start).total_seconds(), 1)
    except (KeyError, ValueError, TypeError):
        return None


def row_for(task: dict, result: dict, snapshot: Path, work: Path, kernel_url: str, settings: dict,
            session_seconds: float | None = None, cost_settings: dict | None = None) -> dict:
    """Score the agent's patch here (sandbox required) and finish the task's row, with what it cost: a failed
    kernel used the allowance too (spec 036 FR-007)."""
    turns = result.get("turns") or []
    cost = ac.task_cost(session_seconds, len(result.get("gpus") or []) or 2,
                        cost_settings or ac.load_settings()) if session_seconds is not None else {}
    extra = {"kaggle_kernel_url": kernel_url, "time_minutes": settings["budget"]["time_minutes"],
             "max_new_tokens": settings["model"].get("max_new_tokens"), "is_thinking": settings["model"].get("thinking"),
             "is_cache_reused": settings["model"].get("reuse_cache", True),
             "max_prompt_tokens": max((t["prompt_tokens"] for t in turns), default=None),
             "prompt_token_count": sum(t["prompt_tokens"] for t in turns),
             "prefill_token_count": sum(t.get("prefill_tokens", t["prompt_tokens"]) for t in turns),
             "output_token_count": sum(t["output_tokens"] for t in turns),
             "model_seconds": round(sum(t["seconds"] for t in turns), 1), "load_seconds": result.get("load_seconds"),
             "script_seconds": _script_seconds(result), **cost, "error_text": result.get("error"),
             "run_ts": pd.Timestamp.now(tz="UTC").isoformat()}   # when it was scored: the weekly allowance budget
    if "row" not in result:
        return {"instance_id": task["instance_id"], "harness_name": ah.HARNESS_NAME, "model_name": settings["name"],
                "is_resolved": False, "reason_text": "kernel failed", **extra}
    row = ah.score_patch(task, result["row"], result.get("patch") or "", snapshot, work, sandboxed=True)
    return {**row, **extra}


def queue(ids: list[str], tasks: dict, past: dict[str, float]) -> dict[str, float]:
    """Each task's expected session seconds, in the order to run them: cheapest expected first; among tasks with no
    earlier run, the smaller reference fix first (it is never shown to the agent; it only orders the run)."""
    ordered = sorted(ids, key=lambda i: (ac.expected_seconds(i, past), len(tasks[i].get("patch") or "")))
    return {i: ac.expected_seconds(i, past) for i in ordered}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, default=TASKS_DIR / "tasks_gated.jsonl")
    ap.add_argument("--ids", required=True,
                    help="comma-separated instance ids (one Kaggle GPU run each), or 'all': every gated task the "
                         "calib:oracle resolves (spec 035 T004) that has no row yet (--rerun: every one)")
    ap.add_argument("--plan-only", action="store_true",
                    help="print the queue and the expected allowance hours, then stop: nothing is uploaded or run")
    ap.add_argument("--rerun", action="store_true", help="with --ids all: run tasks that already have a row too")
    ap.add_argument("--max-gpu-hours", type=float,
                    help="stop before the task that would take this run past this many hours of the Kaggle GPU "
                         "allowance (session time, as Kaggle counts it; spec 036 US2)")
    ap.add_argument("--agent-dir", type=Path, required=True, help="the submission folder (agent.yaml)")
    ap.add_argument("--snapshots", type=Path, default=TASKS_DIR / "snapshots")
    ap.add_argument("--graphs", type=Path, default=TASKS_DIR / "graphs")
    ap.add_argument("--embeddings", type=Path, default=TASKS_DIR / "embeddings")
    ap.add_argument("--model", choices=sorted(MODELS), default="gemma-4-e4b-it")
    ap.add_argument("--time-minutes", type=float, default=30.0,
                    help="the agent's time budget: 5 is the submission's, for the competition's GPUs; 2x T4 with "
                         "transformers runs about 8 tokens a second")
    ap.add_argument("--max-new-tokens", type=int, default=2048)
    ap.add_argument("--thinking", action="store_true", help="Gemma 4's thinking mode (slow on T4s)")
    ap.add_argument("--no-cache-reuse", action="store_true",
                    help="read the whole conversation every turn (as the pilot did), not only the new tokens")
    ap.add_argument("--collect", action="store_true",
                    help="don't upload or push: wait for each task's kernel already running, then score it")
    ap.add_argument("--work", type=Path, default=Path(os.environ.get("TMPDIR", "/tmp")) / "htl_kaggle_agent")
    a = ap.parse_args()
    # check every setting and input before any upload (AGENTS.md, configuration)
    if not a.plan_only and not ah.Sandbox.available():
        sys.exit("no unprivileged user namespaces here: the agent's patch is verified only in the sandbox")
    user = os.environ.get("KAGGLE_USERNAME") or "jcblearning"
    if not a.plan_only and not (os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY")):
        sys.exit("KAGGLE_API_TOKEN is not set (ops/secrets_register.yaml, Kaggle API token)")
    cost_settings = ac.load_settings()   # required: fails at once, naming the setting
    tasks = {t["instance_id"]: t for t in map(json.loads, filter(str.strip, a.tasks.read_text().splitlines()))}
    path = OUT_DIR / f"{a.model}_kaggle.csv"
    done = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["instance_id", "session_seconds"])
    if a.ids == "all":
        oracle = pd.read_csv(OUT_DIR / f"oracle_{a.tasks.stem}.csv")
        ids = sorted(oracle.loc[oracle["is_resolved"].astype(bool), "instance_id"])
        if not a.rerun:
            ids = [i for i in ids if i not in set(done["instance_id"])]
    else:
        ids = [i.strip() for i in a.ids.split(",") if i.strip()]
    missing = [i for i in ids if i not in tasks or not (a.snapshots / f"{i}.tgz").exists()]
    if missing:
        sys.exit(f"not in {a.tasks.name} or no snapshot: {', '.join(missing)}")
    instruction, tools, budget, unsupported = run_agent.agent_config(a.agent_dir)
    budget.time_minutes = a.time_minutes
    if unsupported:
        print(f"not supported by this harness, left out: {', '.join(unsupported)}")
    model_cfg = {"variant": a.model, "max_new_tokens": a.max_new_tokens, "thinking": a.thinking,
                 "max_context": 24576, "reuse_cache": not a.no_cache_reuse, "max_memory": {"0": "12GiB", "1": "13GiB"}}
    # probe 4 (Nov 2026): every weight on the GPUs (the 5.25 GiB per-layer embedding table can't be offloaded: it is
    # copied back on each forward and runs out of memory); a 24k-token prompt then peaks at 10.6 and 11.6 GiB
    settings = {"name": a.model, "model": model_cfg, "budget": budget.__dict__, "tools": tools,
                "left_out": unsupported, "harness_name": ah.HARNESS_NAME, "note": ah.HARNESS_NOTE,
                "hardware": "Kaggle GPU (2x T4), transformers fp16, internet off"}

    past = {r.instance_id: float(r.session_seconds) for r in done.itertuples()
            if "session_seconds" in done and pd.notna(r.session_seconds)}
    expected = queue(ids, tasks, past)
    ids = list(expected)
    if a.max_gpu_hours is not None:
        plan, left = ac.plan_under_cap(ids, expected, a.max_gpu_hours)
        print(f"cap {a.max_gpu_hours} allowance hours: {len(plan)} of {len(ids)} tasks fit, expected "
              f"{sum(expected[i] for i in plan) / 3600:.2f} h")
    if a.plan_only:
        total = sum(expected.values()) / 3600
        print(f"{len(ids)} tasks queued, expected {total:.1f} h of the Kaggle GPU allowance "
              f"({total / cost_settings['kaggle_weekly_allowance_hours']['value']:.0%} of a week's), est. "
              f"{total * 2 * cost_settings['t4_usd_per_gpu_hour']['value']:.2f} USD at a cloud's T4 price; first: "
              f"{', '.join(ids[:5])}")
        return 0
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    api.dataset_list(user=user, page=1)   # one cheap authenticated call before the uploads
    used = 0.0
    for n, iid in enumerate(ids, 1):
        if a.max_gpu_hours is not None and used + expected[iid] / 3600 > a.max_gpu_hours:
            print(f"stopping before {iid}: {used:.2f} h used, it would take the run past {a.max_gpu_hours} h; "
                  f"{len(ids) - n + 1} tasks left: {', '.join(ids[n - 1:])}")
            break
        task, slug = tasks[iid], bundle.slug(iid)
        kref = f"{user}/{kernel_slug(iid)}"
        work = a.work / iid
        k = None
        if not a.collect:
            stem = f"{task['repo'].split('/')[-1]}_{task['base_commit']}"
            shutil.rmtree(work, ignore_errors=True)
            b = bundle.build(task, a.snapshots / f"{iid}.tgz", a.graphs / f"{stem}.json",
                             a.embeddings / f"{stem}.npz", work / "bundle", instruction, tools, budget, user, model_cfg)
            print(f"[{n}/{len(ids)}] {iid}: uploading its bundle to {user}/{slug} (private)", flush=True)
            _upload_bundle(api, b, f"{user}/{slug}")
            k = work / "kernel"
            k.mkdir(parents=True)
            shutil.copyfile(REPO_ROOT / "kaggle" / "agent_kernel.py", k / "agent_kernel.py")
            (k / "kernel-metadata.json").write_text(json.dumps(kernel_metadata(user, slug, MODELS[a.model]), indent=1))
        print(f"[{n}/{len(ids)}] {iid}: the agent on a Kaggle GPU, {kref}", flush=True)
        t0 = time.monotonic()   # push to output: queue and boot included, so it errs high (the API gives no split)
        result = _run_kernel(api, k, kref, work / "output", int((a.time_minutes + 25) * 60))   # + load and setup
        session = time.monotonic() - t0
        used += session / 3600
        shutil.rmtree(work / "score", ignore_errors=True)
        row = row_for(task, result, a.snapshots / f"{iid}.tgz", work / "score",
                      f"https://www.kaggle.com/code/{kref}", settings, session, cost_settings)
        table = merge_rows(path, [row])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False)
        print(f"[{n}/{len(ids)}] {iid}: {'resolved' if row['is_resolved'] else row.get('reason_text')}"
              f" ({row.get('tool_call_count')} calls, {row.get('model_seconds')} s generating, "
              f"{session / 60:.1f} min of allowance, est. {row.get('estimated_cost_usd')} USD)", flush=True)
    (OUT_DIR / f"{a.model}_kaggle_settings.json").write_text(json.dumps(settings, indent=1) + "\n")
    t = pd.read_csv(path)
    print(f"\n{int(t['is_resolved'].sum())} of {len(t)} resolved -> {path.relative_to(REPO_ROOT)}; this run used "
          f"{used:.2f} h of the Kaggle GPU allowance\n{ah.HARNESS_NOTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
