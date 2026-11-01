---
pr: 238
branch: spec/233-027-study-gold-names
title: "Name the Benchmark and GPU encoder tables by the gold conventions (spec 027)"
author: jcbowyer
reviewed_at: 2026-10-28
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: Name the Benchmark and GPU encoder tables by the gold conventions (spec 027)

## Summary
Spec 027 brings the last gold tables under AGENTS.md "SQL and data names":
- `labeled_notes` becomes `dim_study_note`.
- `benchmark_results` becomes `benchmark_metric`, replaced per job run instead of plain append.
- The GPU encoder job writes `fact_prediction` by `replace_batch` per (run, method) instead of appending to
  `encoder_gpu_predictions`.

Both tables are declared in `gold_names.py` and `gold_model.py`, the diagrams are regenerated, and the migration
carries dev's existing tables. The reviewer ran the actual `score()` output and dev's real column lists through the
mapping and the migration plan. No Critical or Important findings; two Minor ones are fixed in this push. Approve
with nits.

## Scope of Change
- Files changed: 29 (+~400 / -52, of which 4 PNGs and 2 drawio files are generated)
- Areas touched: python, databricks, docs, specs, diagrams, AGENTS.md
- Commits: 6ef6309 Name the Benchmark and GPU encoder tables by the gold conventions (spec 027); review commit
- Range reviewed: `origin/main...6ef6309`, then the review fixes

## CI Status
| Check | Status |
|---|---|
| Test every change (Python, R parity, bundle) | running on 6ef6309; re-runs on the review push |
| Check the branch name and issue link | success |

## Secrets, PHI and Claims Scan
Clean. Synthetic study tables only; no credentials, real data or organization claims.

## Strengths
- `to_gold` renames all columns at once, so `job_run_id`→`run_id` and `run_id`→`model_run_id` don't collide.
  Checked on a two-model concat: 24 in, 24 out, no NaT.
- The migration's new text→timestamp step for `_ts` columns is what lets `benchmark_results.timestamp` merge into a
  timestamp column.
- The GPU rows follow the MedGemma reader's pattern, which Load results already respects: databricks file versions
  count as loaded, and its delete excludes `source_code = 'databricks'`.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `08_encoder_gpu.py`: a blank line split the stdlib imports, adding a ruff I001. **Fixed.**
- Rows the migration carries from `benchmark_results` have null `run_id`, `run_ts` and `git_commit_sha`: the old
  table has no source for them. This is harmless because `model_run_id` keys them and no delete by `run_id` matches
  null. **Documented** in `docs/gold_tables.md`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims | ✅ | |
| Test first | ✅ | 9 tests failed before the code |
| Python and R in parity | n/a | no label, scoring, reliability or cost change |
| Spec for big changes | ✅ | `specs/027-study-gold-names/` (spec, plan, tasks); issue #233 |
| Configuration | ✅ | no new settings; jobs pass `{{job.run_id}}` |
| Idempotent writes | ✅ | the two plain appends replaced by `replace_batch`; rows carry `run_id`, `run_ts`, `git_commit_sha` |
| Docs | ✅ | gold_tables, deployment, r/README, AGENTS.md `_mm` |
| Commits | ✅ | |

## Test Coverage
`cd python && pytest -q tests`: 942 passed, 15 skipped. New tests check:
- that the frames become their declared tables, with the migration plan for the old names;
- `run_prediction_rows`;
- that notebooks 01 and 08 never plain-append;
- that the jobs pass `run_id`;
- the `_mm` suffix.

Not run: the Benchmark and GPU encoder jobs on Databricks.

## Verdict
approve-with-nits (both nits fixed). Merge when CI is green. The next Load results copies dev's `labeled_notes`
(754 rows) and `benchmark_results` (36 rows, 3 runs).
