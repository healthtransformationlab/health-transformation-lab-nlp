"""Watch Colab official runs and ping the phone when one goes stale or finishes (#888).

Polls the same session.json uploads as ``colab_status.py`` (about every eight minutes from a live
tab). Writes:

- ``kaggle/colab_watch_status.json`` — current rows + events (the ideas HTML reads this)
- ``kaggle/colab_watch_log.jsonl`` — one line per state change

Optional ntfy: set ``NTFY_TOPIC`` (and optionally ``NTFY_SERVER``, default ``https://ntfy.sh``).

    python kaggle/colab_watch.py --branch data/849-028-colab-public-bundle --once
    python kaggle/colab_watch.py --branch data/849-028-colab-public-bundle --interval 120

Does not start a Colab tab or a GPU run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = REPO_ROOT / "kaggle" / "colab_watch_status.json"
LOG_PATH = REPO_ROOT / "kaggle" / "colab_watch_log.jsonl"

# Import sibling without installing the package as a module path.
sys.path.insert(0, str(REPO_ROOT / "kaggle"))
import colab_status as cs  # noqa: E402


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(now: dt.datetime | None = None) -> str:
    return (now or utc_now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def ntfy_send(title: str, body: str, *, topic: str, server: str) -> None:
    url = f"{server.rstrip('/')}/{topic}"
    req = urllib.request.Request(
        url,
        data=body.encode(),
        method="POST",
        headers={"Title": title, "Tags": "desktop,colab"},
    )
    try:
        urllib.request.urlopen(req, timeout=30)
    except (urllib.error.URLError, TimeoutError) as err:
        print(f"ntfy failed: {err}", file=sys.stderr)


def load_prev(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return {row["label"]: row["state"] for row in data.get("rows", []) if "label" in row and "state" in row}


def append_log(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def mirror_to_ideas(status: dict, ideas_status: Path | None) -> None:
    if ideas_status is None:
        return
    ideas_status.parent.mkdir(parents=True, exist_ok=True)
    ideas_status.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n")


def poll_once(
    *,
    branch: str,
    list_path: str | None,
    gpu: str | None,
    prev: dict[str, str],
    topic: str | None,
    server: str,
    ideas_status: Path | None,
) -> dict[str, str]:
    user = os.environ.get("KAGGLE_USERNAME") or "jcblearning"
    now = utc_now()
    runs = cs.run_list(branch, list_path)
    rows = cs.status_rows(runs, cs.kaggle_session_reader(user), now)
    events = []
    for row in rows:
        label, state = row["label"], row["state"]
        was = prev.get(label)
        if was is None:
            events.append({"ts": iso(now), "label": label, "from": None, "to": state, "kind": "seen"})
        elif was != state:
            kind = "finished" if state == "finished" else "stale" if state == "stale" else "changed"
            events.append({"ts": iso(now), "label": label, "from": was, "to": state, "kind": kind})
            if topic and kind in ("finished", "stale"):
                ntfy_send(
                    f"Colab {kind}: {label}",
                    f"{label}: {was} → {state} ({row.get('uploaded_ts') or 'no upload'})",
                    topic=topic,
                    server=server,
                )
            append_log(LOG_PATH, events[-1])

    nxt = cs.next_run(rows, gpu) if gpu else None
    # Keep a short rolling event list on the status file for the HTML panel.
    prior_events = []
    if STATUS_PATH.exists():
        try:
            prior_events = json.loads(STATUS_PATH.read_text()).get("events") or []
        except json.JSONDecodeError:
            prior_events = []
    merged_events = (prior_events + events)[-40:]

    payload = {
        "updated_ts": iso(now),
        "branch": branch,
        "gpu": gpu,
        "next_label": nxt,
        "rows": rows,
        "events": merged_events,
        "log_path": str(LOG_PATH),
        "note": (
            "Pro+ background execution: you can close the tab. "
            "VPN off. Reopen only when state is stale, not when the tab looks sad."
        ),
    }
    write_status(STATUS_PATH, payload)
    mirror_to_ideas(payload, ideas_status)
    print(cs.render(rows, gpu, now))
    if events:
        for event in events:
            print(f"event {event['kind']}: {event['label']} {event['from']} -> {event['to']}")
    return {row["label"]: row["state"] for row in rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--branch", default="data/849-028-colab-public-bundle")
    ap.add_argument("--list", help="local colab_official_run.json instead of the branch")
    ap.add_argument("--gpu", default="A100", help="GPU for next-run hint (L4 or A100)")
    ap.add_argument("--interval", type=int, default=120, help="seconds between polls (ignored with --once)")
    ap.add_argument("--once", action="store_true", help="one poll and exit")
    ap.add_argument(
        "--ideas-status",
        default=os.environ.get(
            "HTL_IDEAS_COLAB_STATUS",
            str(Path.home() / "projects" / "gemma-developer-agent-private" / "analysis" / "colab_launches.json"),
        ),
        help="also write status JSON here for the ideas HTML panel",
    )
    ap.add_argument("--no-ideas-mirror", action="store_true")
    a = ap.parse_args(argv)

    topic = os.environ.get("NTFY_TOPIC", "").strip() or None
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").strip()
    ideas_status = None if a.no_ideas_mirror else Path(a.ideas_status)

    prev = load_prev(STATUS_PATH)
    while True:
        prev = poll_once(
            branch=a.branch,
            list_path=a.list,
            gpu=a.gpu,
            prev=prev,
            topic=topic,
            server=server,
            ideas_status=ideas_status,
        )
        if a.once:
            return 0
        time.sleep(max(30, a.interval))


if __name__ == "__main__":
    raise SystemExit(main())
