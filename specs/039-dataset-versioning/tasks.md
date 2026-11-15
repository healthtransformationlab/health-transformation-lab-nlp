# Tasks: Versioned dataset releases (spec 039)

## US1 - declare a version + changelog, gate on drift (#707)

- [x] T001 [US1] Failing tests in `python/tests/test_dataset_version.py` (plan, "Tests first")
- [x] T002 [US1] Add `version` and `changelog` to each dataset in `kaggle/dataset_docs.yaml` (start at `1.0.0`), and
  the semver rule as a comment
- [x] T003 [US1] `health_transformation_lab_nlp.dataset_version`: `version`, `changelog`, `latest_change` (all `@traced`)
- [x] T004 [US1] Extend `test_kaggle_dataset_docs.py` (or a sibling) to store the published file/column hash and fail on
  a change without a version bump + changelog line
- [x] T005 [US1] AGENTS.md "Publishing datasets": the version + changelog rule and the semver meaning (#722)

## US2 - provenance manifest inside every dataset (#708)

- [x] T006 [US2] Failing tests in `python/tests/test_dataset_manifest.py`
- [x] T007 [US2] `build_manifest` and `write_manifest` in `dataset_version` (`@traced`); `row_count` for `.csv`/`.jsonl`
- [x] T008 [US2] Call `write_manifest` in `kaggle/publish.py`, `kaggle/publish_tasks.py`, `huggingface/publish.py`
  before upload; pass the commit through (workflow `--commit`, else `git rev-parse HEAD`)
- [x] T009 [US2] Document `manifest.json` in `kaggle/dataset_docs.yaml` as a published file (so the usability check and
  US1 gate know it) and in the dataset cards

## US3 - one version string on both platforms and a release tag (#709)

- [ ] T010 [US3] Failing tests in `python/tests/test_dataset_release.py` (mock the Kaggle and HF clients)
- [ ] T011 [US3] `release_message` and `release_tag` in `dataset_version` (`@traced`)
- [ ] T012 [US3] Use `release_message` as the Kaggle version note and the HF commit message; create `data/<slug>-vX.Y.Z`
  as a git tag and an HF revision tag, both idempotent; print both URLs; `--metadata-only` makes neither
- [ ] T013 [US3] `ops/secrets_register.yaml`: confirm `HF_PUBLISH_TOKEN` write scope covers tagging; note #649 reuses this

## Across the spec

- [ ] T014 One PR per user story, each `Closes #<issue>`; a review in `pull_requests/pr-<n>-review.md` against
  `.claude/review-rubric.md` and these rules
- [ ] T015 `/speckit-analyze` to cross-check spec, plan and tasks before the first `feat` branch

Notes: tests before code (AGENTS.md). No dataset values change; the first publish under this spec is a PATCH that adds
the manifest and the version note, not a data change. Publishing to Kaggle or Hugging Face waits for the owner's word
(AGENTS.md, rule 6: publishing outside this repo).
