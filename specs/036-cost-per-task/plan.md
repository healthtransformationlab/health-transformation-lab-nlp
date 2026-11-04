# Plan: what each task costs, and spending less

## US2 first (#569): the Gemma run is the one about to spend real allowance

- `ops/cost_settings.yaml`: the Kaggle weekly allowance and the T4 price, each with a value, a source and the date it
  was read (FR-005). Required: a malformed file stops the runner at once.
- `python/health_transformation_lab_nlp/agent_cost.py`:
  - `load_settings`;
  - `task_cost`: allowance hours (session time, as Kaggle counts it), GPU-hours (by GPU count, as a cloud bills)
    and an estimated cost with its basis;
  - `expected_seconds`, `plan_under_cap`.
- `python/scripts/60_kaggle_agent.py`:
  - each kernel's session time, from push to output (queue and boot included: the API gives no split, so it errs
    high), and its script time from the kernel's own timestamps;
  - the cost columns on every row, failed kernels included;
  - `--ids all` (every gated task the oracle resolves, without a row yet), and `--max-gpu-hours`;
  - the queue: cheapest expected first, and among tasks with no earlier run, the smaller reference fix first. Not
    shown to the agent: it only orders the run.
- **Bias, stated:** cheapest-first runs the easier tasks first, so a run its cap stops reports its rate over the
  tasks it ran, never over the whole set.
- Gold: `fact_agent_task_run` in `diagrams/_build/gold_model.py`, loaded from `data/tasks/agent_runs/` by Load results
  (delete-then-append by model and settings), with table and column comments (spec 034). It comes in the PR after the
  runner's, before the full run's results are committed.

## US1 (#568): DBUs per job run

- First, one query in the dev workspace: can the job's identity read `system.billing.usage` and
  `system.billing.list_prices`? The answer decides US1's size and goes in this plan.
- `doctor_job.billing_costs(usage, prices)`: one row per job run, its DBUs summed over SKUs and priced at the list
  price in effect at usage time. Joined onto the timeline runs by `job_run_id`, so `cost_usd` is filled before
  `merge_spans`; a span value still wins.
- Missing tables: one warning, and costs stay empty (FR-002, FR-003).

## US3 (#570): recommendations and the view

- `doctor.classify`: `duration_drift` (duration over 2x the trailing median, no other class), SEV4, after
  `cost_anomaly`.
- `ops/runbook.yaml`: allow-listed actions for `cost_anomaly` and `duration_drift`, each naming the file and setting.
- Grader dashboards (spec 019) and a Genie space: cost per resolved task by model, tier and settings, with
  "estimated" on the cost; `calib:` and `sim:` rows left out (FR-012).
