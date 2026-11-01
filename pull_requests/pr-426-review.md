---
pr: 426
branch: feat/350-027-doctor-job
title: "027 US5: the pipeline doctor runs as a job and writes its decisions"
author: claude (agent session)
reviewed_at: 2026-11-01
reviewer: coordinator verification against .claude/review-rubric.md (no separate reviewer subagent in this session)
verdict: approve-with-nits
---

# PR Review: 027 US5: the pipeline doctor runs as a job and writes its decisions

## Summary
Adds the Pipeline doctor job (T010), its notebook and the pandas module behind it (T011), and a Pipeline doctor
dashboard (T012). The job reads `system.lakeflow.job_run_timeline`, optionally merges a span export, and writes
three new gold tables, each delete-then-append by `run_id`. Each failed run gets a recommendation from the
runbook allow-list. A new SEV1/SEV2 decision fails the run with the drafted notification; SEV3/SEV4 wait for
the digest. The job is created paused and runs nothing on deploy. Tests and CI (including `bundle`) are green.
Verdict: approve with nits. The nits are design limits that only a real run will show. None of them blocks.

## Scope of Change
- Files changed: 25 (+~2250 / -15, mostly the generated dashboard JSON and ERD sources)
- Areas touched: python, databricks, diagrams, ops, docs, specs
- Commits: cbf49a8 027 US5: the pipeline doctor runs as a job and writes its decisions; 051b5cd Merge origin/main
  into feat/350-027-doctor-job; plus this review commit (also fixes a caller-dict mutation in `diagnose`)
- Range reviewed: `1964f71..HEAD`

## CI Status
| Check | Status |
|---|---|
| python | success |
| bundle | success |
| postgres | success |
| r-parity | skipped (no R or metric change) |
| check (PR conventions) | success |

## Secrets, PHI and Claims Scan
- Secrets: clean. No tokens or keys in the diff, and the notebook never reads `DATABRICKS_TOKEN` (a test asserts it).
- PHI / real data: clean. The doctor reads run metadata only. `merge_spans` refuses any column naming a note,
  and a test checks the module never imports note code.
- Organization claims: clean. No company claims, and none of the forbidden names.

## Strengths
- Every decision the notebook makes lives in `doctor_job.py` with 30+ unit tests. The notebook only reads and writes.
- Column types are declared once (`doctor_job.TABLES`), and tests check them against `gold_model.py` and `gold_names.py`.
- Settings are checked before any work, and each failure names the setting. System-table access is probed
  before the expensive reads.
- Paging is deduplicated by run, so a rerun of the doctor never pages twice. It skips its own runs.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- `databricks/notebooks/13_pipeline_doctor.py`: notifications are only as good as the job's notification
  settings. The run fails on a new SEV1/SEV2, but the job has no `email_notifications` or notification
  destination, because no address or destination id can be committed. Verified by reading `jobs.yml`. Fix:
  the owner adds `email_notifications.on_failure` (or a destination) per environment before unpausing.
- `doctor_job.timeline_runs`: without the span export, a failure carries only its termination code
  (e.g. `RUN_EXECUTION_ERROR`). That usually classifies as `unknown` (SEV2), so most failures will page until
  the export exists. Verified in `test_every_recent_run_gets_its_signals_and_every_failure_a_decision`. This is
  documented in `docs/dataops.md` and printed as a warning by the notebook.

### 🔵 Nits / suggestions (Minor)
- `delta.replace_keys` passes object-dtype pandas columns with an explicit DDL to `createDataFrame`. This was
  tested against a fake Spark only; the first real run on serverless (Spark Connect, Arrow) is the true check.
- `diagnose` mutated the caller's `decisions` dict. **Fixed in this commit** (works on a copy).
- The gold ERD PNGs were not re-rendered (no drawio renderer here); the `.mmd`, `.drawio` and `data_model.md`
  sources were regenerated.
- One pre-existing import-order ruff error remains in `python/tests/test_bundle.py`
  (`test_every_model_that_can_be_scored_has_a_plain_name`). It was already on main and this PR leaves it alone.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | scan clean |
| Synthetic only, no PHI | Yes | run metadata only; note columns refused |
| No organization claims | Yes | |
| Test first | Yes | bundle, delta, job-module and dashboard tests written and failing first |
| Python and R in parity | n/a | no label, scoring or metric change |
| Simulated labelled | Yes | the dashboard test fixture uses the SIMULATED baseline history, test only |
| Paths | Yes | `paths.REPO_ROOT` via `doctor` / `doctor_job` |
| Spec for big changes | Yes | spec 027 US5; tasks T010-T012 ticked; plan notes notebook 13 |
| Configuration | Yes | three bundle variables, same in every target; `judge_max_usd` replaces the scorecard literal; the PR says dev/uat/prod get the job created, paused |
| Secrets register | n/a | no credential; a `system.lakeflow` SELECT grant is needed (owner) |
| Idempotent writes | Yes | delete-then-append by `run_id`; rows carry `doctor_run_id`, `loaded_ts`, `doctor_git_commit_sha` |
| Alerts | Yes, with the 🟡 above | severity from the runbook; SEV1/2 now, SEV3/4 for the digest; owner from config |
| Retries | Yes | `max_retries: 0`, explained; 30-minute timeout |
| SQL and data names | Yes | `test_sql_conventions.py` passes on the three new tables |

## Test Coverage
Run locally with `PYTHONPATH` pinned to the worktree: `python -m pytest -q tests` gave 1313 passed, 15 skipped
after merging main. `42_build_dashboards.py --check` is clean, and `ruff check` on the changed files is clean
except the pre-existing error above. Not covered: the notebook's Spark and system-table calls, which only a
real run exercises. `databricks bundle validate` passed in CI's `bundle` check.

## Verdict
Approve with nits. Before unpausing or running the job, the owner should grant `system.lakeflow` read access
to the job's identity and add a failure-notification destination.
