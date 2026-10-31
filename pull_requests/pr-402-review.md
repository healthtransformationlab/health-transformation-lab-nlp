---
pr: 402
branch: docs/401-005-dq-site-grader
title: "005 DOCS4: the website's data-quality page follows the EHR DQ grader design"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve
---

# PR Review: 005 DOCS4: the website's data-quality page follows the EHR DQ grader design

## Summary
`dq_site.build()` now reads `grader_tables.dq_tables`, the tables the Databricks EHR DQ grader reads, and writes one
section per grader dataset: tiles, missingness, checks, accuracy, concordance, prevalence by clinic and by scale,
transitions, temporal change, and injected errors. The tests recompute each tile from the grader's SQL definitions
(`dashboards.DQ_SQL`) and tie the sections to the grader's dataset names, so the two can't drift apart. The full
suite passes. Approve.

## Secrets, PHI and Claims Scan
Clean. Statuses and counts only, never note text. The file and the page are labelled synthetic. Reliability is
shown as "not assessed".

## Findings
None blocking. The "Records to recheck" page of the grader is not on the website yet; it is the obvious next tab.

## Rubric
`@traced` on public functions; paths via `paths.py`; tests first. `Closes #401`.
