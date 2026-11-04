---
pr: (see the PR for #547)
branch: fix/547-025-run-kbench-llm
title: "025 BUG5: pass kbench.llm in the task's run call, and record the first Kaggle runs"
author: claude (agent session)
reviewed_at: 2026-11-04
reviewer: coordinator review against .claude/review-rubric.md (small diff)
verdict: approve
---

# PR Review: 025 BUG5: pass kbench.llm in the task's run call, and record the first Kaggle runs

## Summary
Kaggle errored all three model runs because the task file's run call didn't pass `kbench.llm`: we had
assigned it to a variable first. The file now calls `perio_bench.run(kbench.llm, df, judge_llm=kbench.judge_llm)` when
Kaggle is configured, and keeps the scripted dry run otherwise. A test checks for the call. It failed first and passes
after. `docs/kaggle_benchmarks.md` records the scores from the three runs' logs, which finished all 223 notes before
Kaggle marked them errored. They are labelled as agreement with the generator's answer key on synthetic notes. The
doc says the judge was the same Google model for all three, and that the runs are not on a leaderboard yet.
Verdict: approve.

## Scope of Change
- Files changed: 4 (task file, test, doc, this review)
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| python | see the PR; green before merge |

## Secrets, PHI and Claims Scan
Clean. The model names are Kaggle proxy slugs, cited to the workflow run and the Kaggle logs. The doc claims nothing
about any company beyond those runs.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- The judge model also wrote one of the three answer sets (the self-judging caveat is in the doc). A later run could
  set a judge from another vendor for every model.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | ✅ | `test_task_file_runs_the_task_on_kbench_llm` failed first |
| Simulated is labelled | ✅ | real runs say synthetic and answer key; the dry run still prints SIMULATED |
| Words | ✅ | `test_wording.py` passes |
| Figures cite their source | ✅ | the workflow run and `kaggle b t log` |

## Test Coverage
`tests/test_kbench.py`: 17 passed. Kaggle's `_validate_task_in_file` accepts the file. `ruff check` is clean. The
wording, benchmark-order and no-org-name tests pass.

## Verdict
approve: merge once CI is green. The clean rerun waits for the Kaggle daily allowance to reset.
