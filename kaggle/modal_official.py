"""The competition's evaluator loop on a Modal GPU, started from GitHub Actions (028 AI15, #804).

Modal is one more Linux machine with a GPU, as Colab is (kaggle/colab_official.py), so a run here is that helper's
`run_one`: the same pinned packages, the inputs laid out as Kaggle mounts them, one sealed bundle (no fix and no tests
beside the agent), the results sent to the same private Kaggle dataset, and the same refusal to start a run whose
entry in the run list does not accept an open network (ADR 0005). What differs:

- **It starts from GitHub Actions** (.github/workflows/modal-agent.yml), so each run matches a commit, and the helper
  reads the run list from that commit (`point_at_checkout`), not from the tip of `main` over the network.
- **The dollar cap is Modal's own time limit.** Modal bills the GPU by the second, so the run's `max_usd`, at the GPU's
  price in ops/cost_settings.yaml, becomes the function's timeout: the GPU cannot run past it. The CPU and memory beside
  it cost a little more and are not capped. A run that stops at the limit resumes where it stopped when started again
  (the helper restores what it already sent to Kaggle).
- **The Kaggle credentials reach the machine for this run only** (`modal.Secret.from_local_environ`), from the GitHub
  environment `dev`; nothing is stored in Modal.

    python kaggle/modal_official.py preflight --label <label> --gpu L4 --max-usd 5 >> "$GITHUB_ENV"
    modal run --detach kaggle/modal_official.py --label <label> --gpu L4 --max-usd 5

Needs MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (the Modal CLI reads them), KAGGLE_USERNAME, and KAGGLE_API_TOKEN (or
KAGGLE_KEY). Every value stays in the environment: none is printed.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETTINGS = HERE.parent / "ops" / "cost_settings.yaml"
RUN_LIST = "colab_official_run.json"
HELPER = "colab_official.py"
GPUS = ("L4", "A10", "A100-40GB")                          # Modal's names; Modal checks them when the run starts
PRICE_KEYS = {"L4": "modal_l4_usd_per_gpu_hour", "A10": "modal_a10_usd_per_gpu_hour",
              "A100-40GB": "modal_a100_40gb_usd_per_gpu_hour"}
MAX_TIMEOUT_SECONDS = 24 * 3600                            # Modal's longest time limit for one function call
MIN_TIMEOUT_SECONDS = 20 * 60                              # less cannot load the model and run one task
REMOTE_DIR = "/htl/kaggle"                                 # where the helper and the run list sit on the machine
CREDENTIALS = ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "KAGGLE_USERNAME")
# The packages the helper installs (colab_official.PINS), baked into the image so a run does not wait for them. Kept
# as a copy because this file is imported on Modal's machine too, where the helper is not beside it; a test keeps
# them equal.
PINS = ("vllm==0.19.1", "google-adk==1.36.1", "litellm==1.82.4", "kagglehub", "kaggle==2.2.5", "six", "pytest",
        "pyyaml", "docker")


def gpu_choice(name: str) -> str:
    """The GPU as Modal names it, or a refusal naming the choices."""
    wanted = str(name).strip().upper()
    for gpu in GPUS:
        if gpu.upper() == wanted:
            return gpu
    raise SystemExit(f"gpu {name!r} is not offered here; choose one of {', '.join(GPUS)}")


def load_prices(path: Path = SETTINGS) -> dict:
    """Each GPU's Modal price per GPU-hour with its source and read date, from ops/cost_settings.yaml."""
    import yaml
    settings = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    prices = {}
    for gpu, key in PRICE_KEYS.items():
        entry = settings.get(key) or {}
        if not (isinstance(entry.get("value"), (int, float)) and entry["value"] > 0 and entry.get("source")
                and entry.get("read_date")):
            raise SystemExit(f"{Path(path).name}: {key} needs a positive value, a source and a read_date")
        prices[gpu] = entry
    return prices


