# Spec 028 US5 (T011b, #636): ONE task through the competition's OWN evaluator on a Kaggle GPU. The agent loop is
# swegemma's (Evaluator.evaluate_task, subprocess sandbox), the model server is vLLM from the competition's wheelhouse
# dataset, and the steps follow the competition's starter notebook (ryanholbrook/getting-started-gemma-4-developer-agent,
# cells 2, 8 and 10). What differs from that notebook: the task comes from this task's private bundle
# (kaggle/official_agent_bundle.py), not the competition's dataset, and the bundle holds no reference patch and no
# tests. So the evaluator's verification step has nothing to verify here; the agent's patch is verified afterwards
# with the same evaluator's verify_task on the published snapshot (kaggle/official_verify.py). Internet off.
#
# Writes /kaggle/working/result.json: the agent's patch, the evaluator's counts, the settings and versions used, and
# the evaluator's own log and trace for the task.
#
# A batch (official_batch.json in the bundle) runs several tasks in this one kernel, when the GPU allowance cannot pay
# for a kernel's start-up per task. Each task's files are sealed in the dataset; this kernel opens one, runs it,
# deletes it, then opens the next, so the agent never has two tasks' snapshots within reach. The key is put in this
# file by the runner (SEAL_KEY), read at start, and the file is then removed from the machine.
#
# HTL_ENDPOINT (a dry run without a GPU): an OpenAI-compatible endpoint to use instead of installing the wheelhouse
# and starting vLLM. HTL_BUNDLE and HTL_OUT point at the bundle and the output folder.
import asyncio
import glob
import hashlib
import importlib
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
from pathlib import Path

SEAL_KEY = ""   # set by the runner for a batch (kaggle/official_agent_run.py); never committed
T_START = time.monotonic()

for _k, _v in {"TRANSFORMERS_NO_TF": "1", "TRANSFORMERS_NO_FLAX": "1", "TRANSFORMERS_OFFLINE": "1",
               "VLLM_NO_USAGE_STATS": "1", "VLLM_WORKER_MULTIPROC_METHOD": "spawn", "VLLM_ENGINE_READY_TIMEOUT_S": "1200",
               "VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS": "1", "NCCL_DEBUG": "WARN", "LITELLM_LOCAL_MODEL_COST_MAP": "True",
               "LITELLM_TELEMETRY": "False", "LITELLM_LOG": "WARNING", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
               "OTEL_SDK_DISABLED": "true", "OTEL_PYTHON_DISABLED": "true", "MLFLOW_DISABLE_AGENT_HINT": "1"}.items():
    os.environ[_k] = _v
os.environ.setdefault("OPENAI_API_KEY", "EMPTY")
os.environ.setdefault("LOCAL_API_KEY", "EMPTY")

OUT = Path(os.environ.get("HTL_OUT", "/kaggle/working"))
ENDPOINT = os.environ.get("HTL_ENDPOINT")   # set: a dry run against a stand-in server, no wheelhouse, no vLLM
ALLOWED_MODELS = {"gemma-4-31b-it-qat-w4a16-ct", "gemma-4-12b-it-qat-w4a16-ct", "gemma-4-e4b-it-qat-w4a16-ct",
                  "gemma-4-e2b-it-qat-w4a16-ct"}
VLLM_EXTRA_ARGS = {"gemma-4-12b-it-qat-w4a16-ct": ("--hf-overrides",
                                                    '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}')}
HARNESS_NAME = "swegemma (Evaluator.evaluate_task, subprocess sandbox)"
result: dict = {"started_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def quiet_logging() -> None:
    for name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy", "litellm", "httpx", "httpcore", "openai", "urllib3",
                 "opentelemetry", "opentelemetry.context"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.WARNING)
        if "litellm" in name.lower():
            lg.propagate = False
            lg.handlers.clear()


