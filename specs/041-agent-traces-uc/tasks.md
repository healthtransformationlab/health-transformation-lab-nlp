# Tasks: Coding-agent traces live in Unity Catalog, declared in the bundle (spec 041)

## US1 - the bundle declares the agent-trace schema and an experiment bound to it (#856)

- [x] T001 [US1] Failing test `python/tests/test_agent_traces_bundle.py`
- [x] T002 [US1] `databricks/resources/agent_traces.yml`: schema, grants, experiment with `trace_location`
- [x] T003 [US1] Pin `databricks/setup-cli@v1.22.1` in `ci.yml` and `deploy.yml`
- [x] T004 [US1] `databricks bundle validate -t dev` with CLI 1.22.1; record the output in the PR
- [ ] T005 [US1] After the merge deploy, read the experiment's trace location through the API and record it on #856

## US3 - the 414 traces and their assessments move there (#858)

- [ ] T006 [US3] Failing test `python/tests/test_migrate_agent_traces.py`
- [ ] T007 [US3] `databricks/notebooks/15_migrate_agent_traces.py` and the count table
- [ ] T008 [US3] Run it once on serverless; record the counts, the duration and the cost in the PR

## US2 - a committed loader, once per task-run (#857)

- [ ] T009 [US2] Fixture run folders and a failing test `python/tests/test_load_agent_traces.py`
- [ ] T010 [US2] `kaggle/load_agent_traces.py`; `AGENT_TRACE_EXPERIMENT` in `docs/telemetry.md`
- [ ] T011 [US2] Load the next finished Colab run and rerun it to show nothing new is written

## US4 - SQL views (#859)

- [ ] T012 [US4] List the span attribute keys from the migrated spans
- [ ] T013 [US4] Failing test `python/tests/test_agent_trace_views.py`
- [ ] T014 [US4] `databricks/setup/agent_trace_views.sql`; check the row and solved counts against US3

## Cleanup

- [ ] T015 Drop `scratch_uc_trace_probe` and `/Shared/scratch-uc-trace-probe` once US1's experiment holds a trace
