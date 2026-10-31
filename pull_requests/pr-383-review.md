---
pr: 383
branch: feat/369-029-open-dental-extract
title: "Generate the synthetic Open Dental extract and load it into Databricks"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve-with-nits
---

# PR Review: Generate the synthetic Open Dental extract and load it into Databricks

## Summary
The PR adds a seeded generator for the 28 Open Dental tables, the silver cleaning, and a job that loads bronze and
silver. The deploy starts the job when bronze is empty. The tests cover:
- determinism and the untouched global random state;
- the columns against the silver model;
- keys and foreign keys;
- that the truth stays out of the extract;
- the declared diagnosis rates and the list switch;
- plan copies;
- Open Dental's value conventions;
- the job, the notebook and the deploy step.

The job hasn't run on Databricks yet; its first run is after the merge. Approve, with nits.

## Secrets, PHI and Claims Scan
- Secrets: clean. No credential is added; the job uses the bundle's identity.
- PHI / real data: clean. Every row is generated. Offices, sites, addresses and postcodes are visibly synthetic
  ("Synthetic Dental Clinic A", "Example Avenue", state "ZZ").
- Organization claims: clean. No practice is named. Medication RxCUIs, SNOMED, ICD and CDC race codes are public
  vocabulary codes.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- **Spark conversion is untested.** `12_load_open_dental.py` hands pandas nullable `Int64` columns (silver
  `periomeasure`) to `spark.createDataFrame`. Recent Databricks runtimes accept them through Arrow, but nothing here
  can run that. If the first run fails on it, cast those columns to `double` in `save()`.
### 🔵 Nits / suggestions (Minor)
- **An unused provider row.** `build` creates the first general dentist, then replaces it in the list with a
  periodontist, so one provider is never assigned to a patient. Harmless.
- **Few extractions.** With the default rates, extractions during the record are rare (about 350 completed per
  2,000 patients). Spec 029 US3 will show whether that's enough to train on; the rates are parameters.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets, PHI or organization claims | Yes | |
| Test first | Yes | each test file failed before its code |
| Seeds fixed | Yes | `seed=42` and `Params` defaults; own stream |
| Telemetry | Yes | every public function is `@traced`; the row-builder is private |
| Configuration | Yes | the job checks its settings before work; parameters come from the bundle resources; the PR names the environments |
| Idempotent writes and batch keys | Yes | overwrite per run; `run_id`, `run_ts`, `git_commit_sha` on every row |
| Alerts and ops | Yes | `ops/pipeline_config.yaml` entry |
| Python and R in parity | n/a | no label or scoring rule yet (T006 brings the R twin) |
| Branch and issue | Yes | `feat/369-…`, `Closes #369` |

## Test Coverage
`cd python && python -m pytest -q tests`: 1141 passed, 16 skipped.

## Verdict
Approve with nits. Merge after #382, once CI is green. Then check the first "Load Open Dental" run.
