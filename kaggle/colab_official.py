"""The competition's evaluator loop on a Colab GPU, laid out as on Kaggle (028 AI9, #687).

kaggle/official_agent_kernel.py finds its bundle, the competition's wheels and the model by searching /kaggle/input,
and writes to /kaggle/working. A Colab machine is a Linux machine with a GPU and root, but it has a read-only
/kaggle/input of its own: this lays the same inputs out the same way under /content, tells the kernel where they are
(HTL_INPUT, HTL_OUT), installs the model server and the agent framework at the versions the Kaggle kernels recorded,
and runs the same kernel file. What differs from a Kaggle kernel is said where the run is reported: one GPU, a
different base image and Python (the kernel leaves out the few wheels compiled for Kaggle's Python alone), and a
network at the machine's edge.

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
# `docker` is the Docker SDK: the competition's evaluator imports it even for its subprocess sandbox, and Kaggle's image
# has it where Colab's does not (the second test run stopped there). Nothing here starts a container.
PINS = ("vllm==0.19.1", "google-adk==1.36.1", "litellm==1.82.4", "kagglehub", "kaggle==2.2.5", "six", "pytest", "pyyaml",
        "docker")
# Laid out as Kaggle lays out /kaggle, but under /content: Colab has a read-only /kaggle/input of its own.
KAGGLE = Path("/content/htl_kaggle")
LOG = Path("/content/htl_colab.log")
RESULT_PREFIX = "htlnlp-colab-official-"
DEAD_PROXY = "http://127.0.0.1:9"                                         # nothing listens there
SECRET_NAME = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_KEY|_KEY$|^KAGGLE_|^HF_|^TBE_|^GCE_METADATA|"
                         r"^GOOGLE_APPLICATION|^AWS_|^AZURE_", re.I)
NETWORK_COMMAND = re.compile(r"(^|[\s;&|(])(curl|wget|ssh|scp|nc|telnet)\s|pip3?\s+(install|download)|"
                             r"git\s+(clone|fetch|pull|push|ls-remote|remote\s+add)|(apt|apt-get|conda|npm|uv)\s+"
                             r"(install|add|update)|urllib\.request|requests\.(get|post)|httpx\.", re.I)
UPLOAD_EVERY_SECONDS = 480   # what a dropped session can lose: the tasks finished since the last upload
# This branch's own files, which a notebook that has made its runs keeps reading (`follow`).
BRANCH_FILES = ("https://raw.githubusercontent.com/healthtransformationlab/health-transformation-lab-nlp/"
                "refs/heads/feat/687-028-colab-paired-run/kaggle/")
FOLLOW_MINUTES = 150     # how long a notebook waits for the run list to name another run, after each run
POLL_SECONDS = 60
DONE: dict[str, int] = {}   # label -> the kernel's exit code, for each run this notebook session has made


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


def base_label(label: str) -> str:
    """The run a listed label stands for. A notebook does not make a run twice in one session, so a run that stopped
    before it began is listed again as `<label>-try<n>`; its results still go where the run's own go."""
    return re.sub(r"-try\d+$", "", label)


def download_dataset(api, ref: str, dest: Path) -> None:
    """A dataset's files under `dest`, at the paths their names give. The whole download is tried first. Kaggle
    answers "not found" to it for some datasets that are ready and whose files can each be had (the arms' 1.2 GB
    bundles, November 12, 2026), so each file is then fetched on its own."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        api.dataset_download_files(ref, path=str(dest), unzip=True, quiet=True)
        return
    except Exception as e:  # noqa: BLE001 - whatever the whole download said, the files are tried one by one
        say(f"the whole download of {ref} was refused ({type(e).__name__}: {str(e)[:120]}); fetching its files one by one")
    import zipfile
    names, token = [], None
    while True:
        page = api.dataset_list_files(ref, page_token=token, page_size=200)
        names += [f.name for f in (page.files or [])]
        token = getattr(page, "next_page_token", None) or getattr(page, "nextPageToken", None)
        if not token:
            break
    for n, name in enumerate(names, 1):
        want = dest / name
        want.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                api.dataset_download_file(ref, name, path=str(dest), quiet=True)   # the client writes <path>/<name>
                break
            except Exception:  # noqa: BLE001 - a blip: the same file again
                if attempt == 2:
                    raise
                time.sleep(5)
        flat = dest / Path(name).name   # a client that writes the bare file name instead
        for got in (want, flat):
            packed = got.with_name(got.name + ".zip")
            if packed.exists() and not got.exists():   # Kaggle hands some files over zipped
                with zipfile.ZipFile(packed) as z:
                    z.extractall(got.parent)
                packed.unlink()
        if not want.exists() and flat.exists():
            flat.rename(want)
        if not want.exists():
            raise SystemExit(f"{ref}: {name} was not written where its name says")
        if n % 25 == 0:
            say(f"  {n} of {len(names)} files of {ref}")
    say(f"{ref}: {len(names)} files, one by one")


def kernel_paths(root: Path = KAGGLE) -> dict:
    """Where the kernel is told its inputs and its output are (it looks under /kaggle unless told)."""
    return {"HTL_INPUT": str(Path(root) / "input"), "HTL_OUT": str(Path(root) / "working")}


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


def branch_file(name: str) -> str:
    """This branch's copy of a file in kaggle/. The query keeps a cached copy from being served after a change."""
    import urllib.request
    with urllib.request.urlopen(f"{BRANCH_FILES}{name}?t={int(time.time())}", timeout=60) as r:  # noqa: S310 - the repo
        return r.read().decode()


