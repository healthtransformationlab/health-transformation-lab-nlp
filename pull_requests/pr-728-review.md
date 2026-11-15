---
pr: 728
branch: feat/709-039-release-tags
title: "039 US3: one version string carried to Kaggle, Hugging Face and a release tag"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator
verdict: approve
---

# PR Review: 039 US3: one version string carried to Kaggle, Hugging Face and a release tag

## Summary

A published version now carries one release string, built from the dataset's declaration (#707), as both Kaggle's
version note and Hugging Face's commit message. With `--tag`, each release is marked `data/<slug>-vX.Y.Z` in git and
on Hugging Face, and tagging twice changes nothing. The publish workflows tag every new version, but not a
metadata-only refresh. Their publishing jobs get `contents: write` to push the tag. Closes #709. Approve.

## Scope of Change

- Files changed: 12:
  - `dataset_version.py`
  - the three publishing scripts and the two publish workflows
  - two READMEs, `ops/secrets_register.yaml`
  - new `test_dataset_release.py`, and one updated test in `test_kaggle_publish_tasks.py`
  - `tasks.md`
- Areas touched: publishing code and workflows (run by hand only), the package, tests, the secrets register's
  description of one token.

## CI Status

To be read on the PR's latest commit before merging.

## Findings

None blocking, none to fix. Notes:

- **Settings.** Three jobs go from `contents: read` to `contents: write`. They run only by `workflow_dispatch`, in the
  `dev` environment, and the only write is `git push origin refs/tags/data/<slug>-vX.Y.Z`. No secret or variable
  changes. The Hugging Face token's write-contents permission already covers tags, as the register now says.
- **Idempotence.** `create_git_tag` asks the remote first. When both publishing jobs tag the same version at once,
  both push a lightweight tag on the same commit, and the second push is a no-op. A remote that already holds the tag
  on another commit is left alone: the version was released there first. Republishing changed files under an old
  version number would mean it was never bumped, and #707's gate stops that for schema changes. Hugging Face tagging
  checks the repo's tags, then creates with `exist_ok=True`.
- **The tag name.** `data/<slug>-vX.Y.Z` is a valid git ref (a test runs `git check-ref-format`). On Hugging Face, its
  URL encodes the slash (`data%2F...`). Whether Hugging Face accepts the name itself is learned on the first tagged
  publish. A refusal there would fail that run loudly after the upload, never silently.
- **Option checks.** `--tag` is refused before any build where no version is made: without `--upload`, with
  `--metadata-only`, or for the organisation page (AGENTS.md, "Check settings before doing work"). The test makes
  sure the refusal comes from these checks, not from an unknown option.
- **`--message`.** It goes from the Kaggle scripts, because the release string replaces it, and stays only for the
  organisation page, so a dataset version can't carry a different note.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue and branch | Yes | `feat/709-039-...`; `Closes #709`; spec 039 names #709 |
| Spec before code | Yes | `specs/039-dataset-versioning/` on `main` |
| Test first | Yes | All 21 new tests failed before the change |
| Settings change by pull request | Yes | The PR names the three jobs whose permissions change, and says no environment changes |
| Secrets register | Yes | `HF_PUBLISH_TOKEN`'s entry says it also tags; scope and expiry unchanged |
| Publishing | Yes | Merging publishes nothing; both workflows are `workflow_dispatch` only |
| Changes to these rules | None | `AGENTS.md` untouched (#722 holds the rule line) |

## Verdict

Approve, and merge when every check is green on the latest commit.
