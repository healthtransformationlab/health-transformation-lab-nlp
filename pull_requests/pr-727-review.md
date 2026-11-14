---
pr: 727
branch: feat/708-039-dataset-manifest
title: "039 US2: provenance shipped inside every published dataset"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator
verdict: approve
---

# PR Review: 039 US2: provenance shipped inside every published dataset

## Summary

Every build now writes `manifest.json` into the dataset from the files it holds: the slug, the version from #707,
the git commit, the build time, and each file's SHA-256, size and row count. One builder serves the Kaggle notes,
results and task-set builds and both Hugging Face builds, and every card points to it. The new file is described, so
each dataset goes to 1.1.0 under #707's rule. Closes #708. Approve.

## Scope of Change

- Files changed: 12:
  - `dataset_version.py` (`build_manifest`, `write_manifest`, the constants)
  - the three builders: `kaggle/publish.py`, `kaggle/publish_tasks.py`, `huggingface/publish.py`
  - `kaggle/dataset_docs.yaml` (`manifest.json` described, versions 1.1.0), `kaggle/README.md`
  - new `test_dataset_manifest.py`, and the four builder test files
  - `tasks.md`
- Areas touched: publishing code (not run by merging), the package, tests, a spec's task list. No data value, metric
  or label rule.

## CI Status

To be read on the PR's latest commit before merging.

## Findings

None blocking, none to fix. Notes:

- **The manifest can't drift from the files.** It's built from the staged folder after every data file is copied, in
  all three builders. The Kaggle builds describe it with its real path, so the usability check sees it.
- **Row counts.** CSV rows are counted as records with `csv.reader`, so a note with a quoted line break counts once.
  JSONL counts non-blank lines. A test covers both.
- **The commit check.** The workflows pass `--commit ${{ github.sha }}`, a full SHA. Short SHAs are accepted, as the
  existing build tests pass `abc1234`. Anything that isn't hex fails at once, before any hashing (AGENTS.md, "Check
  settings before doing work").
- **The version bump was required, not optional.** #707's gate fails when a published file appears without a new
  version, and this PR is its first real use.
- **Kaggle's own `dataset-metadata.json`** is written after the manifest and never listed in it. It's Kaggle's upload
  metadata, not data.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue and branch | Yes | `feat/708-039-...`; `Closes #708`; spec 039 names #708 |
| Spec before code | Yes | `specs/039-dataset-versioning/` on `main` |
| Test first | Yes | The new tests failed before the change; the builder tests failed until the builds wrote the manifest |
| Telemetry | Yes | `build_manifest` and `write_manifest` are `@traced`; no row-level data reaches a span |
| Publishing datasets | Yes | Every published file (now including `manifest.json`) is described; nothing is published by merging |
| Changes to these rules | None | `AGENTS.md` untouched |

## Verdict

Approve, and merge when every check is green on the latest commit.
