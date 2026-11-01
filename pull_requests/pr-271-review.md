---
pr: 271
branch: docs/270-020-kaggle-collection-private
title: "Drop the step that makes the Kaggle collection public"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-29
reviewer: coordinator verification (a docs change with one test; no reviewer subagent run)
verdict: approve
---

# PR Review: Drop the step that makes the Kaggle collection public

## Summary
The owner made the collection but couldn't find any setting to make it public, either on a phone or in the
desktop-site view, and Kaggle documents none. The README now treats the collection as an optional private list.
It points to its own "What's on Kaggle" table as the shared index, where every item is public on its own. The
spec 020 US4 text gains a note saying so. A new test checks that the section doesn't ask for a public collection.
Approve.

## Scope of Change
- Files changed: 3 (README, spec, test), plus this review
- Areas touched: docs, specs, python tests
- Commits: 87ff23e Drop the step that makes the Kaggle collection public; this review
- Range reviewed: `origin/main..docs/270-020-kaggle-collection-private`

## CI Status
| Check | Status |
|---|---|
| python, PR conventions | pending when written; see the PR |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean.
- Organization claims: clean. The only claim about Kaggle is that it offers no public setting for collections,
  which is based on what the owner saw. The README doesn't present it as a documented Kaggle policy.

## Strengths
- The existing test that the collection's name is in the README still passes. The name and the steps are kept.
- The anchor `#whats-on-kaggle` matches GitHub's slug for the "What's on Kaggle" heading.
- The steps now list all three notebooks and the model. Before, they listed two notebooks and said the model
  would come "later".

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
None.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | |
| Synthetic only, no PHI | Yes | |
| No organization claims; vendors cited | Yes | a statement about Kaggle's product, from the owner's own check |
| Test first | Yes | the new test failed before the README change |
| Spec for big changes | Yes | spec 020's US4 updated |
| Commits | Yes | imperative subject, body says why, co-author trailer |
| Branch and issue | Yes | `docs/270-020-kaggle-collection-private`, `Closes #270` |

## Test Coverage
`cd python && python -m pytest -q tests`: 1054 passed, 15 skipped.

## Verdict
Approve. It can merge once CI is green. The test is a `.py` file, so the merge starts the usual dev deploy, which changes nothing in Databricks.
