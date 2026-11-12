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
import contextlib
import glob
import hashlib
import importlib
import io
import json
import logging
import os
import re
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
# Where the bundle, the wheelhouse and the model are. Kaggle mounts them here; a Colab run puts them elsewhere and
# says where, since Colab has a read-only folder of its own at this path (#687).
INPUT = Path(os.environ.get("HTL_INPUT", "/kaggle/input"))
ENDPOINT = os.environ.get("HTL_ENDPOINT")   # set: a dry run against a stand-in server, no wheelhouse, no vLLM
ALLOWED_MODELS = {"gemma-4-31b-it-qat-w4a16-ct", "gemma-4-12b-it-qat-w4a16-ct", "gemma-4-e4b-it-qat-w4a16-ct",
                  "gemma-4-e2b-it-qat-w4a16-ct"}
VLLM_EXTRA_ARGS = {"gemma-4-12b-it-qat-w4a16-ct": ("--hf-overrides",
                                                    '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}')}
HARNESS_NAME = "swegemma (Evaluator.evaluate_task, subprocess sandbox)"
SPAN_TEXT_KEYS = ("_name", "_code", "_id", ".name", ".model", ".type", ".system", ".operation")
MAX_SPAN_TEXT = 64   # with telemetry on, a span keeps text only as a short label: requests, replies, code stay here
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
    found = (glob.glob(str(INPUT / "**" / "official_batch.json"), recursive=True)
             or glob.glob(str(INPUT / "**" / "official_task.json"), recursive=True))
    return Path(found[0]).parent


def _keep_attribute(key: str, value) -> bool:
    """Numbers and booleans, and text only as a short label (a key ending as SPAN_TEXT_KEYS do, at most
    MAX_SPAN_TEXT characters)."""
    if isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, list):
        return all(isinstance(v, (bool, int, float)) for v in value)
    return isinstance(value, str) and len(value) <= MAX_SPAN_TEXT and key.endswith(SPAN_TEXT_KEYS)


def span_line(span) -> str:
    """One span as a JSON line in the repository's span layout (spec 014 US6), keeping what _keep_attribute keeps:
    the agent framework's spans also carry whole requests and replies (prompts, code), which never leave the kernel.
    No events, and a status without its message."""
    d = json.loads(span.to_json(indent=None))
    d["attributes"] = {k: v for k, v in (d.get("attributes") or {}).items() if _keep_attribute(k, v)}
    d["events"], d["links"] = [], []
    d["status"] = {"status_code": (d.get("status") or {}).get("status_code", "UNSET")}
    res = (d.get("resource") or {}).get("attributes") or {}
    d["resource"] = {"attributes": {k: v for k, v in res.items() if _keep_attribute(k, v)}, "schema_url": ""}
    return json.dumps(d) + "\n"


def start_tracing(path: Path):
    """With telemetry on (the runner's --telemetry): the agent framework's own spans, each model call and tool call,
    filtered (span_line) into a file beside result.json. Off by default, as the competition runs it."""
    os.environ["OTEL_SDK_DISABLED"] = "false"
    os.environ.pop("OTEL_PYTHON_DISABLED", None)
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

    out = open(path, "w", encoding="utf-8")   # one file a run: a rerun replaces it
    provider = TracerProvider(resource=Resource.create({"service.name": "health_transformation_lab",
                                                        "service.namespace": "health-transformation-lab-nlp",
                                                        "deployment.environment": "dev"}))
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=out, formatter=span_line)))
    trace.set_tracer_provider(provider)
    return provider, out


def start_gpu_sampler(path: Path, interval_ms: int = 5000):
    """nvidia-smi's own loop: each GPU's utilization, memory and power every interval_ms, to a CSV (036 US2, #569)."""
    out = open(path, "w", encoding="utf-8")
    out.write("timestamp,gpu_index,utilization_pct,memory_used_mb,power_w\n")
    out.flush()
    return subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,index,utilization.gpu,memory.used,power.draw",
                             "--format=csv,noheader,nounits", "-lms", str(interval_ms)], stdout=out,
                            stderr=subprocess.DEVNULL), out


def _task_span(instance_id: str):
    """A span around one task, so the agent framework's spans nest under it; a no-op when tracing is off."""
    try:
        from opentelemetry import trace
        return trace.get_tracer("official_agent_kernel").start_as_current_span(
            "official_agent_kernel.task", attributes={"instance_id": instance_id})
    except Exception:  # noqa: BLE001 - tracing never stops a task
        return contextlib.nullcontext()


def find_competition(root: Path | None = None) -> Path:
    """The attached competition's folder: the one holding HARNESS_README.md, tasks.jsonl and snapshots/ (028 AI4)."""
    root = Path(root) if root else INPUT
    for readme in sorted(glob.glob(str(Path(root) / "**" / "HARNESS_README.md"), recursive=True)):
        folder = Path(readme).parent
        if (folder / "tasks.jsonl").is_file() and (folder / "snapshots").is_dir():
            return folder
    raise SystemExit(f"no competition attached under {root}: a development-set batch needs it")


