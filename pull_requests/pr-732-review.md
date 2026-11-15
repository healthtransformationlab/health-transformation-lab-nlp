---
pr: 732
branch: chore/731-028-paper-track-scores
title: "028 CHORE1: refresh each Paper Track writeup's main-leaderboard score from Kaggle"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator (one new script and its tests; each point traced in the code, the tests run, and the script run live)
verdict: approve
---

# PR Review: 028 CHORE1: refresh each Paper Track writeup's main-leaderboard score from Kaggle

## Summary

The PR adds `kaggle/paper_track_scores.py`. It matches every published Paper Track writeup to a team on the main
leaderboard by its authors' Kaggle usernames and writes one CSV row per writeup. A live run on 2026-11-15 matched 840
of 1,494 writeups, against 825 in the old Nov 13 copy, and the spot checks agree with that copy. Verdict:
**approve**.

## Scope of Change

- Files changed: 4 (+330 / -0)
  - `kaggle/paper_track_scores.py`
  - `kaggle/README.md`
  - `python/tests/test_kaggle_paper_track_scores.py`
  - this review
- Areas touched: kaggle, python tests, docs
- Commits: the script commit and the review commit
- Range reviewed: `origin/main..HEAD`

## CI Status

| Check | Status |
|---|---|
| Tests, PR conventions | running at the time of writing. The branch `chore/731-…` and `Closes #731` meet the rule, and #731 has all four parts |

## Secrets, PHI and Claims Scan

- **Secrets:** clean. The token is read from the environment and never printed or written.
- **PHI:** none. No clinical data is involved.
- **Claims:** every number in the PR comes from the live run.
- **Third-party data:** the CSV holds other entrants' public leaderboard rows, so it is not committed.

## Strengths

- **The match is exact.** It compares Kaggle usernames, not display names, so "Luis Specian" and "LuisSpecian"
  can't be confused, and an unmatched writeup keeps empty cells.
- **The code is easy to test.** Parsing, matching and building the rows are pure functions, tested on in-memory
  inputs. The Kaggle calls sit in two small functions.
- **Each refresh is dated.** Every row carries `leaderboard_taken_at`, which matters because the public
  leaderboard is scored on half the test data.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- **Fixed in the review commit: the README didn't say what to install.** It now says `pip install "kaggle>=2.2"`.
  That package provides `kagglesdk`, which lists the writeups. Like the other `kaggle/` scripts, it isn't a
  dependency in `python/pyproject.toml`.
- **Open: the team is matched per author, not per writeup.**
  - What: if two co-authors are on different leaderboard teams, the better-ranked team is shown, and `matched_on`
    names the username that matched.
  - Status: acceptable for a sheet of scores.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first, four parts | ✅ | #731 |
| Branch and `Closes` | ✅ | |
| Test first | ✅ | 6 tests cover every "Done when" line |
| Synthetic only / no PHI | ✅ | |
| Secrets | ✅ | Uses the existing Kaggle token (`ops/secrets_register.yaml`); no new credential |
| Wording, org names, bench order | ✅ | The repo-wide tests pass |
| Publishing or compute that needs the owner's say | n/a | Read-only calls to Kaggle |

## Test Coverage

- `pytest tests/test_kaggle_paper_track_scores.py`: 6 passed.
- `test_wording`, `test_no_org_references`, `test_bench_order`, `test_model_inventory`, `test_telemetry_calls` and
  `test_telemetry_scripts`: pass.
- `ruff check`: clean.
- Live: `python kaggle/paper_track_scores.py` matched 840 of 1,494 writeups to the 5,739 teams.

## Verdict

**approve.** Merge once the checks are green.
