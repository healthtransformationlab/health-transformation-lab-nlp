---
pr: 956
branch: fix/955-028-cancelled-kernel-collect
title: "028 BUG14: keep the tasks a cancelled batch kernel finished when collecting it"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: claude-code (in-session checklist against .claude/review-rubric.md; local pytest; collected the real cancelled kernel)
verdict: approve-with-nits
---

# PR Review: keep the tasks a cancelled batch kernel finished when collecting it

## Summary

Closes #955. When a batch kernel ends without its run-level `result.json` (cancelled, stopped by Kaggle, out of
time), collect now builds the run from the per-task `tasks/<id>/result.json` files the kernel writes as each task
ends. Before, it dropped them all. The PR also adds the cancelled run's own table, collected this way.

## Checks against the rubric

| Item | Result |
|---|---|
| Test first | The new test failed (`partial_batch_result` missing) before the code. 57 tests in `test_official_agent.py` pass, and 173 across the five related files. |
| Contract as written in the issue | `partial_batch_result(out, status, model)` returns the error text, runs, `is_batch` and `model_name`. `partial_note` is the exact text. |
| Not-run rule (spec 028) unchanged | A task with no file isn't in `runs`, so it is counted as not run with the default reason, "not reached by the kernel". |
| Failures say how they ended | The settings note records the kernel's ending status. The printed line still shows the error. |
| Real data | Collecting `jcblearning/htlnlp-offrun-devset-e4b-pub-k` gives 4 of 20 resolved and 3 not reached, and writes the table, the settings and the note. Before the fix: "0 of 0 resolved". |
| No secrets, no task text | The table has counts and verdicts only, as the other run tables do. |
| CareQuest / wording / bench order | Not touched. `test_no_org_references.py` and `test_wording.py` pass. |

## Findings

- Blocking: none.
- Nit: in a table built this way, `gpu_count` and `gpu_name` are blank, because they come from the run-level file. The
  PR says so. The kernel's `gpu_samples.csv` could fill them later if it matters.
- Nit: the model now falls back to the declared model when the run-level file is missing. If a submission declared
  no allowed model, it stays blank rather than stopping the collect, which is right for reading a finished run back.

## Verdict

**approve-with-nits**
