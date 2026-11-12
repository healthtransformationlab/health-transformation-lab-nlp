---
pr: 693
branch: fix/692-034-kaggle-angle-brackets
title: "034 BUG4: send Kaggle no text with an angle bracket"
author: jcbowyer
reviewed_at: 2026-11-12
reviewer: coordinator review of the diff against the rubric (no reviewer subagent: a six-file wording and guard change, reviewed line by line)
verdict: approve
---

# PR Review: 034 BUG4: send Kaggle no text with an angle bracket (#692)

Reviewed against `.claude/review-rubric.md` and AGENTS.md. Range: `526ea08..9c7f05a`.

## Summary

Kaggle keeps nothing after a `<` in a description. Two cards and three descriptions used placeholders written with
angle brackets, so the task set's page ended before its licence section and the first column of each of its
tabular files had no description. The placeholders are reworded, a test fails when one returns, and the publish
scripts refuse to write metadata that holds one.

## Scans

| Scan | Result |
|---|---|
| Secrets | none in the diff; the Kaggle token is read from the environment at run time and appears nowhere |
| PHI or real data | none; no data file changes |
| Organisation claims | none; `test_no_org_references.py` passes |

## Checks

| Check | Result |
|---|---|
| Branch `fix/692-034-kaggle-angle-brackets`, `Closes #692`; a wording fix with a guard and tests, so no spec | ok |
| The owner asked for it on November 12, 2026 ("Fix this and any other pending actions", on a photo of the dataset's pending action) and was told first that only descriptions change. A pull request that publishes outside the repository waits for the owner's word (AGENTS.md "Branches and issues", 6): given | ok |
| The cause is observed, not assumed, for the two cards: Kaggle's API returns 3,357 of the task set's 5,388 characters, ending at `` `<repo name>_<base_commit>` ``, and 1,070 characters of the results card, ending at `` `ai_predictions_<model>.csv` ``; the notes card, which has no angle bracket, comes back whole | ok |
| The cause is inferred for the pending action: Kaggle's API does not return column descriptions, and its site refuses an automated reader. `instance_id`, described with `<pr or commit>`, is the first column of all four tabular files, and the action opens the first of them by name. The owner's page is the check, after the refresh | note |
| Test first: `test_no_dataset_sends_text_kaggle_would_cut[results]` and `test_the_task_set_sends_no_text_kaggle_would_cut` failed on the texts as they were (one place in the results card; seven in the task set: the card, two file descriptions, four columns) and pass with the new wording | ok |
| The guard is at the one place every path writes metadata, `publish.write_metadata`, and runs before any file is written; `test_writing_the_metadata_refuses_text_kaggle_would_cut` checks that nothing is left on disk | ok |
| The new wording says what the old did. Task ids: 38 are `htlnlp_` and an issue's number, 34 `htlnlp_pr` and a pull request's number, 20 `htlnlp_` and eight characters of a commit, and one has both an issue's and a pull request's number, counted in the published `tasks.jsonl` | ok |
| "Publishing datasets": every file and column still has a description (`test_every_*_is_described` pass); the cards still say what the data is, that it is not affiliated and not for clinical use, and name the third-party files and licences, which Kaggle will now show in full | ok |
| `pytest -q tests/test_kaggle_dataset_docs.py tests/test_kaggle_publish_tasks.py tests/test_wording.py tests/test_no_org_references.py tests/test_bench_order.py`: 86 passed | ok |
| Python and R parity, seeds, paths, prices, deck figures, secrets register, alerts, table writes: not touched | n/a |
| Configuration: no setting changes. Environments: none on merge; the metadata of two public Kaggle datasets after it, by a metadata-only run (no new version) | ok |

| The corrected descriptions of the task set were sent from this branch's head (`2e8f6c0`) on November 12, 2026 at 19:40 UTC, before the merge, at the owner's request the same afternoon: the text sent is the text this pull request merges, and the commit named in the card is the one the live files were published from (`167daa2`, workflow run 42750573206). Read back: 5,419 characters where there were 3,357, ending with the "Published from commit" line and holding the licence section; version 4, 265 files and the last-updated time unchanged | ok |

Nothing blocking.

## Notes
- `ruff` reports the import order at the top of `test_kaggle_dataset_docs.py`. It is the same on `main` and is
  left alone here.
- A lone `>` is not refused: the cards use it for Markdown block quotes, and Kaggle shows those as intended.
- `perio-bench-notes` is also at 9.41 and its card comes back whole, so its one pending action has another cause.
  The owner's page shows which; it gets its own issue once known.
- `perio-bench-results` is not refreshed here. Five of its 38 live files have a name without the `+` the repository's
  name has (`ai_predictions_bert-basecw.csv` for `ai_predictions_bert-base+cw.csv`): Kaggle drops the character, so
  those files' descriptions are never matched. Its card will be sent again with that fixed, under its own issue.
- The issue was first filed as BUG1; BUG1 to BUG3 of spec 034 already existed, so it is BUG4.
