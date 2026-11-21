"""Dispatch the leaderboard watch when GitHub's schedule has gone quiet (014 BUG3 #809).

GitHub often skips `schedule` triggers. The watch itself is every two hours; this script runs hourly and:

  last completed watch age > 3.5 h   `gh workflow run` leaderboard-watch.yml (workflow_dispatch)
  last completed watch age >= 6 h    write data/tasks/leaderboard_watch_stale.json (SEV3 for the daily digest)
  otherwise                          clear that stale marker if present; nothing else

Needs the gh CLI with `actions: write` (GH_TOKEN). Read-only on Kaggle: it only starts the watch workflow.

    python .github/scripts/leaderboard_watch_keepalive.py
    python .github/scripts/leaderboard_watch_keepalive.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_FILE = "leaderboard-watch.yml"
WORKFLOW_NAME = "Watch the competition's leaderboard entries"
STALE_PATH = REPO_ROOT / "data" / "tasks" / "leaderboard_watch_stale.json"
DISPATCH_HOURS = 3.5
ALERT_HOURS = 6.0


def _parse_iso(iso_ts: str) -> datetime:
    # GitHub returns ...Z; fromisoformat accepts +00:00
    t = datetime.fromisoformat(iso_ts[:-1] + "+00:00" if iso_ts.endswith("Z") else iso_ts)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def hours_since(iso_ts: str, now: datetime) -> float:
    return (now - _parse_iso(iso_ts)).total_seconds() / 3600.0


def should_dispatch(hours: float) -> bool:
    return hours > DISPATCH_HOURS


def is_stale_alert(hours: float) -> bool:
    return hours >= ALERT_HOURS


def _gh(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    return subprocess.run(["gh", *args], check=check, capture_output=True, text=True, env=env)


def last_completed_created_at(repo: str) -> str | None:
    """ISO createdAt of the newest completed run of the watch workflow, or None if never."""
    r = _gh([
        "run", "list", "--repo", repo, "--workflow", WORKFLOW_FILE, "--status", "completed",
        "--limit", "20", "--json", "createdAt,event,conclusion,status",
    ])
    rows = json.loads(r.stdout or "[]")
    if not rows:
        return None
    rows.sort(key=lambda x: x["createdAt"], reverse=True)
    return rows[0]["createdAt"]


def dispatch_watch(repo: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"dry-run: would dispatch {WORKFLOW_NAME} on {repo}")
        return
    _gh(["workflow", "run", WORKFLOW_FILE, "--repo", repo])
    print(f"dispatched {WORKFLOW_FILE} on {repo} (workflow_dispatch)")


def write_stale(hours: float, last_iso: str | None, now: datetime, *, dry_run: bool) -> None:
    body = {
        "stale_hours": round(hours, 2),
        "last_finished_ts": last_iso,
        "recorded_ts": now.isoformat().replace("+00:00", "Z"),
        "severity_code": "SEV3",
        "reason_text": "leaderboard-watch has not completed for six or more hours (014 BUG3 #809)",
    }
    if dry_run:
        print(f"dry-run: would write {STALE_PATH} {body}")
        return
    STALE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STALE_PATH.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {STALE_PATH} ({hours:.1f} h since last completed watch)")


def clear_stale(*, dry_run: bool) -> None:
    if not STALE_PATH.is_file():
        return
    if dry_run:
        print(f"dry-run: would remove {STALE_PATH}")
        return
    STALE_PATH.unlink()
    print(f"removed {STALE_PATH}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--now", default="", help="ISO timestamp for tests")
    a = ap.parse_args(argv)
    repo = a.repo or "healthtransformationlab/health-transformation-lab-nlp"
    now = _parse_iso(a.now) if a.now else datetime.now(UTC)

    last = last_completed_created_at(repo)
    if last is None:
        print("no completed leaderboard-watch run found: dispatching")
        dispatch_watch(repo, dry_run=a.dry_run)
        write_stale(ALERT_HOURS, None, now, dry_run=a.dry_run)
        return 0

    hours = hours_since(last, now)
    print(f"last completed watch at {last} ({hours:.2f} h ago)")
    if should_dispatch(hours):
        dispatch_watch(repo, dry_run=a.dry_run)
    if is_stale_alert(hours):
        write_stale(hours, last, now, dry_run=a.dry_run)
    else:
        clear_stale(dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
