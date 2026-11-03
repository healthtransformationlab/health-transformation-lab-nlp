---
pr: 498
branch: feat/485-033-extract-risk-shares
title: "033 US2: the Open Dental extract's smoking and diabetes follow published US figures"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: Claude Code (checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve, with insurance left for a follow-up
---

# PR Review: published smoking and diabetes shares in the Open Dental extract (spec 033 US2)

## Summary
`synthetic.draw_risk` takes its smoking and HbA1c shares as keyword arguments, defaulting to the old values.
`open_dental.Params` sets the extract's shares from checked sources (11.6% smoke, item 72; 15.8% diabetes by
HbA1c >= 6.5, item 73). Everything the extract feeds is rerun and recommitted, with before/after tables in
`docs/tooth_loss.md` and the PR body.

## Checks
- **Test first:** `tests/test_risk_shares.py` failed (8 of 9) before the code. The defaults reproduce the old draws
  exactly, stream position included. The shares are recovered within 4 SE on 200,000 seeded draws and in a
  4,000-patient extract. Impossible shares fail at once, naming the setting.
- **Study unchanged:** the study rebuild test compares every committed study file byte for byte and passes. No
  benchmark note, answer key or ladder file changes.
- **US8 norm:** `entry_other_rate_norm` now draws at the extract's shares and keys its cache on them, so each age
  band keeps its mean count. The pooled periodontal-share test still passes. `research.md` gives the new norm
  (1.047, was 1.040).
- **Reruns are generated, not hand-edited:** presets (58), data-quality page (50), tooth table (47 via the parity
  inputs), silver dictionary ERD (`silver_erd.py`, PNG rendered by `drawio_render.js`; the unchanged OMOP PNG came
  out byte-identical). The tooth-loss numbers in `docs/tooth_loss.md` and `docs/presets.md` come from the rerun
  CSVs (`data/results/`, git-ignored). The "before" run on `main` reproduced the committed numbers exactly.
- **Parity:** R parity passes (15 blocks, 0 differences). The 26 unrelated files the inputs script rewrote in this
  container were restored.
- **Full suite:** 1,865 passed, 16 skipped after the presets test fix. `ruff check` clean.
- **Telemetry:** `risk_kwargs` (both) carry `@traced`. **Synthetic only**, results labelled SYNTHETIC.

## Notes
- **Insurance is not done.** The ADA HPI coverage figures could not be checked from the session (host blocked), so
  `insurance_shares` stays a placeholder and SC-003 holds for smoking and diabetes only. It needs either the host
  allowed or another checked source, then a one-line `Params` change and a rerun.
- `heavy_smoking_fraction` (0.44) is a placeholder: no daily vs some-days split was checked.
- The HbA1c draw keeps its shape (half 5.8-6.9, half 7.0-10.5), so pre-diabetes stays rare (about 6.6% of patients
  at the new share), well below US figures. That is outside this story.
- The missing-at-entry AUC rose by about 0.03 on the 5-seed means. The page says why (more diabetes, faster
  attachment loss). It is a property of the generator, not a model gain.
- This branch merges the US1 branch (#489), so the card's diff shows here until #489 merges.

## Verdict
Approve. Insurance stays a follow-up.
