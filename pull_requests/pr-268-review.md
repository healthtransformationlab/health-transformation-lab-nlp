---
pr: 268
branch: docs/266-benchmark-status
title: "Say how far along each benchmark is: PerioBench built, OralHealthBench planned, AccessBench exploratory"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator review against the rubric (wording only)
verdict: approve
---

# PR Review: Say how far along each benchmark is

## Summary
The README and decks described OralHealthBench and AccessBench in the present tense, as if built. Per the owner:
PerioBench has working code and results on synthetic records, OralHealthBench is planned (building on
GlobalDentBench), AccessBench is exploratory. The README now leads with PerioBench, heads section 2 "OralHealthBench
(planned)", and uses "will ask" / "would ask"; both deck covers list PerioBench first ("built and tested on synthetic
records") and OralHealthBench as "planned on top of GlobalDentBench"; the pitch's closing slide lists PerioBench first.
Approve.

## Checks
- Full suite passes; decks rebuilt; EDR cover rendered in Chromium (fits).
- No figure changes; no secrets, PHI or organization claims.