def stage_competition_task(comp: Path, instance_id: str, work: Path) -> None:
    """One development task, as the evaluator reads it: its row without the reference patch (its tests stay, for the
    evaluator's verification, as in the competition's own run), its snapshot, graph and embeddings linked from the
    mounted competition, never copied."""
    row = next((r for r in map(json.loads, filter(str.strip, (comp / "tasks.jsonl").read_text().splitlines()))
                if r.get("instance_id") == instance_id), None)
    if row is None:
        raise SystemExit(f"{instance_id} is not in the competition's tasks.jsonl")
    row.pop("patch", None)
    work.mkdir(parents=True, exist_ok=True)
    (work / "tasks.jsonl").write_text(json.dumps(row) + "\n")
    stem = f"{row['repo'].split('/')[-1]}_{row['base_commit']}"
    for folder, names in (("snapshots", [f"{instance_id}.tgz"]),
                          ("graphs", [f"{stem}.json", f"{instance_id}.json"]),
                          ("embeddings", [f"{stem}.npz", f"{instance_id}.npz"])):
        (work / folder).mkdir(exist_ok=True)
        for name in names:
            if (comp / folder / name).exists():
                os.symlink(comp / folder / name, work / folder / name)
    for shared in ("wheels", "sandbox"):   # the tests' dependencies and their setup script: the evaluator looks for
        if (comp / shared).exists():       # them beside tasks.jsonl (swegemma's resolve_wheels_dir), or no test runs
            os.symlink(comp / shared, work / shared)
    if not (work / "snapshots" / f"{instance_id}.tgz").exists():
        raise SystemExit(f"{instance_id} has no snapshot in the competition's files")


def check_task_fields(has_patch: bool, has_tests: bool, with_tests: bool) -> None:
    """Never run the agent beside a reference patch; tests only for a development task, whose evaluator verifies the
    patch with them after the agent phase, as the competition's own run does."""
    if has_patch:
        raise SystemExit("the task carries a reference patch: refusing to run the agent beside it")
    if has_tests and not with_tests:
        raise SystemExit("the bundle carries the task's tests: refusing to run the agent beside them")


def unseal(data: bytes, key: bytes, name: str) -> bytes:
    """What kaggle/official_agent_bundle.py's `seal` sealed: XOR with a SHAKE-256 keystream of the key and name."""
    stream = hashlib.shake_256(key + name.encode()).digest(len(data))
    return (int.from_bytes(data, "big") ^ int.from_bytes(stream, "big")).to_bytes(len(data), "big")


def wheel_fits(name: str, version: tuple = tuple(sys.version_info[:2])) -> bool:
    """Whether a wheel's file name says it installs on this Python: a pure-Python or abi3 wheel for this version or
    an earlier one, or a wheel compiled for exactly this version. The wheelhouse is built for Kaggle's Python 3.12,
    where every wheel fits. On another Python (Colab's is 3.13) the few compiled for 3.12 alone are left out, since
    pip refuses the whole install if one is named, and those packages stay as the machine has them."""
    tags = name[:-len(".whl")].split("-")[-3:]
    if len(tags) < 3:
        return True
    for one in tags[0].split("."):
        m = re.fullmatch(r"(py|cp)(\d)(\d*)", one)
        if not m or int(m.group(2)) != version[0]:
            continue
        built_for = (int(m.group(2)), int(m.group(3) or 0))
        if built_for == tuple(version) or ((m.group(1) == "py" or tags[1] == "abi3") and built_for <= tuple(version)):
            return True
    return False


def install_wheelhouse() -> Path:
    """The starter notebook's cell 2: every wheel of the wheelhouse dataset, no dependencies resolved."""
    wheelhouse = Path(glob.glob(str(INPUT / "**" / "swegemma-*.whl"), recursive=True)[0]).parent
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
    left_out = sorted(Path(w).name for w in wheels if not wheel_fits(Path(w).name))
    if left_out:   # never on Kaggle, whose Python the wheelhouse is built for
        result["wheels_left_out"] = left_out
        wheels = [w for w in wheels if Path(w).name not in left_out]
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels], check=True)
    importlib.invalidate_caches()
    return wheelhouse


def start_vllm(agent_dir: Path, declared_model: str):
    """The starter notebook's cell 8: vLLM on every GPU, the Gemma 4 tool-call and reasoning parsers."""
    import torch
    from adk_submission import VllmConfig, VllmServer, discover_adapters
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS

    model_path = Path(glob.glob(str(INPUT / "**" / declared_model / "**" / "config.json"), recursive=True)[0]).parent
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


