"""The competition's own verification on its development tasks with the reference patch and with an empty patch, in a
CPU Kaggle kernel (028 AI4, #668). The reference patch must resolve a task and the empty one must not, as on our own
tasks (the paper's Section 5), before an agent's verdict on the same tasks in a Kaggle kernel can be read.

    python kaggle/official_controls_run.py --dataset <folder holding the competition's tasks.jsonl> \\
        --agent-dir <submission folder> --sample 40 --seed 20261110 --competition gemma-4-developer-agent --work <dir>

The kernel attaches the competition and the evaluator's wheelhouse and verifies from the competition's own folder,
where the tests' wheels and setup script sit beside tasks.jsonl. It runs on a CPU, so no GPU allowance is spent. Rows
go to data/tasks/official_agent_runs/devset_controls.csv: ids, verdicts, exit codes and seconds, never the
competition's test output.
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

HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run = _load("official_agent_run")
bundle = _load("official_agent_bundle")
REPO_ROOT, OUT_DIR, WHEELHOUSE = run.REPO_ROOT, run.OUT_DIR, run.WHEELHOUSE
NAME = "devset-controls"
KINDS = {"oracle": "reference", "null": "empty"}      # official_verify.py's --patch, and the table's name for it
COLUMNS = ["instance_id", "patch_source_code", "is_resolved", "test_exit_code", "error_text", "verify_seconds", "run_ts"]
PATCH_COLUMNS = ["instance_id", "patch_key", "is_resolved", "test_exit_code", "error_text", "verify_seconds", "run_ts"]


def patch_rounds(patches: list[dict]) -> list[list[dict]]:
    """Given patches split so each round holds at most one patch per task (official_verify.py takes one patch per task
    per call), in the order given (#853)."""
    rounds: list[list[dict]] = []
    for p in patches:
        for r in rounds:
            if all(q["instance_id"] != p["instance_id"] for q in r):
                r.append(p)
                break
        else:
            rounds.append([p])
    return rounds


def kernel_metadata(username: str, competition: str, docker_image: str | None) -> dict:
    """Private, CPU, internet off: the controls bundle, the evaluator's wheelhouse and the competition; no model."""
    kslug = run.kernel_slug(NAME)
    meta = {"id": f"{username}/{kslug}", "title": kslug.replace("-", " "), "code_file": "official_controls_kernel.py",
            "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": False, "enable_tpu": False,
            "enable_internet": False, "dataset_sources": [f"{username}/{bundle.slug(NAME)}", WHEELHOUSE],
            "competition_sources": [competition], "kernel_sources": [], "model_sources": []}
    if docker_image:
        meta.update(docker_image=docker_image, docker_image_pinning_type="original")
    return meta


def build_bundle(ids: list[str], submission_dir: Path, out: Path, username: str, patches: list[dict] | None = None) -> Path:
    """The submission (the evaluator's model registry reads it), kaggle/official_verify.py and the ids: no task. With
    `patches` ({instance_id, patch_key, patch}), those are verified in rounds in place of the two controls (#853)."""
    submission_dir, out = Path(submission_dir), Path(out)
    if not (submission_dir / "agent.yaml").is_file():
        raise SystemExit(f"{submission_dir} has no agent.yaml: not a submission folder")
    if out.exists():
        shutil.rmtree(out)
    (out / "submission").mkdir(parents=True)
    for name in bundle.SUBMISSION_ENTRIES:
        src = submission_dir / name
        if src.is_dir():
            shutil.copytree(src, out / "submission" / name)
        elif src.is_file():
            shutil.copyfile(src, out / "submission" / name)
    shutil.copyfile(HERE / "official_verify.py", out / "official_verify.py")
    meta = {"instance_ids": list(ids), "kinds": list(KINDS), "concurrency": 3}
    if patches:
        meta["kinds"], meta["rounds"] = [], []
        for n, r in enumerate(patch_rounds(patches)):
            name = f"patches_{n}.jsonl"
            (out / name).write_text("".join(json.dumps({"instance_id": p["instance_id"], "patch_key": p["patch_key"],
                                                        "patch": p["patch"]}) + "\n" for p in r))
            meta["rounds"].append({"file": name, "instance_ids": [p["instance_id"] for p in r]})
    (out / "controls.json").write_text(json.dumps(meta, indent=1) + "\n")
    (out / "dataset-metadata.json").write_text(json.dumps({
        "title": "htlnlp official input devset controls", "id": f"{username}/{bundle.slug(NAME)}",
        "licenses": [{"name": "CC-BY-4.0"}]}, indent=1) + "\n")
    return out


def row_for(verdict: dict, run_ts: str) -> dict:
    """One table row: the verdict, its exit code and time; the error cut to 200 characters; never the test output."""
    error = verdict.get("error")
    return {"instance_id": verdict["instance_id"], "patch_source_code": KINDS[verdict["patch_kind"]],
            "is_resolved": bool(verdict.get("resolved")), "test_exit_code": verdict.get("test_exit_code"),
            "error_text": error[:200] if isinstance(error, str) else error, "verify_seconds": verdict.get("seconds"),
            "run_ts": run_ts}


def patch_rows(verdicts: list[dict], keys: dict, run_ts: str) -> list[dict]:
    """Rows of devset_patch_checks.csv for one round: `keys` maps each task to the patch_key verified in that round."""
    return [{"instance_id": v["instance_id"], "patch_key": keys[v["instance_id"]], "is_resolved": bool(v.get("resolved")),
             "test_exit_code": v.get("test_exit_code"),
             "error_text": v["error"][:200] if isinstance(v.get("error"), str) else v.get("error"),
             "verify_seconds": v.get("seconds"), "run_ts": run_ts} for v in verdicts]


def write_patch_table(pd, rows: list[dict]) -> Path:
    """Merge into devset_patch_checks.csv by patch_key (re-runnable)."""
    path = OUT_DIR / "devset_patch_checks.csv"
    table = pd.DataFrame(rows, columns=PATCH_COLUMNS)
    if path.exists():
        old = pd.read_csv(path)
        table = pd.concat([old[~old.patch_key.isin(set(table.patch_key))], table], ignore_index=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.sort_values(["instance_id", "patch_key"]).to_csv(path, index=False)
    return path


def write_table(pd, rows: list[dict]) -> Path:
    """Merge the rows into the committed table by instance_id and patch source (re-runnable)."""
    path = OUT_DIR / "devset_controls.csv"
    table = pd.DataFrame(rows, columns=COLUMNS)
    if path.exists():
        old = pd.read_csv(path)
        keys = set(zip(table.instance_id, table.patch_source_code))
        old = old[[(i, p) not in keys for i, p in zip(old.instance_id, old.patch_source_code)]]
        table = pd.concat([old, table], ignore_index=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.sort_values(["instance_id", "patch_source_code"]).to_csv(path, index=False)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True, help="a folder holding the competition's tasks.jsonl")
    ap.add_argument("--agent-dir", type=Path, required=True, help="the submission folder (agent.yaml)")
    pick = ap.add_mutually_exclusive_group(required=True)
    pick.add_argument("--ids", help="comma-separated instance ids")
    pick.add_argument("--sample", type=int, help="the draw official_agent_run.py makes, stratified by repository")
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--competition", required=True)
    ap.add_argument("--docker-image", help="pin the kernel's image, as the agent's run does")
    ap.add_argument("--kernel-minutes", type=int, default=180)
    ap.add_argument("--patches", type=Path, help="JSONL of {instance_id, patch_key, patch}: verify these instead (#853)")
    ap.add_argument("--work", type=Path, default=Path(os.environ.get("TMPDIR", "/tmp")) / "htl_official_controls")
    a = ap.parse_args()

    import pandas as pd
    tasks = {t["instance_id"]: t for t in map(json.loads,
                                              filter(str.strip, (a.dataset / "tasks.jsonl").read_text().splitlines()))}
    ids = (run.sample(run.strata(tasks, {}, "competition"), a.sample, a.seed) if a.sample
           else [i.strip() for i in a.ids.split(",") if i.strip()])
    if missing := [i for i in ids if i not in tasks]:
        sys.exit(f"not in the tasks.jsonl given: {', '.join(missing)}")
    if not (os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY")):
        sys.exit("KAGGLE_API_TOKEN is not set (ops/secrets_register.yaml, Kaggle API token)")
    user = os.environ.get("KAGGLE_USERNAME") or "jcblearning"
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    api.dataset_list(user=user, page=1)   # one cheap authenticated call before the upload

    work = a.work / NAME
    shutil.rmtree(work, ignore_errors=True)
    patches = ([json.loads(line) for line in a.patches.read_text().splitlines() if line.strip()] if a.patches else None)
    if patches and (missing := sorted({p["instance_id"] for p in patches} - set(ids))):
        sys.exit(f"patches for tasks not in --ids: {', '.join(missing)}")
    b = build_bundle(ids, a.agent_dir, work / "bundle", user, patches=patches)
    print(f"controls for {len(ids)} tasks: uploading to {user}/{bundle.slug(NAME)} (private)", flush=True)
    run._upload_bundle(api, b, f"{user}/{bundle.slug(NAME)}")
    k = work / "kernel"
    k.mkdir(parents=True)
    shutil.copyfile(HERE / "official_controls_kernel.py", k / "official_controls_kernel.py")
    (k / "kernel-metadata.json").write_text(json.dumps(kernel_metadata(user, a.competition, a.docker_image), indent=1))
    api.kernels_push(str(k), timeout=str(a.kernel_minutes * 60))
    kref = f"{user}/{run.kernel_slug(NAME)}"
    print(f"the evaluator's verification on a Kaggle CPU, {kref}", flush=True)
    t0, status = time.monotonic(), ""
    while True:
        time.sleep(run.POLL_SECONDS)
        try:
            status = str(api.kernels_status(kref).status).lower()
        except Exception:  # noqa: BLE001, S112 - a blip; the next poll tells
            continue
        if any(s in status for s in ("complete", "error", "cancel")):
            break
    out = work / "output"
    out.mkdir(parents=True, exist_ok=True)
    api.kernels_output(kref, str(out), force=True)
    res = json.loads((out / "result.json").read_text()) if (out / "result.json").exists() else {}
    print(f"kernel {status} after {(time.monotonic() - t0) / 60:.1f} min" + (f"; ERROR {res['error'][:400]}"
                                                                             if res.get("error") else ""), flush=True)
    rows = []
    for kind in KINDS:
        f = out / f"verdicts_{kind}.jsonl"
        verdicts = [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
        rows += [row_for(v, res.get("finished_ts")) for v in verdicts]
        print(f"{KINDS[kind]} patch: {sum(bool(v.get('resolved')) for v in verdicts)} of {len(verdicts)} resolved",
              flush=True)
    if rows:
        print(f"-> {write_table(pd, rows).relative_to(REPO_ROOT)}")
    meta = json.loads((b / "controls.json").read_text())
    checked = []
    for n, r in enumerate(meta.get("rounds") or []):
        keys = {json.loads(line)["instance_id"]: json.loads(line)["patch_key"]
                for line in (b / r["file"]).read_text().splitlines() if line.strip()}
        f = out / f"verdicts_round_{n}.jsonl"
        verdicts = [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
        checked += patch_rows(verdicts, keys, res.get("finished_ts"))
    if checked:
        print(f"given patches: {sum(r['is_resolved'] for r in checked)} of {len(checked)} resolved")
        print(f"-> {write_patch_table(pd, checked).relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
