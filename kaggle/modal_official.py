"""The competition's evaluator loop on a Modal GPU, started from GitHub Actions (028 AI15, #804).

Modal is one more Linux machine with a GPU, as Colab is (kaggle/colab_official.py), so a run here is that helper's
`run_one`: the same pinned packages, the inputs laid out as Kaggle mounts them, one sealed bundle (no fix and no tests
beside the agent), the results sent to the same private Kaggle dataset, and the same refusal to start a run whose
entry does not accept an open network (ADR 0005). What differs:

- **Its own run list**, `kaggle/modal_official_run.json`, read from the commit Actions checked out
  (`point_at_checkout`). Colab sessions follow `colab_official_run.json` and start every run listed there, so a Modal
  run is never put in it.
- **The machine** is a CUDA development image with Python 3.13 (Colab's), git (the evaluator diffs with it) and
  procps. It is checked on a CPU (`machine_problems`) before a GPU is started.
- **The dollar cap is Modal's own time limit.** The run's `max_usd`, at the hourly price of the GPU plus the CPU and
  memory at their hard limits (`CPU_CORES`, `MEMORY_MIB`; prices in ops/cost_settings.yaml), becomes the function's
  timeout, so the run cannot cost more. A run stopped at the limit loses what it finished since its last upload (up
  to 8 minutes) and its final log, as a Colab session that drops does; to carry on, its entry names the stopped run's
  session (the log names it) in `resume_session`.
- **Small runs start on their own; larger ones wait for the owner** (#806, ADR 0008). A run whose `max_usd` is within
  `modal_auto_max_usd`, and that keeps this month's Modal spend within `modal_auto_monthly_usd`, starts without anyone
  clicking (`approval_needed`). Any other run waits in the GitHub environment `modal-approval` until the owner
  approves it, and is refused if that environment has no required reviewer (`gate_problems`).
- **The Kaggle credentials reach the machine for this run only** (`modal.Secret.from_local_environ`), from the GitHub
  environment `dev`; nothing is stored in Modal.

    python kaggle/modal_official.py preflight --label <label> --gpu L4 --max-usd 5 >> "$GITHUB_OUTPUT"
    modal billing summary --json | python kaggle/modal_official.py approval --max-usd 5 >> "$GITHUB_OUTPUT"
    curl .../environments/modal-approval | python kaggle/modal_official.py gate      # only when approval is needed
    modal app list --json | python kaggle/modal_official.py busy
    modal run --detach kaggle/modal_official.py --label <label> --gpu L4 --max-usd 5

Needs MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (the Modal CLI reads them), KAGGLE_USERNAME, and KAGGLE_API_TOKEN or
KAGGLE_KEY (each passed on under its own name). Every value stays in the environment: none is printed.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETTINGS = HERE.parent / "ops" / "cost_settings.yaml"
RUN_LIST = "modal_official_run.json"                       # Modal's own run list, beside this file
HELPER_RUN_LIST = "colab_official_run.json"                # the name the helper asks for; answered with RUN_LIST
HELPER = "colab_official.py"
APP_NAME = "htlnlp-official-agent"
GPUS = ("L4", "A10", "A100-40GB")                          # Modal's names; Modal checks them when the run starts
PRICE_KEYS = {"L4": "modal_l4_usd_per_gpu_hour", "A10": "modal_a10_usd_per_gpu_hour",
              "A100-40GB": "modal_a100_40gb_usd_per_gpu_hour"}
CPU_PRICE_KEY = "modal_cpu_usd_per_core_hour"
MEMORY_PRICE_KEY = "modal_memory_usd_per_gib_hour"
CPU_CORES = (2.0, 6.0)        # request and hard limit, in physical cores (Colab's L4 machine has 12 vCPUs, 6 cores)
MEMORY_MIB = (16384, 32768)   # request and hard limit; raise the limit (and so the hourly price) if a run runs out
MAX_TIMEOUT_SECONDS = 24 * 3600                            # Modal's longest time limit for one function call
MIN_TIMEOUT_SECONDS = 30 * 60                              # the kernel alone waits up to 20 minutes for its model server
REMOTE_DIR = "/htl/kaggle"                                 # where the helper and the run list sit on the machine
CREDENTIALS = ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "KAGGLE_USERNAME")
KAGGLE_NAMES = ("KAGGLE_USERNAME", "KAGGLE_API_TOKEN", "KAGGLE_KEY")
BASE_IMAGE = "nvidia/cuda:12.8.1-devel-ubuntu22.04"        # the CUDA toolkit, as Kaggle's and Colab's images have
APT = ("git", "procps")                                    # git: the evaluator's diff; procps: the helper's pkill
TOOLS = ("git", "pkill", "unshare", "nvcc")
PACKAGES = ("vllm", "google.adk", "litellm", "kagglehub", "kaggle", "docker", "yaml", "pytest")
# The same check the Kaggle workflow makes on its runner: the evaluator's subprocess sandbox needs unprivileged user
# namespaces.
SANDBOX_PROBE = ("unshare", "--user", "--map-root-user", "--mount", "--net", "--pid", "--fork", "true")
STOPPED_STATES = ("stopped", "stopping...", "disabled")
AUTO_KEYS = {"per_run": "modal_auto_max_usd", "monthly": "modal_auto_monthly_usd"}   # ops/cost_settings.yaml
APPROVAL_ENVIRONMENT = "modal-approval"                    # the GitHub environment an over-limit run waits in
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


def _price(settings: dict, key: str, path: Path) -> dict:
    entry = settings.get(key) or {}
    if not (isinstance(entry.get("value"), (int, float)) and entry["value"] > 0 and entry.get("source")
            and entry.get("read_date")):
        raise SystemExit(f"{Path(path).name}: {key} needs a positive value, a source and a read_date")
    return entry


def load_prices(path: Path = SETTINGS) -> dict:
    """Each GPU's Modal price per GPU-hour with its source and read date, from ops/cost_settings.yaml."""
    import yaml
    settings = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {gpu: _price(settings, key, path) for gpu, key in PRICE_KEYS.items()}


