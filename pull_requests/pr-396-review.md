---
pr: 396
branch: docs/395-029-analysis-plan
title: "029 DOCS1: pre-specified analysis plan for the tooth-loss model, and an evaluation checklist"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve-with-nits
---

# PR Review: 029 DOCS1: pre-specified analysis plan, and an evaluation checklist

## Summary
Docs only. The plan is written before any model result, in TRIPOD+AI's order, with a change log. It separates what
is fixed from what the study lead decides, and names the default used until then. The checklist states PerioBench's
gaps plainly: no real reference standard, no over-time or second-site test, no reporting checklist yet. The three new
references were checked against their published records. Approve, with nits.

## Secrets, PHI and Claims Scan
Clean. No organization or practice is named; "a second practice" is generic. Real data stays inside its own
environment; only aggregates leave.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- **The plan fixes the XGBoost hyperparameters** (depth 3, 200 trees). That's defensible and simple, but say in the
  thesis why they weren't tuned: a small labelled set, and avoiding test-set leakage. Tuning inside the training set
  stays allowed.
### 🟢 Nits / Suggestions
- **Item numbers in TRIPOD+AI's 27-item checklist aren't cited per section.** Map them when results are reported (plan
  section 16).
- **Registering the plan on OSF (section 15)** is the step that makes "pre-specified" checkable by others.

## Rubric
- No code, label or metric changed, so no spec code, test or R twin is needed. `Closes #395`.
- Wording: case finding, never "diagnose"; diagnosis only as recorded by a dentist.
