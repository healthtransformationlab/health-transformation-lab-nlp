---
pr: 404
branch: fix/403-erd-line-routing
title: "Route data-dictionary ERD lines around tables, not through them"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve
---

# PR Review: Route data-dictionary ERD lines around tables, not through them

## Summary
The data-dictionary ERDs' lines used to run through other tables, overlap in shared lanes, and loop over the whole
diagram. A grid router in `dictionary_erd.py` now routes them:
- table areas, the legend and area title bands are blocked;
- turns, shared lanes, crossings, area borders and space outside the areas all cost extra;
- lines to the same key row merge into one trunk.

The new test checks every segment against every table and against the areas' vertical span, for both models. Both
PNGs were regenerated and checked by eye. Approve.

## Secrets, PHI and Claims Scan
Clean. These are diagram files only, and the profile counts come from the seeded synthetic extract as before.

## Findings
None blocking.
- **Wider gap:** the gap between tables went from 28 to 56 px, so the diagrams are slightly wider.
- **Long trunk:** a few lines still take a long trunk, e.g. into OMOP `concept`. That is acceptable, since every
  route stays among the areas.
- **Router size:** the router is about 120 lines of plain Python with numpy, and builds both diagrams in seconds.

## Rubric
- Test written for the reported defect.
- Generated files rebuilt by `silver_erd.py`, not edited by hand.
- No telemetry rule applies: `diagrams/_build` is outside the package.
- `Closes #403`.
