---
pr: 482
branch: chore/481-032-silver-erd-pngs
title: "032 CHORE1: re-render the Open Dental silver ERD PNGs with the insurance tables"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: coordinator (generated images only; checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: re-render the Open Dental silver ERD PNGs

## Summary
The three Open Dental silver PNGs are rendered from the committed `.drawio` sources with the repo's renderer, so they
show the insurance tables US6 added.

## Checks
- **Generated, not hand-edited:** rendered by `diagrams/_build/drawio_render.js` with a local draw.io webapp
  (`render.md`).
- **Renderer matches:** the OMOP silver PNGs, whose sources are unchanged, came out byte-identical.
- **Content:** the entity ERD shows `carrier`, `insplan`, `inssub` and `patplan`, linked to `patient`.
- **No code, data or result changes.**

## Verdict
Approve.
