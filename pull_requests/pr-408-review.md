---
pr: 408
branch: docs/407-reference-audit
title: "000 DOCS2: correct references that don't match their sources"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: coordinator verification of three checker subagents' findings
verdict: approve
---

# PR Review: 000 DOCS2: correct references that don't match their sources

## Summary
Every entry in `docs/references.md` was checked against its source by three checker subagents. Before any edit, the
coordinator checked the findings that change an author or a title against primary metadata:
- the arXiv listings for 2 and 6;
- the dataset's own citation for 43;
- dblp and Reviewer.ly for 5;
- medRxiv and PMC for 29.

Eleven entries are corrected, and the same wrong names are fixed in the five docs that repeat them. Approve.

## Secrets, PHI and Claims Scan
Clean. These are citations only.

## Findings
None blocking. Where a source host was unreachable, the check relied on search results; the PR lists those entries.
Optional additions (31's published version, the errata for 12 and 55) are left for later.

## Rubric
- No generated file was touched.
- The documentation tests pass.
- `Closes #407`.
