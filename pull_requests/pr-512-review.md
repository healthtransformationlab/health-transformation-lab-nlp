---
pr: 512
branch: docs/511-000-limited-compute-wording
title: "000 DOCS4: say why Databricks and GPU runs wait for the owner: limited compute, not cost"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: coordinator (rule wording; checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: limited compute, not cost

## Summary
One bullet of AGENTS.md rule 6 reworded. The same runs still wait for the owner; the reason given is now accurate.

## Checks
- **Rule change:** rule changes wait for the owner. The owner asked for this one ("fix the rule wording"), so it can
  merge once green.
- **Accuracy:** the workspace is Databricks Free Edition and the GPUs are Kaggle's free tier; neither bills, and both
  are quota-limited.
- **Tests:** agent-docs, wording, benchmark-order and organisation-name tests pass.

## Verdict
Approve.
