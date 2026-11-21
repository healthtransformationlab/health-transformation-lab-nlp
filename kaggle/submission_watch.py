"""Watch this team's leaderboard entries in the Gemma 4 Developer Agent competition (spec 014 US7, #791).

    python kaggle/submission_watch.py --competition gemma-4-developer-agent --ledger data/tasks/leaderboard_entries.csv

An entry runs on Kaggle's own machines with no code of ours, so it can't be traced: the API gives its status, score
and dates, nothing more. This keeps them in a ledger, one row per entry (overwritten, so a rerun changes nothing), and
sends one span `leaderboard_entry` per status change through the package's telemetry (DENTAL_TELEMETRY; azure in the
leaderboard-watch workflow when APPINSIGHTS_CONNECTION_STRING is set). The submissions list hides a pending entry, so
every entry the ledger holds that isn't complete is also looked up by its ref.

- `first_seen_ts`: when this watcher first saw the entry.
- `finished_ts` / `completed_ts`: when it first saw COMPLETE or failed (error / Notebook Timeout). Empty when the
  entry was already terminal on first sight (the real finish time is unknown).
- `wall_hours` (also written as `scoring_hours` for older readers): finished_ts less submitted_ts.
- `final_status_text`: the public score, or `Notebook Timeout` when Kaggle says the notebook exceeded runtime.
- `agent_commit_sha`: the agent's commit, when the description names one after "main " (`main 9c9cd3a`).

Optional `--entries PATH` writes the slim companion CSV used by gemma-developer-agent-private
(`analysis/leaderboard_entry.csv`): ref, submitted_ts, finished_ts, wall_hours, final_status_text.

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
           "finished_ts", "scoring_hours", "wall_hours", "final_status_text", "agent_commit_sha"]
ENTRIES_COLUMNS = ["ref", "submitted_ts", "finished_ts", "wall_hours", "final_status_text"]
STATUSES = ("pending", "complete", "error")
COMMIT = re.compile(r"\bmain ([0-9a-f]{7,40})\b")
TIMEOUT_PHRASE = "exceeded the allowed runtime"
TS = "%Y-%m-%dT%H:%M:%SZ"
TERMINAL = frozenset({"complete", "error"})


def now_ts() -> str:
    return datetime.now(UTC).strftime(TS)


def _parse_ts(text: str) -> datetime:
    return datetime.strptime(text, TS).replace(tzinfo=UTC)


def commit_of(description: str) -> str:
    m = COMMIT.search(description or "")
    return m.group(1) if m else ""


def final_status_text(status: str, public_score: str, error_description: str = "") -> str:
    """Score string, or Notebook Timeout when Kaggle reports a runtime exceedance."""
    err = (error_description or "").lower()
    if TIMEOUT_PHRASE in err or (status == "error" and "runtime" in err and "exceed" in err):
        return "Notebook Timeout"
    if status == "error" and not (public_score or "").strip():
        return "Notebook Timeout" if TIMEOUT_PHRASE in err else (error_description or "error")
    if (public_score or "").strip() != "":
        return str(public_score).strip()
    if status == "pending":
        return "pending"
    return ""


def wall_hours_between(submitted_ts: str, finished_ts: str) -> str:
    if not submitted_ts or not finished_ts or finished_ts == "unknown":
        return "unknown" if finished_ts == "unknown" else ""
    return f"{(_parse_ts(finished_ts) - _parse_ts(submitted_ts)).total_seconds() / 3600:.2f}"


def entry_rows(submissions: list[dict], ledger: list[dict], now_ts: str) -> list[dict]:
    """The ledger after this watch: one row per entry, by ref, from the submissions seen now and what the ledger
    already holds. Entries the API didn't return this time are kept as they were. Sorted by submission time, then
    ref."""
    old = {str(r["ref"]): r for r in ledger}
    rows = {ref: {c: (r.get(c) or "") for c in COLUMNS} for ref, r in old.items()}
    for s in submissions:
        ref = str(s["ref"])
        before = old.get(ref)
        status = s["status"]
        error_description = s.get("error_description") or ""
        # Preserve a known finish; set it the first time we see COMPLETE or failed after a non-terminal row.
        finished = (before or {}).get("finished_ts") or (before or {}).get("completed_ts") or ""
        if finished == "unknown":
            finished = ""
        before_status = (before or {}).get("status") or ""
        if not finished and status in TERMINAL and before is not None and before_status not in TERMINAL:
            finished = now_ts
        elif not finished and status in TERMINAL and before is None:
            # Already done before we watched: wall time unknown; leave finished empty and mark on write via
            # wall_hours unknown only when we choose to — keep finished empty (existing contract).
            finished = ""
        submitted = s.get("submitted_ts") or (before or {}).get("submitted_ts") or ""
        score = "" if s.get("public_score") is None else str(s["public_score"])
        # Prefer a timeout label even when Kaggle leaves status as COMPLETE with an error_description.
        text = final_status_text(status, score, error_description)
        if text == "Notebook Timeout" and status == "complete":
            status = "error"
        hours = wall_hours_between(submitted, finished) if finished else ""
        description = s.get("description") or ""
        rows[ref] = {
            "ref": ref,
            "description": description,
            "submitted_ts": submitted,
            "status": status,
            "public_score": score,
            "first_seen_ts": (before or {}).get("first_seen_ts") or now_ts,
            "completed_ts": finished,
            "finished_ts": finished,
            "scoring_hours": hours,
            "wall_hours": hours,
            "final_status_text": text if status in TERMINAL or text == "pending" else text,
            "agent_commit_sha": commit_of(description),
        }
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
    error = getattr(s, "error_description", None) or getattr(s, "_error_description", None) or ""
    if TIMEOUT_PHRASE in str(error).lower():
        status = "error"
    return {"ref": str(s.ref), "description": s.description or "", "submitted_ts": date or "", "status": status,
            "public_score": "" if s.public_score in (None, "") else str(s.public_score),
            "error_description": str(error or "")}


def make_api():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def read_ledger(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Older ledgers lack finished_ts / wall_hours / final_status_text; fill blanks.
    out = []
    for r in rows:
        row = {c: (r.get(c) or "") for c in COLUMNS}
        if not row["finished_ts"] and row["completed_ts"]:
            row["finished_ts"] = row["completed_ts"]
        if not row["wall_hours"] and row["scoring_hours"]:
            row["wall_hours"] = row["scoring_hours"]
        if not row["scoring_hours"] and row["wall_hours"]:
            row["scoring_hours"] = row["wall_hours"]
        out.append(row)
    return out


def write_ledger(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows([{c: r.get(c, "") for c in COLUMNS} for r in rows])
    tmp.replace(path)                                  # overwrite whole: a rerun writes the same file


def write_entries_csv(path: Path, rows: list[dict]) -> None:
    """Slim companion used by gemma-developer-agent-private analysis/leaderboard_entry.csv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = [{c: r.get(c, "") for c in ENTRIES_COLUMNS} for r in rows]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ENTRIES_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(slim)
    tmp.replace(path)


