# PR #603 review: wait for a new Kaggle version before its metadata; shorten the task-set kernel title

Closes #602. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict
Nothing blocking.

## Checks
- **Root cause, not a retry loop on errors:** right after a new version, Kaggle lists the old version's files. The fix
  waits on the listing, not on the error, and then describes only what's live. So a slow version leaves one file
  undescribed until the next publish; it no longer fails the run.
- **Bounded:** at most 40 × 15 s (10 minutes), well inside the job timeout.
- **Kernel title:** `coding agent tasks quickstart`, 29 characters. The slug matches the title, as `JOBS` requires.
  The workflow polls that slug; a test checks it.
- **Tests first:** the two upload tests and the title test failed before the change and pass after it.
  `FakeApi` in `test_kaggle_dataset_docs.py` now lists the folder's files.
- **Rules:** no data, label, metric or schema change, so no spec is needed. No secrets. Wording and bench order
  are unaffected.

## Not blocking
- `publish_tasks.py --metadata-only` already filters to live files; it shares `metadata_only`.
