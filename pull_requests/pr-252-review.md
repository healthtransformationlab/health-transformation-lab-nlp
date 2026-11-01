---
pr: 252
branch: chore/249-025-hf-token-fallback
title: "Publish to Hugging Face with HF_TOKEN when HF_PUBLISH_TOKEN isn't set"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator (workflow env, messages, register, one test)
verdict: approve
---

# PR Review: HF_TOKEN fallback for publishing

## Summary
The Hugging Face publish job uses `HF_TOKEN` when `HF_PUBLISH_TOKEN` isn't set, at the owner's request. Verdict:
approve.

## Scope of Change
- Commits: 1390a4b Publish to Hugging Face with HF_TOKEN when HF_PUBLISH_TOKEN isn't set
- Range reviewed: `origin/main..1390a4b`

## Rubric
- **Settings checked first:** the shape and write-access check still runs before any work. A read-only token fails
  there, naming both settings.
- **One declaration per setting:** the fallback is in the workflow only, recorded in the register and the README.
- **Least privilege:** `HF_TOKEN` must have write access for publishing to pass. The register says so. A
  separate publish token stays the documented first choice.
- **Tests first:** the new test failed before the change.

## CI Status
| Check | Status |
|---|---|
| python | 1039 passed, 15 skipped locally |