def find_bundle() -> Path:
    if os.environ.get("HTL_BUNDLE"):
        return Path(os.environ["HTL_BUNDLE"])
    found = (glob.glob("/kaggle/input/**/official_batch.json", recursive=True)
             or glob.glob("/kaggle/input/**/official_task.json", recursive=True))
    return Path(found[0]).parent


def unseal(data: bytes, key: bytes, name: str) -> bytes:
    """What kaggle/official_agent_bundle.py's `seal` sealed: XOR with a SHAKE-256 keystream of the key and name."""
    stream = hashlib.shake_256(key + name.encode()).digest(len(data))
    return (int.from_bytes(data, "big") ^ int.from_bytes(stream, "big")).to_bytes(len(data), "big")


def install_wheelhouse() -> Path:
    """The starter notebook's cell 2: every wheel of the wheelhouse dataset, no dependencies resolved."""
    wheelhouse = Path(glob.glob("/kaggle/input/**/swegemma-*.whl", recursive=True)[0]).parent
    for pattern in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth", "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
        for pth in glob.glob(pattern):
            try:
                os.unlink(pth)
            except OSError:
                pass
    tmp = Path("/tmp/wheelhouse")
    tmp.mkdir(parents=True, exist_ok=True)
    for w in wheelhouse.glob("*.whl"):
        if "cutlass" in w.name.lower():
            continue
        name = w.name.replace("cu128", "+cu128") if ("cu128" in w.name and "+" not in w.name) else w.name
        if not (tmp / name).exists():
            try:
                os.symlink(w, tmp / name)
            except OSError:
                shutil.copyfile(w, tmp / name)
    wheels = sorted(str(w) for w in tmp.glob("*.whl"))
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels], check=True)
    importlib.invalidate_caches()
    return wheelhouse


