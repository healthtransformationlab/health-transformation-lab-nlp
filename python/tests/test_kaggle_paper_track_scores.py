"""Issue #731 (spec 028): each Paper Track writeup's main-leaderboard score, matched by Kaggle username.

Everything here runs on tiny in-memory inputs; nothing calls Kaggle."""
import csv
import importlib.util
import sys

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("paper_track_scores", REPO_ROOT / "kaggle" / "paper_track_scores.py")
pts = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = pts  # dataclasses look their module up while the class is built
_spec.loader.exec_module(pts)

LEADERBOARD = (
    "\ufeffRank,TeamId,TeamName,LastSubmissionDate,Score,SubmissionCount,TeamMemberUserNames\n"
    '1,11,"Team One","2026-11-10 08:00:00",0.29,18,alice\n'
    '7,17,"Two People","2026-11-12 03:45:13",0.24,8,"Bob, carol"\n'
    '40,40,"Carol Solo","2026-11-01 01:00:00",0.20,3,carol\n'
)


def item(wid, team_users=(), collab_users=(), state="PUBLISHED", authors="Some Author"):
    return {
        "id": wid,
        "team": {"teamMembers": [{"userName": u} for u in team_users]} if team_users else None,
        "writeUp": {
            "title": f"Writeup {wid}",
            "url": f"/competitions/gemma-4-developer-agent-paper/writeups/w{wid}",
            "contentState": state,
            "authors": authors,
            "collaborators": [{"userName": u} for u in collab_users],
        },
    }


def test_parse_leaderboard_reads_the_bom_and_lowercases_usernames():
    teams = pts.parse_leaderboard(LEADERBOARD)
    assert [t.rank for t in teams] == [1, 7, 40]
    assert teams[0].name == "Team One" and teams[0].score == "0.29" and teams[0].entries == "18"
    assert teams[1].usernames == frozenset({"bob", "carol"})


def test_writeup_takes_usernames_from_team_and_collaborators_once():
    w = pts.writeup_from_dict(item(5, team_users=("Alice",), collab_users=("alice", "Dave")))
    assert w.usernames == ("alice", "dave")
    assert w.url == "https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups/w5"


def test_unpublished_writeup_is_skipped():
    assert pts.writeup_from_dict(item(6, collab_users=("alice",), state="DRAFT")) is None


def test_match_picks_the_best_ranked_team_and_none_when_no_author_has_one():
    teams = pts.parse_leaderboard(LEADERBOARD)
    rows = pts.build_rows(
        [
            pts.writeup_from_dict(item(1, collab_users=("carol",))),
            pts.writeup_from_dict(item(2, collab_users=("zed",))),
            pts.writeup_from_dict(item(3, team_users=("dave",), collab_users=("ALICE",))),
        ],
        teams,
        "2026-11-15 00:03 UTC",
    )
    by_id = {r["writeup_id"]: r for r in rows}
    # carol is on rank 7 and rank 40: the better rank wins.
    assert (by_id["1"]["main_lb_team"], by_id["1"]["main_lb_rank"], by_id["1"]["matched_on"]) == ("Two People", "7", "carol")
    assert by_id["3"]["main_lb_score"] == "0.29" and by_id["3"]["matched_on"] == "alice"


def test_unmatched_writeup_keeps_empty_cells_and_every_row_is_stamped():
    rows = pts.build_rows(
        [pts.writeup_from_dict(item(2, collab_users=("zed",)))], pts.parse_leaderboard(LEADERBOARD), "T"
    )
    (row,) = rows
    for col in ("main_lb_team", "main_lb_rank", "main_lb_score", "main_lb_entries", "main_lb_last_submission",
                "matched_on"):
        assert row[col] == "", col
    assert row["leaderboard_taken_at"] == "T"
    assert list(row) == pts.COLUMNS


def test_main_writes_the_csv_from_a_downloaded_leaderboard(tmp_path, monkeypatch):
    lb = tmp_path / "lb.csv"
    lb.write_text(LEADERBOARD, encoding="utf-8")
    monkeypatch.setattr(pts, "list_writeups", lambda _c: [pts.writeup_from_dict(item(9, collab_users=("bob",)))])
    out = tmp_path / "out.csv"
    assert pts.main(["--leaderboard-csv", str(lb), "--out", str(out)]) == 0
    (row,) = list(csv.DictReader(out.open(encoding="utf-8")))
    assert row["writeup_id"] == "9" and row["main_lb_team"] == "Two People" and row["main_lb_rank"] == "7"
