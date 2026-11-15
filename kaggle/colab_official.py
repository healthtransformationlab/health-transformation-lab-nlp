"""The competition's evaluator loop on a Colab GPU, laid out as on Kaggle (028 AI9, #687).

kaggle/official_agent_kernel.py finds its bundle, the competition's wheels and the model by searching /kaggle/input,
and writes to /kaggle/working. A Colab machine is a Linux machine with a GPU and root, but it has a read-only
/kaggle/input of its own: this lays the same inputs out the same way under /content, tells the kernel where they are
(HTL_INPUT, HTL_OUT), installs the model server and the agent framework at the versions the Kaggle kernels recorded,
and runs the same kernel file. What differs from a Kaggle kernel is said where the run is reported: one GPU, a
different base image and Python (the kernel leaves out the few wheels compiled for Kaggle's Python alone), and a
network at the machine's edge. A batch of the competition's development tasks reads them from the attached
competition on Kaggle; no competition is mounted here, so its files for the batch's tasks alone are fetched with the
notebook's token and laid out where Kaggle mounts them (`fetch_competition_files`, #780).

Two things a Kaggle kernel gave for free are done here by hand:

- **No credential in reach.** The kernel's process starts from an environment with no token, no account name and no
  address of Colab's own credential services. The evaluator then starts each of the agent's commands from a short
  list of environment names of its own, and no credential is on it.
- **The network is read, not blocked.** For the kernel's process every proxy variable points at a port nothing
  listens on, pip has no index, and the Hugging Face hub is offline. None of that reaches the agent's commands: the
  evaluator's list of names holds no proxy, so a command can reach the network (the review of #690 found this after
  the runs of #687). What covers the commands is that each is read afterwards (`network_command_count`) and the
  count is reported, with the tasks it was in. Nothing here blocks the network at the machine (#691, item 6), so a
  run starts only when its entry in the run list says the operator accepts that it is open
  (`"network_open_acknowledged": true`; docs/adr/0005-colab-runs-need-the-open-network-accepted.md).

Everything is logged to one file, and the log and whatever the kernel wrote go to a private Kaggle dataset when the
run ends, however it ends, and every few minutes while it runs: the run can be read without the notebook's screen.

Opened by kaggle/colab_official_agent.ipynb, which reads the Kaggle token from Colab's Secrets. No token is here.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"                 # the competition's evaluator
COMPETITION = "gemma-4-developer-agent"   # whose development tasks a batch reads, when its order names none
MODEL = "google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2"             # as the starter notebook attaches it
# A run that names no model gets MODEL. An entry of the run list can name another (`"model": <handle>`), since the
# kernel serves the one model the submission declares and finds it under the inputs (028 AI12, #748: E2B).
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
                         r"^GOOGLE_APPLICATION|^AWS_|^AZURE_", re.IGNORECASE)
# What reaches for the network, in a command or in any tool call's arguments (#691, item 7: the first list missed
# Python sockets, `pip -q install`, `git -C x pull`, and anything outside run_command). The registered analyses of
# #687 keep the audit as it was committed then.
NETWORK_COMMAND = re.compile(
    r"(^|[\s;&|(`'\"])(curl|wget|ssh|scp|sftp|rsync|nc|ncat|netcat|socat|telnet|ftp|aria2c|nslookup|dig|ping)\s"
    r"|pip3?(\s+-{1,2}[\w-]+(=\S+)?)*\s+(install|download)\b"
    r"|git(\s+-[A-Za-z]\s+\S+|\s+--?[\w-]+(=\S+)?)*\s+(clone|fetch|pull|push|ls-remote|remote\s+add|submodule\s+(update|add))\b"
    r"|\b(apt|apt-get|conda|mamba|npm|yarn|pnpm|uv|poetry|gem|cargo|brew|easy_install)\s+(\S+\s+)?(install|add|update|sync)\b"
    r"|\bgo\s+(get|install)\s"
    r"|urllib\.request|urllib3|requests\.(get|post|put|patch|head|delete|request|Session)|httpx|aiohttp|http\.client"
    r"|import\s+socket|from\s+socket\s+import|socket\.(socket|create_connection|getaddrinfo)|/dev/(tcp|udp)/"
    r"|ftplib|smtplib|websocket|hf_hub_download|snapshot_download|huggingface-cli\s+download|\bhf\s+download\b",
    re.IGNORECASE)
UPLOAD_EVERY_SECONDS = 480   # what a dropped session can lose: the tasks finished since the last upload
# The branch whose files a notebook that has made its runs keeps reading (`follow`). `main`, where the run list says
# stop. A new run is made from a branch of its own: point this and the notebook's BRANCH there while it is made, and
# back before it merges (the runs of #687 read feat/687-028-colab-paired-run).
BRANCH_FILES = ("https://raw.githubusercontent.com/healthtransformationlab/health-transformation-lab-nlp/"
                "refs/heads/main/kaggle/")
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
    names = [name for name, _ in listed_files(api, ref)]
    for n, name in enumerate(names, 1):
        want = dest / name
        want.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                api.dataset_download_file(ref, name, path=str(dest), quiet=True)   # the client writes <path>/<name>
                break
            except Exception:   # a blip: the same file again
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


def listed_files(api, ref: str) -> list[tuple[str, int | None]]:
    """Each file a dataset lists, with its size in bytes where the listing gives one, every page read."""
    out, token = [], None
    while True:
        page = api.dataset_list_files(ref, page_token=token, page_size=200)
        for f in page.files or []:
            size = next((v for v in (getattr(f, a, None) for a in ("total_bytes", "totalBytes", "size"))
                         if isinstance(v, int) and not isinstance(v, bool)), None)
            out.append((f.name, size))
        token = getattr(page, "next_page_token", None) or getattr(page, "nextPageToken", None)
        if not token:
            return out


def missing_files(listed: list[tuple[str, int | None]], dest: Path) -> list[str]:
    """The listed files that are not on disk under `dest`, or are there at another size (#691, item 4: a download
    that stopped part way left a folder that was not empty, and it counted as complete)."""
    gone = []
    for name, size in listed:
        p = Path(dest) / name
        if not p.is_file() or (size is not None and p.stat().st_size != size):
            gone.append(name)
    return gone


def competition_dir(competition: str, root: Path = KAGGLE) -> Path:
    """Where Kaggle mounts an attached competition: /kaggle/input/competitions/<its slug>. The kernel searches its
    inputs for the folder holding HARNESS_README.md, tasks.jsonl and snapshots/ (find_competition)."""
    return Path(root) / "input" / "competitions" / competition


# What every development task needs beside its own files: the harness guide the kernel finds the folder by, the task
# list, and the tests' wheels and the sandbox's setup script, which the evaluator looks for beside tasks.jsonl.
COMPETITION_SHARED = ("HARNESS_README.md", "tasks.jsonl")
COMPETITION_SHARED_FOLDERS = ("wheels/", "sandbox/")


def listed_competition_files(api, competition: str) -> list[tuple[str, int | None]]:
    """Each file the competition lists, with its size in bytes where the listing gives one, every page read."""
    out, token = [], None
    while True:
        page = api.competition_list_files(competition, page_token=token, page_size=200)
        for f in page.files or []:
            size = next((v for v in (getattr(f, a, None) for a in ("total_bytes", "totalBytes", "size"))
                         if isinstance(v, int) and not isinstance(v, bool)), None)
            out.append((f.name, size))
        token = getattr(page, "next_page_token", None) or getattr(page, "nextPageToken", None)
        if not token:
            return out


def competition_files(listed: list[tuple[str, int | None]], tasks: list[dict],
                      instance_ids: list[str]) -> list[tuple[str, int | None]]:
    """The competition's files a batch of `instance_ids` reads, from its listing and its tasks.jsonl rows: the shared
    files, and each task's snapshot, graph and embeddings under the names the kernel looks for
    (stage_competition_task: `<repo>_<base_commit>` or the task's id). The snapshots of all 129 tasks are 21.5 GB;
    a batch takes its own tasks' only. Stops on a task tasks.jsonl does not hold, or one with no snapshot."""
    names = {n for n, _ in listed}
    rows = {t.get("instance_id"): t for t in tasks}
    if (unknown := [i for i in instance_ids if i not in rows]):
        raise SystemExit(f"not in the competition's tasks.jsonl: {', '.join(unknown)}")
    wanted = {n for n in names if n in COMPETITION_SHARED or n.startswith(COMPETITION_SHARED_FOLDERS)}
    for iid in instance_ids:
        if f"snapshots/{iid}.tgz" not in names:
            raise SystemExit(f"the competition lists no snapshots/{iid}.tgz")
        stem = f"{rows[iid]['repo'].split('/')[-1]}_{rows[iid]['base_commit']}"
        wanted |= {f"snapshots/{iid}.tgz"} | {n for n in (f"graphs/{stem}.json", f"graphs/{iid}.json",
                                                          f"embeddings/{stem}.npz", f"embeddings/{iid}.npz")
                                             if n in names}
    return sorted((n, size) for n, size in listed if n in wanted)


def download_competition_file(api, competition: str, name: str, dest: Path, tries: int = 3, sleep=time.sleep) -> None:
    """One competition file to `dest/<name>`, unzipped where Kaggle hands it over zipped, as download_dataset does
    for a dataset's files."""
    import zipfile
    want = Path(dest) / name
    want.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(tries):
        try:
            api.competition_download_file(competition, name, path=str(dest), quiet=True)   # writes <path>/<name>
            break
        except Exception:   # a blip: the same file again
            if attempt == tries - 1:
                raise
            sleep(5)
    flat = Path(dest) / Path(name).name   # a client that writes the bare file name instead
    for got in (want, flat):
        packed = got.with_name(got.name + ".zip")
        if packed.exists() and not got.exists():   # Kaggle hands some files over zipped
            with zipfile.ZipFile(packed) as z:
                z.extractall(got.parent)
            packed.unlink()
    if not want.exists() and flat.exists():
        flat.rename(want)
    if not want.exists():
        raise SystemExit(f"{competition}: {name} was not written where its name says")


def fetch_competition_files(api, competition: str, instance_ids: list[str], root: Path = KAGGLE) -> Path:
    """A development batch's competition files on this machine, laid out where Kaggle mounts the competition
    (competition_dir), with the Kaggle client the notebook's token authenticated: Colab mounts no competition (#780).
    Only the batch's own tasks' snapshots, graphs and embeddings are fetched, and another batch's left on the machine
    are removed, so the agent never has them within reach. A file already there at its listed size is not fetched
    again; any other is. Returns the competition's folder."""
    dest = competition_dir(competition, root)
    listed = listed_competition_files(api, competition)
    if not listed:
        raise SystemExit(f"{competition} lists no files: is the account behind the token joined to it?")
    shared = [(n, size) for n, size in listed if n in COMPETITION_SHARED]
    if "tasks.jsonl" not in {n for n, _ in shared}:
        raise SystemExit(f"{competition} lists no tasks.jsonl")
    for name in missing_files(shared, dest):
        download_competition_file(api, competition, name, dest)
    tasks = [json.loads(line) for line in (dest / "tasks.jsonl").read_text().splitlines() if line.strip()]
    picked = competition_files(listed, tasks, instance_ids)
    keep = {n for n, _ in picked}
    for folder in ("snapshots", "graphs", "embeddings"):   # another batch's tasks do not stay beside this one's
        for p in sorted((dest / folder).glob("*")) if (dest / folder).exists() else []:
            if p.relative_to(dest).as_posix() not in keep:
                p.unlink() if p.is_file() or p.is_symlink() else shutil.rmtree(p)
    gone = missing_files(picked, dest)
    size = sum(s or 0 for _, s in picked)
    say(f"{competition}: {len(picked)} files for {len(instance_ids)} tasks ({size / 1e9:.2f} GB), {len(gone)} to fetch "
        f"-> {dest}")
    for n, name in enumerate(gone, 1):
        download_competition_file(api, competition, name, dest)
        if n % 25 == 0:
            say(f"  {n} of {len(gone)} files of {competition}")
    if (left := missing_files(picked, dest)):
        raise SystemExit(f"{competition}: after the download, {len(left)} files are missing or of another size: "
                         + ", ".join(left[:10]))
    say(f"{competition}: all {len(picked)} files for the batch's {len(instance_ids)} tasks, at their listed sizes, "
        f"where Kaggle mounts the competition")
    return dest


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
    with urllib.request.urlopen(f"{BRANCH_FILES}{name}?t={int(time.time())}", timeout=60) as r:   # the repository's own file
        return r.read().decode()


def fresh_helper(get=branch_file):
    """This file as the branch has it now, so a fix pushed there applies to the next run without a second tap."""
    import types
    mod = types.ModuleType("colab_official")
    exec(compile(get("colab_official.py"), "colab_official.py", "exec"), mod.__dict__)  # noqa: S102 - the repo's own file
    return mod


def gpu_name(csv_text: str) -> str:
    """The machine's GPU, from what `nvidia-smi --query-gpu=name,... --format=csv` printed ("" when it printed none)."""
    rows = [line for line in (csv_text or "").splitlines() if line.strip()]
    return rows[1].split(",")[0].strip() if len(rows) > 1 else ""


def is_for_this_gpu(wanted: str | None, name: str) -> bool:
    """Whether a run is made on a machine whose GPU is `name`. An entry of the run list can name the GPU it is for
    (`"gpu": "A100"`): the list offers a run to every session that reads it, and two sessions on two GPUs once made
    the same arm (#687). A run that names no GPU is made anywhere, and so is any run where the GPU could not be read:
    not knowing must not stop an arm."""
    if not wanted or not name:
        return True
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(wanted)}(?![A-Za-z0-9])", name, re.IGNORECASE) is not None


