---
pr: 489
branch: docs/484-033-data-card
title: "033 US1: a data card lists every synthetic-data parameter with its value and a checked source or \"placeholder\""
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: Claude Code (checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: the synthetic data card (spec 033 US1)

## Summary
Adds `docs/synthetic_data.md`, one table per generator (study visits, the Open Dental extract, the medical record)
with each parameter's value, meaning, source or "placeholder", the published figure and the repo's check. Nine
sources are checked and added to `docs/references.md` (items 72-80). A test keeps the card in step with the code.

## Checks
- **Test first:** `tests/test_synthetic_data_card.py` failed (199 of 200) before the card existed; it now passes. It
  covers every `open_dental.Params` field, every keyword argument of `synthetic.draw_risk` (none yet: US2 adds
  them), the named module constants and each medical-record condition. It checks the row exists, that the source
  names an existing references.md item, a code citation or "placeholder", and that the value shown is the code's.
  A negative test shows a row with an empty source fails.
- **Sources (SC-002):** each new item says where it was checked (PMC or cdc.gov full text; abstracts for the two
  attachment-loss cohorts). The PMID suggested for the Oslo figure (11063391) was a different paper. The right one
  is cited and the mix-up is noted. The ADA HPI coverage figures and the Open Dentistry Journal audit could not be
  opened from the session, so they are named as unchecked and not cited. `insurance_shares` stays a placeholder.
- **Synthetic only, no names beyond cited publications:** institutions in item 76 are described, not named.
  The organisation-name, wording and benchmark-order tests pass.
- **No data or results change:** docs, a README line and a test only. Full suite 1832 passed, 16 skipped.

- **Known gaps (owner's addition):** edentulism and state geography are listed as gaps, not parameters, with
  #500 (033 US4) tracking the fix. NCHS Data Brief 368 and the NCHS QuickStats (items 79-80) were checked on
  cdc.gov; the America's Health Rankings state figures could not be opened, so they are marked unchecked.

## Notes
- Inline rates (the clinic profiles, the patient-table rates in `build_with_readings`) are on the card as grouped
  rows, but the test does not check them because they are not named constants. Naming them would change no output
  and could be a follow-up.
- The study rows for smoking and HbA1c are written so that US2's keyword arguments will be checked as soon as they
  exist.

## Verdict
Approve.
