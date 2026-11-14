---
pr: 710
branch: spec/706-039-dataset-versioning
title: "spec 039: version datasets for Kaggle and Hugging Face"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator
verdict: approve
---

# PR Review: spec 039 — version datasets for Kaggle and Hugging Face

## Summary

Spec, plan and tasks for versioning the datasets we publish to Kaggle and Hugging Face. It is documentation only: no
code, no data, no settings. It adds the companion to spec 038's one-declaration-plus-CI-gate pattern — a declared
version and changelog per dataset, a `manifest.json` shipped inside every dataset, and one version string carried to
both platforms and to a release tag. The three user stories (#707, #708, #709) stay open for their own `feat` PRs; this
PR only `Refs` them (epic #706).

## Scope of Change

- Files changed: 3 (new): `specs/039-dataset-versioning/spec.md`, `plan.md`, `tasks.md`.
- Areas touched: specs only.
- No Python, no data, no workflow, no settings.

## CI Status

| Check | Status |
|---|---|
| PR conventions | branch `spec/706-039-dataset-versioning` (type `spec`, epic #706, slug starts with 039); `Refs #707-#709`; the linked user stories carry the four parts; `spec.md` names each story |
| the rest (python, bundle, r-parity, …) | no code changed; expected green on the last commit |

## Secrets, PHI and Claims Scan

- **Secrets:** none. US3 reuses the existing `HF_PUBLISH_TOKEN` (already in `ops/secrets_register.yaml`); no new
  credential, no value anywhere.
- **PHI / real data:** none. Versioning changes how a dataset is released and described; it adds no rows and changes no
  values.
- **Org names / wording / bench order:** clean (scanned: no banned organisation name, no "diagnose/accuracy", no
  benchmark named out of order).

## Strengths

- One declaration: version and changelog live in `kaggle/dataset_docs.yaml`, the one place a dataset is already
  described; the CI gate reuses the file/column surface `test_kaggle_dataset_docs.py` already walks.
- Provenance is built from the files actually published, so it can't drift; it generalises the manifest the private
  Open Navigator task set already ships.
- Idempotence and safety are stated up front: `--metadata-only` makes no version and no tag, re-tagging is a no-op, and
  the content hash (not `built_ts`) is what the gate keys on, so rebuilding alone never forces a bump.
- Out-of-scope is explicit: no data values change, no automatic semver, Kaggle's own version numbers left alone, no
  back-filling.

## Findings

### 🔴 Blocking

None.

### 🟡 Should fix (non-blocking, for the implementing PRs)

1. **The US1 gate and `test_kaggle_dataset_docs.py` must stay one check, not two** that can disagree. The plan says to
   extend the existing derivation; the US1 PR should add the version/hash assertion inside (or beside) that test so the
   published-surface set is computed once.
2. **`manifest.json` becomes a published file**, so US2 must add it to `dataset_docs.yaml` (T009) or the usability
   check and the US1 gate will flag an undescribed file. Called out in tasks; keep it in the same PR as the manifest.

### 🔵 Nits

3. The model (`publish_model.py`) adopts the changelog and manifest but keeps Kaggle's model-instance versioning and
   takes no `data/<slug>` tag; spec.md says so — the US PRs should not tag the model.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Spec before code | ✅ | this PR is the spec; the user stories' `feat` branches come after |
| One issue per story; epic + sub-issues (from 2026-11-14) | ✅ | epic #706, stories #707-#709 as sub-issues, each with the four parts |
| Branch/PR convention | ✅ | `spec/706-039-dataset-versioning`; `Refs` the stories |
| No secrets / PHI | ✅ | scan above |
| Synthetic only | ✅ | no data |
| Test first (for the code PRs) | n/a here | tasks put failing tests first in each story |
| Docs | ✅ | spec, plan, tasks |

## Verdict

**Approve.** Documentation only; it starts no run, publishes nothing and deletes nothing. It is mergeable when the
conventions check is green on the last commit. The two "should fix" notes are guidance for the implementing PRs, not
changes to this one.
