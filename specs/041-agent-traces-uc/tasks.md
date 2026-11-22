# Tasks: Coding-agent traces live in Unity Catalog, declared in the bundle (spec 041)

## US1 - the bundle declares the agent-trace schema and an experiment bound to it (#856)

- [x] T001 [US1] Failing test `python/tests/test_agent_traces_bundle.py`
- [x] T002 [US1] `databricks/resources/agent_traces.yml`: schema, grants, experiment with `trace_location`
- [x] T003 [US1] Pin `databricks/setup-cli@v1.22.1` in `ci.yml` and `deploy.yml`
- [x] T004 [US1] `databricks bundle validate -t dev` with CLI 1.22.1; record the output in the PR
- [ ] T005 [US1] After the merge deploy, read the experiment's trace location through the API and record it on #856

## US2 - a committed loader, once per task-run (#857)

- [x] T009 [US2] Fixture run folders and a failing test `python/tests/test_load_agent_traces.py`
- [x] T010 [US2] `kaggle/load_agent_traces.py`; `AGENT_TRACE_EXPERIMENT` in `docs/telemetry.md`
- [ ] T011 [US2] Load the next finished Colab run and rerun it to show nothing new is written

## US3 - the 414 traces and their assessments move there (#858)

- [x] T006 [US3] Reload the 414 traces' run folders with the loader into `/Shared/coding-agent-runs`
- [x] T007 [US3] Score them again (code scorers, then the grounding judge) and write the count table
- [x] T008 [US3] Record the counts against the old experiment, the duration and the serverless cost in the PR
  (Reload + rescore done before ADR 0012; this PR adds the fallback migrate notebook and its test.)

## US4 - SQL views (#859)

- [x] T012 [US4] List the span attribute keys from the migrated spans
- [x] T013 [US4] Failing test `python/tests/test_agent_trace_views.py`
- [x] T014 [US4] `databricks/setup/agent_trace_views.sql`; check the row and solved counts against US3

## Cleanup

- [ ] T015 Drop `scratch_uc_trace_probe` and `/Shared/scratch-uc-trace-probe` once US1's experiment holds a trace
