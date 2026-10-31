---
pr: 400
branch: docs/399-005-dq-site-json
title: "005 DOCS3: publish the data-quality results as JSON for the website"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve-with-nits
---

# PR Review: 005 DOCS3: publish the data-quality results as JSON for the website

## Summary
`dq_site.build()` gathers the committed data-quality results into one JSON file, `docs/site/data-quality.json`:
- the 16 checks, with plain labels;
- completeness, overall and per clinic, with clinics beyond 2 SD flagged;
- reversals over time per method;
- planted errors caught;
- the Open Dental realism profile.

A test fails if the file is stale. Nothing is re-run except the seeded Open Dental extract (about 10 s). Tests came
first; the full suite passes. Approve, with nits.

## Secrets, PHI and Claims Scan
Clean. Counts and shares only, from synthetic data, with `is_synthetic: true` and a plain note in the file.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- **The website copies this file by hand**, as it does the decks. #375's workflow (still open, needs
  `SITE_DEPLOY_TOKEN`) could copy it too once merged.
### 🟢 Nits / Suggestions
- **No clinic is beyond 2 SD in the current synthetic data**, so the flag shows nothing yet. It's tested on a hand-made
  case.

## Rubric
- `@traced` on public functions; paths via `paths.py`; seeds fixed. `Closes #399`.
- Wording: plain labels, no "diagnose"; the page is labelled synthetic.