def load_side_prices(path: Path = SETTINGS) -> dict:
    """Modal's price per CPU core-hour and per GiB-hour of memory, with their sources and read dates."""
    import yaml
    settings = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {"cpu": _price(settings, CPU_PRICE_KEY, path), "memory": _price(settings, MEMORY_PRICE_KEY, path)}


def hourly_usd(gpu_usd: float, cpu_usd_per_core: float, memory_usd_per_gib: float) -> float:
    """The most an hour of the run can cost: the GPU, and the CPU and memory at their hard limits."""
    return gpu_usd + CPU_CORES[1] * cpu_usd_per_core + MEMORY_MIB[1] / 1024 * memory_usd_per_gib


def timeout_seconds(max_usd: float, usd_per_hour: float) -> int:
    """How long the run may go on for `max_usd` at this hourly price: Modal stops the function there."""
    try:
        usd = float(max_usd)
    except (TypeError, ValueError):
        raise SystemExit(f"max_usd {max_usd!r} is not a number") from None
    if not math.isfinite(usd) or usd <= 0:
        raise SystemExit(f"max_usd must be a number above 0, not {max_usd!r}")
    seconds = math.floor(usd / usd_per_hour * 3600)
    if seconds < MIN_TIMEOUT_SECONDS:
        raise SystemExit(f"max_usd {usd:g} buys {seconds} seconds at {usd_per_hour:.2f} USD an hour, under the "
                         f"{MIN_TIMEOUT_SECONDS // 60} minutes one task needs; raise max_usd")
    return min(seconds, MAX_TIMEOUT_SECONDS)


def credential_problems(env) -> list[str]:
    """What is missing or malformed among the credentials, by name. A value is never put in the message."""
    problems = []
    for name in list(CREDENTIALS) + ["KAGGLE_API_TOKEN"]:
        value = env.get(name) or (env.get("KAGGLE_KEY") if name == "KAGGLE_API_TOKEN" else "")
        if not value:
            problems.append(f"{name} is not set in the GitHub environment 'dev'"
                            + (" (or KAGGLE_KEY)" if name == "KAGGLE_API_TOKEN" else ""))
        elif any(c.isspace() for c in value):
            problems.append(f"{name} holds whitespace: copy it again, whole, into the GitHub environment 'dev'")
    return problems


def kaggle_secret_names(env) -> list[str]:
    """The Kaggle credentials that are set, each passed to the machine under its own name: the Kaggle library reads a
    legacy key only as KAGGLE_KEY, and KAGGLE_API_TOKEN only as an access token."""
    return [name for name in KAGGLE_NAMES if env.get(name)]


