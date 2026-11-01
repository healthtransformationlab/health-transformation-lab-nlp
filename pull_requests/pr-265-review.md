---
pr: 265
branch: docs/264-no-the-lab
title: "Name the benchmark or agent where the decks still said \"the lab\""
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator review against the rubric (wording only)
verdict: approve
---

# PR Review: Name the benchmark or agent where the decks still said "the lab"

## Summary
#263 missed four "the lab"s, one of them on a visible slide: the pitch's journey slide heading is now "The open agent:
the research goes to them" (parallel to "Today: they go to the research"), and its notes, the tests slide's notes
and the EDR connect slide's notes name the open agent or OralHealthBench. A new test, `test_slides_name_the_benchmark
_not_the_lab`, fails if "the lab" appears in any slide's text or notes ("Health Transformation Lab", the name, is
fine); it failed on both decks before the fix. Approve.

## Checks
- Deck, claims and wording tests pass; full suite run before the first commit (1053 passed, 15 skipped).
- Journey slide rendered in Chromium: the new heading fits on one line.