def listed_entry(label: str, get=branch_file, tries: int = 3, sleep=time.sleep) -> dict | None:
    """The branch's run list's entry for the run `label`, or None when it is not listed or the list cannot be read.
    The run reads its own entry: a session that began before entries could name a GPU hands a run only its label,
    bundle and kernel, and what else a run needs to know (`gpu`, `network_open_acknowledged`, `resume_session`) is
    read here."""
    for attempt in range(tries):
        try:
            runs = json.loads(get("colab_official_run.json")).get("runs", [])
            return next((r for r in runs if r.get("label") == label), None)
        except Exception as e:  # noqa: BLE001 - a read that fails is tried again
            say(f"could not read the run list's entry for {label} (try {attempt + 1} of {tries}): {type(e).__name__}")
            if attempt < tries - 1:
                sleep(15)
    return None


def listed_model(label: str, get=branch_file, tries: int = 3, sleep=time.sleep) -> str:
    """The model handle the branch's run list names for the run `label`, or MODEL when its entry names none (as no
    entry before 028 AI12 does) or it is not listed. Unlike the GPU, the model cannot be guessed: a list that cannot
    be read stops the run, since an E2B arm given E4B would load a model its submission does not declare."""
    for attempt in range(tries):
        try:
            runs = json.loads(get("colab_official_run.json")).get("runs", [])
            handle = next((r.get("model") for r in runs if r.get("label") == label), None) or MODEL
            break
        except Exception as e:  # noqa: BLE001 - a read that fails is tried again, then the run stops
            say(f"could not read which model {label} is for (try {attempt + 1} of {tries}): {type(e).__name__}")
            if attempt < tries - 1:
                sleep(15)
    else:
        raise SystemExit(f"could not read which model {label} is for: the run is not made with a guessed model")
    model_dir(Path("/"), handle)   # a handle that is not owner/model/framework/variation/version stops the run here
    return handle