def timeout_seconds(max_usd: float, usd_per_gpu_hour: float) -> int:
    """How long the GPU may run for `max_usd` at this price: Modal stops the function there."""
    try:
        usd = float(max_usd)
    except (TypeError, ValueError):
        raise SystemExit(f"max_usd {max_usd!r} is not a number") from None
    if usd <= 0:
        raise SystemExit("max_usd must be above 0")
    seconds = math.floor(usd / usd_per_gpu_hour * 3600)
    if seconds < MIN_TIMEOUT_SECONDS:
        raise SystemExit(f"max_usd {usd:g} buys {seconds} seconds at {usd_per_gpu_hour} USD an hour, under the "
                         f"{MIN_TIMEOUT_SECONDS // 60} minutes one task needs; raise max_usd")
    return min(seconds, MAX_TIMEOUT_SECONDS)


def credential_problems(env) -> list[str]:
    """What is missing or malformed among the credentials, by name. A value is never put in the message."""
    problems = []
    names = list(CREDENTIALS) + ["KAGGLE_API_TOKEN"]
    for name in names:
        value = env.get(name) or (env.get("KAGGLE_KEY") if name == "KAGGLE_API_TOKEN" else "")
        if not value:
            problems.append(f"{name} is not set in the GitHub environment 'dev'"
                            + (" (or KAGGLE_KEY)" if name == "KAGGLE_API_TOKEN" else ""))
        elif any(c.isspace() for c in value):
            problems.append(f"{name} holds whitespace: copy it again, whole, into the GitHub environment 'dev'")
    return problems


