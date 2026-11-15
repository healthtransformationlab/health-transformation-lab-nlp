---
pr: 733
branch: feat/730-039-model-changelog-manifest
title: "039 AI2: the published Kaggle model adopts the changelog and the manifest"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: 039 AI2: the published Kaggle model adopts the changelog and the manifest

## Summary

The encoder model now gets a declared version and changelog (`models:` in `kaggle/dataset_docs.yaml`), a release
string as its Kaggle instance-version note, and a `manifest.json` in its folder. That is what spec 039 says the model
adopts. As the spec says, it gets no tag. Closes #730, the last open sub-issue of epic #706 apart from #722 (the
`AGENTS.md` line, waiting for the owner). Approve.

## Scope of Change

- Files changed: 8:
  - `dataset_version.py` (`models` lookup, `NOT_DATA`)
  - `kaggle/dataset_docs.yaml` (`models:`), `kaggle/publish_model.py`
  - `.github/workflows/kaggle-encoders.yml` (`--message` removed)
  - `kaggle/README.md`, `tasks.md`
  - `test_dataset_version.py`, `test_kaggle_model.py`
- Areas touched: model publishing (runs only after a full GPU run started by hand), the package, tests

## CI Status

To be read on the PR's latest commit before merging.

## Findings

None blocking, none to fix. Notes:

- **Dataset slugs win on a clash.** A slug is looked up under `datasets` first, then `models`. No slug is in both, and
  a model has no `schema_sha256`. The #707 gate passes a hash only for datasets, so a model's declaration is checked
  for its version and changelog alone.
- **The manifest.** It's written after the two Kaggle metadata files, and `NOT_DATA` leaves them out, as it leaves
  out `dataset-metadata.json`. A test compares the manifest with the folder's listing, minus those two files and
  itself.
- **What `--message` carried.** The note it built ("Trained on Kaggle by <run URL>") pointed to the publishing run.
  That URL is still in the workflow's job summary. The release string, like the datasets', names the version, the
  change and the trained commit.
- **The card.** It's unchanged, because `MANIFEST_NOTE` speaks of a dataset. The contract on #730 records this.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue and branch | Yes | `feat/730-039-...`; `Closes #730`; the contract was settled on the issue before the first commit |
| Test first | Yes | The 5 new tests failed before the change |
| Telemetry | Yes | No new public function; the changed ones stay `@traced` |
| Limited compute | Not started | Merging runs nothing; the encoder workflow is `workflow_dispatch` only |
| Changes to these rules | None | `AGENTS.md` untouched |

## Verdict

Approve, and merge when every check is green on the latest commit.