def load_helper(kaggle_dir: Path):
    """kaggle/colab_official.py as this checkout has it."""
    spec = importlib.util.spec_from_file_location("colab_official", Path(kaggle_dir) / HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def point_at_checkout(co, kaggle_dir: Path):
    """Make the helper read Modal's run list from this checkout. It fetches the branch's files over the network, and its
    functions take that reader as a default argument, so the default is swapped wherever it appears."""
    original = co.branch_file

    def from_checkout(name: str) -> str:
        return (Path(kaggle_dir) / (RUN_LIST if name == HELPER_RUN_LIST else name)).read_text(encoding="utf-8")

    co.branch_file = from_checkout
    for obj in vars(co).values():
        if inspect.isfunction(obj) and obj.__defaults__ and any(d is original for d in obj.__defaults__):
            obj.__defaults__ = tuple(from_checkout if d is original else d for d in obj.__defaults__)
    return co


def run_entry(label: str, kaggle_dir: Path) -> dict:
    """The run's entry in this checkout's Modal run list. Refused when it is not listed, names no bundle or no kernel
    dataset (a sealed batch's kernel holds its key, so it never comes from a URL), names a GPU (the workflow chooses
    it), or does not accept an open network in so many words (ADR 0005)."""
    plan = json.loads((Path(kaggle_dir) / RUN_LIST).read_text(encoding="utf-8"))
    entry = next((r for r in plan.get("runs", []) if r.get("label") == label), None)
    if entry is None:
        raise SystemExit(f"{label} is not in kaggle/{RUN_LIST} on this branch; add its entry there first")
    if not entry.get("bundle") or not entry.get("kernel_dataset"):
        raise SystemExit(f"{label}: its entry needs a bundle and a kernel_dataset")
    if entry.get("gpu"):
        raise SystemExit(f"{label}: its entry names a gpu ({entry['gpu']}); on Modal the workflow's gpu input chooses "
                         "it, so leave it out")
    if entry.get("network_open_acknowledged") is not True:
        raise SystemExit(f"{label}: its entry must say \"network_open_acknowledged\": true, on the run's own branch "
                         "(ADR 0005): nothing blocks the network on the machine")
    return entry


def plan(label: str, gpu: str, max_usd: float, env, kaggle_dir: Path = HERE, settings: Path = SETTINGS) -> dict:
    """Everything checked before Modal is called, every problem reported together."""
    problems = list(credential_problems(env))
    entry, chosen, price, side, seconds = None, None, None, None, None
    for step in ("entry", "gpu", "price"):
        try:
            if step == "entry":
                entry = run_entry(label, kaggle_dir)
                co = load_helper(kaggle_dir)
                co.results_ref("x", co.base_label(label))   # the results dataset is named from the label
            elif step == "gpu":
                chosen = gpu_choice(gpu)
            elif chosen:
                price, side = load_prices(settings)[chosen], load_side_prices(settings)
                seconds = timeout_seconds(max_usd, hourly_usd(price["value"], side["cpu"]["value"],
                                                              side["memory"]["value"]))
        except SystemExit as e:
            problems.append(str(e))
    if price is None and chosen is None:
        try:
            timeout_seconds(max_usd, 1.0)
        except SystemExit as e:
            problems.append(str(e))
    if problems:
        raise SystemExit("not started:\n- " + "\n- ".join(problems))
    hourly = hourly_usd(price["value"], side["cpu"]["value"], side["memory"]["value"])
    return {"label": label, "bundle": entry["bundle"], "kernel_dataset": entry["kernel_dataset"],
            "model": entry.get("model"), "gpu": chosen, "max_usd": float(max_usd),
            "usd_per_gpu_hour": price["value"], "usd_per_hour_at_limits": round(hourly, 4),
            "cpu_cores": list(CPU_CORES), "memory_mib": list(MEMORY_MIB),
            "price_source": f"{price['source']} (read {price['read_date']}); CPU and memory: "
                            f"{side['cpu']['source']} (read {side['cpu']['read_date']})",
            "timeout_seconds": seconds}


def machine_problems(which=shutil.which, run=subprocess.run, find_spec=importlib.util.find_spec,
                     version=tuple(sys.version_info[:2])) -> list[str]:
    """What the machine lacks for a run, checked on a CPU before a GPU is started: the tools the helper and the
    evaluator call, Colab's Python, the pinned packages, and the sandbox's user namespaces."""
    problems = []
    path = os.environ.get("PATH", "") + os.pathsep + "/usr/local/cuda/bin"
    problems += [f"no {tool} on the machine" for tool in TOOLS if not which(tool, path=path)]
    if tuple(version) != (3, 13):
        problems.append(f"Python {'.'.join(map(str, version))}, not 3.13")
    for name in PACKAGES:
        try:
            found = find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            problems.append(f"the package {name} is not installed")
    if which("unshare", path=path):
        done = run(list(SANDBOX_PROBE), capture_output=True, text=True, timeout=60)
        if done.returncode:
            problems.append("unshare cannot make an unprivileged user namespace, which the evaluator's sandbox "
                            f"needs: {(done.stderr or '').strip()[:200]}")
    return problems


def running_apps(listing) -> list[str]:
    """The ids of this app's runs still going, from `modal app list --json`. A detached run carries on after its job
    ends, so a new run waits for it."""
    return [str(a.get("app_id")) for a in listing
            if a.get("description") == APP_NAME and str(a.get("state", "")) not in STOPPED_STATES]


def load_auto_limits(path: Path = SETTINGS) -> dict:
    """What a run may spend without the owner's approval: per run, and this month in all (ops/cost_settings.yaml)."""
    import yaml
    settings = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {name: _price(settings, key, path)["value"] for name, key in AUTO_KEYS.items()}


def _json_in(text: str):
    """The JSON object or list in a command's output, which may carry a line of other text around it."""
    text = text or ""
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start:end + 1])


