"""Run the agent through the competition's OWN evaluator on Kaggle GPUs, one task per private kernel, and verify
each patch with the same evaluator here (spec 028 US5, T011b, #636).

    python kaggle/official_agent_run.py --dataset <published dataset dir> --agent-dir ~/gemma-developer-agent \\
        --sample 20 --seed 20261110 --plan-only          # print the draw; nothing is uploaded or run
    python kaggle/official_agent_run.py ... --sample 20 --seed 20261110 --work <dir>      # run and collect
    python kaggle/official_agent_run.py ... --ids htlnlp_143 --work <dir>                 # a pilot

For each task: kaggle/official_agent_bundle.py builds a private dataset with that task alone in the evaluator's
layout (no reference patch, no tests); a private kernel (kaggle/official_agent_kernel.py, internet off, GPU) installs
the competition's wheelhouse, serves the model with vLLM and calls swegemma's Evaluator.evaluate_task, as the
competition's starter notebook does. The patch comes back and swegemma's verify_task scores it here against the
published snapshot and the task's tests (the same call as kaggle/official_verify.py).

The sample is drawn with a seed and stratified by fidelity tier (`sample`), never ordered by cost. Each run uses a
Kaggle GPU: the weekly allowance is shared, so a run waits for the owner (AGENTS.md, Branches and issues 6).

Rows go to data/tasks/official_agent_runs/<model>_swegemma.csv (COLUMNS), the settings to its _settings.json.
Needs KAGGLE_API_TOKEN, and an interpreter that has the evaluator's wheels and this repository's test dependencies.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
OUT_DIR = REPO_ROOT / "data" / "tasks" / "official_agent_runs"
WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"                 # the competition's evaluator and vLLM
MODEL_SOURCE = "google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2"      # as the starter notebook attaches it
STARTER_MACHINE_SHAPE = "NvidiaL4"                                       # the starter notebook's accelerator
POLL_SECONDS, UPLOAD_TRIES, UPLOAD_RETRY_SECONDS = 30, 4, 60
COLUMNS = ["instance_id", "tier_code", "harness_name", "model_name", "is_resolved", "test_exit_code", "reason_text",
           "agent_patch_bytes", "tool_call_count", "llm_call_count", "agent_seconds", "load_seconds",
           "session_seconds", "gpu_count", "gpu_name", "command_timeout_seconds", "max_tool_calls", "max_time_minutes",
           "max_turns", "max_output_tokens", "thinking_budget", "kaggle_kernel_url", "run_ts", "error_text"]

_spec = importlib.util.spec_from_file_location("official_agent_bundle", HERE / "official_agent_bundle.py")
bundle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bundle)


def sample(tiers: dict[str, str], n: int, seed: int) -> list[str]:
    """`n` task ids drawn with `seed`, stratified by tier in proportion to each tier's size (largest remainder),
    returned sorted. The order of `tiers` does not matter; nothing about a task's cost or size does either."""
    if n > len(tiers):
        raise SystemExit(f"asked for {n} tasks, only {len(tiers)} to draw from")
    groups: dict[str, list[str]] = {}
    for iid, tier in tiers.items():
        groups.setdefault(tier, []).append(iid)
    quota = {t: n * len(ids) / len(tiers) for t, ids in groups.items()}
    take = {t: int(q) for t, q in quota.items()}
    for t in sorted(groups, key=lambda t: (-(quota[t] - take[t]), t))[: n - sum(take.values())]:
        take[t] += 1
    rng = random.Random(seed)
    drawn: list[str] = []
    for t in sorted(groups):
        drawn += rng.sample(sorted(groups[t]), take[t])
    return sorted(drawn)


def kernel_slug(instance_id: str) -> str:
    """Not the bundle's slug: Kaggle refuses a kernel with the same slug as one of the owner's datasets."""
    return "htlnlp-offrun-" + re.sub(r"[^a-z0-9]+", "-", instance_id.lower()).strip("-")


