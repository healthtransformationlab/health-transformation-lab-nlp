"""What a Colab tab would run, and whether a tab that looked disconnected is still running (028 US7, #847).

Every Colab run sends `session.json` (its session id, a note such as "still running" or "finished, kernel exit 0", and
when it was sent) to its results dataset, jcblearning/htlnlp-colab-official-<label>, about every eight minutes. This
reads the run list on a branch, looks each run up, and says for each: finished, running (an upload in the last 20
minutes), stale (none for 20 minutes or more: the tab has most likely dropped) or not started. With --gpu it names
the run a new tab on that GPU would make. Read the answer before opening a tab: a tab that looked disconnected may
still be running (on November 16, one "disconnected quickly" and finished 1 h 44 min later).

    python kaggle/colab_status.py --branch data/824-028-colab-devset --gpu L4

Needs the Kaggle token the other kaggle/ scripts use (KAGGLE_API_TOKEN or KAGGLE_KEY, and KAGGLE_USERNAME). Reads only.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "healthtransformationlab/health-transformation-lab-nlp"
RESULT_PREFIX = "htlnlp-colab-official-"   # kaggle/colab_official.py's results_ref
STALE_MINUTES = 20                          # a live run uploads about every eight minutes


def base_label(label: str) -> str:
    """`<label>-try<n>` is the same run listed again; its results go where the run's own go (colab_official.py)."""
    return re.sub(r"-try\d+$", "", label)


def state_of(session: dict | None, now: dt.datetime) -> str:
    if not session:
        return "not started"
    if str(session.get("note_text", "")).startswith("finished"):
        return "finished"
    sent = dt.datetime.strptime(session["uploaded_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    return "running" if now - sent < dt.timedelta(minutes=STALE_MINUTES) else "stale"


def status_rows(runs: list[dict], read_session, now: dt.datetime) -> list[dict]:
    """One row per listed run, in the list's order (the order a notebook makes them in)."""
    rows = []
    for run in runs:
        session = read_session(base_label(run["label"]))
        rows.append({"label": run["label"], "gpu": run.get("gpu") or "any", "state": state_of(session, now),
                     "session_id": (session or {}).get("session_id", ""),
                     "uploaded_ts": (session or {}).get("uploaded_ts", "")})
    return rows


def next_run(rows: list[dict], gpu: str) -> str | None:
    """The run a new tab on `gpu` would make: the first one for that GPU (or for any) that is neither finished nor
    being made by a running tab. A stale run is made again; it goes on from its last upload."""
    for r in rows:
        if r["gpu"] != "any" and r["gpu"].lower() != gpu.lower():
            continue
        if r["state"] in ("finished", "running"):
            continue
        return r["label"]
    return None


def render(rows: list[dict], gpu: str | None, now: dt.datetime | None = None) -> str:
    out = []
    for r in rows:
        age = ""
        if r["uploaded_ts"] and now:
            sent = dt.datetime.strptime(r["uploaded_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            age = " (%d min ago)" % ((now - sent).total_seconds() // 60)
        out.append("%-24s %-5s %-12s %s %s%s" % (r["label"], r["gpu"], r["state"], r["session_id"] or "-",
                                                r["uploaded_ts"] or "", age))
    if gpu:
        out.append("next on %s: %s" % (gpu, next_run(rows, gpu) or "nothing"))
    return "\n".join(out)


def kaggle_session_reader(user: str):
    """Reads session.json from a run's results dataset; None when the dataset or file isn't there (a 403 or 404)."""
    from kaggle.api.kaggle_api_extended import KaggleApi   # noqa: PLC0415 - only the CLI needs it
    api = KaggleApi()
    api.authenticate()

    def read(label: str) -> dict | None:
        with tempfile.TemporaryDirectory() as td:
            try:
                with contextlib.redirect_stdout(io.StringIO()):   # the client prints each dataset's URL
                    api.dataset_download_file(f"{user}/{RESULT_PREFIX}{label}", "session.json", path=td, force=True,
                                              quiet=True)
            except Exception:  # noqa: BLE001 - a run that never uploaded has no dataset
                return None
            for p in Path(td).iterdir():
                if p.suffix == ".zip":
                    with zipfile.ZipFile(p) as z:
                        return json.loads(z.read("session.json"))
                if p.name.startswith("session"):
                    return json.loads(p.read_text())
        return None
    return read


def run_list(branch: str, path: str | None) -> list[dict]:
    if path:
        return json.loads(Path(path).read_text())["runs"]
    url = f"https://raw.githubusercontent.com/{REPO}/refs/heads/{branch}/kaggle/colab_official_run.json"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())["runs"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--branch", default="main", help="the branch whose run list a notebook reads")
    ap.add_argument("--gpu", help="the GPU of the tab you would open (L4 or A100)")
    ap.add_argument("--list", help="a local run list instead of the branch's")
    a = ap.parse_args(argv)
    user = os.environ.get("KAGGLE_USERNAME") or "jcblearning"
    now = dt.datetime.now(dt.timezone.utc)
    rows = status_rows(run_list(a.branch, a.list), kaggle_session_reader(user), now)
    print(render(rows, a.gpu, now))
    return 0


if __name__ == "__main__":
    sys.exit(main())