def start_vllm(agent_dir: Path, declared_model: str):
    """The starter notebook's cell 8: vLLM on every GPU, the Gemma 4 tool-call and reasoning parsers."""
    import torch
    from adk_submission import VllmConfig, VllmServer, discover_adapters
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS

    model_path = Path(glob.glob(f"/kaggle/input/**/{declared_model}/**/config.json", recursive=True)[0]).parent
    adapters = discover_adapters(str(agent_dir), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
    adapter_map = getattr(adapters, "adapters", None) or {}
    ranks = [r for info in adapter_map.values() if (r := getattr(info, "rank", None)) is not None and r > 0]
    gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 1
    tp_size = 4 if gpu_count >= 4 else (2 if gpu_count >= 2 else 1)
    # The starter notebook asks torch whether bfloat16 is supported; on a T4 torch says yes and vLLM then refuses it
    # (compute capability below 8.0). So ask for the capability itself, and use float16 where bfloat16 is not native.
    capability = min(torch.cuda.get_device_capability(i) for i in range(gpu_count)) if torch.cuda.is_available() else (0, 0)
    dtype = "bfloat16" if capability >= (8, 0) else "float16"
    cfg = VllmConfig(
        model=str(model_path), port=8000, host="127.0.0.1", tool_call_parser="gemma4", reasoning_parser="gemma4",
        max_model_len=32768, dtype=dtype, gpu_memory_utilization=0.90, enable_auto_tool_choice=True,
        enable_lora=bool(adapter_map), max_loras=max(1, len(adapter_map)), max_lora_rank=max(ranks) if ranks else 128,
        scheduler_reserve_full_isl=False, tensor_parallel_size=tp_size, startup_timeout=60 * 20,
        extra_args=VLLM_EXTRA_ARGS.get(declared_model, ()))
    server = VllmServer(cfg, adapter_manifest=adapters)
    server.start()
    models = server.create_model_registry(aliases=[declared_model], model_prefix="openai/",
                                          api_key=os.environ.get("LOCAL_API_KEY", "EMPTY"))
    info = {"server_name": "vLLM", "model_path": str(model_path), "dtype": dtype, "tensor_parallel_size": tp_size,
            "compute_capability": ".".join(map(str, capability)), "self_test": self_test(server),
            "max_model_len": 32768, "gpu_memory_utilization": 0.90, "tool_call_parser": "gemma4",
            "reasoning_parser": "gemma4",
            "gpus": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}
    return server, models, adapters, info


def self_test(server) -> dict:
    """One short completion straight to the server before any task: a server that cannot answer stops the kernel
    here, not after it has spent the GPU allowance on tasks that all fail the same way."""
    import urllib.request
    base = str(getattr(server, "base_url", "http://127.0.0.1:8000/v1")).rstrip("/")
    with urllib.request.urlopen(f"{base}/models", timeout=60) as r:
        model_id = json.loads(r.read())["data"][0]["id"]
    body = json.dumps({"model": model_id, "max_tokens": 16, "temperature": 0,
                       "messages": [{"role": "user", "content": "Reply with the single word: ready"}]}).encode()
    req = urllib.request.Request(f"{base}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read())
    msg = out["choices"][0]["message"]
    return {"seconds": round(time.monotonic() - t0, 1), "completion_tokens": (out.get("usage") or {}).get("completion_tokens"),
            "reply_text": str(msg.get("content") or msg.get("reasoning_content") or "")[:80]}


def versions() -> dict:
    from importlib import metadata
    out = {}
    for pkg in ("swegemma", "adk-submission", "adk-eval-core", "google-adk", "vllm", "transformers", "torch", "litellm"):
        try:
            out[pkg] = metadata.version(pkg)
        except Exception:  # noqa: BLE001 - a package the dry run does not have
            out[pkg] = None
    return out


def run_task(bundle: Path, agent_dir: Path, models, adapters, overrides: dict, out_dir: Path) -> dict:
    """The starter notebook's cell 10 for one task, with the agent's patch kept as soon as the agent phase ends."""
    import litellm
    import yaml
    from google.adk.agents.context_cache_config import ContextCacheConfig
    from google.adk.apps._configs import EventsCompactionConfig
    from swegemma.config import EvalConfig, build_submission_limits
    from swegemma.evaluate import Evaluator
    from swegemma.models import load_tasks

    litellm.drop_params = True
    task = load_tasks(bundle / "tasks.jsonl")[0]
    if task.patch or task.test_patch:
        raise SystemExit("the bundle carries a reference patch or tests: refusing to run the agent beside them")
    cfg_file = next((c for n in ("eval_config.yaml", "eval_config.yml") if (c := agent_dir / n).is_file()), None)
    raw = (yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}) if cfg_file else {}
    section = {**raw.get("evaluation", raw), **{k: v for k, v in overrides.items() if v is not None}}
    turns_raw = section.get("max_turns", section.get("max_llm_calls"))
    budgets = {"timeout_seconds": int(section.get("timeout_seconds", 300)),
               "verification_timeout_seconds": int(section.get("verification_timeout_seconds", 300)),
               "max_tool_calls": int(section.get("max_tool_calls", 100)),
               "max_time_minutes": float(section.get("max_time_minutes", 60.0)),
               "max_turns": int(turns_raw) if turns_raw is not None else None}
    limits, gen = build_submission_limits()
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir = out_dir / "results"
    config = EvalConfig(
        tasks_path=bundle / "tasks.jsonl", snapshots_dir=bundle / "snapshots", results_dir=results_dir,
        submission_dir=agent_dir, models=models, sandbox="subprocess", limits=limits, generation_constraints=gen,
        adapter_manifest=adapters,
        context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
        events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=14336,
                                                        event_retention_size=5),
        graph_dir=str(bundle / "graphs"), embeddings_dir=str(bundle / "embeddings"), verbose=False,
        display_mode="quiet", **budgets)
    kept: dict = {}

    class KeepingEvaluator(Evaluator):
        """The evaluator, unchanged, that also writes the agent phase's patch down before its verification step."""

        async def _run_agent_sandbox(self, *args, **kwargs):
            t0 = time.monotonic()
            patch, error, trace = await super()._run_agent_sandbox(*args, **kwargs)
            kept.update(patch=patch or "", agent_error=error, agent_phase_seconds=round(time.monotonic() - t0, 1))
            (out_dir / "agent_patch.diff").write_text(patch or "")
            return patch, error, trace

    evaluator = KeepingEvaluator(config)
    t0 = time.monotonic()
    res = asyncio.run(evaluator.evaluate_task(task=task, task_index=1, total_tasks=1))
    out = {"instance_id": task.instance_id, "patch": kept.get("patch", res.agent_patch or ""),
           "agent_error": kept.get("agent_error"), "agent_phase_seconds": kept.get("agent_phase_seconds"),
           "evaluate_seconds": round(time.monotonic() - t0, 1), "tool_call_count": int(res.tool_calls or 0),
           "llm_call_count": getattr(res, "total_llm_calls", None), "error_text": getattr(res, "error_message", None),
           "budgets": budgets, "generation_defaults": dict(gen.defaults or {}),
           "context_cache": {"min_tokens": 2048, "ttl_seconds": 1800, "cache_intervals": 10},
           "events_compaction": {"compaction_interval": 15, "overlap_size": 2, "token_threshold": 14336,
                                 "event_retention_size": 5},
           # the evaluator's own verification ran without the task's tests (the bundle has none): not a verdict
           "kaggle_verification_without_tests": {"is_resolved": bool(res.resolved), "test_exit_code": res.test_exit_code}}
    for key in ("total_input_tokens", "total_output_tokens", "total_tokens", "total_cost_usd", "trace_path"):
        if getattr(res, key, None) is not None:
            out[key] = getattr(res, key)
    return out


