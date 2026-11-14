---
pr: 724
branch: feat/707-039-dataset-version
title: "039 US1: one declared semantic version and changelog per dataset, enforced by CI"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator
verdict: approve
---

# PR Review: 039 US1: one declared semantic version and changelog per dataset, enforced by CI

## Summary

Each published dataset now declares `version`, `changelog` and `schema_sha256` in `kaggle/dataset_docs.yaml`. A new
`dataset_version` module reads and checks the declaration. A gate in `test_kaggle_dataset_docs.py` hashes what each
dataset publishes, its files and their columns, and fails when that changes without a new version, giving the semver
rule. Closes #707. The `AGENTS.md` line is left to #722. Approve.

## Scope of Change

- Files changed: 7:
  - `kaggle/dataset_docs.yaml` (3 entries and a header note), `kaggle/dataset_docs.py` (`schema_sha256`),
    `kaggle/README.md`
  - new `python/health_transformation_lab_nlp/dataset_version.py`
  - new `python/tests/test_dataset_version.py`, gate tests added to `python/tests/test_kaggle_dataset_docs.py`
  - `specs/039-dataset-versioning/tasks.md` (T001–T004 checked)
- Areas touched: Kaggle publishing metadata (read-only here), the package, tests, a spec's task list. No data value,
  no metric, no label rule.

## CI Status

To be read on the PR's latest commit before merging.

## Findings

None blocking, none to fix. Notes:

- **What the gate can and can't catch.** The hash goes stale whenever a published file or column changes, so the
  change can't land without a new hash, and the failure asks for the version bump and changelog line in the same
  diff. A contributor could still paste the new hash without bumping the version. A check that needs no history
  can't stop that (a review of the diff does), and it's the same trust model as `missing()`, which a placeholder
  description also satisfies.
- **What the hash covers.** Column order and a second file of an already-described kind don't count. Both follow the
  semver rule: neither is a removed, renamed, retyped or new column. Files are keyed by the pattern that describes
  them, so builds whose names carry a commit hash (the task set's graphs and embeddings) hash the same.
- **The task set's hash comes from stand-ins.** It's taken from the same stand-in files the existing docs test
  builds, because the real built files are git-ignored. So it follows the committed CSVs and the sample row's columns.
  This matches how that dataset is already checked.
- **No new names left undeclared.** `schema_sha256`, `problems`, the `docs=` keyword and the hash helper are on the
  issue as a dated line from before the first commit.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue and branch | Yes | `feat/707-039-...`; `Closes #707`; spec 039 names #707 and its plan is in the branch |
| Spec before code | Yes | `specs/039-dataset-versioning/` (spec, plan, tasks) is on `main` |
| Test first | Yes | The tests failed before the change and pass after |
| Telemetry | Yes | Every public function in the new module is `@traced`; the traced-functions test passes |
| Publishing datasets | Yes | Nothing is published; the new keys aren't sent to Kaggle until US3 |
| Changes to these rules | None | `AGENTS.md` untouched; T005 moved to #722 |
| Words and names | Yes | Wording, benchmark-order and organisation-name tests pass |

## Verdict

Approve, and merge when every check is green on the latest commit.