def fresh_helper(get=branch_file):
    """This file as the branch has it now, so a fix pushed there applies to the next run without a second tap."""
    import types
    mod = types.ModuleType("colab_official")
    exec(compile(get("colab_official.py"), "colab_official.py", "exec"), mod.__dict__)  # noqa: S102 - the repo's own file
    return mod


def follow(done: dict, minutes: float = FOLLOW_MINUTES, get=branch_file, make=None, sleep=time.sleep,
           clock=time.monotonic) -> str:
    """After the runs a notebook was started for: keep reading the branch's run list, and make each run it names that
    this session has not made, until it has made them all and the list says stop, or it names nothing new for
    `minutes`. The owner starts the notebook once; a full arm, whose plan is registered only after the test run has
    been read, then starts without a second tap. `done` gains each run's exit code. Returns why the following ended."""
    deadline = clock() + minutes * 60
    while clock() < deadline:
        try:
            plan = json.loads(get("colab_official_run.json"))
        except Exception as e:  # noqa: BLE001 - a read that fails is tried again
            say(f"could not read the run list, trying again: {type(e).__name__}: {str(e)[:200]}")
            sleep(POLL_SECONDS)
            continue
        r = next((r for r in plan.get("runs", []) if r.get("label") not in done), None)
        if r is None:
            if plan.get("stop"):   # every run it names has been made, and no more are coming
                return "the run list says stop"
            sleep(POLL_SECONDS)
            continue
        say(f"the run list names a run this session has not made: {r.get('label')}")
        try:
            code = (make or fresh_helper(get).run_one)(r["label"], r["bundle"], r.get("kernel_dataset"), r.get("kernel_url"))
        except (Exception, SystemExit) as e:  # noqa: BLE001 - a run that cannot start is not tried for ever
            say(f"{r.get('label')} could not start: {type(e).__name__}: {str(e)[:300]}")
            code = 1
        done[r.get("label")] = code
        deadline = clock() + minutes * 60
    return f"nothing new was listed for {minutes:g} minutes"


def earlier_output(downloaded: Path) -> tuple[str, int]:
    """What a run's own results dataset holds from an earlier start: "finished" when its kernel ended and wrote its
    result without an error (the run is not made a second time), "partial" with the number of tasks that have a
    result file (the kernel runs the rest), or "fresh"."""
    work = Path(downloaded) / "working"
    done = len(list(work.glob("tasks/*/result.json"))) if work.exists() else 0
    try:
        whole = json.loads((work / "result.json").read_text())
    except (OSError, ValueError):
        whole = {}
    if whole.get("finished_ts") and "error" not in whole:
        return "finished", done
    return ("partial", done) if done else ("fresh", 0)


def set_aside_parts(out: Path) -> None:
    """The kernel opens its GPU samples and its spans afresh at each start. What an earlier start wrote is kept
    under its own name (`<name>_before_<n>`), and the runner reads the parts as one."""
    for name in ("gpu_samples.csv", "telemetry.jsonl"):
        f = Path(out) / name
        if f.exists():
            stem, suffix = name.rsplit(".", 1)
            n = 1 + len(list(Path(out).glob(f"{stem}_before_*.{suffix}")))
            f.rename(Path(out) / f"{stem}_before_{n}.{suffix}")


def send_until_taken(send, tries: int = 8, wait_seconds: float = 75, sleep=time.sleep) -> bool:
    """A finished run's last upload, tried until Kaggle takes it: Kaggle refuses a new version of a dataset while it
    is still taking the previous one in, and a finished arm is hours of GPU time. True when a try went through."""
    for attempt in range(tries):
        try:
            send()
            return True
        except Exception as e:  # noqa: BLE001 - whatever Kaggle answered, the next try may pass
            say(f"the results were not taken (try {attempt + 1} of {tries}): {type(e).__name__}: {str(e)[:200]}")
            if attempt < tries - 1:
                sleep(wait_seconds)
    return False


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


