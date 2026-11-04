# PR 571 review: spec 036, what each task costs

Refs #568 #569 #570. A spec only, reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Spec number: 036 is free on `main` and on open PRs (564 and 530 only).
- One issue per story, its number next to each story's heading.
- Wording, org-name and bench-order tests pass on the new files.
- Facts the spec states about today's code, checked:
  - `doctor_job.timeline_runs` sets `cost_usd` to NaN;
  - `merge_spans` fills it only from an optional `span_table`, and nothing in the repo emits `pipeline.run.cost_usd`;
  - `doctor.classify` has `cost_anomaly` at `COST_BOUND = 3.0` and no duration rule;
  - the agent run table (`60_kaggle_agent.py`) has seconds but no GPU-hours or cost.
- Outside figures are settings with their source and date, not facts:
  - the Kaggle allowance ("about 30 hours, varies"; third-party guides disagree on the reset time);
  - the T4 price ($0.69 median per GPU-hour, getdeploying.com, Oct 26 2026), always labelled an estimate.

## Findings
- Not blocking: US1 depends on Free Edition exposing `system.billing`. The spec makes that its first task and
  works with empty costs if it doesn't. If the check fails, US1 shrinks to the warning and US3 runs on agent
  costs alone.
- Not blocking: the duration bound (2x the trailing median) is a default; the plan may tune it against run history.

Nothing blocking. A spec changes no data, runs nothing and publishes nothing, so it can merge when CI is green.
