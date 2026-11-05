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
- [x] T007 Failing tests, then `doctor_job.read_billing`, `billing_costs` and `merge_billing` onto the timeline runs
  (before the span export, which wins); one warning when the tables can't be read. A DBU column waits for a suffix
  (DBUs are fractional: not `_count`)

## US3 - Cost and duration recommendations, and the view #570
- [x] T008 Failing tests, then `duration_drift` in `doctor.classify` (over 2x the trailing median, no other class,
  SEV4) and the runbook's `fix_text` (file and setting) for it and `cost_anomaly`, in every recommendation's text
- [ ] T009 Cost per resolved task on the grader dashboards and in Genie

## US4 - The data-quality report covers spend and speed against budgets and targets #576
- [x] T010 Failing tests, then `ops/budgets.yaml` (each budget and target with its period, limit, owner and action)
  and `governance.py`: the budget and target checks and the cost data's own checks, in `dq_check`'s columns plus
  `measure_text`, added to `dq_check` by Load results; agent runs carry `run_ts` for the weekly allowance
- [ ] T011 Routing: a failing budget, or a cap that stopped a run, to the daily digest (SEV3); drift alone stays SEV4
  (FR-016)
- [ ] T012 A Governance page on the grader dashboards and Genie instructions from the same rows (FR-017)