def run_task(bundle: Path, agent_dir: Path, models, adapters, overrides: dict, out_dir: Path,
             with_tests: bool = False) -> dict:
    """The starter notebook's cell 10 for one task, with the agent's patch kept as soon as the agent phase ends.
    `with_tests`: a development task, whose tests the evaluator's verification uses; its verdict is kept."""
    import litellm
    import yaml
    from google.adk.agents.context_cache_config import ContextCacheConfig
    from google.adk.apps._configs import EventsCompactionConfig
    from swegemma.config import EvalConfig, build_submission_limits
    from swegemma.evaluate import Evaluator
    from swegemma.models import load_tasks

    litellm.drop_params = True
    task = load_tasks(bundle / "tasks.jsonl")[0]
    check_task_fields(bool(task.patch), bool(task.test_patch), with_tests)
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
           }
    if with_tests:   # a development task: the evaluator verified the patch with the task's tests, as the competition does
        out["verification"] = {"is_resolved": bool(res.resolved), "test_exit_code": res.test_exit_code}
    else:            # ours: the evaluator's verification ran without the task's tests (the bundle has none): not a verdict
        out["kaggle_verification_without_tests"] = {"is_resolved": bool(res.resolved), "test_exit_code": res.test_exit_code}
    for key in ("total_input_tokens", "total_output_tokens", "total_tokens", "total_cost_usd", "trace_path"):
        if getattr(res, key, None) is not None:
            out[key] = getattr(res, key)
    return out


def server_gone(done: list) -> bool:
    """True when the last two tasks made no model call and ended at their time limit or on a server error: the
    model server has stopped answering, and every further task would only spend the GPU allowance. Two tasks that
    fail before any call for another reason (the submission's own prompt) are the agent's, and the batch goes on."""
    marks = ("session timeout", "InternalServerError", "Connection error", "APIConnectionError", "ServiceUnavailable")
    last = done[-2:]
    return len(last) == 2 and all(r.get("llm_call_count") == 0 and any(m in (r.get("agent_error") or "") for m in marks)
                                  for r in last)


def run_batch(root: Path, meta: dict, key: bytes, agent_dir: Path, models, adapters) -> dict:
    """Each task of the batch in turn: open its sealed files, run it, delete them. Stops before a task that could
    not finish inside the kernel's own time budget, so the GPU allowance is never overrun mid-task."""
    overrides = meta.get("budget_overrides") or {}
    from_competition = meta.get("source") == "competition"
    comp = find_competition() if from_competition else None
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
        started_unix = time.time()
        try:
            if from_competition:
                stage_competition_task(comp, iid, work)
            else:
                plain = unseal((root / "sealed" / f"{iid}.bin").read_bytes(), key, iid)
                with tarfile.open(fileobj=io.BytesIO(plain)) as tar:
                    tar.extractall(work, filter="data")
                del plain
            with _task_span(iid):
                one = run_task(work, agent_dir, models, adapters, overrides, OUT / "tasks" / iid,
                               with_tests=from_competition)
        except BaseException as e:  # noqa: BLE001 - one task's failure is its row; the next task still runs
            one = {"instance_id": iid, "error": f"{type(e).__name__}: {str(e)[:1500]}",
                   "trace": traceback.format_exc()[-4000:]}
        finally:
            shutil.rmtree(work, ignore_errors=True)   # the next task must not find this one's snapshot
        one["elapsed_minutes_at_end"] = round((time.monotonic() - T_START) / 60, 2)
        one["started_unix"], one["ended_unix"] = round(started_unix, 3), round(time.time(), 3)
        runs[iid] = one
        dead = [r for r in runs.values() if "error" in r or (r.get("agent_error") and not r.get("tool_call_count"))]
        if len(runs) == 2 and len(dead) == 2:   # both of the first two failed outright: stop, keep the allowance
            for rest in meta["instance_ids"]:
                runs.setdefault(rest, {"instance_id": rest, "is_skipped": True,
                                       "skip_reason_text": "stopped: the first two tasks failed outright"})
        if server_gone([r for r in runs.values() if not r.get("is_skipped")]):
            for rest in meta["instance_ids"]:
                runs.setdefault(rest, {"instance_id": rest, "is_skipped": True,
                                       "skip_reason_text": "stopped: two tasks in a row had no answer from the model server"})
        (OUT / "tasks" / iid).mkdir(parents=True, exist_ok=True)
        (OUT / "tasks" / iid / "result.json").write_text(json.dumps(one, indent=1, default=str))
        print(json.dumps({k: v for k, v in one.items() if k not in ("patch", "trace")}, default=str), flush=True)
    return runs


def main() -> None:
    server, sampler, tracer = None, None, None
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
        if meta.get("telemetry") and not ENDPOINT:   # before the agent framework is imported
            try:
                sampler = start_gpu_sampler(OUT / "gpu_samples.csv")
            except Exception as e:  # noqa: BLE001 - telemetry never stops the run
                result["gpu_sampler_error"] = f"{type(e).__name__}: {str(e)[:300]}"
            try:
                tracer = start_tracing(OUT / "telemetry.jsonl")
                result["is_traced"] = True
            except Exception as e:  # noqa: BLE001
                result["tracing_error"] = f"{type(e).__name__}: {str(e)[:300]}"
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
        for stop in ((lambda: (sampler[0].terminate(), sampler[1].close())) if sampler else None,
                     (lambda: (tracer[0].shutdown(), tracer[1].close())) if tracer else None):
            if stop is not None:
                try:
                    stop()
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