def listed_gpu(label: str, get=branch_file, tries: int = 3, sleep=time.sleep) -> str | None:
    """The GPU the branch's run list says the run `label` is for, or None (none named, or the list unread)."""
    return (listed_entry(label, get, tries, sleep) or {}).get("gpu") or None


NETWORK_REFUSAL = ("is not started: the network is open to the agent's commands on this machine (nothing blocks it, "
                   "#691 item 6), and the run's entry in the run list does not say the operator accepts that. Add "
                   '"network_open_acknowledged": true to the entry, on the run\'s own branch, only after reading '
                   "docs/adr/0005-colab-runs-need-the-open-network-accepted.md")


def network_open_acknowledged(entry: dict | None) -> bool:
    """Whether a run's entry says, in so many words, that the operator accepts an open network (#691, item 6). A run
    list that cannot be read, or an entry that does not say it with `true`, does not."""
    return bool(entry) and entry.get("network_open_acknowledged") is True


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
    result without an error and without stopping itself (the run is not made a second time), "partial" with the
    number of tasks that have a result file (the kernel runs the rest), or "fresh". A kernel that stopped itself (its
    deadline, or two tasks with no answer from the model server) marked the rest skipped: those can still be run."""
    work = Path(downloaded) / "working"
    done = len(list(work.glob("tasks/*/result.json"))) if work.exists() else 0
    try:
        whole = json.loads((work / "result.json").read_text())
    except (OSError, ValueError):
        whole = {}
    stopped = any(r.get("is_skipped") for r in (whole.get("runs") or {}).values() if isinstance(r, dict))
    if whole.get("finished_ts") and "error" not in whole and not stopped:
        return "finished", done
    return ("partial", done) if done or stopped else ("fresh", 0)


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


class StatusUnknown(Exception):
    """Kaggle's status call failed for a reason other than "no such dataset": whether the dataset is there is not
    known, so nothing may be done that takes it to be missing."""


def is_not_found(e: BaseException) -> bool:
    """Whether an error from the Kaggle client says the dataset does not exist (HTTP 404), as against any other
    failure (a blip, a refused token, a server error)."""
    response = getattr(e, "response", None)
    code = getattr(response, "status_code", None) or getattr(e, "status", None) or getattr(e, "code", None)
    if isinstance(code, int):
        return code == 404
    return "404" in str(e) and "not found" in str(e).lower()


def is_forbidden(e: BaseException) -> bool:
    """Whether an error from the Kaggle client is HTTP 403. Kaggle answers 403, not 404, for a private dataset that
    does not exist (#815), and also for one the token may not read."""
    response = getattr(e, "response", None)
    code = getattr(response, "status_code", None) or getattr(e, "status", None) or getattr(e, "code", None)
    if isinstance(code, int):
        return code == 403
    return "403" in str(e) and "forbidden" in str(e).lower()


def listed_as_own(api, ref: str) -> bool | None:
    """Whether the owner's own datasets, private ones included, hold `ref`: True or False, or None when Kaggle's
    listing fails. Used after a 403, which alone cannot tell a missing dataset from one that may not be read (#815)."""
    owner, _, slug = ref.partition("/")
    try:
        found = api.dataset_list(user=owner, search=slug) or []
    except Exception:  # noqa: BLE001 - a listing that fails tells nothing
        return None
    return any(str(getattr(d, "ref", d)).lower() == ref.lower() for d in found)


def dataset_exists(api, ref: str, tries: int = 3, sleep=time.sleep) -> bool:
    """True when the dataset is there, False when Kaggle says there is no such dataset: a 404, or a 403 for a dataset
    its owner's own list does not hold (#815). Any other failure is tried again, then raises StatusUnknown (#691,
    item 3: a failed status call was read as "nothing to resume")."""
    for attempt in range(tries):
        try:
            api.dataset_status(ref)
            return True
        except Exception as e:  # noqa: BLE001 - sorted below: missing, or not known
            if is_not_found(e):
                return False
            if is_forbidden(e):
                listed = listed_as_own(api, ref)
                if listed is not None:
                    return listed
            if attempt == tries - 1:
                raise StatusUnknown(f"{type(e).__name__}: {str(e)[:200]}") from e
            sleep(15)
    return False


def was_taken(response) -> bool:
    """Whether Kaggle took an upload: its answer says "ok" and names no error. The client answers some refusals with
    a status of "error" and no exception (#691, item 1), and an answer of None is no answer."""
    if response is None:
        return False
    get = response.get if isinstance(response, dict) else lambda k, d=None: getattr(response, k, d)
    return str(get("status", "") or "").lower() == "ok" and not get("error", None)


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


def session_id() -> str:
    """This notebook session's id: when it first ran a run here (UTC) and a random part, kept on the machine so every
    run of the session, and every fresh copy of this file `follow` loads, gives the same. A new Colab session is a new
    machine, and so a new id."""
    f = LOG.parent / "htl_session"
    try:
        sid = f.read_text().strip()
        if sid:
            return sid
    except OSError:
        pass
    sid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(4)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(sid)
    return sid


def upload(api, user: str, label: str, out: Path, note: str) -> None:
    """The log and the kernel's output so far, as a new version of the run's private dataset (made on first use),
    with the session that sent it (`session.json`). Raises unless Kaggle took it (#691, item 1), and leaves no copy
    of the output behind (item 5)."""
    ref = results_ref(user, label)
    stage = LOG.parent / "htl_upload"
    shutil.rmtree(stage, ignore_errors=True)
    try:
        (stage / "working").mkdir(parents=True)
        if LOG.exists():
            shutil.copyfile(LOG, stage / "colab.log")
        for p in files_to_return(out) if Path(out).exists() else []:
            dest = stage / "working" / p.relative_to(out)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
        (stage / "session.json").write_text(json.dumps({
            "session_id": session_id(), "label": label, "note_text": note[:100],
            "uploaded_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
        (stage / "dataset-metadata.json").write_text(json.dumps(results_metadata(user, label)))
        if dataset_exists(api, ref):   # a status that cannot be had raises: never a new dataset over an existing one
            answer = api.dataset_create_version(str(stage), version_notes=note[:100], quiet=True, dir_mode="zip")
        else:
            answer = api.dataset_create_new(str(stage), public=False, quiet=True, dir_mode="zip")
        if not was_taken(answer):
            raise RuntimeError(f"Kaggle did not take the upload to {ref}: status "
                               f"{getattr(answer, 'status', None)!r}, error {str(getattr(answer, 'error', None))[:200]!r}")
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    print(f"uploaded to {ref}: {note}", flush=True)


def restore(api, user: str, label: str, out: Path, resume_session: str | None = None,
            sleep=time.sleep) -> tuple[str, int]:
    """Give a run its own earlier output back, from its results dataset, before anything is uploaded over it: a
    session that dropped then costs the tasks since its last upload, not the run. Stops the run (#691, item 3) when
    Kaggle cannot say whether the dataset is there, when it is there and cannot be read, and when an unfinished
    upload is another session's and the run's entry does not name that session (`resume_session`): two sessions on
    one GPU model, or a run list that cannot be read, would otherwise go on from each other's output."""
    ref = results_ref(user, label)
    try:
        if not dataset_exists(api, ref, sleep=sleep):
            return "fresh", 0
    except StatusUnknown as e:
        raise SystemExit(f"could not tell whether {ref} exists ({e}): stopped, since a run that cannot see its earlier "
                         "output could be made again over it") from e
    got = LOG.parent / "htl_restore"
    shutil.rmtree(got, ignore_errors=True)
    got.mkdir(parents=True)
    try:
        for attempt in range(3):
            try:
                download_dataset(api, ref, got)
                break
            except Exception as e:
                if attempt == 2:
                    raise SystemExit(f"{ref} exists and could not be read: {type(e).__name__}") from e
                sleep(20)
        state, done = earlier_output(got)
        try:
            owner = json.loads((got / "session.json").read_text()).get("session_id") or "unrecorded"
        except (OSError, ValueError):
            owner = "unrecorded"   # an upload from before #691
        mine = session_id()
        if state != "finished" and owner != mine and resume_session != owner:
            raise SystemExit(f"{ref} was last sent by session {owner}, not this one ({mine}): another session may be "
                             f"making this run. To go on from that upload, give the run's entry "
                             f'"resume_session": "{owner}"')
        if state != "fresh" and state != "finished":
            shutil.rmtree(out, ignore_errors=True)
            shutil.copytree(got / "working", out)
        return state, done
    finally:
        shutil.rmtree(got, ignore_errors=True)   # nothing of an earlier start is kept but what the kernel is given


def fetch(api, kagglehub, bundle: str, kernel_dataset: str | None, kernel_url: str | None,
          root: Path = KAGGLE, with_model: bool = True, handle: str = MODEL) -> Path:
    """The inputs at Kaggle's paths, and the kernel file: for a development batch (its order says
    `"source": "competition"`), the competition's files for its tasks too. `handle`: the model to mount. Returns the
    kernel file's path."""
    (Path(root) / "input").mkdir(parents=True, exist_ok=True)
    for old in stale_bundles(root, dataset_dir(bundle, root)):
        say(f"removing another run's bundle: {old}")
        shutil.rmtree(old, ignore_errors=True)
    for ref in (WHEELHOUSE, bundle):
        dest = dataset_dir(ref, root)
        listed = listed_files(api, ref)
        if not listed:
            raise SystemExit(f"{ref} lists no files")
        if (gone := missing_files(listed, dest)):   # a folder that is not empty is not complete (#691, item 4)
            if dest.exists() and any(dest.iterdir()):
                say(f"{ref}: {len(gone)} of its {len(listed)} files are missing or of another size; downloading it again")
                shutil.rmtree(dest)
            say(f"downloading {ref} -> {dest}")
            download_dataset(api, ref, dest)
            if (gone := missing_files(listed, dest)):
                raise SystemExit(f"{ref}: after the download, {len(gone)} listed files are missing or of another size: "
                                 + ", ".join(gone[:10]))
        say(f"{ref}: all {len(listed)} listed files, at their listed sizes")
    order = dataset_dir(bundle, root) / "official_batch.json"
    meta = json.loads(order.read_text()) if order.exists() else {}
    if meta.get("source") == "competition":   # a development batch: no competition is mounted here (#780)
        fetch_competition_files(api, meta.get("competition") or COMPETITION, meta["instance_ids"], root)
    target = model_dir(root, handle)
    if with_model and not (target / "config.json").exists():
        say(f"downloading the model {handle}")
        cached = Path(kagglehub.model_download(handle))
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
        kernel.write_bytes(urllib.request.urlopen(kernel_url, timeout=60).read())   # the repository's own file
    if not kernel.exists():
        raise SystemExit(f"no official_agent_kernel.py in {kernel_dataset or kernel_url}")
    return kernel


def start_kernel(kernel: Path, out: Path, log) -> subprocess.Popen:
    """The kernel's process, in a process group of its own so that it and everything it started end together, from
    an environment with no credential."""
    return subprocess.Popen([sys.executable, "-u", str(kernel)], cwd=str(out),
                            env={**kernel_env(dict(os.environ)), **kernel_paths(KAGGLE)},
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def end_process_group(proc: subprocess.Popen, grace_seconds: float = 30) -> None:
    """End the kernel's whole process group: asked first, then made to."""
    for sig in (signal.SIGTERM, signal.SIGKILL):   # SIGKILL for whatever of the group is left, leader or not
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            if sig == signal.SIGKILL:
                say(f"the kernel's process {proc.pid} did not end")


def wait_for_kernel(proc: subprocess.Popen, stop: threading.Event, uploader: threading.Thread,
                    sleep=time.sleep, poll_seconds: float = 60, grace_seconds: float = 30) -> int:
    """Wait for the kernel, and however the wait ends (the notebook's stop button raises KeyboardInterrupt here),
    stop the uploader and end the kernel's process group before going on (#691, item 2): an uploader left going
    would send `working/`, by then the next run's, to this run's dataset."""
    started = time.monotonic()
    try:
        while proc.poll() is None:
            sleep(poll_seconds)
            print(f"  kernel running, {round((time.monotonic() - started) / 60)} min", flush=True)
        return proc.returncode
    finally:
        stop.set()
        if proc.poll() is None:
            say("the wait was stopped: ending the kernel's processes")
        end_process_group(proc, grace_seconds)
        uploader.join(timeout=max(grace_seconds, 1) * 10)   # an upload under way finishes; none starts after it


def clear_earlier_output(out: Path, send_earlier) -> None:
    """An earlier run's output on this machine is sent, then removed, before the next run starts (#691, item 5):
    nothing of one arm stays on the machine for the next. `send_earlier(label)` uploads it as that run's. Output
    whose results did not reach Kaggle and still cannot be sent is kept, and no run starts over it."""
    out = Path(out)
    if not out.exists() or not any(out.iterdir()):
        return
    marker = LOG.parent / "htl_working_label"
    earlier = marker.read_text().strip() if marker.exists() else ""
    if not earlier:
        raise SystemExit(f"{out} holds output this helper did not record the run of: it is neither sent nor removed. "
                         "Copy it off the machine and remove it, then start again")
    not_sent = LOG.parent / f"htl_not_sent_{earlier}"
    if not_sent.exists():
        say(f"the results of {earlier} did not reach Kaggle: sending them before anything else")
        if not send_until_taken(lambda: send_earlier(earlier)):
            raise SystemExit(f"the results of {earlier} are only on this machine and could not be sent: they are kept, "
                             "and no run starts over them")
        not_sent.unlink()
    say(f"removing {earlier}'s output from this machine: it is on Kaggle")
    shutil.rmtree(out)


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
            user: str | None = None, model: str | None = None) -> int:
    """One run, start to finish. Returns the kernel's exit code (or 1 when it never started). `model`: the model
    handle to mount; by default the one the run's entry in the run list names (`listed_model`)."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    user = user or os.environ["KAGGLE_USERNAME"]
    listed, label = label, base_label(label)   # `<label>-try<n>` is the same run, listed again
    results_ref(user, label)   # refuse a bad label before any work
    out, code, api = KAGGLE / "working", 1, None
    # A new version of a Kaggle dataset replaces its files, so nothing is uploaded until this run's own earlier output
    # has been looked at: never an empty folder over an arm's results.
    may_upload = False
    say(f"run {label}{'' if listed == label else ' (listed as ' + listed + ')'}: bundle {bundle}; "
        f"kernel from {kernel_dataset or kernel_url}; session {session_id()}")
    try:
        shown = run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv"])
        entry = listed_entry(listed)
        wanted, name = (entry or {}).get("gpu") or None, gpu_name(shown.stdout)
        if not is_for_this_gpu(wanted, name):   # another session's run: nothing of it is read, and nothing is sent
            say(f"{label} is for a machine with a {wanted}; this one has a {name}: it is not made here")
            return 0
        if not network_open_acknowledged(entry):   # #691, item 6: nothing blocks the network at the machine
            say(f"{label} {NETWORK_REFUSAL}")
            return 1
        handle = model or listed_model(listed)
        say(f"{label}: model {handle}")
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
        clear_earlier_output(out, lambda earlier: upload(api, user, earlier, out, "finished; sent before the next run"))
        state, done_count = restore(api, user, label, out, resume_session=(entry or {}).get("resume_session"))
        if state == "finished":
            say(f"{label} already finished in an earlier start ({done_count} tasks with a result): not run again")
            return 0
        (LOG.parent / "htl_working_label").write_text(label)   # whose output `working/` holds, for the next run
        may_upload = True
        if state == "partial":
            say(f"{label}: an earlier start left {done_count} tasks with a result; the kernel runs the rest")
        try:   # a first note, so the run can be seen to have started without the notebook's screen
            upload(api, user, label, out, "started")
        except Exception as e:  # noqa: BLE001 - a note that fails must not stop the run
            say(f"the first note was not sent, carrying on: {type(e).__name__}: {str(e)[:200]}")
        kernel = fetch(api, kagglehub, bundle, kernel_dataset, kernel_url, handle=handle)
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
        try:
            with LOG.open("a") as log:
                proc = start_kernel(kernel, out, log)
                code = wait_for_kernel(proc, stop, uploader)
        finally:
            stop.set()
            subprocess.run(["pkill", "-f", "vllm"], check=False)   # a model server left behind would hold the GPU
        say(f"kernel exit {code}")
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
            print("nothing was uploaded: the run was not made here, or ended before its earlier output had been "
                  "looked at", flush=True)
        elif send_until_taken(send):
            not_sent.unlink(missing_ok=True)
            shutil.rmtree(out, ignore_errors=True)   # on Kaggle now: nothing of this run stays for the next (#691, 5)
        else:
            not_sent.write_text("")   # `main` keeps the GPU while this is here
            print("THE LOG COULD NOT BE UPLOADED. Copy the text above.", flush=True)
    return code