def load_helper(kaggle_dir: Path):
    """kaggle/colab_official.py as this checkout has it."""
    spec = importlib.util.spec_from_file_location("colab_official", Path(kaggle_dir) / HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def point_at_checkout(co, kaggle_dir: Path):
    """Make the helper read its run list from this checkout. It fetches the branch's files over the network, and its
    functions take that reader as a default argument, so the default is swapped wherever it appears."""
    original = co.branch_file

    def from_checkout(name: str) -> str:
        return (Path(kaggle_dir) / name).read_text(encoding="utf-8")

    co.branch_file = from_checkout
    for obj in vars(co).values():
        if inspect.isfunction(obj) and obj.__defaults__ and any(d is original for d in obj.__defaults__):
            obj.__defaults__ = tuple(from_checkout if d is original else d for d in obj.__defaults__)
    return co


def run_entry(label: str, kaggle_dir: Path) -> dict:
    """The run's entry in this checkout's run list. Refused when it is not listed, names no bundle, or does not accept
    an open network in so many words (ADR 0005)."""
    plan = json.loads((Path(kaggle_dir) / RUN_LIST).read_text(encoding="utf-8"))
    entry = next((r for r in plan.get("runs", []) if r.get("label") == label), None)
    if entry is None:
        raise SystemExit(f"{label} is not in kaggle/{RUN_LIST} on this branch; add its entry there first")
    if not entry.get("bundle"):
        raise SystemExit(f"{label}: its entry names no bundle")
    if entry.get("network_open_acknowledged") is not True:
        raise SystemExit(f"{label}: its entry must say \"network_open_acknowledged\": true, on the run's own branch "
                         "(ADR 0005): nothing blocks the network on the machine")
    return entry


def plan(label: str, gpu: str, max_usd: float, env, kaggle_dir: Path = HERE, settings: Path = SETTINGS) -> dict:
    """Everything checked before Modal is called, every problem reported together."""
    problems = list(credential_problems(env))
    entry, chosen, price, seconds = None, None, None, None
    for step in ("entry", "gpu", "price"):
        try:
            if step == "entry":
                entry = run_entry(label, kaggle_dir)
            elif step == "gpu":
                chosen = gpu_choice(gpu)
            elif chosen:
                price = load_prices(settings)[chosen]
                seconds = timeout_seconds(max_usd, price["value"])
        except SystemExit as e:
            problems.append(str(e))
    if price is None and chosen is None:
        try:
            timeout_seconds(max_usd, 1.0)
        except SystemExit as e:
            problems.append(str(e))
    if problems:
        raise SystemExit("not started:\n- " + "\n- ".join(problems))
    return {"label": label, "bundle": entry["bundle"], "kernel_dataset": entry.get("kernel_dataset"),
            "kernel_url": entry.get("kernel_url"), "model": entry.get("model"), "gpu": chosen,
            "max_usd": float(max_usd), "usd_per_gpu_hour": price["value"],
            "price_source": f"{price['source']} (read {price['read_date']})", "timeout_seconds": seconds}


def cli(argv: list[str] | None = None, env=None, kaggle_dir: Path = HERE) -> dict:
    """`preflight`: check everything, then print the GPU and the time limit as KEY=VALUE lines for $GITHUB_ENV, and
    the plan (no credential in it) on stderr."""
    ap = argparse.ArgumentParser(prog="modal_official.py")
    ap.add_argument("command", choices=["preflight"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--gpu", default="L4")
    ap.add_argument("--max-usd", default="5")
    a = ap.parse_args(argv)
    p = plan(a.label, a.gpu, a.max_usd, os.environ if env is None else env, kaggle_dir)
    print(f"HTL_MODAL_GPU={p['gpu']}")
    print(f"HTL_MODAL_TIMEOUT={p['timeout_seconds']}")
    print(json.dumps(p, indent=1), file=sys.stderr)
    return p


try:                                                       # the preflight and the tests run without Modal installed
    import modal
except ImportError:
    modal = None

if modal is not None and __name__ != "__main__":   # `modal run` and the machine import this file
    GPU = os.environ.get("HTL_MODAL_GPU", "L4")
    TIMEOUT = int(os.environ.get("HTL_MODAL_TIMEOUT", str(MIN_TIMEOUT_SECONDS)))
    image = (modal.Image.debian_slim(python_version="3.13")              # Colab's Python, as the Colab runs had
             .pip_install(*PINS)
             .env({"HTL_MODAL_GPU": GPU, "HTL_MODAL_TIMEOUT": str(TIMEOUT)})
             .add_local_file(HERE / HELPER, f"{REMOTE_DIR}/{HELPER}")
             .add_local_file(HERE / RUN_LIST, f"{REMOTE_DIR}/{RUN_LIST}"))
    app = modal.App("htlnlp-official-agent", image=image)

    @app.function(gpu=GPU, timeout=TIMEOUT, retries=0, max_containers=1,
                  secrets=[modal.Secret.from_local_environ(["KAGGLE_USERNAME", "KAGGLE_API_TOKEN"])])
    def run_on_gpu(p: dict) -> int:
        """One run on the GPU: the helper's `run_one`, reading the run list from the files of this commit."""
        co = point_at_checkout(load_helper(Path(REMOTE_DIR)), Path(REMOTE_DIR))
        return co.run_one(p["label"], p["bundle"], p.get("kernel_dataset"), p.get("kernel_url"), model=p.get("model"))

    @app.local_entrypoint()
    def main(label: str, gpu: str = "L4", max_usd: str = "5"):
        p = plan(label, gpu, max_usd, os.environ)
        if (p["gpu"], p["timeout_seconds"]) != (GPU, TIMEOUT):
            raise SystemExit("run the workflow's preflight first: its HTL_MODAL_GPU and HTL_MODAL_TIMEOUT must match "
                             f"this run ({p['gpu']}, {p['timeout_seconds']} s)")
        print(f"{label}: {p['gpu']} for at most {p['timeout_seconds']} s ({p['max_usd']:g} USD at "
              f"{p['usd_per_gpu_hour']} an hour, {p['price_source']})")
        code = run_on_gpu.remote(p)
        if code:
            raise SystemExit(f"{label}: the kernel ended with exit code {code}")


if __name__ == "__main__":                                 # the workflow's preflight
    cli()
