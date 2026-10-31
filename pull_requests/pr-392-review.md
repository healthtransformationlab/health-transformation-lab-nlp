---
pr: 392
branch: docs/391-005-standards-page
title: "005 DOCS2: one page comparing the standards, sources and orders"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve-with-nits
---

# PR Review: 005 DOCS2: one page comparing the standards, sources and orders

## Summary
This PR adds a generated page that puts three things side by side:
- the definitions: 2017 AAP/EFP, 2012 CDC/AAP and ACES;
- the reading orders;
- how often each pair of sources agrees.

It also lists the decisions still open. Every number is read from committed files, and a test fails if the page goes
stale. No score, label or data changes. The full suite passes (1167 passed, 16 skipped). Approve, with nits.

## Secrets, PHI and Claims Scan
Clean. The page is labelled synthetic at the top. The 234 vs 173 comparison carries the caveat that the answer key
was made from the measurements. Citations are the existing reference items 4, 7 and 35.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🟢 Nits / Suggestions
- **`docs/site_level_omop.md` still has its own hand-copied 2017 vs CDC/AAP table.** It could link here instead. The
  numbers match today.
- **The cross-tabs are dry-run outputs** (the generator spreads loss across sites as a placeholder). The page's banner
  covers this, and `site_level_omop.md` says so too.

## Rubric
- Generated docs with a staleness test: yes (`scripts/48_standards_doc.py --check`, `test_standards_doc.py`).
- `@traced` on the public functions; paths via `paths.py`.
- `Closes #391`, and the branch is `docs/391-…`.
- Wording: "finding gum disease in dental records (phenotyping)", and diagnosis only as recorded by the clinician.
