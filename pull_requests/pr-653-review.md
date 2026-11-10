---
pr: 653
branch: data/652-028-task-screen
title: "028 AI3: screen 30 published tasks: does each statement say what its tests check?"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-10
reviewer: the authoring session (the table's counts recomputed; the two passes compared; no separate reviewer of the pull request)
verdict: approve
---

# PR Review: 028 AI3: screen 30 published tasks: does each statement say what its tests check?

## Summary
Adds one table, its README and a test. An AI reviewer rated 30 of the 93 published tasks on SWE-bench Verified's two
questions, in two passes; 5 pass, and in 25 the tests need something the statement and hints never give. The table
and README say plainly that no person verified the ratings. Nothing is published outside the repository and no job
runs. Nothing blocking.

## Scope of Change
- Files changed: 3 added (the table, its README, one test); this review file is the fourth
- Areas touched: data / python (tests)
- Commits: `315628b` Screen 30 published tasks: does each statement say what its tests check?
- Range reviewed: `4f32b3d..315628b`

## CI Status
| Check | Status |
|---|---|
| All checks | started when the branch was pushed and again with this file; the head commit must be green before merge (AGENTS.md rule 6) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. The table holds ratings and short reasons about the repository's own task statements and tests.
- **Organization claims:** clean. `test_no_org_references.py` passes with the table in the tree.

## Strengths
- The sample is drawn with a seed within each statement source, not chosen.
- Every rating has a reason that names what the tests need, so a reader can check any row against the task.
- The screen is cross-tabulated with the model's run, which is what makes it more than a quality note: 1 of 3 resolved where the screen passes, 0 of 13 where it fails.
- The README's "What it cannot show" is specific.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **No person verified the ratings.** It is stated in the table, the README and the pull request. A plain-language
   sheet was given to the owner the same day; if answers come back they are added as their own column, not merged
   into the AI's.
2. **The second pass is not independent.** It read the first pass's ratings before giving its own. 30 of 30
   agreeing therefore says the restatement is consistent, not that two reviewers reached the result separately.
3. **Long test patches were cut at 12,000 characters** (`is_test_patch_cut`). A cut can hide a requirement; it cannot
   hide one that was seen, so it can only make a task look fairer than it is.

### 🔵 Nits / suggestions (Minor)
4. The whole set (93) was not screened. The remaining 63 can be done the same way.
5. `tasks_excluded.csv` and `tasks_sample.jsonl` were rebuilt by `55_build_tasks.py` to read the task rows and came
   out unchanged; nothing but the three new files is in the diff.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets; synthetic only, no PHI | ✅ | scans above |
| No organization claims | ✅ | |
| Test first | ✅ | the test reads the table and README; it cannot pass without them |
| Simulated is labelled simulated | ✅ | not a simulation; labelled as an AI reviewer's screen wherever it is reported |
| Spec for big changes | ✅ | under spec 028 as an action item (#652); no dataset, metric or label rule changes |
| Publishing datasets | n/a | not published to Kaggle; `test_kaggle_dataset_docs.py` passes |
| Wording, benchmark order | ✅ | `test_wording.py`, `test_bench_order.py` pass |
| Commits | ✅ | imperative subject, body says why, co-author trailer |
| Python and R parity, seeds, paths, prices, configuration, secrets register, writes, alerts | n/a | |

## Test Coverage
- `test_task_screen.py` (5 tests): the 30 are published tasks in the stated strata; ratings on the scale and
  `is_pass` derived from them; the second pass recorded; the run columns equal to the run table; the README's counts
  equal to the table's.
- Run locally with `test_wording.py`, `test_no_org_references.py`, `test_bench_order.py`,
  `test_kaggle_dataset_docs.py`: 59 passed. `ruff check` on the new test: clean.
- Not tested: whether a rating is right. That is what a person's check is for.

## Verdict
Approve. No outward publish and no compute, so it merges when the head commit is green (AGENTS.md rule 6).
