---
pr: 390
branch: docs/389-005-patel-order-check
title: "005 DOCS1: check the design's evidence order against Patel et al. 2022"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve
---

# PR Review: 005 DOCS1: check the design's evidence order against Patel et al. 2022

## Summary
Docs only. Action item A2, references item 4 and the evidence-rules section now say what the paper (PMC9788909,
open access) actually does:
- the clinician's recorded diagnosis, then notes, then charting, each filling gaps;
- no procedure diagnosis codes, and nothing on planned procedures;
- charting from the most recent complete, approved visit only;
- no test of the order against experts.

The decisions this leaves for the study lead are named, not made. Approve.

## Secrets, PHI and Claims Scan
Clean. The claims are about a published paper, cited with its PMC link. The paper's own words are quoted only in
the issue.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🟢 Nits / Suggestions
- **The paper's reported numbers are inconsistent.** It gives the note extractor 87% recall, but its confusion counts
  (224 TP, 0 FN) give 100%. The share of patients with a diagnosis from notes is 18% in one place and 13% in
  another. Neither is quoted in the repo, so nothing here depends on them; worth knowing before citing those numbers.

## Rubric
- No code, data, label or metric changed, so no spec, test or R twin is needed.
- `Closes #389`, and the branch is `docs/389-…`. Wording and organization-reference checks pass.
