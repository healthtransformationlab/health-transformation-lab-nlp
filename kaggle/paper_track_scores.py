"""Main-leaderboard score for every Paper Track writeup, from Kaggle's own data.

Downloads the full public leaderboard of the Gemma 4 Developer Agent competition and every published writeup of its
Paper Track, then matches each writeup to a leaderboard team by the authors' Kaggle usernames (exact match, not
display names). Writes one CSV row per writeup; a writeup whose authors have no leaderboard team keeps empty
score cells, never a guess.

    KAGGLE_API_TOKEN=... python kaggle/paper_track_scores.py --out paper_track_scores.csv

Issue #731 (spec 028).

The public leaderboard is scored on about half the test data, so every row carries the time it was taken.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MAIN = "gemma-4-developer-agent"
PAPER = "gemma-4-developer-agent-paper"

COLUMNS = [
    "writeup_id",
    "title",
    "kaggle_url",
    "authors",
    "author_usernames",
    "main_lb_team",
    "main_lb_rank",
    "main_lb_score",
    "main_lb_entries",
    "main_lb_last_submission",
    "matched_on",
    "leaderboard_taken_at",
]


@dataclass(frozen=True)
class Team:
    rank: int
    name: str
    score: str
    entries: str
    last_submission: str
    usernames: frozenset[str]


@dataclass(frozen=True)
class Writeup:
    writeup_id: int
    title: str
    url: str
    authors: str
    usernames: tuple[str, ...]


def parse_leaderboard(text: str) -> list[Team]:
    """Kaggle's leaderboard CSV (Rank, TeamName, Score, SubmissionCount, LastSubmissionDate, TeamMemberUserNames)."""
    rows = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    teams = []
    for r in rows:
        members = frozenset(u.strip().lower() for u in (r.get("TeamMemberUserNames") or "").split(",") if u.strip())
        teams.append(
            Team(
                rank=int(r["Rank"]),
                name=r["TeamName"],
                score=r["Score"],
                entries=r["SubmissionCount"],
                last_submission=r["LastSubmissionDate"],
                usernames=members,
            )
        )
    return teams


def writeup_from_dict(d: dict) -> Writeup | None:
    """One item of ListHackathonWriteUps (camelCase dict); None for a writeup that isn't published."""
    w = d.get("writeUp") or {}
    if w.get("contentState") not in (None, "PUBLISHED"):
        return None
    names: list[str] = []
    for m in (d.get("team") or {}).get("teamMembers") or []:
        names.append(m.get("userName") or "")
    for m in w.get("collaborators") or []:
        names.append(m.get("userName") or "")
    usernames = tuple(dict.fromkeys(n.strip().lower() for n in names if n and n.strip()))
    url = w.get("url") or ""
    return Writeup(
        writeup_id=int(d["id"]),
        title=w.get("title") or "",
        url=f"https://www.kaggle.com{url}" if url.startswith("/") else url,
        authors=w.get("authors") or "",
        usernames=usernames,
    )


def match(writeup: Writeup, by_user: dict[str, Team]) -> tuple[Team | None, str]:
    """The best-ranked leaderboard team any author is on, and which username matched."""
    hits = [(by_user[u], u) for u in writeup.usernames if u in by_user]
    if not hits:
        return None, ""
    return min(hits, key=lambda h: h[0].rank)


def build_rows(writeups: list[Writeup], teams: list[Team], taken_at: str) -> list[dict[str, str]]:
    by_user: dict[str, Team] = {}
    for t in teams:
        for u in t.usernames:
            if u not in by_user or t.rank < by_user[u].rank:
                by_user[u] = t
    rows = []
    for w in sorted(writeups, key=lambda w: w.writeup_id):
        team, user = match(w, by_user)
        rows.append(
            {
                "writeup_id": str(w.writeup_id),
                "title": w.title,
                "kaggle_url": w.url,
                "authors": w.authors,
                "author_usernames": ", ".join(w.usernames),
                "main_lb_team": team.name if team else "",
                "main_lb_rank": str(team.rank) if team else "",
                "main_lb_score": team.score if team else "",
                "main_lb_entries": team.entries if team else "",
                "main_lb_last_submission": team.last_submission if team else "",
                "matched_on": user,
                "leaderboard_taken_at": taken_at,
            }
        )
    return rows


# --- Kaggle calls -------------------------------------------------------------------------------------------------


def _token() -> str:
    token = os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_API_KEY")
    if not token:
        sys.exit("Set KAGGLE_API_TOKEN (Kaggle -> Settings -> API -> Generate New Token)")
    return token


def download_leaderboard(competition: str) -> str:
    os.environ.setdefault("KAGGLE_API_TOKEN", _token())
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    with tempfile.TemporaryDirectory() as tmp:
        api.competition_leaderboard_download(competition, tmp, quiet=True)
        archive = next(Path(tmp).glob("*.zip"))
        with zipfile.ZipFile(archive) as z:
            name = next(n for n in z.namelist() if n.endswith(".csv"))
            return z.read(name).decode("utf-8")


def list_writeups(competition: str) -> list[Writeup]:
    from kagglesdk import KaggleClient
    from kagglesdk.competitions.types.hackathon_api_service import ApiListHackathonWriteUpsRequest

    out: list[Writeup] = []
    token = ""
    with KaggleClient(api_token=_token()) as client:
        while True:
            req = ApiListHackathonWriteUpsRequest()
            req.competition_name = competition
            req.page_size = 100
            if token:
                req.page_token = token
            resp = client.competitions.hackathon_api_client.list_hackathon_write_ups(req)
            page = type(resp).to_dict(resp)
            for item in page.get("hackathonWriteUps") or []:
                w = writeup_from_dict(item)
                if w is not None:
                    out.append(w)
            token = page.get("nextPageToken") or ""
            if not token:
                return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=Path("paper_track_scores.csv"))
    p.add_argument("--leaderboard-csv", type=Path, help="use a downloaded leaderboard CSV instead of fetching it")
    args = p.parse_args(argv)

    taken_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    text = args.leaderboard_csv.read_text(encoding="utf-8") if args.leaderboard_csv else download_leaderboard(MAIN)
    teams = parse_leaderboard(text)
    writeups = list_writeups(PAPER)
    rows = build_rows(writeups, teams, taken_at)

    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    matched = sum(1 for r in rows if r["main_lb_team"])
    print(f"{len(teams)} leaderboard teams, {len(rows)} writeups, {matched} matched to a team -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
