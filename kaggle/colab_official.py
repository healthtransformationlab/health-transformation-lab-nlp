"""The competition's evaluator loop on a Colab GPU, laid out as on Kaggle (028 AI9, #687).

kaggle/official_agent_kernel.py finds its bundle, the competition's wheels and the model by searching /kaggle/input,
and writes to /kaggle/working. A Colab machine is a Linux machine with a GPU and root: this puts the same inputs at
the same paths, installs the model server and the agent framework at the versions the Kaggle kernels recorded, and
runs that kernel file unchanged. What differs from a Kaggle kernel is said where the run is reported: one GPU, a
different base image, and a network at the machine's edge.

Two things a Kaggle kernel gave for free are done here by hand:

- **No credential in reach.** The kernel's process, and every command the agent runs under it, starts from an
  environment with no token, no account name and no address of Colab's own credential services.
- **No way out.** Every proxy variable points at a port nothing listens on, pip has no index, and the Hugging Face
  hub is offline. That is softer than Kaggle's "internet off", so the agent's commands are read afterwards
  (`network_command_count`) and the count is reported.

Everything is logged to one file, and the log and whatever the kernel wrote go to a private Kaggle dataset when the
run ends, however it ends, and every few minutes while it runs: the run can be read without the notebook's screen.

Opened by kaggle/colab_official_agent.ipynb, which reads the Kaggle token from Colab's Secrets. No token is here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"                 # the competition's evaluator
MODEL = "google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2"             # as the starter notebook attaches it
# The versions the Kaggle kernels recorded (their `_settings.json`), from PyPI with their dependencies; the wheels of
# the wheelhouse are then installed over them by the kernel itself, as on Kaggle.
PINS = ("vllm==0.19.1", "google-adk==1.36.1", "litellm==1.82.4", "kagglehub", "kaggle==2.2.5", "six", "pytest", "pyyaml")
KAGGLE = Path("/kaggle")
LOG = Path("/content/htl_colab.log")
RESULT_PREFIX = "htlnlp-colab-official-"
DEAD_PROXY = "http://127.0.0.1:9"                                         # nothing listens there
SECRET_NAME = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_KEY|_KEY$|^KAGGLE_|^HF_|^TBE_|^GCE_METADATA|"
                         r"^GOOGLE_APPLICATION|^AWS_|^AZURE_", re.I)
NETWORK_COMMAND = re.compile(r"(^|[\s;&|(])(curl|wget|ssh|scp|nc|telnet)\s|pip3?\s+(install|download)|"
                             r"git\s+(clone|fetch|pull|push|ls-remote|remote\s+add)|(apt|apt-get|conda|npm|uv)\s+"
                             r"(install|add|update)|urllib\.request|requests\.(get|post)|httpx\.", re.I)
UPLOAD_EVERY_SECONDS = 900


def dataset_dir(ref: str, root: Path = KAGGLE) -> Path:
    """Where Kaggle mounts an attached dataset: /kaggle/input/<its slug>."""
    return Path(root) / "input" / ref.split("/", 1)[1]


def model_dir(root: Path = KAGGLE, handle: str = MODEL) -> Path:
    """Where Kaggle mounts an attached model: /kaggle/input/models/<owner>/<model>/<framework>/<variation>/<version>."""
    parts = handle.split("/")
    if len(parts) != 5:
        raise SystemExit(f"a model handle is owner/model/framework/variation/version: {handle}")
    owner, model, framework, variation, version = parts
    return Path(root) / "input" / "models" / owner / model / framework.lower() / variation / version


def kernel_env(env: dict) -> dict:
    """The environment the kernel starts from: what the caller has, less every credential and every address of a
    credential service, with every way out pointed at a port nothing listens on. This machine itself stays
    reachable, since the model server runs on it."""
    kept = {k: v for k, v in env.items() if not SECRET_NAME.search(k)}
    local = "127.0.0.1,localhost,::1"
    return {**kept, **{name: DEAD_PROXY for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                                                       "ALL_PROXY", "all_proxy")},
            "NO_PROXY": local, "no_proxy": local, "PIP_NO_INDEX": "1", "HF_HUB_OFFLINE": "1",
            "MPLBACKEND": "Agg"}   # a notebook's inline plotting backend means nothing to a command the agent runs


def results_ref(user: str, label: str) -> str:
    """The private dataset a run's log and output go to."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,30}", label):
        raise SystemExit(f"a run's label is lowercase letters, digits and hyphens, at most 31 characters: {label!r}")
    return f"{user}/{RESULT_PREFIX}{label}"


