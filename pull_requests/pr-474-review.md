---
pr: 474
branch: fix/471-proc-dx-unknown-digit
title: "000 BUG2: read a K05.3 code with an unknown severity digit as unknown"
author: jcbowyer
reviewed_at: 2026-11-02
reviewer: coordinator (one-line fix with a regression test; checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: read a K05.3 code with an unknown severity digit as unknown

## Summary
`read_proc_dx` now returns unknown for a `K05.3xx` code whose severity digit isn't 1-3, as the R twin already does,
instead of raising `KeyError`.

## Checks against the rubric
- **Test first:** the regression test failed before the fix.
- **Spec:** none needed; a one-line bug with a regression test (AGENTS.md "When a change needs a spec").
- **Python/R parity:** R already returned unknown for these codes; this brings Python in line.
- **Results:** no synthetic code has this form, so no committed result changes.
- **Telemetry:** no new public function.

## Findings
None.

## Verdict
Approve.