def fetch(api, competition: str, ledger: list[dict]) -> list[dict]:
    """Every entry of this team: the list, then each ledger entry not complete that the list left out, by ref."""
    seen = {}
    for s in api.competition_submissions(competition, page_size=100) or []:
        if s is not None:
            seen[str(s.ref)] = submission_dict(s)
    lookup = getattr(api, "get_submission", None) or api.competition_submission
    for r in ledger:
        ref = str(r["ref"])
        if ref not in seen and r.get("status") not in TERMINAL:
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
    ap.add_argument("--entries", type=Path, default=None,
                    help="optional slim CSV (ref, submitted_ts, finished_ts, wall_hours, final_status_text)")
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
        if a.entries is not None:
            write_entries_csv(a.entries, rows)
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
        report_export(telemetry)


def report_export(telemetry) -> bool:
    """Send the run's spans now and say whether the backend took them (014 BUG2, #801): a switch that says "azure"
    is not evidence that anything arrived. Prints nothing when telemetry is off."""
    if telemetry.active_exporter() == "off":
        return True
    ok = telemetry.flush()
    if ok:
        print("telemetry export: ok")
    else:
        line = "telemetry export: FAILED (the spans did not reach the backend; the exporter's warnings are above)"
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::warning title=telemetry export::{line}")
        print(line, file=sys.stderr)
    return ok


if __name__ == "__main__":
    sys.exit(main())