def results_metadata(user: str, label: str) -> dict:
    return {"id": results_ref(user, label), "title": f"htlnlp colab official {label}"[:50],
            "licenses": [{"name": "CC-BY-4.0"}]}


def files_to_return(out: Path, max_bytes: int = 200 * 2**20) -> list[Path]:
    """Every file the kernel wrote, but its own copy of the submission and anything too large to be a result."""
    out = Path(out)
    return sorted(p for p in out.rglob("*") if p.is_file() and p.relative_to(out).parts[0] != "submission"
                  and p.stat().st_size <= max_bytes)


def stale_bundles(root: Path, keep: Path) -> list[Path]:
    """Folders under /kaggle/input that hold another run's bundle. The kernel takes the first bundle it finds, so a
    second run on the same machine must not find the first one's."""
    found = {p.parent for name in ("official_batch.json", "official_task.json")
             for p in (Path(root) / "input").rglob(name)}
    return sorted(d for d in found if d.resolve() != Path(keep).resolve())


def network_command_count(commands: list[str]) -> int:
    """How many of the agent's commands reach for the network: a download tool, an installer, or git over a remote.
    A URL that is only read or searched for in a file does not count."""
    return sum(bool(NETWORK_COMMAND.search(c)) for c in commands)


# ---- below: only run on the Colab machine ----------------------------------------------------------------------------

def say(message: str) -> None:
    line = f"[{time.strftime('%H:%M:%S', time.gmtime())}Z] {message}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def run(command: list[str], tail: int = 4000, **kwargs) -> subprocess.CompletedProcess:
    """One command, its output kept in the log (the last part of it on the screen)."""
    say("$ " + " ".join(command))
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False, **kwargs)
    with LOG.open("a") as f:
        f.write(done.stdout[-60000:] + "\n")
    print(done.stdout[-tail:], flush=True)
    say(f"exit {done.returncode}")
    return done