def run_batch(root: Path, meta: dict, key: bytes, agent_dir: Path, models, adapters) -> dict:
    """Each task of the batch in turn: open its sealed files, run it, delete them. Stops before a task that could
    not finish inside the kernel's own time budget, so the GPU allowance is never overrun mid-task."""
    overrides = meta.get("budget_overrides") or {}
    deadline = T_START + float(meta.get("deadline_minutes", 45)) * 60
    per_task = float(meta.get("task_minutes_reserved", 6.5)) * 60
    runs: dict = {}
    for iid in meta["instance_ids"]:
        if iid in runs:
            continue
        if time.monotonic() + per_task > deadline:
            runs[iid] = {"instance_id": iid, "is_skipped": True, "skip_reason_text": "the kernel's time budget ran out"}
            continue
        work = Path("/tmp/htl_task")
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        try:
            plain = unseal((root / "sealed" / f"{iid}.bin").read_bytes(), key, iid)
            with tarfile.open(fileobj=io.BytesIO(plain)) as tar:
                tar.extractall(work, filter="data")
            del plain
            one = run_task(work, agent_dir, models, adapters, overrides, OUT / "tasks" / iid)
        except BaseException as e:  # noqa: BLE001 - one task's failure is its row; the next task still runs
            one = {"instance_id": iid, "error": f"{type(e).__name__}: {str(e)[:1500]}",
                   "trace": traceback.format_exc()[-4000:]}
        finally:
            shutil.rmtree(work, ignore_errors=True)   # the next task must not find this one's snapshot
        one["elapsed_minutes_at_end"] = round((time.monotonic() - T_START) / 60, 2)
        runs[iid] = one
        dead = [r for r in runs.values() if "error" in r or (r.get("agent_error") and not r.get("tool_call_count"))]
        if len(runs) == 2 and len(dead) == 2:   # both of the first two failed outright: stop, keep the allowance
            for rest in meta["instance_ids"]:
                runs.setdefault(rest, {"instance_id": rest, "is_skipped": True,
                                       "skip_reason_text": "stopped: the first two tasks failed outright"})
        (OUT / "tasks" / iid).mkdir(parents=True, exist_ok=True)
        (OUT / "tasks" / iid / "result.json").write_text(json.dumps(one, indent=1, default=str))
        print(json.dumps({k: v for k, v in one.items() if k not in ("patch", "trace")}, default=str), flush=True)
    return runs