def kernel_metadata(username: str, instance_id: str, machine_shape: str | None, docker_image: str | None) -> dict:
    """Private, GPU, internet off; this task's bundle, the competition's wheelhouse and the model, nothing else."""
    kslug = kernel_slug(instance_id)
    meta = {"id": f"{username}/{kslug}", "title": kslug.replace("-", " "), "code_file": "official_agent_kernel.py",
            "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_tpu": False,
            "enable_internet": False, "dataset_sources": [f"{username}/{bundle.slug(instance_id)}", WHEELHOUSE],
            "competition_sources": [], "kernel_sources": [], "model_sources": [MODEL_SOURCE]}
    if machine_shape:
        meta["machine_shape"] = machine_shape
    if docker_image:
        meta.update(docker_image=docker_image, docker_image_pinning_type="original")
    return meta


def row_for(result: dict, verdict: dict | None, tier: str, kernel_url: str, session_seconds: float | None) -> dict:
    """One table row: what the evaluator's agent phase did on Kaggle, and its verification's verdict on the patch."""
    budgets, server = result.get("budgets") or {}, result.get("server") or {}
    gen = result.get("generation_defaults") or {}
    gpus = server.get("gpus") or []
    version = (result.get("versions") or {}).get("swegemma")
    harness = result.get("harness_name") or "swegemma"
    row = {
        "instance_id": result.get("instance_id"), "tier_code": tier,
        "harness_name": harness.replace("swegemma", f"swegemma {version}", 1) if version else harness,
        "model_name": result.get("model_name"), "is_resolved": bool(verdict and verdict.get("resolved")),
        "test_exit_code": verdict.get("test_exit_code") if verdict else None,
        "reason_text": "", "agent_patch_bytes": len((result.get("patch") or "").encode()),
        "tool_call_count": result.get("tool_call_count"), "llm_call_count": result.get("llm_call_count"),
        "agent_seconds": result.get("agent_phase_seconds"), "load_seconds": result.get("load_seconds"),
        "session_seconds": round(session_seconds, 1) if session_seconds is not None else None,
        "gpu_count": len(gpus) or None, "gpu_name": gpus[0] if gpus else None,
        "command_timeout_seconds": budgets.get("timeout_seconds"), "max_tool_calls": budgets.get("max_tool_calls"),
        "max_time_minutes": budgets.get("max_time_minutes"), "max_turns": budgets.get("max_turns"),
        "max_output_tokens": gen.get("max_output_tokens"),
        "thinking_budget": (gen.get("thinking_config") or {}).get("thinking_budget"),
        "kaggle_kernel_url": kernel_url, "run_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "error_text": result.get("error") or result.get("agent_error"),
    }
    if "error" in result or "patch" not in result:
        row["reason_text"] = "kernel failed"
    elif not row["agent_patch_bytes"]:
        row["reason_text"] = "empty patch"
    elif verdict is None:
        row["reason_text"] = "not verified"
    elif not row["is_resolved"]:
        row["reason_text"] = (verdict.get("error") or {1: "tests fail with the agent's patch",
                                                       2: "errors before any test ran"}.get(
            verdict.get("test_exit_code"), f"exit code {verdict.get('test_exit_code')}"))[:200]
    return {c: row[c] for c in COLUMNS}


