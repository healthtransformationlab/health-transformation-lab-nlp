---
pr: 357
branch: spec/345-027-pipeline-doctor
title: "Add the pipeline doctor: DataOps on the run tables (spec 027)"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator (self-review by the authoring session against .claude/review-rubric.md; no separate reviewer subagent was run, so the owner should read §Findings before merging)
verdict: approve with one should-fix
---

# PR Review: Add the pipeline doctor: DataOps on the run tables (spec 027)

## Summary
Spec 027 adds the DataOps layer that spec 014 named as "next": four metadata tables, six signals, a
rules-first remediation ladder, graduation to automatic, an evaluation on the repo's own nine incidents and a
switch-off test of what each table contributes. Pure pandas, 31 tests, full suite green. The spec's one
quantitative claim ("most of what breaks in production is visible in metadata before anyone reads a log")
is stated as a measured share, with intervals, not as a premise. Verdict: approve, with one should-fix on
the incident set's provenance text.

## Scope of Change
- Files changed: 11 (+1,240 / -1)
- Areas touched: specs, package (`doctor.py`), tests, `ops/` YAML, `data/ops/` CSV, docs
- Commits:
  - a1b148f Add the pipeline doctor: DataOps on the run tables (spec 027)
  - 89ebeca Spec 027: configuration-management failure classes first; measure the share, don't assume it
  - edec598 Spec 027: record the issue number next to each user story (#345-#351)
- Range reviewed: `origin/main..edec598`

## CI Status
| Check | Status |
|---|---|
| python | pending on GitHub; 1,099 passed, 15 skipped locally on the branch head |
| postgres, r-parity, bundle | pending; untouched (no table writes, no R-side metric, bundle files unchanged) |

## Secrets, PHI and Claims Scan
Clean. The diff holds no credentials (grep for Databricks, Hugging Face, Application Insights and AWS token
shapes: no hits), no note text (the incident rows carry error types, counts and durations only; a test
asserts `doctor.py` never imports the note modules), and no organization claim (the spec and docs say
"personal learning project" and name no employer; the org-reference test passes).

## Strengths
- The claim is tested, not asserted: `doctor.ablation` hides each table in turn and the spec reports the
  drop with Wilson intervals on nine incidents, and says nine is small.
- Names follow AGENTS.md "SQL and data names" throughout (`dim_`/`fact_` tables, typed suffixes), and the
  spec's constitution check names the test that enforces the no-notes rule.
- The configuration-management classes (credential expiry, vulnerability, deprecation, config drift) sit
  first in the rule order, matching AGENTS.md "Configuration and secrets" ("most production failures are
  configuration").
- Graduation to automatic is code with a stated rule (N matches; two misses revert), not a prompt.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`data/ops/incident.csv` timestamps and costs are illustrative, and the file does not say so.** The
   nine incidents are real (each `recorded_in_text` points at the spec, doc or job definition that records
   it), but their `started_ts`, `duration_seconds` and `cost_usd` values were filled in to make the rows
   complete, not read from a run table. Add a header comment or a `is_simulated`-style column (constitution
   IV: simulated is labelled simulated) and say the same in the spec's "Evaluation" section. The class and
   action columns, which the eval scores, are not affected.

### 🔵 Nits / suggestions (Minor)
1. `doctor.ablation` is the function name; the docs now call it a switch-off test. Keep both words together
   at first mention in `docs/dataops.md` so a reader can find the function.
2. `baseline_history` is labelled simulated in its docstring and rows (`data_label_code = simulated`); the
   spec's ablation table could repeat "SIMULATED baseline" in its caption.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | run metadata only; no-notes import test |
| No organization claims; vendors cited | ✅ | personal project wording; no vendor figures |
| Test first | ✅ | 31 tests; tasks.md lists failing-test tasks before implementation |
| Python and R in parity | ✅ | no reported metric or label changed |
| Simulated is labelled simulated | 🟡 | baseline history yes; incident timings/costs see should-fix 1 |
| Seeds fixed | ✅ | no sampler added |
| Paths | ✅ | `paths.REPO_ROOT` |
| Spec for big changes | ✅ | specs/027 with spec, plan, tasks; issues #345-#351 |
| Prices | ✅ | `cost_usd` values are illustrative, see should-fix 1 |
| Deck figures | ✅ | no slides touched |
| Commits | ✅ | imperative, body says why, co-author trailer |
| Docs | ✅ | `docs/dataops.md`; `docs/telemetry.md` links it |
| Configuration | ✅ | no settings added; `ops/*.yaml` are data the doctor reads |
| Secrets register | ✅ | no credential made or used |
| Idempotent writes | ✅ | no table writes in this PR (the job is US5, planned) |
| Alerts | ✅ | runbook entries carry SEV level, owner and action |

## Test Coverage
`python/tests/test_doctor.py`: signals with and without history; each class including the four
configuration-management ones; precedence (credential over volume); never-started → source_late; config
covers every bundle job; recommend (first action, retry exhaustion, allow-list, impact one hop, notification
without row data); graduation (N matches, two misses, fewer than N, non-reversible); incident set and
lineage coverage; evaluate shape and intervals; ablation directions; no-notes import. Not covered: a real
run table from a workspace (US5).

## Addendum (2026-10-29, later commit)
US8 (forecasting and alert batching) was added to the spec with `ops/dependency_inventory.csv`. Checked: the
inventory carries no invented dates (two Python end-of-life months cite their PEPs; model and platform rows
say unknown); the credential forecast reads expiry dates only and never a value. No test or metric change in
this repo; the code lives in the shared package.

## Verdict
Approve with one should-fix: label the illustrative timing and cost values in `incident.csv`. Everything
else meets the rubric. Merge when CI is green and the owner has read the findings.
