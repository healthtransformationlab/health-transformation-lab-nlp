---
pr: 423
branch: feat/201-024-periodx-chart
title: "024 US1: PerioDx Diagnoser: status, stage, extent and grade from the chart as Patel et al. 2022 Fig. 2"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent available in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 024 US1: PerioDx Diagnoser from the chart (Patel et al. 2022, Fig. 2)

## Summary
This adds `periodx.chart_status`, the paper's chart rule tree, as a function from a synthetic chart to:
- the figure's status box;
- stage I–IV;
- extent;
- grade, with an explicit `not_assessable`.

Every threshold is a named constant citing Fig. 2. The three open arrows use the readings spec 024 records. A
documented adapter maps the repo's worst-site summary chart to the figure's tooth counts. The base-R twin agrees
on every value of 6,000 seeded cases, run locally with R. Nothing reads the Diagnoser into a dataset yet, so every
committed output is unchanged.

Verdict: approve with nits. The nits are about disclosure, not correctness.

## Scope of Change
- Files changed: 8 (+932 / -5); no generated data committed (the parity cases go to the git-ignored `data/labels/`)
- Areas touched: python, r, docs, specs
- Commits:
  - 9de1a80 Add failing tests for the PerioDx Diagnoser (Patel et al. 2022, Fig. 2)
  - 13a7d36 Find status, stage, extent and grade in a chart as Patel et al. 2022 Fig. 2
- Range reviewed: `origin/main (1964f71)..13a7d36`

## CI Status
| Check | Status |
|---|---|
| python | pending at review time; local run green (below) |
| r-parity | pending; the spec 024 block passed locally under R |
| postgres, bundle | pending; not touched by this PR |

## Secrets, PHI and Claims Scan
- **Secrets:** clean. No tokens, keys or credentialed URLs in the diff.
- **PHI / real data:** clean. Every chart is hand-built or seeded synthetic; the paper's data is named as never coming in.
- **Organization claims:** clean. The paper is cited by author, journal, DOI and licence, and only for its method.

## Strengths
- Fig. 2 is followed box by box, with each reading in one place (`FIG2_CONSTANTS`). A test checks that every
  constant cites the figure.
- Tooth loss is checked before stage I/II on every path, as the spec requires (acceptance 3 tested).
- Partial-data fallbacks are explicit, and they are reported only when they could have changed the branch taken.
  For example, a missing furcation class doesn't count once bone loss > 33% already holds.
- The names follow AGENTS.md "Words": `chart_status` and "finds status", with "Diagnoser" only as the paper's own
  name.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `periodx.py` `chart_from_summary`: recession is never in the summary chart.
  - **Effect:** every summary chart that answers no to the bone-loss and CAL questions lists `recession_teeth` as
    partial, so "decided on partial data" will be high for healthy and gingivitis visits.
  - **Verification:** `write_parity_cases` puts 59% of the seeded cases in `partial`.
  - **Fix:** honest as it is. US3's completeness table should say that this count reflects the summary chart, not
    missing care.
- `PerioDxChart.__post_init__` checks BOP and the bone-loss category, but not negative PD or CAL. `labels.PerioChart`
  does. This is low risk, since inputs come from the generator.
- `DETECTABLE_BL_PCT = 0`: the synthetic gingivitis charts carry 0–10% bone loss, so many enter the reduced
  periodontium branch. Their label is still gingivitis or healthy unless a 4 mm pocket exists. It is listed as an
  owner decision in docs/periodx.md.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | hand-built and seeded charts |
| No organization claims; vendors cited | ✅ | paper cited with DOI |
| Test first | ✅ | tests committed before the code (9de1a80) |
| Python and R in parity | ✅ | `r/R/14_spec024.R` + `test_parity.R` block; 0 differences locally |
| Simulated is labelled simulated | n/a | no results reported |
| Seeds fixed | ✅ | `write_parity_cases(seed=24)` |
| Paths | ✅ | `LABELS_DIR` |
| Spec for big changes | ✅ | spec 024, tasks T001–T003 ticked |
| Words rule | ✅ | `test_wording.py` passes on the new files |
| @traced | ✅ | `test_telemetry_calls.py` passes |
| Commits | ✅ | imperative, body says why, trailers |
| Configuration / secrets register / idempotent writes / alerts | n/a | none touched |

## Test Coverage
- `tests/test_periodx.py` (77 tests): every Fig. 2 branch, all three acceptance scenarios, grade paths and
  boundaries (0.25 and 1.0), extent pairs, categories, fallbacks and the summary adapter.
- Run locally:
  - `python -m pytest -q tests`: 1324 passed, 15 skipped;
  - `ruff check` on the changed files: clean;
  - the spec 024 block of `r/tests/test_parity.R` under R: 4,000 + 2,000 cases with 0 differences.
- Not run: the full `test_parity.R`, which needs all `make_parity_inputs.sh` outputs; CI runs it.

## Verdict
Approve with nits. Nothing has to change before merge.