def _wait_dataset(api, ref: str, max_seconds: int = 1800) -> None:
    for _ in range(max_seconds // POLL_SECONDS):
        try:
            if str(api.dataset_status(ref)).lower().endswith("ready"):
                return
        except Exception:  # noqa: BLE001, S110 - not listed yet
            pass
        time.sleep(POLL_SECONDS)
    raise SystemExit(f"{ref}: not ready after {max_seconds} s")


def _upload_bundle(api, folder: Path, ref: str) -> None:
    try:
        api.dataset_status(ref)
        exists = True
    except Exception:  # noqa: BLE001 - a missing dataset is an HTTP error here
        exists = False
    for attempt in range(UPLOAD_TRIES):   # Kaggle sometimes drops a create: it passes on a retry (#615)
        try:
            r = (api.dataset_create_version(str(folder), "This task's bundle", dir_mode="zip") if exists
                 else api.dataset_create_new(str(folder), public=False, dir_mode="zip"))
            break
        except Exception as e:  # the client raises plain HTTP errors
            if attempt == UPLOAD_TRIES - 1:
                raise
            print(f"upload of {ref} failed ({e}); trying again in {UPLOAD_RETRY_SECONDS} s", flush=True)
            time.sleep(UPLOAD_RETRY_SECONDS)
    if r is None or str(r.status).lower() != "ok":
        raise SystemExit(f"Kaggle refused {ref}: {getattr(r, 'error', None)}")
    time.sleep(10)
    _wait_dataset(api, ref)


def _verify(tasks_file: Path, snapshots: Path, agent_dir: Path, patches: dict[str, str], work: Path) -> dict[str, dict]:
    """swegemma's verify_task on each non-empty patch, against the published snapshot and the task's tests."""
    todo = {i: p for i, p in patches.items() if p.strip()}
    if not todo:
        return {}
    work.mkdir(parents=True, exist_ok=True)
    pfile, out = work / "patches.jsonl", work / "verdicts.jsonl"
    pfile.write_text("".join(json.dumps({"instance_id": i, "patch": p}) + "\n" for i, p in todo.items()))
    subprocess.run([sys.executable, str(HERE / "official_verify.py"), "--tasks", str(tasks_file), "--snapshots-dir",
                    str(snapshots), "--submission-dir", str(agent_dir), "--results-dir", str(work / "results"),
                    "--patch", "file", "--patch-file", str(pfile), "--concurrency", "3", "--out", str(out)],
                   check=True, cwd=work, env={**os.environ, "MLFLOW_DISABLE_AGENT_HINT": "1"})
    return {r["instance_id"]: r for r in map(json.loads, filter(str.strip, out.read_text().splitlines()))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True,
                    help="the published task set as downloaded: tasks.jsonl, snapshots/, graphs/, embeddings/")
    ap.add_argument("--agent-dir", type=Path, required=True, help="the submission folder (agent.yaml)")
    pick = ap.add_mutually_exclusive_group(required=True)
    pick.add_argument("--ids", help="comma-separated instance ids")
    pick.add_argument("--sample", type=int, help="draw this many tasks, stratified by tier, with --seed")
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--plan-only", action="store_true", help="print the tasks and stop: nothing is uploaded or run")
    ap.add_argument("--collect", action="store_true", help="don't upload or push: collect kernels already run")
    ap.add_argument("--concurrency", type=int, default=2, help="kernels running at once (Kaggle allows two GPU sessions)")
    ap.add_argument("--machine-shape", default=STARTER_MACHINE_SHAPE,
                    help="the accelerator to ask for; the kernel records the GPUs it actually got")
    ap.add_argument("--docker-image", help="pin the kernel's image (the starter notebook pins one)")
    ap.add_argument("--max-time-minutes", type=float, help="override the submission's per-task time budget")
    ap.add_argument("--kernel-minutes", type=int, default=45, help="Kaggle stops a kernel after this long")
    ap.add_argument("--work", type=Path, default=Path(os.environ.get("TMPDIR", "/tmp")) / "htl_official_agent")
    ap.add_argument("--no-table", action="store_true", help="a pilot: print the rows, write no table")
    a = ap.parse_args()

    import pandas as pd
    tasks = {t["instance_id"]: t for t in map(json.loads,
                                              filter(str.strip, (a.dataset / "tasks.jsonl").read_text().splitlines()))}
    tiers_all = pd.read_csv(REPO_ROOT / "data" / "tasks" / "task_manifest.csv", usecols=["instance_id", "tier_code"])
    manifest = {r.instance_id: r.tier_code for r in tiers_all.itertuples() if r.instance_id in tasks}
    ids = sample(manifest, a.sample, a.seed) if a.sample else [i.strip() for i in a.ids.split(",") if i.strip()]
    missing = [i for i in ids if i not in tasks or not (a.dataset / "snapshots" / f"{i}.tgz").exists()]
    if missing:
        sys.exit(f"not in the published tasks.jsonl or no snapshot: {', '.join(missing)}")
    by_tier = {t: sum(manifest[i] == t for i in ids) for t in sorted(set(manifest.values()))}
    print(f"{len(ids)} tasks" + (f", drawn with seed {a.seed}, stratified by tier" if a.sample else "")
          + f" ({', '.join(f'{t} {n}' for t, n in by_tier.items())}): {', '.join(ids)}")
    if a.plan_only:
        return 0
    if not (os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY")):
        sys.exit("KAGGLE_API_TOKEN is not set (ops/secrets_register.yaml, Kaggle API token)")
    user = os.environ.get("KAGGLE_USERNAME") or "jcblearning"
    overrides = {"max_time_minutes": a.max_time_minutes} if a.max_time_minutes else {}
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    api.dataset_list(user=user, page=1)   # one cheap authenticated call before the uploads

    waiting, running, results, sessions = list(ids), {}, {}, {}
    while waiting or running:
        while waiting and len(running) < a.concurrency:
            iid = waiting.pop(0)
            kref, work = f"{user}/{kernel_slug(iid)}", a.work / iid
            if not a.collect:
                shutil.rmtree(work, ignore_errors=True)
                task = tasks[iid]
                stem = bundle.code_index_name(task["repo"], task["base_commit"])
                b = bundle.build(task, a.dataset / "snapshots" / f"{iid}.tgz", a.dataset / "graphs" / f"{stem}.json",
                                 a.dataset / "embeddings" / f"{stem}.npz", a.agent_dir, work / "bundle", user, overrides)
                print(f"{iid}: uploading its bundle to {user}/{bundle.slug(iid)} (private)", flush=True)
                _upload_bundle(api, b, f"{user}/{bundle.slug(iid)}")
                k = work / "kernel"
                k.mkdir(parents=True)
                shutil.copyfile(HERE / "official_agent_kernel.py", k / "official_agent_kernel.py")
                (k / "kernel-metadata.json").write_text(json.dumps(
                    kernel_metadata(user, iid, a.machine_shape, a.docker_image), indent=1))
                api.kernels_push(str(k), timeout=str(a.kernel_minutes * 60))
                print(f"{iid}: the evaluator on a Kaggle GPU, {kref}", flush=True)
            running[iid] = time.monotonic()
        time.sleep(POLL_SECONDS)
        for iid in list(running):
            kref = f"{user}/{kernel_slug(iid)}"
            try:
                status = str(api.kernels_status(kref).status).lower()
            except Exception:  # noqa: BLE001, S112 - a blip; the next poll tells
                continue
            if not any(s in status for s in ("complete", "error", "cancel")):
                continue
            sessions[iid] = time.monotonic() - running.pop(iid)
            out = a.work / iid / "output"
            out.mkdir(parents=True, exist_ok=True)
            try:
                api.kernels_output(kref, str(out), force=True)
            except Exception as e:  # noqa: BLE001 - the row says so
                print(f"{iid}: could not download its output ({e})", flush=True)
            res = out / "result.json"
            results[iid] = json.loads(res.read_text()) if res.exists() else {
                "instance_id": iid, "error": f"kernel ended {status} and wrote no result.json"}
            r = results[iid]
            print(f"{iid}: kernel {status}; patch {len((r.get('patch') or '').encode())} bytes, "
                  f"{r.get('tool_call_count')} tool calls, agent {r.get('agent_phase_seconds')} s, "
                  f"GPUs {(r.get('server') or {}).get('gpus')}" + (f"; ERROR {r['error'][:300]}" if "error" in r else ""),
                  flush=True)

    verdicts = _verify(a.dataset / "tasks.jsonl", a.dataset / "snapshots", a.agent_dir,
                       {i: (r.get("patch") or "") for i, r in results.items()}, a.work / "_verify")
    rows = [row_for({"instance_id": i, **results[i]}, verdicts.get(i), manifest.get(i, ""),
                    f"https://www.kaggle.com/code/{user}/{kernel_slug(i)}",
                    None if a.collect else sessions.get(i)) for i in ids]
    table = pd.DataFrame(rows, columns=COLUMNS)
    print(table[["instance_id", "tier_code", "is_resolved", "reason_text", "agent_patch_bytes", "tool_call_count",
                 "agent_seconds", "gpu_count", "gpu_name"]].to_string(index=False))
    print(f"\n{int(table.is_resolved.sum())} of {len(table)} resolved, by the competition's evaluator end to end")
    if a.no_table:
        return 0
    model = next((r.get("model_name") for r in results.values() if r.get("model_name")), "gemma-4-e4b-it-qat-w4a16-ct")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{model}_swegemma.csv"
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=COLUMNS)
    keep = old[~old["instance_id"].isin(table["instance_id"])]
    merged = (pd.concat([keep, table], ignore_index=True) if len(keep) else table).sort_values("instance_id")
    merged.to_csv(path, index=False)   # merged by instance_id: re-runnable
    print(f"-> {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