def approval_needed(max_usd, summary_text: str, settings: Path = SETTINGS) -> tuple[bool, str]:
    """Whether the run waits for the owner's approval, and why. It does when `max_usd` is over the per-run limit, when
    this month's Modal spend (`modal billing summary --json`, its `metered_cost`) plus `max_usd` is over the monthly
    limit, and when that spend cannot be read: not knowing is never taken for being under."""
    limits = load_auto_limits(settings)
    try:
        usd = float(max_usd)
    except (TypeError, ValueError):
        usd = float("nan")
    if not math.isfinite(usd) or usd <= 0:
        return True, f"max_usd {max_usd!r} is not a positive number"
    if usd > limits["per_run"]:
        return True, (f"max_usd {usd:g} is over the {limits['per_run']:g} USD a run may spend without approval "
                      f"({AUTO_KEYS['per_run']})")
    try:
        spent = float(_json_in(summary_text)["metered_cost"])
        if not math.isfinite(spent) or spent < 0:
            raise ValueError(spent)
    except (ValueError, KeyError, TypeError):
        return True, "this month's Modal spend could not be read (modal billing summary), so the run waits for approval"
    if spent + usd > limits["monthly"]:
        return True, (f"this month's Modal spend, {spent:.2f} USD, plus max_usd {usd:g} is over the "
                      f"{limits['monthly']:g} USD a month runs may spend without approval ({AUTO_KEYS['monthly']})")
    return False, (f"max_usd {usd:g} is within {limits['per_run']:g} USD a run, and {spent:.2f} USD spent this month "
                   f"plus it is within {limits['monthly']:g}: it starts without approval")


def gate_problems(environment_text: str) -> list[str]:
    """Why the approval job must refuse the run, from GitHub's answer for the environment it waited in. GitHub makes a
    missing environment on the spot, with no rule, so a run is let through only when a required reviewer is set."""
    try:
        env = _json_in(environment_text)
    except ValueError:
        return [f"the GitHub environment {APPROVAL_ENVIRONMENT} could not be read, so the run is refused"]
    if not isinstance(env, dict) or env.get("name") != APPROVAL_ENVIRONMENT:
        why = env.get("message") if isinstance(env, dict) else None
        return [(f"the GitHub environment {APPROVAL_ENVIRONMENT} could not be read ({why or 'another answer'}), so "
                 "the run is refused")]
    rules = env.get("protection_rules") or []
    if not any(r.get("type") == "required_reviewers" and r.get("reviewers") for r in rules):
        return [(f"the GitHub environment {APPROVAL_ENVIRONMENT} has no required reviewer, so nobody approved this "
                 f"over-limit run and it is refused: add the owner under Settings, Environments, "
                 f"{APPROVAL_ENVIRONMENT}, Required reviewers")]
    return []


