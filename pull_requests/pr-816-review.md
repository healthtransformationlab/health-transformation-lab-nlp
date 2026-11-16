---
pr: 816
branch: fix/815-028-new-dataset-403
title: "028 BUG1: a 403 for a dataset its owner does not have is a fresh start"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-15
reviewer: a read-only reviewer subagent over the first commit (rubric step 3), which read kaggle 2.2.5's installed source; each finding then checked by the authoring session against that source and against Kaggle's live listing, read-only, before acting on it (step 4)
verdict: approve (after the second commit; the first had one blocking finding)
---

# PR Review: 028 BUG1: a 403 for a dataset its owner does not have is a fresh start

## Summary
The Modal trial stopped before any work. Kaggle answered 403, not 404, for its new private results dataset, and the
shared helper read anything but a 404 as "cannot tell" (#691, item 3). The first commit read a 403 through the
owner's dataset list.

The reviewer found:

- **one blocking finding:** a token of another account could read an existing dataset as missing;
- **three Should-fix findings:** only page one was read; an empty answer read as "not there"; the fake client built
  in the assumption at risk.

The second commit fixes all four, with tests. Nothing blocking remains. Merging starts no run.

## Scans
- **Secrets:** none. **PHI / real data:** none. **Organization claims:** none.

## What Kaggle does (checked)
kaggle 2.2.5's installed source:

- `dataset_list` reads one page of 20 and returns `None` for an empty answer;
- `mine=True` lists the token owner's own datasets;
- `get_config_value("username")` is the token's user, checked with Kaggle for an access token.

Kaggle's live listing, read-only, from the agent session:

- the token's user is `jcblearning`;
- a search for an existing private dataset's exact slug returns it;
- a search for the trial's missing results dataset returns an empty list;
- the search matches loosely: `colab-graph` matched three datasets;
- `mine` pages of 20 do not overlap.

## Findings and what was done
| # | Severity | Finding | Checked by | Outcome |
|---|---|---|---|---|
| 1 | 🔴 Blocking | Nothing tied the token to the dataset's owner. If `KAGGLE_USERNAME` and the token named different accounts, the listing could not see the owner's private datasets. An existing dataset would then read as missing, and the run would start fresh over it. | `KAGGLE_USERNAME` and the token are separate secrets; the source's `_introspect_token` | Fixed. `listed_as_own` answers only when `get_config_value("username")` is the owner (case ignored), and lists with `mine=True`. Any other token answers None, so the run stops as before. Test. |
| 2 | 🟡 Should fix | Only page one (20 rows) was read, and the search matches loosely, so an existing dataset could sit past it. | the source's paging; the live loose match | Fixed. Every page is read until a short one. Past `LISTING_PAGES` (25), the answer is None. Tests: a match on page two, and a listing longer than the cap. |
| 3 | 🟡 Should fix | `dataset_list` returns None for an empty answer, and `or []` read that as "not there". A change in the ref's form could also make every check False. | the source | Fixed. A None answer is None, and a ref with no `/` is None. Tests. (An empty list, which is what Kaggle returns for a search with no match, still means "not there": that is the trial's case.) |
| 4 | 🟡 Should fix | The fake matched by substring on one unpaged list. Dropping `.lower()`, or stopping without trying again, passed the tests. | the reviewer's mutations | Fixed. The fake now pages by 20, has a token user and can give odd answers. The test asserts three status calls before stopping. Seven mutations were tried; six fail a test. The survivor, dropping the `found is None` check, behaves the same: iterating None raises, and the `except` answers None. |
| 5 | ✅ | The existing failed-status test still holds: a 500, a 401 and a network error stop the run. | ran | No change. |
| 6 | 🔵 Note | `upload()` uses the same check. A wrong "missing" there leads to `dataset_create_new`, which Kaggle refuses for a name that is taken. The run's results would then stay only on the machine. | read | With findings 1 to 3 fixed, a wrong "missing" needs a full listing from the owner's own token that leaves out a dataset it has. |

## Compliance
| Rule | Result |
|---|---|
| Test first | The regression test failed before each commit's fix and passes after. |
| A small fix gets an issue and a regression test, no spec | #815, with its four parts. |
| Failures stop a run rather than guess (#691, item 3) | Kept: anything short of a full answer from the owner's own token stops the run. |
| Wording, organization names | Their tests pass. |

## Checks
- `tests/test_colab_official.py` and `tests/test_modal_official.py`: 101 passed.
- Whole suite on the second commit, `pytest -q -n auto tests`: 2,829 passed, 37 skipped.
- `ruff check` on the two files: the same five findings as on `main` (none from this change).

## Should fix
- Nothing before merge.

## Secrets, Real Data and Claims Scan
Secrets: none. Real data: none. Claims: none.
