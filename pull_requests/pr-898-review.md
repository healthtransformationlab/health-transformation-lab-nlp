---
pr: 898
branch: feat/864-042-model-drivers-uc
title: "042 US2: model drivers load into Databricks"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator (adapted from pr-869-review)"
verdict: approve
---

# PR 898 review: the model ranking, its drivers and the LLM readers' traces and scores load into Databricks

Closes #864. Stacked on PR 865. Range: `feat/863-042-model-drivers..feat/864-042-model-drivers-uc`. Files:
`python/health_transformation_lab_nlp/model_drivers_load.py` (new), `python/scripts/75_load_model_drivers.py` (new),
`python/tests/test_load_model_drivers.py` (new), `model_drivers.py` (the Databricks section of the generated page),
`docs/model_drivers.md` (regenerated), `docs/results_storage.md`, `specs/042-model-drivers/spec.md`, `tasks.md`.

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none committed. The loader reads the workspace through the Databricks SDK's own auth and never prints
  a credential. A test builds a token-shaped string in memory and checks that no trace contains it.
- **Real data:** none. The notes in the traces are the synthetic review notes, and every trace is tagged
  `data_label = synthetic`.
- **Claims:** the PR's counts were read back from the workspace by SQL after the load, not from the loader's own
  output.

## Findings (verified)

1. **The first load failed after writing the 43 runs.** MLflow's Unity Catalog tracing needs a SQL warehouse id
   (`MLFLOW_TRACING_SQL_WAREHOUSE_ID`). The client now sets it from the warehouse it uses. The rerun skipped the 43
   runs as designed.
2. **Runs are idempotent per commit, not forever.** A rerun on a new commit logs another 43, so the experiment
   holds one set per commit loaded (86 now). That is intended (FR-006) and is said in the PR. Filter on
   `tags.git_commit_sha`.
3. **The span status was first set to ERROR for a wrong answer.** A wrong reading isn't a failed call, so the status
   is now always OK and correctness is an assessment.
4. **The page's example SQL indexed a VARIANT column as a map,** which failed on the warehouse. It now uses
   `variant_get`. All three example queries were run on the warehouse.
5. **The experiment isn't declared in the bundle** (spec 042 Risks). Its trace location can't change after creation,
   and declaring it now clashes with the name. An ADR should decide whether to adopt or rebuild it.

## Compliance

Spec first (042), issue #864 and `Closes #864`, branch `feat/864-...`. Typed column names. Every public function is
traced. Writes are idempotent (CREATE OR REPLACE for tables, a `trace_key` check for traces), with the batch key on
every row.

## Checks

- `test_load_model_drivers.py`: 7 passed. `test_model_drivers.py` and `test_telemetry_calls.py` also pass.
- Dev workspace: 8 tables, 9,796 rows, 0 columns without a comment, 669 traces, and correct shares equal to the
  leaderboard for all three LLMs.

## Verdict

Approve after PR 865 merges and this is retargeted to `main`.

---

Changed 2026-11-21: replacement PR for closed #869; base is now `main` after US1. Verdict remains approve. Merge under AGENTS.md #497; keep the head branch until US3–US5 retarget.
