# Implementation plan: Versioned dataset releases (spec 039)

## Sources of truth

- `kaggle/dataset_docs.yaml` stays the one place a dataset is described. It gains `version` and `changelog` per
  dataset, beside the `files`/`columns`/`update_frequency` it already holds. No second registry.
- The version, changelog, manifest and release string are all read from that one declaration, as the contracts are
  read from the gold model (spec 038).
- Git is the source of `git_commit_sha`; the manifest is built from the files being published, never hand-written.

## Names (copied to the issues)

- Module `health_transformation_lab_nlp.dataset_version`, every public function `@traced`:
  - `version(slug: str) -> str` — the dataset's semver from `dataset_docs.yaml`
  - `changelog(slug: str) -> list[str]` — newest first
  - `latest_change(slug: str) -> str` — the newest changelog line
  - `build_manifest(folder: Path, slug: str, commit: str) -> dict`
  - `write_manifest(folder: Path, slug: str, commit: str) -> Path` — writes `folder/manifest.json`
  - `release_message(slug: str, commit: str) -> str` — `v<X.Y.Z> — <latest_change> (<commit[:12]>)`
  - `release_tag(slug: str) -> str` — `data/<slug>-v<X.Y.Z>`
- `manifest.json` shape: `{slug, version, git_commit_sha, built_ts, files: {path: {sha256, bytes, row_count?}}}`.
  `row_count` only for `.csv` (header excluded) and `.jsonl` (non-blank lines).
- Tests: `python/tests/test_dataset_version.py`, `test_dataset_manifest.py`, `test_dataset_release.py`.
- Touched: `kaggle/publish.py`, `kaggle/publish_tasks.py`, `kaggle/publish_model.py` (changelog + manifest only),
  `huggingface/publish.py` (`--tag`), `kaggle/dataset_docs.yaml`, AGENTS.md "Publishing datasets".

## How the pieces fit

1. **US1 (declare + gate).** Add `version`/`changelog` to each dataset in `dataset_docs.yaml`. Set each one's starting
   version from its current published state (`1.0.0`, changelog line "1.0.0 — first versioned release"). The CI gate
   extends `test_kaggle_dataset_docs.py`'s existing file/column derivation: it already knows each dataset's published
   file and column set; store a hash of that set beside the version, and fail when the hash changes but the version
   didn't (with the semver rule in the message). This reuses the one place that already walks the published surface.
2. **US2 (manifest).** `build_manifest` walks the publish folder (the files `files_of`/the tasks builder already stage)
   and hashes each. `write_manifest` drops `manifest.json` into the folder before `dir_mode="zip"` upload, so it ships
   inside the dataset on both platforms. `git_commit_sha` comes from the caller (the workflow passes `--commit`, as HF
   already does); locally, `git rev-parse HEAD`.
3. **US3 (one string + tags).** `release_message` builds the note from US1. `kaggle/publish.py` passes it to
   `dataset_create_version`; `huggingface/publish.py` passes it as `commit_message`. After a successful upload (not
   `--metadata-only`), create the git tag `data/<slug>-vX.Y.Z` (skip if it exists) and, for HF, `HfApi.create_tag`
   (catch "already exists" and treat as a no-op). Print both URLs.

## Tests first (each story)

- `test_dataset_version.py`: a dataset with no/invalid version fails; `version` not matching the top changelog line
  fails; a changed published file/column set with no bump fails; a clean set passes. Uses a small fixture docs file.
- `test_dataset_manifest.py`: build over a temp folder with a CSV, a JSONL and a binary; assert every file hashed, bytes
  correct, `row_count` only on the two tabular files, and `git_commit_sha` equals `git rev-parse HEAD`.
- `test_dataset_release.py`: `release_message` identical for the Kaggle and HF call paths (both read the same function);
  `release_tag` well-formed; mocked clients show re-tagging an existing tag makes no second create.

## Idempotence and safety

- A second publish with no change: the file/column hash is unchanged, so no version bump is required; the manifest is
  byte-identical except `built_ts`, so (option) exclude `built_ts` from the zip-equality check or accept a new version
  only when the content hash changes. Decision: the manifest records `built_ts` but the US1 gate keys on the content
  hash, not the manifest, so rebuilding alone never forces a bump.
- Tagging is idempotent (skip-if-exists) on both platforms.
- No secret is printed; HF tagging uses the existing `HF_PUBLISH_TOKEN` (write scope already recorded in
  `ops/secrets_register.yaml`). No new credential.

## Out of scope (from spec.md)

No data values change; no automatic semver inference; Kaggle's own version numbers are left as they are; historical
versions are not back-filled.