def main() -> None:
    server = None
    try:
        bundle = find_bundle()
        is_batch = (bundle / "official_batch.json").exists()
        meta = json.loads((bundle / ("official_batch.json" if is_batch else "official_task.json")).read_text())
        result.update(harness_name=HARNESS_NAME, is_dry_run=bool(ENDPOINT), is_batch=is_batch)
        key = bytes.fromhex(SEAL_KEY) if is_batch else b""
        if is_batch and not ENDPOINT:
            try:
                os.remove(__file__)   # the key was only here; now it is only in this process
                result["is_source_removed"] = True
            except OSError:
                result["is_source_removed"] = False
        if not is_batch:
            result["instance_id"] = meta["instance_id"]
        agent_dir = OUT / "submission"   # a writable copy, as the starter notebook makes
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
        shutil.copytree(bundle / "submission", agent_dir)
        if not ENDPOINT:
            smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                 capture_output=True, text=True, check=False)
            result["gpus_seen"] = [line.strip() for line in smi.stdout.splitlines() if line.strip()]
            t = time.monotonic()
            result["wheelhouse"] = str(install_wheelhouse())
            result["install_seconds"] = round(time.monotonic() - t, 1)
        quiet_logging()
        from adk_submission.discovery import discover_declared_models
        declared = discover_declared_models(agent_dir)
        if len(declared) != 1 or next(iter(declared)) not in ALLOWED_MODELS:
            raise SystemExit(f"the submission must declare exactly one of {sorted(ALLOWED_MODELS)}: {sorted(declared)}")
        model_name = next(iter(declared))
        if ENDPOINT:
            os.environ["LOCAL_INFERENCE_URL"] = ENDPOINT
            from adk_submission import discover_adapters
            from swegemma.cli import _build_cli_model_registry
            models, adapters = _build_cli_model_registry(submission_dir=agent_dir), discover_adapters(str(agent_dir))
            server_info = {"server_name": "stand-in endpoint (dry run)"}
        else:
            t = time.monotonic()
            server, models, adapters, server_info = start_vllm(agent_dir, model_name)
            result["load_seconds"] = round(time.monotonic() - t, 1)
        result.update(model_name=model_name, server=server_info, versions=versions())
        if is_batch:
            result["runs"] = run_batch(bundle, meta, key, agent_dir, models, adapters)
        else:
            result.update(run_task(bundle, agent_dir, models, adapters, meta.get("budget_overrides") or {}, OUT))
    except BaseException as e:  # noqa: BLE001 - the failure goes in result.json, where the runner reads it
        result.update(error=f"{type(e).__name__}: {str(e)[:1500]}", trace=traceback.format_exc()[-6000:])
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "error_full.txt").write_text(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")   # a server's whole output
    finally:
        if server is not None:
            try:
                server.stop()
            except Exception:  # noqa: BLE001, S110 - the kernel is ending anyway
                pass
    shutil.rmtree(OUT / "submission", ignore_errors=True)
    result["finished_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    OUT.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in result.items() if k != "runs"}
    slim["runs"] = {i: {k: v for k, v in r.items() if k != "trace"} for i, r in (result.get("runs") or {}).items()}
    (OUT / "result.json").write_text(json.dumps(slim if result.get("is_batch") else result, indent=1, default=str))
    print(json.dumps({k: v for k, v in result.items() if k not in ("patch", "trace", "runs")}, indent=1, default=str))
    if "error" in result:
        print(result["trace"])


if __name__ == "__main__":
    main()
