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

The competition's own development set (028 AI4, #668): `--source competition --batch --competition <slug>` with
`--dataset` a folder holding the competition's tasks.jsonl alone. The draw is stratified by repository; the bundle
holds the submission and the order only; the kernel reads each task from the attached competition's files, and the
evaluator verifies the patch there with the task's tests, as the competition's own run does. Rows go to
<model>_swegemma_devset.csv. Nothing of the competition's data is committed: ids, verdicts and counts only.
Needs KAGGLE_API_TOKEN, and an interpreter that has the evaluator's wheels and this repository's test dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
OUT_DIR = REPO_ROOT / "data" / "tasks" / "official_agent_runs"
WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"                 # the competition's evaluator and vLLM
MODEL_SOURCE = "google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2"      # as the starter notebook attaches it
STARTER_MACHINE_SHAPE = "NvidiaL4"                                       # the starter notebook's accelerator
POLL_SECONDS, UPLOAD_TRIES, UPLOAD_RETRY_SECONDS = 30, 4, 60
COLUMNS = ["instance_id", "tier_code", "is_in_sample", "harness_name", "model_name", "is_resolved", "test_exit_code", "reason_text",
           "agent_patch_bytes", "tool_call_count", "llm_call_count", "graph_tool_call_count", "sub_agent_call_count",
           "skill_call_count", "outside_workspace_call_count", "prompt_token_count", "output_token_count",
           "agent_seconds", "load_seconds",
           "script_seconds", "gpu_count", "gpu_name", "command_timeout_seconds", "max_tool_calls", "max_time_minutes",
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


def strata(tasks: dict, manifest: dict, source: str) -> dict[str, str]:
    """What a draw is stratified by: our tasks by fidelity tier (the manifest), the competition's development tasks
    by repository (028 AI4, #668)."""
    if source == "competition":
        return {iid: t.get("repo", "") for iid, t in tasks.items()}
    return {iid: tier for iid, tier in manifest.items() if iid in tasks}


def verdict_from_kernel(result: dict) -> dict | None:
    """A development task's verdict: the evaluator's own verification in the kernel, with the task's tests."""
    v = result.get("verification")
    return {"resolved": bool(v.get("is_resolved")), "test_exit_code": v.get("test_exit_code")} if v else None


def batch_trace_counts(output: Path, instance_id: str) -> dict | None:
    """A batch task's trace as downloaded (tasks/<id>/results/traces/trace_<id>.json), counted as one task's is."""
    trace = Path(output) / "tasks" / instance_id / "results" / "traces" / f"trace_{instance_id}.json"
    return trace_counts(json.loads(trace.read_text())) if trace.exists() else None


_LABEL = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
COLAB_RESULTS_PREFIX = "htlnlp-colab-official-"   # kaggle/colab_official.py sends a run's log and output there
COLAB_KERNEL_PREFIX = "htlnlp-colab-kernel-"      # a batch's keyed kernel file, for the Colab notebook to run


def colab_results_ref(user: str, name: str) -> str:
    return f"{user}/{COLAB_RESULTS_PREFIX}{name}"


def colab_results_url(ref: str) -> str:
    """The page of a Colab run's results: its dataset, or one version of it (`owner/slug/<n>`)."""
    owner, slug, *version = ref.split("/")
    return f"https://www.kaggle.com/datasets/{owner}/{slug}" + (f"/versions/{version[0]}" if version else "")


def colab_session(log_text: str) -> str | None:
    """Which notebook session an upload is from: the time its log opens with (HH:MM:SS, UTC)."""
    for line in log_text.splitlines():
        if (m := re.match(r"\[(\d\d:\d\d:\d\d)Z\]", line)):
            return m.group(1)
    return None


def check_colab_session(log_text: str, wanted: str | None) -> None:
    """Two notebook sessions once made one arm at the same time and sent their output to its dataset in turn (#687),
    so "the latest version" was whichever sent last. An arm is read from a version by number, and reading stops
    unless that version's log opens with the session meant."""
    got = colab_session(log_text)
    if wanted and got != wanted:
        raise SystemExit(f"this upload is from the session that began at {got}, not the one meant ({wanted}): "
                         "nothing is collected from it")


def colab_kernel_metadata(user: str, name: str) -> dict:
    return {"id": f"{user}/{COLAB_KERNEL_PREFIX}{name}", "title": f"htlnlp colab kernel {name}"[:50],
            "licenses": [{"name": "CC-BY-4.0"}]}


def colab_run_entry(user: str, name: str) -> dict:
    """One run of kaggle/colab_official_run.json (028 AI9, #687): the sealed bundle and the keyed kernel file, each in
    its own private dataset. The key is in the second only, as it is in a pushed Kaggle kernel only."""
    return {"label": name, "bundle": f"{user}/{bundle.slug(name)}", "kernel_dataset": f"{user}/{COLAB_KERNEL_PREFIX}{name}"}


def colab_output(downloaded: Path, out: Path) -> None:
    """What a Colab run sent back, put where a kernel's output is read from: its `working/` folder and its log."""
    work = Path(downloaded) / "working"
    if not (work / "result.json").exists():
        raise SystemExit(f"no result.json under {work}: the Colab run has not finished, or wrote none")
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(work, out)
    if (Path(downloaded) / "colab.log").exists():
        shutil.copyfile(Path(downloaded) / "colab.log", Path(out) / "colab.log")
    merge_parts(out)


def merge_parts(out: Path) -> None:
    """A run that started again (a Colab session that dropped) wrote its GPU samples and its spans in parts,
    `<name>_before_<n>` for each earlier start and `<name>` for the last. Put them back together, oldest first, so
    each task's samples and spans are found whichever start ran it. Running it twice changes nothing."""
    for name, has_header in (("gpu_samples.csv", True), ("telemetry.jsonl", False)):
        stem, suffix = name.rsplit(".", 1)
        parts = sorted(Path(out).glob(f"{stem}_before_*.{suffix}"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
        if not parts:
            continue
        last = Path(out) / name
        texts = [p.read_text() for p in parts] + ([last.read_text()] if last.exists() else [])
        if has_header:
            head = texts[0].splitlines(keepends=True)[:1]
            body = [line for t in texts for line in t.splitlines(keepends=True)[1:]]
            last.write_text("".join(head + body))
        else:
            last.write_text("".join(texts))
        for p in parts:
            p.unlink()


# What a Colab run's settings say of the network. The proxies set on the kernel's process do not reach the agent's
# commands: the evaluator's sandbox starts each from its own short list of environment names (the review of #690).
COLAB_INTERNET = ("open at the machine's edge. The kernel's process had no credential and every proxy pointed at a port "
                  "nothing listens on, but the evaluator starts each of the agent's commands from a short list of "
                  "environment names of its own, which holds neither: no credential reached a command, and a command "
                  "could reach the network. Every command is read for that afterwards (network_audit; "
                  "kaggle/colab_official.py)")


def trace_commands(trace: dict) -> list[str]:
    """Every command the agent ran, from the evaluator's own trace of a task."""
    out = []
    for step in trace.get("steps") or []:
        for call in step.get("tool_calls") or []:
            if call.get("function_name") == "run_command":
                args = call.get("arguments") or {}
                text = args.get("command") or args.get("cmd") or next((v for v in args.values() if isinstance(v, str)), "")
                out.append(text)
    return out


def network_audit(traces: dict[str, dict]) -> dict:
    """A run on a machine with a network (Colab): how many of the agent's commands reach for it, and in which
    tasks. On Kaggle the kernels have no network, so nothing is counted there."""
    spec = importlib.util.spec_from_file_location("colab_official", HERE / "colab_official.py")
    co = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(co)
    commands = {i: trace_commands(t) for i, t in traces.items()}
    hits = {i: co.network_command_count(c) for i, c in commands.items()}
    return {"command_count": sum(len(c) for c in commands.values()), "network_command_count": sum(hits.values()),
            "instance_ids": sorted(i for i, n in hits.items() if n)}


def batch_name(source: str, label: str | None) -> str:
    """What a batch's dataset, kernel, work folder and table are named after: `label` when given, so two arms of one
    experiment run side by side (028 AI7, #674), else the source's own name."""
    if label is None:
        return "devset" if source == "competition" else "batch"
    if not _LABEL.fullmatch(label) or len(label) > 24:
        raise SystemExit(f"--label {label!r}: lowercase letters, digits and single hyphens, at most 24 characters")
    return label


def read_context(path: Path) -> dict[str, str]:
    """instance_id -> the text to add to that task's hints, from JSON lines (scripts/69_failure_report.py)."""
    rows = map(json.loads, filter(str.strip, Path(path).read_text().splitlines()))
    return {r["instance_id"]: r["context_text"] for r in rows}


def with_context(tasks: dict, contexts: dict[str, str], ids: list[str]) -> dict:
    """The drawn tasks with their context after their hints; the tasks as published are left alone. Every drawn task
    must have one: an arm where some tasks lack it is not that arm."""
    missing = [i for i in ids if not (contexts.get(i) or "").strip()]
    if missing:
        raise SystemExit(f"no context for {', '.join(missing)}: every task of this arm needs one")
    out = dict(tasks)
    for i in ids:
        hints = (tasks[i].get("hints_text") or "").strip()
        out[i] = {**tasks[i], "hints_text": (hints + "\n\n" if hints else "") + contexts[i]}
    return out


def context_note(path: Path, contexts: dict[str, str], ids: list[str]) -> dict:
    """What the settings say about an arm's context: the file's hash and its size, never its text."""
    return {"file_name": Path(path).name, "file_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "task_count": len(ids), "max_context_chars": max(len(contexts[i]) for i in ids), "added_to": "hints_text"}


def batch_meta(a, overrides: dict) -> dict:
    """What a batch kernel is told besides its order: budgets, its deadline, the seed, and telemetry when asked."""
    meta = {"budget_overrides": overrides, "deadline_minutes": a.deadline_minutes, "seed": a.seed}
    if getattr(a, "telemetry", False):
        meta["telemetry"] = True
    return meta


def gpu_stats(samples: Path, start_unix: float, end_unix: float) -> dict | None:
    """One task's GPU use from the kernel's nvidia-smi samples between its start and end (036 US2, #569): mean
    utilization, peak memory, and energy (each GPU's mean power over the task's time, summed over the GPUs)."""
    import csv
    from datetime import datetime, timezone
    if not Path(samples).exists() or start_unix is None or end_unix is None:
        return None
    rows = []
    with open(samples, encoding="utf-8") as f:
        for r in csv.reader(f):
            if not r or r[0].startswith("timestamp"):
                continue
            try:
                ts = datetime.strptime(r[0].strip(), "%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=timezone.utc).timestamp()
                rows.append((ts, int(r[1]), float(r[2]), float(r[3]), float(r[4])))
            except (ValueError, IndexError):   # "[N/A]" power on some GPUs, a cut-off last line
                continue
    inside = [r for r in rows if start_unix <= r[0] <= end_unix]
    if not inside:
        return None
    power: dict[int, list[float]] = {}
    for _, gpu, _, _, watts in inside:
        power.setdefault(gpu, []).append(watts)
    hours = (end_unix - start_unix) / 3600
    return {"gpu_sample_count": len(inside), "avg_gpu_utilization_pct": round(sum(r[2] for r in inside) / len(inside), 2),
            "max_gpu_memory_used_mb": max(r[3] for r in inside),
            "gpu_energy_wh": sum(sum(w) / len(w) for w in power.values()) * hours}


def kernel_slug(instance_id: str) -> str:
    """Not the bundle's slug: Kaggle refuses a kernel with the same slug as one of the owner's datasets."""
    return "htlnlp-offrun-" + re.sub(r"[^a-z0-9]+", "-", instance_id.lower()).strip("-")


def kernel_metadata(username: str, instance_id: str, machine_shape: str | None, docker_image: str | None,
                    competition: str | None = None) -> dict:
    """Private, GPU, internet off; this task's bundle, the competition's wheelhouse and the model, nothing else.
    `competition` attaches the competition as the starter notebook does (its accelerator may depend on it); its
    files are the competition's own tasks, not ours."""
    kslug = kernel_slug(instance_id)
    meta = {"id": f"{username}/{kslug}", "title": kslug.replace("-", " "), "code_file": "official_agent_kernel.py",
            "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_tpu": False,
            "enable_internet": False, "dataset_sources": [f"{username}/{bundle.slug(instance_id)}", WHEELHOUSE],
            "competition_sources": [competition] if competition else [], "kernel_sources": [],
            "model_sources": [MODEL_SOURCE]}
    if machine_shape:
        meta["machine_shape"] = machine_shape
    if docker_image:
        meta.update(docker_image=docker_image, docker_image_pinning_type="original")
    return meta


def kernel_source(source: str, key: bytes) -> str:
    """The kernel file a batch is pushed with: the committed one, with this run's key in place of the empty one."""
    if source.count('SEAL_KEY = ""') != 1:
        raise SystemExit("the kernel no longer has exactly one empty SEAL_KEY to fill")
    return source.replace('SEAL_KEY = ""', f'SEAL_KEY = "{key.hex()}"')


GRAPH_TOOLS = {"get_code_neighbors", "search_similar_code", "get_code_subgraph"}
SKILL_TOOLS = {"list_skills", "load_skill", "load_skill_resource", "run_skill_script"}
WRITTEN_TEXT = {"content", "old_string", "new_string"}   # what the model writes into a file is not a path it reaches
OUTSIDE = re.compile(r"/kaggle/|/tmp/htl|\.\./\.\.|/root/|/etc/|/proc/")   # a tool argument reaching past the workspace


def trace_counts(trace: dict) -> dict:
    """From the evaluator's own trace of a task: its token totals, and how many tool calls were graph tools, went to
    a sub-agent, used a skill, or named a path outside the workspace (an agent must never need to)."""
    calls = [c for s in trace.get("steps") or [] for c in s.get("tool_calls") or []]
    names = [c.get("function_name") or "" for c in calls]
    core = GRAPH_TOOLS | SKILL_TOOLS | {"run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch"}
    final = trace.get("final_metrics") or {}
    return {"prompt_token_count": final.get("total_prompt_tokens"), "output_token_count": final.get("total_completion_tokens"),
            "graph_tool_call_count": sum(n in GRAPH_TOOLS for n in names),
            "sub_agent_call_count": sum(bool(n) and n not in core for n in names),
            "skill_call_count": sum(n in SKILL_TOOLS for n in names),
            "outside_workspace_call_count": sum(bool(OUTSIDE.search(json.dumps(
                {k: v for k, v in (c.get("arguments") or {}).items() if k not in WRITTEN_TEXT}))) for c in calls)}


COMPETITION_DEFAULTS = {"timeout_seconds": 300, "verification_timeout_seconds": 300, "max_tool_calls": 100,
                        "max_time_minutes": 60.0, "max_turns": None, "max_output_tokens": 16384, "thinking_budget": 4096}
# what the starter notebook and swegemma.config.build_submission_limits use when a submission sets nothing


def settings_for(result: dict, seed: int | None, drawn: list[str], pool_count: int, machine_shape: str | None,
                 docker_image: str | None, competition: str | None, agent_commit: str | None,
                 source: str = "published", tasks_per_kernel: int = 1, colab: bool = False) -> dict:
    """What a run used, how its sample was drawn, and each budget that differs from the competition's defaults.
    `colab`: the run was made on a Colab machine by kaggle/colab_official.py, not in a Kaggle kernel (#687)."""
    budgets, gen = result.get("budgets") or {}, result.get("generation_defaults") or {}
    used = {**budgets, "max_output_tokens": gen.get("max_output_tokens"),
            "thinking_budget": (gen.get("thinking_config") or {}).get("thinking_budget")}
    version = (result.get("versions") or {}).get("swegemma")
    harness = result.get("harness_name") or "swegemma"
    development = source == "competition"
    return {
        "harness_name": harness.replace("swegemma", f"swegemma {version}", 1) if version else harness,
        "model_name": result.get("model_name"), "versions": result.get("versions"), "server": result.get("server"),
        "budgets": budgets, "generation_defaults": gen, "context_cache": result.get("context_cache"),
        "events_compaction": result.get("events_compaction"),
        "kernel": {"machine_shape_asked": "Colab, one GPU" if colab else machine_shape,
                   "docker_image": None if colab else docker_image, "competition_attached": competition,
                   "internet": COLAB_INTERNET if colab else False,
                   "tasks_per_kernel": tasks_per_kernel},
        "agent_commit_sha": agent_commit,
        "sample": {"seed": seed, "drawn_count": len(drawn), "pool_count": pool_count, "instance_ids": drawn,
                   "method_text": ("drawn with the seed from the competition's development set, stratified by "
                                   "repository in proportion to each repository's size (largest remainder); not "
                                   "ordered by cost or size") if development else (
                                  "drawn with the seed from the published tasks, stratified by fidelity tier in "
                                  "proportion to each tier's size (largest remainder); not ordered by cost or size")},
        "differences_from_competition_defaults": [
            {"setting_name": k, "used": used.get(k), "competition_default": v,
             "source_text": "the submission's eval_config.yaml"}
            for k, v in COMPETITION_DEFAULTS.items() if k in used and used.get(k) != v],
        "notes": [
            ("The agent loop, the model server and the verification are the competition's: swegemma's "
             "Evaluator.evaluate_task (subprocess sandbox), vLLM from the competition's wheelhouse dataset, and "
             "swegemma's verify_task, following the competition's starter notebook."),
            ("The kernel attached the competition and read each development task from its mounted files, with no "
             "reference patch staged beside the agent; the evaluator verified each patch there with the task's tests, "
             "as the competition's own run does. Tool calls naming a path outside the workspace are counted in "
             "outside_workspace_call_count.") if development else
            ((f"All {tasks_per_kernel} tasks were given to one process on a Colab machine, each sealed until its turn, "
              "beside a bundle" if colab else
              f"All {tasks_per_kernel} tasks were given to one private, offline kernel, each sealed until its turn, beside a "
              "bundle" if tasks_per_kernel > 1 else "Each task ran alone in a private, offline kernel beside a bundle")
             + " with no reference patch and no tests, "
             "so the evaluator's verification had nothing to verify there. The patch was verified afterwards with "
             "the same evaluator's verify_task against the published snapshot and the task's tests."),
            "The number format follows the GPU: bfloat16 on compute capability 8.0 or above, float16 below.",
            *((("Run on a Colab machine, not in a Kaggle kernel: the same kernel file, with the competition's wheels, "
                "the model and the bundle at the paths Kaggle mounts them. The model server and the agent framework "
                "were installed from PyPI at the versions the Kaggle kernels recorded, and the competition's "
                "wheelhouse was installed over them by the kernel, as on Kaggle. One GPU and Colab's base image, so "
                "its counts are not set beside a Kaggle kernel's as if one run."),) if colab else ()),
        ],
    }


def given_sample(settings: dict, method_text: str | None) -> dict:
    """The settings of a run whose ids were given (--ids), not drawn by it: say so, and keep the seed as the order's
    (a batch runs its tasks in a seeded shuffle)."""
    sample = dict(settings["sample"])
    sample["order_seed"], sample["seed"] = sample.get("seed"), None
    sample["method_text"] = ("the ids were given to this run, not drawn by it"
                             + (f": {method_text}" if method_text else ""))
    return {**settings, "sample": sample}


def _script_seconds(result: dict) -> float | None:
    """The kernel script's own start to end: installing the wheelhouse, loading the model, the agent."""
    try:
        t0, t1 = (time.mktime(time.strptime(result[k], "%Y-%m-%dT%H:%M:%SZ")) for k in ("started_ts", "finished_ts"))
        return round(t1 - t0, 1)
    except (KeyError, ValueError, TypeError):
        return None


def row_for(result: dict, verdict: dict | None, tier: str, kernel_url: str, in_sample: bool = True) -> dict:
    """One table row: what the evaluator's agent phase did on Kaggle, and its verification's verdict on the patch."""
    budgets, server = result.get("budgets") or {}, result.get("server") or {}
    gen = result.get("generation_defaults") or {}
    gpus = server.get("gpus") or []
    version = (result.get("versions") or {}).get("swegemma")
    harness = result.get("harness_name") or "swegemma"
    row = {
        "instance_id": result.get("instance_id"), "tier_code": tier, "is_in_sample": bool(in_sample),
        "harness_name": harness.replace("swegemma", f"swegemma {version}", 1) if version else harness,
        "model_name": result.get("model_name"), "is_resolved": bool(verdict and verdict.get("resolved")),
        "test_exit_code": verdict.get("test_exit_code") if verdict else None,
        "reason_text": "", "agent_patch_bytes": len((result.get("patch") or "").encode()),
        "tool_call_count": result.get("tool_call_count"), "llm_call_count": result.get("llm_call_count"),
        **{k: (result.get("trace_counts") or {}).get(k) for k in (
            "graph_tool_call_count", "sub_agent_call_count", "skill_call_count", "outside_workspace_call_count",
            "prompt_token_count", "output_token_count")},
        "agent_seconds": result.get("agent_phase_seconds"), "load_seconds": result.get("load_seconds"),
        "script_seconds": _script_seconds(result),
        "gpu_count": len(gpus) or None, "gpu_name": gpus[0] if gpus else None,
        "command_timeout_seconds": budgets.get("timeout_seconds"), "max_tool_calls": budgets.get("max_tool_calls"),
        "max_time_minutes": budgets.get("max_time_minutes"), "max_turns": budgets.get("max_turns"),
        "max_output_tokens": gen.get("max_output_tokens"),
        "thinking_budget": (gen.get("thinking_config") or {}).get("thinking_budget"),
        "kaggle_kernel_url": kernel_url, "run_ts": result.get("finished_ts"),
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


def write_table(pd, rows: list[dict], model: str | None, label: str | None = None) -> Path:
    """Merge the rows into the committed table by instance_id (re-runnable); `label` names a separate table, such
    as the development set's."""
    table = pd.DataFrame(rows, columns=COLUMNS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{model or 'gemma-4-e4b-it-qat-w4a16-ct'}_swegemma{'_' + label if label else ''}.csv"
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=COLUMNS)
    keep = old[~old["instance_id"].isin(table["instance_id"])]
    (pd.concat([keep, table], ignore_index=True) if len(keep) else table).sort_values("instance_id").to_csv(path, index=False)
    return path


BATCH_SHARED = ("model_name", "server", "versions", "harness_name", "load_seconds", "finished_ts")
NOT_REACHED = "not reached by the kernel"
NO_ANSWER = "no answer from the model server (no model call)"
NO_ANSWER_KINDS = {"time_limit": ("session timeout",),
                   "server_error": ("InternalServerError", "Connection error", "APIConnectionError", "ServiceUnavailable")}


def error_kind(text: str | None) -> str | None:
    """How an agent phase that made no model call ended, when the model server was the cause: at the task's time
    limit, or on a server or connection error. None for any other error, such as a fault in the submission's own
    prompt, which is the agent's and keeps its row."""
    return next((kind for kind, marks in NO_ANSWER_KINDS.items() if any(m in (text or "") for m in marks)), None)


def not_run_reasons(res: dict) -> dict[str, str]:
    """The tasks of a batch that were not run, each with why. The rule is the pre-registration's (spec 028,
    preregistration-failing-test-report.md, "Exclusions and reruns"): a task the kernel did not reach, or whose
    agent phase did not start. A task that made no model call at all and ended at its time limit or on a server
    error had no answer from the model server: no attempt was made. Any other failure keeps its row, so an arm
    whose own text breaks the prompt does not lose those tasks from its count."""
    out = {}
    for iid, r in (res.get("runs") or {}).items():
        if r.get("is_skipped"):
            out[iid] = NOT_REACHED
        elif r.get("llm_call_count") == 0 and "error" not in r and error_kind(r.get("agent_error")):
            out[iid] = NO_ANSWER
    return out


def not_run_rows(res: dict, order: list[str]) -> list[dict]:
    """One record per task not run, in the run's order, for the settings file beside the table: the reason, and for
    a task with no answer from the model server how it ended and after how long. The exclusion can then be checked
    from committed files."""
    why, runs = not_run_reasons(res), res.get("runs") or {}
    rows = []
    for iid in order:
        if iid in runs and iid not in why:
            continue
        no_answer = why.get(iid) == NO_ANSWER
        r = runs.get(iid) or {}
        rows.append({"instance_id": iid, "reason_text": why.get(iid, NOT_REACHED),
                     "error_kind_code": error_kind(r.get("agent_error")) if no_answer else None,
                     "agent_seconds": r.get("agent_phase_seconds") if no_answer else None})
    return rows


def batch_results(res: dict) -> dict[str, dict]:
    """Each task a batch kernel ran, with what the kernel wrote once for all of them: the model, the server, and its
    finish time, which is each row's batch key (run_ts). The kernel's start is left out, so no row takes the whole
    kernel's time as its own script_seconds. A task that was not run (not_run_reasons) is not in it."""
    shared = {k: res.get(k) for k in BATCH_SHARED}
    out = not_run_reasons(res)
    return {i: {**shared, **r} for i, r in (res.get("runs") or {}).items() if i not in out}


def seeded_order(ids: list[str], seed: int, of_set: list[str] | None = None) -> list[str]:
    """The order a batch runs its tasks in: a seeded shuffle of the ids as given. For a rerun of some tasks, `of_set`
    is the first run's ids as they were given then: each task keeps its place in that run's order."""
    order = list(of_set if of_set is not None else ids)
    if of_set is not None and (missing := [i for i in ids if i not in set(of_set)]):
        raise SystemExit(f"--order-of-ids: not in the first run: {', '.join(missing)}")
    random.Random(seed).shuffle(order)
    return [i for i in order if i in set(ids)] if of_set is not None else order


def order_record(first_run_ids: list[str]) -> dict:
    """What the settings keep of a rerun's order: how many ids the first run was given, and their hash in the
    sequence given, so the order can be rebuilt and checked."""
    return {"of_ids_count": len(first_run_ids), "of_ids_sha256": hashlib.sha256(",".join(first_run_ids).encode()).hexdigest()}


def check_arm_options(label: str | None, context, batch: bool, development: bool) -> None:
    """--label and --context are for a batch of the published tasks, and a context needs a label: without one a
    batch writes to the table of the run of November 10, and a run with added context is another condition."""
    if (label or context) and (not batch or development):
        sys.exit("--label and --context are for a batch of the published tasks: they need --batch, not --source competition")
    if context and not label:
        sys.exit("--context needs --label: a run with added context is its own condition and writes its own table")


def reusable_output(out: Path, reuse: bool) -> bool:
    """True when a collection was asked to reuse a kernel's output that is already in `out`."""
    return bool(reuse) and (Path(out) / "result.json").exists()


# Said after Kaggle's own words when a kernel is refused for the weekly GPU quota: the check to make before a smaller
# run, a wait or another platform (AGENTS.md, "Failures, retries and reruns"; #698).
QUOTA_NEXT_STEP = (" Before another path: is a Colab Pro or Pro+ subscription linked to the Kaggle account (15 or 30 "
                   "more GPU hours a week)? See kaggle/README.md, 'GPU hours'.")


def push_kernel(api, folder: Path, timeout_seconds: int, ref: str) -> None:
    """Push a batch's kernel, and end the run in Kaggle's own words if Kaggle refuses it (no GPU allowance left, two
    GPU sessions already running): there is then no kernel to wait for. A refusal for the GPU quota also names the
    check that comes before another path."""
    try:
        refused = getattr(api.kernels_push(str(folder), timeout=str(timeout_seconds)), "error", None)
    except Exception as e:  # noqa: BLE001 - whatever the client raises is the refusal's text
        refused = f"{type(e).__name__}: {e}"
    if refused:
        more = QUOTA_NEXT_STEP if "gpu quota" in str(refused).lower() else ""
        raise SystemExit(f"{ref}: Kaggle refused the kernel: {str(refused)[:400]}{more}")


def run_batch(a, api, user: str, ids: list[str], tasks: dict, manifest: dict, overrides: dict, pd) -> int:
    """One kernel for every task, in a seeded order, each task sealed until its turn; then verify and tabulate."""
    first_run = getattr(a, "order_of_ids", None)
    first_ids = [i.strip() for i in first_run.split(",") if i.strip()] if first_run else None
    order = seeded_order(ids, a.seed, first_ids)
    development = a.source == "competition"
    colab = bool(getattr(a, "colab", False))
    name = batch_name(a.source, getattr(a, "label", None))
    kref, work = f"{user}/{kernel_slug(name)}", a.work / name
    results = getattr(a, "colab_results", None) or colab_results_ref(user, name)   # where a Colab run's output is read
    if not a.collect:
        shutil.rmtree(work, ignore_errors=True)
        key = os.urandom(32)   # this run's; in the pushed kernel only, never in the dataset or the repository

        def files_of(task: dict):
            stem = bundle.code_index_name(task["repo"], task["base_commit"])
            return (a.dataset / "snapshots" / f"{task['instance_id']}.tgz", a.dataset / "graphs" / f"{stem}.json",
                    a.dataset / "embeddings" / f"{stem}.npz")

        meta = batch_meta(a, overrides)
        if development:
            b = bundle.build_competition_batch(order, a.agent_dir, work / "bundle", user, meta)
        else:
            b = bundle.build_batch([tasks[i] for i in ids], files_of, a.agent_dir, work / "bundle", user, key, order,
                                   meta, name=name)
        print(f"batch of {len(order)}: uploading the {'order' if development else 'sealed bundle'} to "
              f"{user}/{bundle.slug(name)} (private); order {', '.join(order)}", flush=True)
        _upload_bundle(api, b, f"{user}/{bundle.slug(name)}")
        k = work / "kernel"
        k.mkdir(parents=True)
        (k / "official_agent_kernel.py").write_text(kernel_source((HERE / "official_agent_kernel.py").read_text(), key))
        if colab:   # no Kaggle kernel: the keyed file goes to its own private dataset, for the Colab notebook to run
            (k / "dataset-metadata.json").write_text(json.dumps(colab_kernel_metadata(user, name)))
            try:
                _upload_bundle(api, k, colab_kernel_metadata(user, name)["id"])
            finally:
                shutil.rmtree(k)   # the keyed copy does not stay on this machine
            print("ready for kaggle/colab_official_agent.ipynb; its entry in kaggle/colab_official_run.json:\n"
                  + json.dumps(colab_run_entry(user, name)), flush=True)
            return 0
        (k / "kernel-metadata.json").write_text(json.dumps(
            kernel_metadata(user, name, a.machine_shape, a.docker_image, a.competition), indent=1))
        try:
            push_kernel(api, k, a.kernel_minutes * 60, kref)
        finally:
            shutil.rmtree(k)   # the keyed copy does not stay on this machine either, whatever Kaggle answered
        print(f"the evaluator on a Kaggle GPU, {kref}", flush=True)
    t0, status = time.monotonic(), ""
    out = work / "output"
    if a.collect and reusable_output(out, getattr(a, "reuse_output", False)):
        status = "complete (its output was already downloaded)"
    elif colab:
        got = work / "colab_download"
        shutil.rmtree(got, ignore_errors=True)
        got.mkdir(parents=True)
        spec = importlib.util.spec_from_file_location("colab_official", HERE / "colab_official.py")
        co = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(co)
        co.say = lambda message: print(message, flush=True)   # its log file is the Colab machine's
        co.download_dataset(api, results, got)   # file by file where Kaggle refuses the whole
        check_colab_session((got / "colab.log").read_text(errors="replace") if (got / "colab.log").exists() else "",
                            getattr(a, "colab_session", None))
        colab_output(got, out)
        status = f"complete (run on Colab; read from {results})"
    else:
        while True:
            time.sleep(POLL_SECONDS)
            try:
                status = str(api.kernels_status(kref).status).lower()
            except Exception:  # noqa: BLE001, S112 - a blip; the next poll tells
                continue
            if any(s in status for s in ("complete", "error", "cancel")):
                break
        out.mkdir(parents=True, exist_ok=True)
        api.kernels_output(kref, str(out), force=True)
    session = time.monotonic() - t0
    res = json.loads((out / "result.json").read_text()) if (out / "result.json").exists() else {
        "error": f"kernel ended {status} and wrote no result.json"}
    print(f"kernel {status} after {session / 60:.1f} min; GPUs {(res.get('server') or {}).get('gpus') or res.get('gpus_seen')}"
          + (f"; ERROR {res['error'][:400]}" if "error" in res else ""), flush=True)
    shared = {k: res.get(k) for k in BATCH_SHARED}
    done = batch_results(res)
    gpu = {}
    for i in done:
        done[i]["trace_counts"] = batch_trace_counts(out, i)
        if (g := gpu_stats(out / "gpu_samples.csv", done[i].get("started_unix"), done[i].get("ended_unix"))):
            gpu[i] = g
    skipped = [i for i in order if i not in done]
    why = not_run_reasons(res)
    reasons = dict(Counter(why.get(i, NOT_REACHED) for i in skipped))
    if development:   # the evaluator verified each patch in the kernel, with the task's tests
        verdicts = {i: v for i, r in done.items() if (v := verdict_from_kernel(r)) is not None}
    else:
        verdicts = _verify(a.dataset / "tasks.jsonl", a.dataset / "snapshots", a.agent_dir,
                           {i: (r.get("patch") or "") for i, r in done.items()}, work / "_verify")
    rows = [row_for({"instance_id": i, **done[i]}, verdicts.get(i), "" if development else manifest.get(i, ""),
                    (colab_results_url(results) if colab else
                     f"https://www.kaggle.com/code/{kref}"), in_sample=not a.outside_sample) for i in order if i in done]
    table = pd.DataFrame(rows, columns=COLUMNS)
    if len(table):
        print(table[["instance_id", "tier_code", "is_resolved", "reason_text", "agent_patch_bytes", "tool_call_count",
                     "agent_seconds", "gpu_count", "gpu_name"]].to_string(index=False))
    print(f"\n{int(table.is_resolved.sum()) if len(table) else 0} of {len(table)} resolved, by the competition's "
          f"evaluator end to end; {len(skipped)} of the {len(order)} drawn were not run: {', '.join(skipped) or 'none'}"
          + (f" ({'; '.join(f'{k}: {v}' for k, v in reasons.items())})" if skipped else ""))
    (work / "run_summary.json").write_text(json.dumps(
        {"seed": a.seed, "order": order, "run": list(done), "not_run": skipped, "not_run_reasons": reasons,
         "session_seconds": round(session, 1),
         "gpu": gpu, "is_traced": bool(res.get("is_traced")),
         "kernel": {k: v for k, v in res.items() if k != "runs"}}, indent=1, default=str))
    if not a.no_table and rows:
        path = write_table(pd, rows, shared.get("model_name"),
                           name if development or getattr(a, "label", None) else None)
        print(f"-> {path.relative_to(REPO_ROOT)}")
        good = next((r for r in done.values() if r.get("budgets")), None)
        if good and (a.sample or getattr(a, "label", None)):
            commit = subprocess.run(["git", "-C", str(a.agent_dir), "rev-parse", "HEAD"], capture_output=True,
                                    text=True, check=False).stdout.strip() or None
            settings = settings_for(good, a.seed, list(ids), len(manifest), a.machine_shape, a.docker_image,
                                    a.competition, commit, a.source, tasks_per_kernel=len(order), colab=colab)
            if not a.sample:
                settings = given_sample(settings, getattr(a, "sample_method", None))
            settings["notes"] += a.note or []
            if getattr(a, "context_note", None):
                settings["context"] = a.context_note
            if first_ids:
                settings["sample"]["order_of"] = order_record(first_ids)
            if colab:   # nothing blocks the network at a Colab machine's edge: every command the agent ran is read
                traces = {i: json.loads(p.read_text()) for i in done
                          if (p := out / "tasks" / i / "results" / "traces" / f"trace_{i}.json").exists()}
                settings["network_audit"] = {**network_audit(traces), "traced_task_count": len(traces)}
            if skipped:   # the plan's "not run": kept beside the table, since those tasks have no row in it
                settings["not_run"] = {"task_count": len(skipped), "reason_counts": reasons, "instance_ids": skipped,
                                       "tasks": not_run_rows(res, order)}
            path.with_name(path.stem + "_settings.json").write_text(json.dumps(settings, indent=1) + "\n")
    return 0


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
    ap.add_argument("--competition", help="attach this competition to the kernel, as the starter notebook does")
    ap.add_argument("--max-time-minutes", type=float, help="override the submission's per-task time budget")
    ap.add_argument("--kernel-minutes", type=int, default=45, help="Kaggle stops a kernel after this long")
    ap.add_argument("--work", type=Path, default=Path(os.environ.get("TMPDIR", "/tmp")) / "htl_official_agent")
    ap.add_argument("--no-table", action="store_true", help="a pilot: print the rows, write no table")
    ap.add_argument("--reuse-output", action="store_true",
                    help="with --batch --collect: use the kernel's output already in the work folder, without downloading it again")
    ap.add_argument("--order-of-ids", help="with --batch, for a rerun of tasks a first kernel did not run: that run's "
                                           "ids as given then, comma-separated; each task keeps its place in its order")
    ap.add_argument("--note", action="append", help="a sentence to add to the settings file's notes (repeatable)")
    ap.add_argument("--outside-sample", action="store_true",
                    help="these tasks are not part of the drawn sample (a pilot): their rows say so")
    ap.add_argument("--colab", action="store_true",
                    help="with --batch and --label: no Kaggle kernel. Upload the sealed bundle and the keyed kernel file "
                         "for kaggle/colab_official_agent.ipynb; with --collect, read what that run sent back (#687)")
    ap.add_argument("--colab-results", help="with --collect --colab: read the run from this dataset, or from one "
                                            "version of it (owner/slug/<n>), not the one named for --label")
    ap.add_argument("--colab-session", help="with --collect --colab: collect only if the upload's log opens with this "
                                            "notebook session's start (HH:MM:SS, UTC); two sessions once shared a dataset")
    ap.add_argument("--batch", action="store_true",
                    help="every task in ONE kernel, each sealed until its turn: for when the GPU allowance cannot pay "
                         "for a kernel's start-up per task. The order is a seeded shuffle of the tasks")
    ap.add_argument("--source", choices=("published", "competition"), default="published",
                    help="competition: the competition's own development tasks, read in the kernel from the attached "
                         "competition (needs --batch and --competition); --dataset holds its tasks.jsonl only")
    ap.add_argument("--telemetry", action="store_true",
                    help="with --batch: the kernel samples the GPUs and keeps the agent framework's spans, filtered to "
                         "numbers and short labels (spec 014 US6, 036 US2); off by default, as the competition runs it")
    ap.add_argument("--sample-method", help="with --ids and --label: how the ids were chosen, for the settings file")
    ap.add_argument("--label", help="with --batch: name this batch (its dataset, kernel, work folder and table), so two "
                                    "arms of one experiment run side by side")
    ap.add_argument("--context", type=Path,
                    help="with --batch: JSON lines of instance_id and context_text (scripts/69_failure_report.py); each "
                         "drawn task's text is added after its hints, and every drawn task must have one")
    ap.add_argument("--deadline-minutes", type=float, default=45.0,
                    help="with --batch: the kernel stops starting tasks when one more could run past this")
    a = ap.parse_args()

    import pandas as pd
    tasks = {t["instance_id"]: t for t in map(json.loads,
                                              filter(str.strip, (a.dataset / "tasks.jsonl").read_text().splitlines()))}
    tiers_all = pd.read_csv(REPO_ROOT / "data" / "tasks" / "task_manifest.csv", usecols=["instance_id", "tier_code"])
    development = a.source == "competition"
    if development and not (a.batch and a.competition):
        sys.exit("--source competition reads each task from the attached competition: it needs --batch and --competition")
    manifest = strata(tasks, {r.instance_id: r.tier_code for r in tiers_all.itertuples()}, a.source)
    ids = sample(manifest, a.sample, a.seed) if a.sample else [i.strip() for i in a.ids.split(",") if i.strip()]
    missing = [i for i in ids if i not in tasks or (not development and not (a.dataset / "snapshots" / f"{i}.tgz").exists())]
    if missing:
        sys.exit(f"not in the tasks.jsonl given, or no snapshot: {', '.join(missing)}")
    check_arm_options(a.label, a.context, a.batch, development)
    batch_name(a.source, a.label)   # a bad label fails here, before anything is uploaded
    a.context_note = None
    if a.context:
        contexts = read_context(a.context)
        tasks = with_context(tasks, contexts, ids)
        a.context_note = context_note(a.context, contexts, ids)
    by_tier = {t: sum(manifest.get(i) == t for i in ids) for t in sorted(set(manifest.values()))}
    print(f"{len(ids)} tasks" + (f", drawn with seed {a.seed}, stratified by {'repository' if development else 'tier'}"
                                 if a.sample else "")
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

    if a.batch:
        return run_batch(a, api, user, ids, tasks, manifest, overrides, pd)

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
                    kernel_metadata(user, iid, a.machine_shape, a.docker_image, a.competition), indent=1))
                try:
                    pushed = api.kernels_push(str(k), timeout=str(a.kernel_minutes * 60))
                    refused = getattr(pushed, "error", None)
                except Exception as e:  # noqa: BLE001 - Kaggle's limit on GPU sessions at once shows up here
                    refused = str(e)
                if refused:
                    if not running:
                        raise SystemExit(f"{iid}: Kaggle refused the kernel with nothing else running: {refused}")
                    print(f"{iid}: Kaggle refused the kernel for now ({str(refused)[:200]}); it waits its turn", flush=True)
                    waiting.insert(0, iid)
                    break
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
            trace = out / "results" / "traces" / f"trace_{iid}.json"
            if trace.exists():
                results[iid]["trace_counts"] = trace_counts(json.loads(trace.read_text()))
            r = results[iid]
            print(f"{iid}: kernel {status}; patch {len((r.get('patch') or '').encode())} bytes, "
                  f"{r.get('tool_call_count')} tool calls, agent {r.get('agent_phase_seconds')} s, "
                  f"GPUs {(r.get('server') or {}).get('gpus')}" + (f"; ERROR {r['error'][:300]}" if "error" in r else ""),
                  flush=True)

    verdicts = _verify(a.dataset / "tasks.jsonl", a.dataset / "snapshots", a.agent_dir,
                       {i: (r.get("patch") or "") for i, r in results.items()}, a.work / "_verify")
    rows = [row_for({"instance_id": i, **results[i]}, verdicts.get(i), manifest.get(i, ""),
                    f"https://www.kaggle.com/code/{user}/{kernel_slug(i)}", in_sample=not a.outside_sample) for i in ids]
    table = pd.DataFrame(rows, columns=COLUMNS)
    print(table[["instance_id", "tier_code", "is_resolved", "reason_text", "agent_patch_bytes", "tool_call_count",
                 "agent_seconds", "gpu_count", "gpu_name"]].to_string(index=False))
    print(f"\n{int(table.is_resolved.sum())} of {len(table)} resolved, by the competition's evaluator end to end")
    if a.no_table:
        return 0
    model = next((r.get("model_name") for r in results.values() if r.get("model_name")), None)
    out = write_table(pd, rows, model)
    print(f"-> {out.relative_to(REPO_ROOT)}")
    good = next((r for r in results.values() if r.get("budgets")), None)
    if good and a.sample:
        commit = subprocess.run(["git", "-C", str(a.agent_dir), "rev-parse", "HEAD"], capture_output=True, text=True,
                                check=False).stdout.strip() or None
        settings = settings_for(good, a.seed, ids, len(manifest), a.machine_shape, a.docker_image, a.competition, commit)
        settings["notes"] += a.note or []
        out.with_name(out.stem + "_settings.json").write_text(json.dumps(settings, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
