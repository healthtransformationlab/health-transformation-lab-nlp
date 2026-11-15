"""Watch this team's leaderboard entries in the Gemma 4 Developer Agent competition (spec 014 US7, #791).

    python kaggle/submission_watch.py --competition gemma-4-developer-agent --ledger data/tasks/leaderboard_entries.csv

An entry runs on Kaggle's own machines with no code of ours, so it can't be traced: the API gives its status, score
and dates, nothing more. This keeps them in a ledger, one row per entry (overwritten, so a rerun changes nothing), and
sends one span `leaderboard_entry` per status change through the package's telemetry (DENTAL_TELEMETRY; azure in the
leaderboard-watch workflow when APPINSIGHTS_CONNECTION_STRING is set). The submissions list hides a pending entry, so
every entry the ledger holds that isn't complete is also looked up by its ref.

- `first_seen_ts`: when this watcher first saw the entry.
- `completed_ts`: when it first saw it complete, so within one watch (two hours) of the real time, which the API
  doesn't give; empty for an entry already complete when first seen.
- `scoring_hours`: completed_ts less submitted_ts.
- `agent_commit_sha`: the agent's commit, when the description names one after "main " (`main 9c9cd3a`).

An entry that turns to error ends the run with exit code 1 after the ledger is written (SEV2: the workflow fails and
GitHub emails the owner the same day). It fails again on each watch until the ledger that records the error is merged.
A span carries the ref, the status and the score, never the description. Needs KAGGLE_API_TOKEN (or KAGGLE_KEY).
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

COLUMNS = ["ref", "description", "submitted_ts", "status", "public_score", "first_seen_ts", "completed_ts",
           "scoring_hours", "agent_commit_sha"]
STATUSES = ("pending", "complete", "error")
COMMIT = re.compile(r"\bmain ([0-9a-f]{7,40})\b")
TS = "%Y-%m-%dT%H:%M:%SZ"


def now_ts() -> str:
    return datetime.now(UTC).strftime(TS)


def _parse_ts(text: str) -> datetime:
    return datetime.strptime(text, TS).replace(tzinfo=UTC)


def commit_of(description: str) -> str:
    m = COMMIT.search(description or "")
    return m.group(1) if m else ""


def entry_rows(submissions: list[dict], ledger: list[dict], now_ts: str) -> list[dict]:
    """The ledger after this watch: one row per entry, by ref, from the submissions seen now (`ref`, `description`,
    `submitted_ts`, `status`, `public_score`) and what the ledger already holds. Entries the API didn't return this
    time are kept as they were. Sorted by submission time, then ref."""
    old = {str(r["ref"]): r for r in ledger}
    rows = {ref: {c: (r.get(c) or "") for c in COLUMNS} for ref, r in old.items()}
    for s in submissions:
        ref = str(s["ref"])
        before = old.get(ref)
        status = s["status"]
        completed = (before or {}).get("completed_ts") or ""
        if not completed and status == "complete" and before is not None and before.get("status") != "complete":
            completed = now_ts
        submitted = s.get("submitted_ts") or (before or {}).get("submitted_ts") or ""
        hours = ""
        if completed and submitted:
            hours = f"{(_parse_ts(completed) - _parse_ts(submitted)).total_seconds() / 3600:.2f}"
        description = s.get("description") or ""
        rows[ref] = {"ref": ref, "description": description, "submitted_ts": submitted, "status": status,
                     "public_score": "" if s.get("public_score") is None else str(s["public_score"]),
                     "first_seen_ts": (before or {}).get("first_seen_ts") or now_ts, "completed_ts": completed,
                     "scoring_hours": hours, "agent_commit_sha": commit_of(description)}
    return sorted(rows.values(), key=lambda r: (r["submitted_ts"], int(r["ref"]) if r["ref"].isdigit() else 0, r["ref"]))


def status_changes(old: list[dict], new: list[dict]) -> list[dict]:
    """One dict per entry that is new or whose status changed: ref, previous_status ('' for a new entry), status,
    public_score."""
    before = {str(r["ref"]): r.get("status", "") for r in old}
    return [{"ref": r["ref"], "previous_status": before.get(r["ref"], ""), "status": r["status"],
             "public_score": r.get("public_score", "")}
            for r in new if before.get(r["ref"]) != r["status"]]


def submission_dict(s) -> dict:
    """An ApiSubmission (kaggle 2.2.5) as entry_rows reads it; the status as `pending`, `complete` or `error`."""
    status = getattr(s.status, "name", str(s.status)).rsplit(".", 1)[-1].lower()
    date = s.date
    if isinstance(date, datetime):
        date = (date if date.tzinfo else date.replace(tzinfo=UTC)).astimezone(UTC).strftime(TS)
    return {"ref": str(s.ref), "description": s.description or "", "submitted_ts": date or "", "status": status,
            "public_score": "" if s.public_score in (None, "") else str(s.public_score)}


def make_api():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def read_ledger(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_ledger(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)                                  # overwrite whole: a rerun writes the same file


def fetch(api, competition: str, ledger: list[dict]) -> list[dict]:
    """Every entry of this team: the list, then each ledger entry not complete that the list left out, by ref."""
    seen = {}
    for s in api.competition_submissions(competition, page_size=100) or []:
        if s is not None:
            seen[str(s.ref)] = submission_dict(s)
    lookup = getattr(api, "get_submission", None) or api.competition_submission
    for r in ledger:
        ref = str(r["ref"])
        if ref not in seen and r.get("status") != "complete":
            seen[ref] = submission_dict(lookup(int(ref)))
    unknown = sorted({s["status"] for s in seen.values()} - set(STATUSES))
    if unknown:
        raise SystemExit(f"Kaggle returned a status this watcher doesn't know: {', '.join(unknown)}")
    return list(seen.values())


def send_spans(telemetry, changes: list[dict]) -> None:
    for c in changes:
        attrs = {"submission_ref_id": c["ref"], "status_code": c["status"],
                 "previous_status_code": c["previous_status"] or "none"}
        try:
            attrs["public_score_ratio"] = float(c["public_score"])
        except (TypeError, ValueError):
            pass
        with telemetry.pipeline_step("leaderboard_entry", **attrs):
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--competition", required=True, help="the competition's slug, e.g. gemma-4-developer-agent")
    ap.add_argument("--ledger", type=Path, required=True, help="the CSV kept, one row per entry")
    a = ap.parse_args(argv)
    if not (os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY")):
        sys.exit("KAGGLE_API_TOKEN is not set (ops/secrets_register.yaml, Kaggle API token)")

    from health_transformation_lab_nlp import telemetry
    telemetry.setup()                                  # DENTAL_TELEMETRY; off by default
    telemetry.start_script("submission_watch", data_label="public")
    try:
        api = make_api()
        old = read_ledger(a.ledger)
        rows = entry_rows(fetch(api, a.competition, old), old, now_ts())
        write_ledger(a.ledger, rows)
        changes = status_changes(old, rows)
        send_spans(telemetry, changes)
        for c in changes:
            print(f"{c['ref']}: {c['previous_status'] or 'new'} -> {c['status']}"
                  + (f" ({c['public_score']})" if c["public_score"] else ""))
        print(f"{len(rows)} entries, {len(changes)} status changes; telemetry {telemetry.active_exporter()}")
        failed = [c["ref"] for c in changes if c["status"] == "error"]
        if failed:
            print(f"SEV2: leaderboard entries in error: {', '.join(failed)} (kaggle competitions submissions "
                  f"{a.competition}); the ledger records them", file=sys.stderr)
            return 1
        return 0
    finally:
        telemetry.end_script()


if __name__ == "__main__":
    sys.exit(main())
