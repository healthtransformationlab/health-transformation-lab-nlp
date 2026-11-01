---
pr: 263
branch: docs/262-name-the-two-benchmarks
title: "Say what the lab is: name its two benchmarks on the decks and README"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator review against the rubric (wording only; no figures change)
verdict: approve
---

# PR Review: Say what the lab is: name its two benchmarks

## Summary
"The lab" didn't tell a reader what it is. Both deck covers now add one line, "Two open benchmarks: OralHealthBench,
for AI answers on oral health and getting care, and PerioBench, for finding gum disease in dental records", and the
pitch's closing slide's kicker names both. Each body-text "the lab" now says which thing it means (OralHealthBench,
the open agent, or the models and agents behind the two benchmarks), and the EDR connect slide labels its two paths
PerioBench and OralHealthBench. The README names both benchmarks and its GlobalDentBench sentence now matches the decks
("licensing-exam questions", "questions built from published patient cases", #239). Approve.

## Checks
- `cd python && python -m pytest -q tests` passes (deck, claims and wording tests included); decks rebuilt.
- Rendered in Chromium: both covers, the close and the connect slide; nothing overflows the slide.
- No figure changes; no secrets, PHI or organization claims; no "diagnose" wording (test_wording).
