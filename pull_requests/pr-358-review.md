---
pr: 358
branch: spec/352-028-dataops-task-set
title: "Spec 028: the repo's history as a coding-agent task set; manifest and backfilled issues"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator (self-review by the authoring session against .claude/review-rubric.md; no separate reviewer subagent was run, so the owner should read §Findings before merging)
verdict: approve with one should-fix
---

# PR Review: Spec 028: the repo's history as a coding-agent task set; manifest and backfilled issues

## Summary
Spec 028 inventories the repo's history (196 PRs and direct commits) into a manifest with a fidelity tier
and a candidate flag (changed code and tests), and backfills 67 issues so every one of the 115 candidate
tasks has an issue number. The issues quote the original PR or commit text verbatim and say they were
created after the fact. The task format itself (US3-US5) is specified, not built. Stacked on #357.
Verdict: approve, with one should-fix on how the manifest records a PR's base commit.

## Scope of Change
- Files changed: 7 (+~560 / -0) over the #357 base
- Areas touched: specs, package (`task_mine.py`), a script, tests, `data/tasks/task_manifest.csv`
- Commits:
  - 1a8782b Spec 028: the repo's history as a coding-agent task set; manifest and backfilled issues
- Range reviewed: `spec/345-027-pipeline-doctor..1a8782b`

## CI Status
| Check | Status |
|---|---|
| python | pending on GitHub; module tests 8 passed, suite green on the base branch |
| postgres, r-parity, bundle | pending; untouched |

## Secrets, PHI and Claims Scan
Clean. The manifest holds titles, shas, timestamps and counts; the script reads the GitHub token from the
environment (`gh`) and never writes it; no note text; no organization claim.

## Strengths
- Three fidelity tiers instead of one pretended level: the paper can report fidelity by tier.
- The backfilled issues are records, not inventions: verbatim text, the source linked, the label and the
  closing comment say when and why the issue was created.
- Squash merges and merge commits both resolve to their PR; what remains is a true direct commit.
- The convention (every branch to an issue, enforced by CI since #116) now covers the whole candidate set.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`base_commit_sha` for a merge commit is its first parent, not the PR's merge base.** For a merge commit
   on `main`, `parent_sha` is the previous `main` commit, which is correct for "the snapshot before the
   change landed", but for US3 the competition's `base_commit` is the repository "immediately prior to the
   bug fix", and a PR branched earlier may have a different merge base. The REST payload carries `base.sha`;
   the builder (US3) should take `git merge-base` of the PR head and `main`, or `base.sha`, and the manifest
   should record which it used. Not blocking here: the manifest is an inventory and the builder is planned.

### 🔵 Nits / suggestions (Minor)
1. The title key for backfilled issues is `<spec> CHORE<n>`; where the PR implemented a spec user story the
   kind could be `US`. `CHORE` was chosen so no backfilled record is confused with a planned story.
2. `46_mine_tasks.py` re-reads the manifest to keep issue numbers across runs; a test for that merge would
   be cheap.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | token from the environment via `gh`; not logged |
| Synthetic only, no PHI | ✅ | metadata only |
| No organization claims; vendors cited | ✅ | the competition is named as its public pages describe it |
| Test first | ✅ | 8 module tests; the script is verified by running it (dry run, then real) |
| Python and R in parity | ✅ | no reported metric |
| Simulated is labelled simulated | ✅ | nothing simulated |
| Seeds fixed | ✅ | no sampler |
| Paths | ✅ | `paths.REPO_ROOT` |
| Spec for big changes | ✅ | specs/028 with spec, plan, tasks; issues #352-#356 |
| Prices | ✅ | none |
| Deck figures | ✅ | none |
| Commits | ✅ | imperative, body says why, co-author trailer |
| Docs | 🟡 | spec and plan only; a `docs/` page can wait for the builder (US3) |
| Configuration | ✅ | no settings added |
| Secrets register | ✅ | `gh`'s token is the existing session credential; none made |
| Idempotent writes | ✅ | manifest is overwritten whole and keyed by `instance_id`; issue creation skips rows that already have an issue |
| Alerts | ✅ | none |

## Test Coverage
`python/tests/test_task_mine.py`: issue from branch and body, squash subject → PR, spec from text (both
forms), candidate rule incl. grader-stripped files, tiers incl. tool branches, ids, manifest row shape
from a PR and from a commit, backfilled-issue text. Not covered: the REST and git IO in the script.

## Verdict
Approve with one should-fix to carry into US3 (merge base vs first parent). Merge after #357.
