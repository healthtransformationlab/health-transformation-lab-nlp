# PR 685 review: the tasks dataset's listing does not name a competition in its subtitle (#684)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `chore/684-028-tasks-subtitle`, `Closes #684`; a one-line change with a test, so no spec | ok |
| The owner asked for it and approved the change and the refresh of the listing on November 11, 2026 ("Approved"). A pull request that publishes outside the repository waits for the owner's word (AGENTS.md "Branches and issues", 6): given | ok |
| Test first: `test_the_listing_names_no_competition_in_its_title_subtitle_or_tags` failed on the old subtitle (on "gemma") and passes with the new one | ok |
| The new subtitle is 48 characters, within Kaggle's 20 to 80; the three tags stay, as "Publishing datasets" requires at least three | ok |
| The card is unchanged and still says which layout the files follow and which evaluator verified them; the paper cites the dataset for that | ok |
| `metadata_only` in `kaggle/publish_tasks.py` sends the title, subtitle, tags, card, cover, sources and update frequency of the live files: no build and no new version (spec 034) | ok |
| `pytest -q tests/test_kaggle_publish_tasks.py tests/test_kaggle_dataset_docs.py tests/test_wording.py tests/test_no_org_references.py`: 68 passed | ok |
| The listing changes only when the metadata is sent after the merge; the live subtitle, file list and version are read back then | note |

Nothing blocking.

## Notes
- The repository's description on GitHub also names the competition's track. No tool in a cloud session edits a
  repository's About box, so the owner changes that by hand.
- This makes the listing harder to find by a search for the competition's name. It does not hide it: the paper
  and the Writeup link to it, and the Paper Track requires public code and data.
