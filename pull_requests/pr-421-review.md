---
pr: 421
branch: feat/354-028-tasks-jsonl
title: "028 US3: tasks.jsonl rows with patch, test_patch and base commits (gates pending)"
author: Claude Code (agent session)
reviewed_at: 2026-11-01
reviewer: coordinator verification against .claude/review-rubric.md (no reviewer subagent available in this session)
verdict: approve-with-nits
---

# PR Review: 028 US3: tasks.jsonl rows with patch, test_patch and base commits (gates pending)

## Summary
The PR turns each candidate in the task manifest into a `tasks.jsonl` row with the competition's eight fields.
`patch` and `test_patch` are split from the diff at `python/tests/`, and the statement and hints come from each
tier's source, with the organisation name redacted. A merge commit's base is now the PR's merge base, which
answers should-fix 1 of PR review #358 and is recorded in the manifest. The script ran end to end: 116 rows,
0 excluded, a 3-row committed sample. The two gates (T007) were not run because `swegemma` can't be installed
here, so the PR correctly says `Refs #354` and leaves T007 open. Verdict: approve with nits.

## Scope of Change
- Files changed: 7 outside `data/` (+430 / -9); data: `task_manifest.csv` (one new column), `tasks_excluded.csv`, `tasks_sample.jsonl` (21 KB)
- Areas touched: python, specs, data, .gitignore
- Commits: 459c90a Build tasks.jsonl rows from the task manifest (028 US3, T005-T006)
- Range reviewed: `54b2d92..459c90a`

## CI Status
| Check | Status |
|---|---|
| python / postgres / r-parity / bundle | not read from this session (the GitHub API token was invalid); local run below |

## Secrets, PHI and Claims Scan
- Secrets: clean. `52_build_tasks.py` reads `GH_TOKEN`/`GITHUB_TOKEN` only to send a header, and never prints or stores it. The matches for "token" in the diff are manifest titles from history.
- PHI / real data: clean. The sample holds this repo's own issue text and code diffs, with no notes or names.
- Organisation claims: clean. The sample passes `test_no_org_references.py`, and a new test checks that the sample never names the organisation.

## Strengths
- Merge-base diffs mean `patch` + `test_patch` applied to `base_commit` reproduce the PR head's tree exactly.
- `task_row` emits exactly the competition's fields, in its order. The tier lives in the manifest, so a strict loader won't reject an extra key.
- The script checks its settings first (manifest present, clone not shallow, REST reachable) and fails naming the problem.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **One generated row's `patch` names the organisation.** Statements and hints are redacted, but patches can't
   be redacted without breaking `git apply`. Verified: the script's run reports 1 such row, and the sample leaves
   it out. `tasks.jsonl` is git-ignored, so nothing is committed, but it must be handled before publishing
   (US5): drop that task, or rewrite its history. This is an owner decision.

### 🔵 Nits / suggestions (Minor)
1. The changed-file flags in the manifest still come from the first-parent range. Checked: for all 130
   merge-base rows, the file count and candidate flag are the same under the new range, so nothing is stale
   today. `46_mine_tasks.py` now uses the same range on its next run.
2. Tier A hints include `pull_requests/pr-<n>-review.md`, which was written after the fix and can describe
   the solution. The spec asks for it; consider whether hints should be the PR body only.
3. Script number 51 (47 was taken by spec 029) is recorded in `plan.md` and `tasks.md`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | |
| Synthetic only, no PHI | yes | repo text and code only |
| No organization claims | yes | redacted; sample tested |
| Test first | yes | 9 failing tests written before `task_mine.py` changed |
| Python and R in parity | n/a | no label or metric change |
| Simulated is labelled | yes | rows are called "ungated candidates", never verified tasks |
| Seeds fixed | n/a | no sampling |
| Paths | yes | `paths.REPO_ROOT` |
| Spec for big changes | yes | spec 028, tasks ticked |
| Commits | yes | imperative, why, trailers |
| Configuration | yes | no new settings; optional token read from the environment |
| Idempotent writes | yes | every file overwritten whole |

## Test Coverage
New tests cover diff splitting, the merge-base rule, statements by tier, redaction, story extraction, exact
fields, exclusion reasons and the committed sample. Local run: `python -m pytest -q tests` gave 1256 passed and
15 skipped; `ruff check` was clean. The gates are not tested because the evaluator is unavailable.

## Verdict
Approve with nits. Before US5 publishes anything, decide what to do with the row whose patch names the
organisation, and run T007 where `swegemma` is available.