def restore(api, user: str, label: str, out: Path) -> tuple[str, int]:
    """Give a run its own earlier output back, from its results dataset, before anything is uploaded over it: a
    session that dropped then costs the tasks since its last upload, not the run. A dataset that is there and cannot
    be read stops the run, since the next upload would replace it."""
    try:
        api.dataset_status(results_ref(user, label))
    except Exception:  # noqa: BLE001 - no such dataset: a first start
        return "fresh", 0
    got = LOG.parent / "htl_restore"
    shutil.rmtree(got, ignore_errors=True)
    got.mkdir(parents=True)
    for attempt in range(3):
        try:
            download_dataset(api, results_ref(user, label), got)
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise SystemExit(f"{results_ref(user, label)} exists and could not be read: {type(e).__name__}") from e
            time.sleep(20)
    state, done = earlier_output(got)
    if state != "fresh" and state != "finished":
        shutil.rmtree(out, ignore_errors=True)
        shutil.copytree(got / "working", out)
    return state, done


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
            say(f"downloading {ref} -> {dest}")
            download_dataset(api, ref, dest)
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
        download_dataset(api, kernel_dataset, kernel.parent)
    else:
        import urllib.request
        kernel.write_bytes(urllib.request.urlopen(kernel_url, timeout=60).read())  # noqa: S310 - the repo's own file
    if not kernel.exists():
        raise SystemExit(f"no official_agent_kernel.py in {kernel_dataset or kernel_url}")
    return kernel


def release() -> None:
    """Give the GPU back. A notebook left on a finished run still spends the account's compute units."""
    try:
        from google.colab import runtime
        say("releasing the GPU: everything this session made is on Kaggle")
        runtime.unassign()
    except Exception as e:  # noqa: BLE001 - not on Colab, or it would not let go: the page's own timeout does it
        say(f"the GPU was not released ({type(e).__name__}); disconnect the runtime by hand")


def main(label: str, bundle: str, kernel_dataset: str | None = None, kernel_url: str | None = None,
         user: str | None = None, follow_minutes: float = FOLLOW_MINUTES) -> int:
    """What the notebook calls for each run its first reading of the run list named: make the run unless this session
    already has, then follow the branch's run list (`follow`) and give the GPU back. Returns the run's exit code."""
    if label not in DONE:
        DONE[label] = run_one(label, bundle, kernel_dataset, kernel_url, user)
        if follow_minutes:
            say("following the branch's run list, so a run added there starts without a second tap")
            say("the following ended: " + follow(DONE, follow_minutes))
            unsent = sorted(p.name.removeprefix("htl_not_sent_") for p in LOG.parent.glob("htl_not_sent_*"))
            if unsent:   # the only copy of those results is this machine's
                say(f"the GPU is not released: the results of {', '.join(unsent)} did not reach Kaggle. Leave this "
                    "page open and tell the session that started the run.")
            else:
                release()
    return DONE[label]


def run_one(label: str, bundle: str, kernel_dataset: str | None = None, kernel_url: str | None = None,
            user: str | None = None) -> int:
    """One run, start to finish. Returns the kernel's exit code (or 1 when it never started)."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    user = user or os.environ["KAGGLE_USERNAME"]
    listed, label = label, base_label(label)   # `<label>-try<n>` is the same run, listed again
    results_ref(user, label)   # refuse a bad label before any work
    out, code, api = KAGGLE / "working", 1, None
    # A new version of a Kaggle dataset replaces its files, so nothing is uploaded until this run's own earlier output
    # has been looked at: never an empty folder over an arm's results.
    may_upload = False
    say(f"run {label}{'' if listed == label else ' (listed as ' + listed + ')'}: bundle {bundle}; "
        f"kernel from {kernel_dataset or kernel_url}")
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
        state, done_count = restore(api, user, label, out)
        if state == "finished":
            say(f"{label} already finished in an earlier start ({done_count} tasks with a result): not run again")
            return 0
        may_upload = True
        if state == "partial":
            say(f"{label}: an earlier start left {done_count} tasks with a result; the kernel runs the rest")
        try:   # a first note, so the run can be seen to have started without the notebook's screen
            upload(api, user, label, out, "started")
        except Exception as e:  # noqa: BLE001 - a note that fails must not stop the run
            say(f"the first note was not sent, carrying on: {type(e).__name__}: {str(e)[:200]}")
        kernel = fetch(api, kagglehub, bundle, kernel_dataset, kernel_url)
        out.mkdir(parents=True, exist_ok=True)
        set_aside_parts(out)
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
            proc = subprocess.Popen([sys.executable, "-u", str(kernel)], cwd=str(out),
                                    env={**kernel_env(dict(os.environ)), **kernel_paths(KAGGLE)},
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
        def send() -> None:
            nonlocal api
            if api is None:
                from kaggle.api.kaggle_api_extended import KaggleApi
                api = KaggleApi()
                api.authenticate()
            upload(api, user, label, out, f"finished, kernel exit {code}")

        not_sent = LOG.parent / f"htl_not_sent_{label}"
        if not may_upload:
            print("nothing was uploaded: the run ended before its earlier output had been looked at", flush=True)
        elif send_until_taken(send):
            not_sent.unlink(missing_ok=True)
        else:
            not_sent.write_text("")   # `main` keeps the GPU while this is here
            print("THE LOG COULD NOT BE UPLOADED. Copy the text above.", flush=True)
    return code
