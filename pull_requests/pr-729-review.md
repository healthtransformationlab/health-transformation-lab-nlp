---
pr: 729
branch: docs/722-039-agents-version-rule
title: "039 AI1: the dataset version rule in AGENTS.md, \"Publishing datasets\""
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve (merge on the owner's word: it changes AGENTS.md)
---

# PR Review: 039 AI1: the dataset version rule in AGENTS.md, "Publishing datasets"

## Summary

One bullet in `AGENTS.md`'s "Publishing datasets" states what #707 and #708 built:
- each dataset declares `version`, `changelog` and `schema_sha256`;
- the semver rule;
- a changed file or column needs its new version in the same pull request;
- every build ships `manifest.json`.

The closing line names the version check among what `test_kaggle_dataset_docs.py` enforces. T005 is checked off.
Closes #722. Approve. Under rule 6 it merges only on the owner's word.

## Scope of Change

- Files changed: 2: `AGENTS.md` (one bullet, one sentence), `specs/039-dataset-versioning/tasks.md` (T005)
- Areas touched: the agents' rules (read by every coding agent and by `CLAUDE.md`)

## Findings

None blocking, none to fix.
- **Accuracy:** the bullet matches the code on `main`. The keys and the rule are in `dataset_version.py`'s docstring
  and the head of `kaggle/dataset_docs.yaml`. The manifest is what `write_manifest` writes. The test it names is the
  one that fails.
- **Out of scope:** the release tag (#709) isn't mentioned: it's still a pull request. A line for it can follow once
  it merges.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue and branch | Yes | `docs/722-039-...`; `Closes #722` |
| Changes to these rules | Waits | Rule 6: the owner says "merge" |
| Words and names | Yes | Wording, benchmark-order and organisation-name tests pass |

## Verdict

Approve. Merge when the owner says so and every check is green.
