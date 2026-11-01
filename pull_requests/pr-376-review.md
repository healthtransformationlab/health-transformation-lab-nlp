---
pr: 376
branch: feat/369-029-opendental-schemas
title: "029: declare the <layer>_opendental_perio schemas"
author: jcbowyer
reviewed_at: 2026-10-30
reviewer: coordinator (small, declarative change; no subagent needed)
verdict: approve
---

# PR Review: 029: declare the <layer>_opendental_perio schemas

## Summary
This PR does spec 029 task T004. It adds the `opendental_perio` schema family to `schemas.LAYERS`, so
`landing_`, `bronze_`, `silver_` and `gold_opendental_perio` exist. It also declares the four schemas and a managed
landing volume `data` in the bundle, with `prevent_destroy`, and brings spec 029, its plan and tasks, and AGENTS.md
in line with the new names. Silver is now described as Open Dental's tables, cleaned, with the same names and
layout, plus the per-tooth table and `tooth_loss_dq_check`. Verdict: approve.

## Scope of Change
- Files changed: 9 (+77 / -15)
- Areas touched: python (schemas, tests), databricks bundle, specs, AGENTS.md
- Commits:
  - 7d64475 Declare the Open Dental schemas <layer>_opendental_perio
- Range reviewed: `origin/main..7d64475`

## CI Status
| Check | Status |
|---|---|
| python | pending; 1115 passed, 16 skipped locally |
| bundle | pending; `test_bundle` checks the schemas and volume locally |
| postgres, r-parity | pending; untouched by this change |

## Scans
- Secrets: none.
- PHI / real data: none. The schemas hold synthetic data only, and their comments say so.
- Organization claims: none. Open Dental is named only as the public source of the table format (research.md).

## Repo rules
| Rule | Result |
|---|---|
| Test first | Schema and bundle tests were changed first and failed before the code changed |
| Benchmark order | `perio_bench`, `oral_health_bench` and `access_bench` keep their order and come first; `test_bench_order` now checks the benchmarks only, so another schema family doesn't count as a benchmark |
| Databricks names | Same in every target, with no `dev_` prefix; `<layer>_<family>` as in spec 022 |
| Legacy schema names | The old OMOP name stays out of code and tests (`test_no_legacy_schema_names`); spec 029 mentions it once, as history, which `specs/0` allows |
| Spec, issue, branch | Refs #369; branch `feat/369-029-opendental-schemas` |

## Findings
None blocking.

- 🔵 Nit (pre-existing, not in this diff): `ruff check tests/test_bundle.py` reports I001 (import order) at line
  307, in `test_every_model_that_can_be_scored_has_a_plain_name`. It is not on a line this PR changes, so it is
  left as it is.

## Verdict
Approve once CI is green.
