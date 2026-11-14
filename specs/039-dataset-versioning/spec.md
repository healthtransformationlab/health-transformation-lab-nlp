# Feature Specification: Versioned dataset releases for Kaggle and Hugging Face

**Feature Branch**: `spec/706-039-dataset-versioning` (spec); one `feat` branch per user story

**Created**: 2026-11-14

**Status**: draft

**Input**: the owner asked, "How can we version these datasets better for when we publish to Kaggle and Hugging Face."

Today each dataset is published with no real version. `kaggle/publish.py` calls `dataset_create_version(folder,
message, dir_mode="zip")`, where `message` is free text; Kaggle auto-increments its own version number.
`huggingface/publish.py` calls `upload_folder(..., commit_message=message)` with an optional `--commit <sha>`. So:

- there is no semantic version a person can reason about (what changed from 1.2.0 to 1.3.0);
- there is no changelog — Kaggle's version note and HF's commit message are set independently and can say different
  things, or nothing;
- a downloaded dataset carries no provenance: nothing ties the files to the commit, code and inputs that built them;
- a schema change (a column removed or retyped) can ship silently, because only descriptions are checked today
  (`test_kaggle_dataset_docs.py`), not whether the data changed without a version bump.

This is the same gap spec 038 closed for the gold model: one declaration, generated artefacts, and CI that fails on
drift. Datasets need the companion rule — a declared version with a changelog, provenance baked into the data, and one
version string carried to both platforms and to a release tag.

> Personal learning project; synthetic data only (and the published, CC BY 4.0 third-party sets). Versioning changes
> how a dataset is released and described; it adds no rows and changes no values.

## Why now

- We publish to two platforms whose own versioning differs; without one declared version they drift.
- The data contracts (spec 038) pin a table's shape at `version: 1.0.0` but leave "a version bump rule" explicitly out
  of scope. A dataset-version rule is that companion: a schema change bumps the contract version and the dataset
  version together.
- Issue #649 (tag every repository at the contest submission) needs the same tagging machinery.

## Datasets in scope

| Dataset | Published by | Platforms |
|---|---|---|
| `perio-bench-notes` | `kaggle/publish.py`, `huggingface/publish.py` | Kaggle, Hugging Face |
| `perio-bench-results` | `kaggle/publish.py`, `huggingface/publish.py` | Kaggle, Hugging Face |
| `health-transformation-lab-coding-agent-tasks` | `kaggle/publish_tasks.py` | Kaggle |
| the published encoder model | `kaggle/publish_model.py` | Kaggle (model, not dataset) |

The model keeps Kaggle's model-instance versioning; it adopts US1's changelog and US2's manifest, not the dataset tag.

## User stories

### US1 - One declared semantic version and changelog per dataset, enforced by CI (P1) #707

- Each dataset in `kaggle/dataset_docs.yaml` gains `version: "MAJOR.MINOR.PATCH"` and `changelog:`, a list of
  `"X.Y.Z — what changed"` lines, newest first, whose top line's version equals `version`.
- `health_transformation_lab_nlp.dataset_version` exposes `version(slug)`, `changelog(slug)` and `latest_change(slug)`,
  every public function `@traced`.
- Semver rule, documented in `dataset_docs.yaml` and the module: MAJOR a breaking schema change (a column removed,
  renamed or retyped, or a file removed), MINOR a new file or column, PATCH a value, row or fix with no schema change.
- `python/tests/test_dataset_version.py` fails when a dataset has no version, an invalid version, a `version` that
  doesn't match the top changelog line, or a published file/column set that changed (the set
  `test_kaggle_dataset_docs.py` already derives) without the version being bumped and a changelog line added.

### US2 - Provenance shipped inside every published dataset (P1) #708

- Every published dataset folder carries `manifest.json`: `slug`, `version`, `git_commit_sha`, `built_ts` (UTC ISO
  8601), and `files` — each published path mapped to `{sha256, bytes}` plus `row_count` for `.csv` and `.jsonl`.
- The manifest is built from the files actually being published, so it cannot drift from them.
- One builder writes it for both platforms: `build_manifest(folder, slug, commit)` and `write_manifest(folder, slug,
  commit)` in `dataset_version`, both `@traced`; `kaggle/publish.py`, `kaggle/publish_tasks.py` and
  `huggingface/publish.py` call `write_manifest` before upload.
- `python/tests/test_dataset_manifest.py` builds a manifest for a sample folder and checks every file is listed with a
  correct SHA-256, correct bytes, a `row_count` for tabular files only, and `git_commit_sha` equal to the current
  commit.

### US3 - One version string carried to Kaggle, Hugging Face and a release tag (P2) #709

- `release_message(slug, commit)` returns `v<MAJOR.MINOR.PATCH> — <latest changelog line> (<commit short sha>)`, used
  verbatim as the Kaggle `dataset_create_version` note and the Hugging Face commit message.
- On a release, a git tag `data/<slug>-vX.Y.Z` is created on the commit, and a Hugging Face revision tag of the same
  name on the dataset repo (`HfApi.create_tag`).
- `--metadata-only` refreshes metadata with no new version and no tag. Re-tagging an existing version is a no-op, not an
  error. The publish log prints the release string and both tag URLs.
- `python/tests/test_dataset_release.py` checks the message is identical on both platforms, the tag name is well-formed,
  and re-tagging is a no-op (the Kaggle and HF clients are mocked; no network).

## Success criteria

- A reader of a published dataset can read its `manifest.json`, see the exact commit and version, and verify every file
  by SHA-256.
- Changing a published file or column without bumping the version and adding a changelog line fails CI.
- The Kaggle version note, the HF commit message, the git tag and the HF tag for one release all carry the same
  `vX.Y.Z`.
- Re-running a publish with no change (or `--metadata-only`) makes no new version and no duplicate tag.

## Out of scope

- Changing any dataset's rows, columns or values. This spec adds version, changelog, manifest and tags only; the first
  publish under it sets each dataset's starting version from its current state (a PATCH, no data change).
- Deciding the data-contract version-bump rule (spec 038) beyond stating that a schema change bumps both together.
- Automatic semver inference. A person (or the agent) chooses MAJOR/MINOR/PATCH and writes the changelog line; CI only
  checks that a change carries a bump.
- Kaggle's own version numbers (it keeps auto-incrementing); our semver lives in the note, the manifest and the tag.
- Publishing cadence or new datasets; `update_frequency` stays as it is.
- Re-publishing historical versions with back-filled manifests; versioning starts at the next publish.

## Risks

- Kaggle may drop or alter the version note (as it drops column descriptions, #694): the manifest inside the data and
  the git/HF tags are the durable record, so the note is a convenience, not the source of truth.
- HF tagging needs a write-scoped token (`HF_PUBLISH_TOKEN`); `ops/secrets_register.yaml` already records it.
