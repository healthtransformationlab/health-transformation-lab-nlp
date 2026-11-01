---
pr: 465
branch: ci/464-000-site-deploy-key
title: "Let the website deck copy push with a deploy key that doesn't expire"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator verification
verdict: approve-with-nits
---

# PR Review: Let the website deck copy push with a deploy key that doesn't expire

## Summary
The deck copy failed on its first run because `SITE_PUSH_TOKEN` never existed. This PR lets the workflow push with an
SSH deploy key (`SITE_DEPLOY_KEY`), which covers the website repository only and never expires, and keeps the token as
a fallback. The credential and its push access are checked before any build. Approve with nits.

## Scope of Change
- Files changed: 6
  - the workflow, the copy script and its test;
  - `ops/secrets_register.yaml`, AGENTS.md;
  - this review.
- Areas touched: ci, ops, docs.

## Secrets, PHI and Claims Scan
- No secret values anywhere. The register test's base64 scan passes.
- The key is written only to `$RUNNER_TEMP` with mode 600 and removed in an `always()` step. It is never echoed:
  error messages don't include the value, and that is tested.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important)
None.
### 🔵 Nits (Minor)
- **Untested SSH path.** It can't be exercised here: the proxy blocks port 22 and `api.github.com/meta`. Its first real
  test is the owner's first run after adding the key. The run-time check against `api.github.com/meta` guards the
  pinned host key.
- **The token path writes the auth header to `GITHUB_ENV`** for the later steps. It is masked and only lives for the
  job. Before, each step rebuilt the header from the secret.

## Test Coverage
- 7 new tests:
  - preference order, key before token;
  - neither secret set, naming both;
  - malformed keys, never echoed;
  - the CLI's output for later steps;
  - the workflow's order, the pinned host key, `chmod 600` and removal.
- Full suite: 1567 passed, 15 skipped. Every `run:` block passes `bash -n`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | Values never logged or committed |
| Check settings before work | ✅ | Shape check, then a push dry-run, before the build |
| Secrets register | ✅ | Deploy key added, `expires: never`; token marked as the fallback |
| AGENTS.md credential table | ✅ | Row added with how to make it and where it goes |
| Test first | ✅ | |
| Commits | ✅ | `Closes #464` |

## Verdict
Approve with nits. After merging, the owner makes the key (steps in the PR) and runs the workflow once.