def cli(argv: list[str] | None = None, env=None, kaggle_dir: Path = HERE, stdin=None) -> dict:
    """`preflight`: check everything, then print the GPU and the time limit as KEY=VALUE lines for $GITHUB_OUTPUT, and
    the plan (no credential in it) on stderr. `approval`: from `modal billing summary --json` on stdin, print
    `needs_approval=` and `reason=`. `gate`: from GitHub's answer for the approval environment on stdin, refuse unless
    it has a required reviewer. `busy`: refuse when `modal app list --json` on stdin shows a run going, or is empty."""
    ap = argparse.ArgumentParser(prog="modal_official.py")
    ap.add_argument("command", choices=["preflight", "approval", "gate", "busy"])
    ap.add_argument("--label")
    ap.add_argument("--gpu", default="L4")
    ap.add_argument("--max-usd", default="5")
    a = ap.parse_args(argv)
    text = (stdin or sys.stdin).read() if a.command in ("approval", "gate", "busy") else ""
    if a.command == "approval":
        needed, reason = approval_needed(a.max_usd, text)
        print(f"needs_approval={'true' if needed else 'false'}")
        print("reason=" + " ".join(reason.split()))
        print(f"::notice::{reason}", file=sys.stderr)
        return {"needs_approval": needed, "reason": reason}
    if a.command == "gate":
        problems = gate_problems(text)
        if problems:
            raise SystemExit("\n".join(problems))
        print(f"approved by a required reviewer of {APPROVAL_ENVIRONMENT}")
        return {}
    if a.command == "busy":
        try:
            listing = _json_in(text)
        except ValueError:
            raise SystemExit("`modal app list --json` gave nothing to read, so whether a run is going is not known") \
                from None
        going = running_apps(listing)
        if going:
            raise SystemExit(f"a Modal run is still going ({', '.join(going)}): wait for it to end, or stop it with "
                             "`modal app stop <id>`")
        print("no Modal run is going")
        return {}
    if not a.label:
        ap.error("preflight needs --label")
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
    image = (modal.Image.from_registry(BASE_IMAGE, add_python="3.13")   # Colab's Python, as the Colab runs had
             .apt_install(*APT)
             .pip_install(*PINS)
             .env({"HTL_MODAL_GPU": GPU, "HTL_MODAL_TIMEOUT": str(TIMEOUT)})
             .add_local_file(HERE / HELPER, f"{REMOTE_DIR}/{HELPER}")
             .add_local_file(HERE / RUN_LIST, f"{REMOTE_DIR}/{RUN_LIST}"))
    app = modal.App(APP_NAME, image=image)

    @app.function(cpu=1.0, memory=2048, timeout=900, retries=0, max_containers=1)
    def check_machine() -> list[str]:
        """The machine checked on a CPU, for a fraction of a cent, before the GPU is paid for."""
        return machine_problems()

    @app.function(gpu=GPU, timeout=TIMEOUT, cpu=CPU_CORES, memory=MEMORY_MIB, retries=0, max_containers=1,
                  secrets=[modal.Secret.from_local_environ(kaggle_secret_names(os.environ))])
    def run_on_gpu(p: dict) -> int:
        """One run on the GPU: the helper's `run_one`, reading the run list from the files of this commit."""
        co = point_at_checkout(load_helper(Path(REMOTE_DIR)), Path(REMOTE_DIR))
        return co.run_one(p["label"], p["bundle"], p["kernel_dataset"], None, model=p.get("model"))

    @app.local_entrypoint()
    def main(label: str, gpu: str = "L4", max_usd: str = "5"):
        p = plan(label, gpu, max_usd, os.environ)
        if (p["gpu"], p["timeout_seconds"]) != (GPU, TIMEOUT):
            raise SystemExit("run the workflow's preflight first: its HTL_MODAL_GPU and HTL_MODAL_TIMEOUT must match "
                             f"this run ({p['gpu']}, {p['timeout_seconds']} s)")
        missing = check_machine.remote()
        if missing:
            raise SystemExit("the machine lacks what the run needs, so no GPU was started:\n- " + "\n- ".join(missing))
        print(f"{label}: {p['gpu']} for at most {p['timeout_seconds']} s ({p['max_usd']:g} USD at "
              f"{p['usd_per_hour_at_limits']} an hour with the CPU and memory at their limits; {p['price_source']})")
        code = run_on_gpu.remote(p)
        if code:
            raise SystemExit(f"{label}: the kernel ended with exit code {code}")


if __name__ == "__main__":                                 # the workflow's preflight and busy check
    cli()
