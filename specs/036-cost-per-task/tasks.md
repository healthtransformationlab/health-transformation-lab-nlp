# Tasks: what each task costs, and spending less

**Tests**: required (test-first).

## US2 - Every coding-agent task carries its tokens, GPU-hours and an estimated cost #569
- [x] T001 Failing tests: settings with sources, task cost, expected time, the cap; the runner's cost columns, a
  failed kernel's session, the queue order
- [x] T002 `ops/cost_settings.yaml`, `agent_cost.py`
- [x] T003 `scripts/60_kaggle_agent.py`: session and script time, cost columns, `--ids all`, `--max-gpu-hours`
- [x] T004 Gold: `fact_agent_task_run` (gold_model.py, gold_names.py, `grader_tables.agent_tables`), overwritten by Load results from `data/tasks/agent_runs/`, with its comments
- [ ] T005 The full Gemma run under a cap the owner sets (spec 035 T005; owner's go-ahead)

## US1 - Every Databricks job run carries its DBUs and cost #568
- [x] T006 Check: can the job's identity read the billing system tables in dev? No: account admins only (plan.md);
  the jobs' service principals need a grant from an account admin (owner)
- [ ] T007 Failing tests, then `doctor_job.billing_costs` and the join onto the timeline runs; the warning when
  the tables are missing

## US3 - Cost and duration recommendations, and the view #570
- [ ] T008 Failing tests, then `duration_drift` in `doctor.classify` and the runbook actions
- [ ] T009 Cost per resolved task on the grader dashboards and in Genie
