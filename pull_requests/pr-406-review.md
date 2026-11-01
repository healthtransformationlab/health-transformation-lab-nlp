---
pr: 406
branch: docs/405-reliability-reference
title: "000 DOCS1: credit reliability to de Vet et al. 2006, not Liaw et al. 2013"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve
---

# PR Review: 000 DOCS1: credit reliability to de Vet et al. 2006, not Liaw et al. 2013

## Summary
This fixes a wrong citation. Liaw et al. 2013 doesn't define reliability; de Vet et al. 2006 does, so the grader's
reliability domain now credits de Vet everywhere it appears:
- the dashboard, the Genie space and the site JSON;
- `graders.md`, `reliability_cal.py` and specs 013 and 019.

The new reference was checked against publisher-linked records. A test keeps the old credit out. Approve.

## Secrets, PHI and Claims Scan
Clean. This is wording and a reference only; no data changes.

## Findings
None blocking. The specs say what they were corrected from, so the history stays readable.

## Rubric
- Generated files rebuilt by their scripts.
- The test was written first and failed before the fix.
- `Closes #405`.