def upload(api, user: str, label: str, out: Path, note: str) -> None:
    """The log and the kernel's output so far, as a new version of the run's private dataset (made on first use)."""
    stage = Path("/content/htl_upload")
    shutil.rmtree(stage, ignore_errors=True)
    (stage / "working").mkdir(parents=True)
    if LOG.exists():
        shutil.copyfile(LOG, stage / "colab.log")
    for p in files_to_return(out) if Path(out).exists() else []:
        dest = stage / "working" / p.relative_to(out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    (stage / "dataset-metadata.json").write_text(json.dumps(results_metadata(user, label)))
    try:
        api.dataset_status(results_ref(user, label))
        api.dataset_create_version(str(stage), version_notes=note[:100], quiet=True, dir_mode="zip")
    except Exception:  # noqa: BLE001 - no such dataset yet
        api.dataset_create_new(str(stage), public=False, quiet=True, dir_mode="zip")
    print(f"uploaded to {results_ref(user, label)}: {note}", flush=True)


def fetch(api, kagglehub, bundle: str, kernel_dataset: str | None, kernel_url: str | None,
          root: Path = KAGGLE, with_model: bool = True) -> Path:
    """The inputs at Kaggle's paths, and the kernel file. Returns the kernel file's path."""
    (Path(root) / "input").mkdir(parents=True, exist_ok=True)
    for old in stale_bundles(root, dataset_dir(bundle, root)):
        say(f"removing another run's bundle: {old}")
        shutil.rmtree(old, ignore_errors=True)
    for ref in (WHEELHOUSE, bundle):
        dest = dataset_dir(ref, root)
        if not dest.exists() or not any(dest.iterdir()):
            dest.mkdir(parents=True, exist_ok=True)
            say(f"downloading {ref} -> {dest}")
            api.dataset_download_files(ref, path=str(dest), unzip=True, quiet=True)
        say(f"{ref}: {sum(1 for _ in dest.rglob('*'))} entries")
    target = model_dir(root)
    if with_model and not (target / "config.json").exists():
        say(f"downloading the model {MODEL}")
        cached = Path(kagglehub.model_download(MODEL))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(cached, target)
    if target.exists():
        say(f"model at {target}: {sorted(p.name for p in target.iterdir())[:12]}")
    kernel = LOG.parent / "htl_kernel" / "official_agent_kernel.py"
    shutil.rmtree(kernel.parent, ignore_errors=True)
    kernel.parent.mkdir(parents=True)
    if kernel_dataset:   # a batch's kernel carries its seal key: it comes from a private dataset, never from the repo
        api.dataset_download_files(kernel_dataset, path=str(kernel.parent), unzip=True, quiet=True)
    else:
        import urllib.request
        kernel.write_bytes(urllib.request.urlopen(kernel_url, timeout=60).read())  # noqa: S310 - the repo's own file
    if not kernel.exists():
        raise SystemExit(f"no official_agent_kernel.py in {kernel_dataset or kernel_url}")
    return kernel


def main(label: str, bundle: str, kernel_dataset: str | None = None, kernel_url: str | None = None,
         user: str | None = None) -> int:
    """One run, start to finish. Returns the kernel's exit code (or 1 when it never started)."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    user = user or os.environ["KAGGLE_USERNAME"]
    results_ref(user, label)   # refuse a bad label before any work
    out, code, api = KAGGLE / "working", 1, None
    say(f"run {label}: bundle {bundle}; kernel from {kernel_dataset or kernel_url}")
    try:
        if out.exists() and any(out.iterdir()):   # an earlier run's output on this machine: set it aside
            out.rename(out.with_name(f"working_before_{label}_{int(time.time())}"))
        run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv"])
        run([sys.executable, "--version"])
        installed = run([sys.executable, "-m", "pip", "install", "-q", *PINS])
        if installed.returncode:
            raise SystemExit("pip could not install the pinned packages")
        run([sys.executable, "-m", "pip", "list", "--format=freeze"], tail=0)
        import kagglehub
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        api.dataset_list(user=user, page=1)   # one cheap call: the token works
        kernel = fetch(api, kagglehub, bundle, kernel_dataset, kernel_url)
        out.mkdir(parents=True, exist_ok=True)
        say("starting the kernel")
        stop = threading.Event()

        def keep_uploading() -> None:
            while not stop.wait(UPLOAD_EVERY_SECONDS):
                try:
                    upload(api, user, label, out, "still running")
                except Exception as e:  # noqa: BLE001 - an upload that fails must not stop the run
                    say(f"upload failed, carrying on: {type(e).__name__}: {str(e)[:200]}")

        uploader = threading.Thread(target=keep_uploading, daemon=True)
        uploader.start()
        with LOG.open("a") as log:
            proc = subprocess.Popen([sys.executable, "-u", str(kernel)], cwd=str(out), env=kernel_env(dict(os.environ)),
                                    stdout=log, stderr=subprocess.STDOUT)
            started = time.monotonic()
            while proc.poll() is None:
                time.sleep(60)
                print(f"  kernel running, {round((time.monotonic() - started) / 60)} min", flush=True)
            code = proc.returncode
        stop.set()
        say(f"kernel exit {code}")
        subprocess.run(["pkill", "-f", "vllm"], check=False)   # a model server left behind would hold the GPU
    except BaseException as e:  # noqa: BLE001 - whatever stops the run is written down and sent back
        say(f"stopped: {type(e).__name__}: {str(e)[:500]}")
        with LOG.open("a") as f:
            f.write(traceback.format_exc())
    finally:
        try:
            if api is None:
                from kaggle.api.kaggle_api_extended import KaggleApi
                api = KaggleApi()
                api.authenticate()
            upload(api, user, label, out, f"finished, kernel exit {code}")
        except Exception as e:  # noqa: BLE001
            print(f"THE LOG COULD NOT BE UPLOADED ({type(e).__name__}: {str(e)[:300]}). Copy the text above.", flush=True)
    return code
