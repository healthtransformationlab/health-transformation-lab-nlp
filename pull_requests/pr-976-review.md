---
pr: 976
branch: fix/975-batch-kernel-time-limit
title: "028 BUG15: a batch kernel's time limit follows its deadline"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: claude-code (in-session checklist against .claude/review-rubric.md; local pytest; the cut run re-collected from its saved output)
verdict: approve
---

# PR Review: a batch kernel's time limit follows its deadline

## Summary

Closes #975. Kaggle cancels a kernel at the limit it was pushed with. The runner pushed every kernel with
`--kernel-minutes`, default 45, while a batch kernel plans to keep starting tasks until `--deadline-minutes`, default
180. Two approved Kaggle runs were cut at about 44 minutes as a result. `kernel_minutes_for` now gives a batch kernel
its deadline plus 30 minutes, capped at 720, and refuses a smaller batch limit before anything is uploaded. One-task
kernels keep 45 minutes. The PR also commits the cut run's table, with the cause and its cost in the notes. Approve.

## Checks against the rubric

- **Secrets:** none in the diff. The settings file holds paths, model names and notes.
- **Results:** the table says what it is: 2 of 8 resolved, and 15 not reached because the kernel was cancelled. It
  claims no resolve rate for the 23.
- **Test first:** the four new tests failed before the change (4 failed, 22 passed on `-k kernel`) and pass after it.
- **Every push uses the new limit:** both the batch push (`push_kernel`) and the per-task push read
  `a.kernel_minutes_resolved`, and a test asserts the old `a.kernel_minutes * 60` is gone.
- **Settings:** `--kernel-minutes` is still declared once; its default and help text change, and the PR says where.
- **The cause is right:** both cut kernels' logs end at 43.5 and 43.7 minutes of kernel time. Kaggle's
  `CANCEL_ACKNOWLEDGED` matches a session timeout at the 45 minutes the push asked for, and nothing in the five
  repositories cancels kernels.

## Findings

- 🔵 The 30-minute margin covers start-up (model and image) and the last task's verification on the runs seen so far.
  A batch whose start-up is longer would still be cut close to its deadline. The settings notes record it if that
  happens.

## Verdict

**approve**
