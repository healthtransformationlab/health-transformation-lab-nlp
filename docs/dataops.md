# DataOps: the pipeline doctor

Spec 027. The layer that *operates* the pipelines: reads what ran, decides what kind of failure it is,
picks the next action from an allow-list, asks a person, and earns the right to act alone, one failure
class at a time. Agents recommend; code acts.

The idea: automated remediation is mostly a metadata problem. If every pipeline, run, dependency and
runbook entry is already a row in a table, the agent does not read logs, it reads tables, and the LLM
is the last ten percent.

## The four tables

| Table | One row per | Lives in | Locally |
|---|---|---|---|
| `dim_pipeline` | pipeline: owner, SLA, expectations, retry policy, runbook, outputs | `ops/pipeline_config.yaml`, deployed by the bundle | `doctor.load_config()` |
| `fact_pipeline_run` | run or step: timings, counts, schema hash, checks, error type, duration, cost | spec 014 spans + the Jobs API's run list | a pandas frame with the same columns |
| `dim_lineage_edge` | edge: what feeds what | `system.access.table_lineage` | `data/ops/lineage_edge.csv`, `doctor.load_lineage()` |
| `dim_runbook_entry` | failure class: ordered allowed actions, reversible, severity, escalation | `ops/runbook.yaml` | `doctor.load_runbook()` |

Plus `fact_remediation_decision`: one row per recommendation with the human's decision and whether it matched.
Column names follow AGENTS.md "SQL and data names".

## The six signals

`doctor.signals(run, history, config)`: freshness against the SLA, volume against the trailing median,
schema hash against the last ok run, share of checks passed, duration and cost against the trailing
median. Duration and cost are the OpenTelemetry metrics `pipeline.run.duration_seconds` and
`pipeline.run.cost_usd`, grouped by the common span header (`service.name`, `data_product_id`,
`environment`), so the full cost of a run across the stack is one query.

## The ladder

1. **Deterministic**: retry, rerun, hold downstream (already in the jobs and `runlog.py`).
2. **Classify** (`doctor.classify`, rules in order): the configuration-management classes first
   (`credential_expiry`, `vulnerability`, `deprecation`, `config_drift`, `config`), then `platform`,
   `schema_drift`, `volume_anomaly`, `quality_fail`, `cost_anomaly`, `source_late`, `duration_drift` (spec 036: a run
   over twice its trailing median length), `unknown`.
3. **Root cause** (LLM, `unknown` only; planned): run row, last N runs, lineage one hop, runbook entry.
4. **Recommend** (`doctor.recommend`): first allowed action, impact one hop down the lineage, severity,
   owner, templated notification. Never an action off the runbook's list.
5. **Automate** (`doctor.graduation`): a reversible class runs unattended after N matches with the human;
   two misses send it back. The rule is code, not a prompt.

## Measured against our own incidents

`data/ops/incident.csv` is the repo's own incident history as run rows (GPU not free, Python died,
Illegal seek, a short Kaggle run, new columns, a missing secret, a failed quality check, a run that hit
its budget); their timing and cost columns are ILLUSTRATIVE until a run table exists, and the eval does not
score them. `doctor.evaluate` scores the doctor on them; `doctor.ablation` (the function; the docs call it the switch-off test) hides each table in turn: it re-runs the
eval with the config table, the typed conventions, lineage, the metrics or the run history hidden, one at a
time, and whatever drops is what that piece contributed.
Results and reading: spec 027, "The ablation". Nine incidents is a small set and the intervals say so.

Adding an incident: one row in `incident.csv` with the class, the action taken, whether it was reversible,
and where it is written down. If the rules get it wrong, that is a failing test and a rule to add.

```bash
cd python && python - <<'EOF'
from health_transformation_lab_nlp import doctor
cfg, rb, inc, lin = doctor.load_config(), doctor.load_runbook(), doctor.load_incidents(), doctor.load_lineage()
print(doctor.evaluate(inc, cfg, rb, lin).round(2).to_string(index=False))
print(doctor.ablation(inc, cfg, rb, lin).round(2).to_string(index=False))
EOF
```

## Forecasting and alert batching

The same tables predict failures before they happen: the secrets register's expiry dates, the dependency
inventory's end-of-support dates (`ops/dependency_inventory.csv`), and the run table's cost, duration,
volume and schema trends, each giving a predicted class, a date and a severity from the days ladder.
Alerts are routed by that ladder and batched into one digest per owner per period, each problem once.
Both live in the shared package (`pipeline-doctor` `forecast.py`, `digest.py`); this repo supplies the two
files. The inventory has no invented dates: a model or platform without a published end-of-support date
says `unknown`.

The `pipeline_digest` job (`14_pipeline_digest.py`, daily at 07:32 UTC once unpaused, the weekly digest on
Mondays) puts this together. It collects every alert this repo raises:
- failing budget and target checks from `dq_check` (spec 036);
- the doctor's SEV3 and SEV4 recommendations no one has decided yet;
- the forecaster's rows.

It builds the digests with the package's `digest` and writes `fact_digest_item` and `fact_digest_message`. Two
Databricks SQL alerts, one per period, email the day's message to `digest_email` (from the `ALERT_EMAIL` GitHub
variable): Databricks sends it, so there is no mail credential. A SEV1 or SEV2 forecast fails the run, so the job's
failure email pages the owner, as the doctor does. An item that was in the previous digest is marked a repeat; a
repeating SEV2 is flagged for review.

## The job

`Pipeline doctor` (bundle key `pipeline_doctor`, notebook `databricks/notebooks/13_pipeline_doctor.py`,
logic in `doctor_job.py`) is deployed to dev, uat and prod **paused**: running or unpausing it is the
owner's decision. Each run:

1. checks its settings first and fails naming a bad one; then makes one cheap Jobs API call to check it can list
   job runs;
2. reads 60 days of completed job runs from the Jobs API (`jobs.list_runs`; Free Edition can't grant
   `system.lakeflow`, issue 524), keeps this bundle's jobs, and fills counts, schema hash, checks and cost from the
   span export when `doctor_span_table` names one (one row per run, `fact_pipeline_run`'s columns; the export
   from Application Insights isn't built yet, so without it most failures carry only a termination code and
   often classify as `unknown`);
3. writes `fact_pipeline_run`, `fact_pipeline_signal` (the six signals for each run in the last
   `doctor_lookback_days`) and `fact_remediation_decision` (one per failed run), each delete-then-append by
   `run_id`, every row stamped with the doctor's own `doctor_run_id`;
4. fails with the drafted notification when there is a **new** SEV1 or SEV2 decision, so the job's failure
   notification reaches the owner; SEV3 and SEV4 wait in the table for the digests. It never pages twice for
   the same run, and it never diagnoses its own runs.

Settings (bundle variables, the same names in every target): `judge_endpoint` and `judge_max_usd` (the
root-cause rung, shared with the judge scorecard's budget; the rung itself is US6 and isn't called yet),
`doctor_lookback_days` (7) and `doctor_span_table` (`none`). Approval is a run parameter until an approval
UI exists: run the job with `decisions` = `run_id=action_code,...` and `decided_by`; an action off the
runbook's list for that run's class fails the run. Decisions are carried forward and decide graduation. The
job acts on nothing.

The **Pipeline doctor** dashboard (built by `python/scripts/42_build_dashboards.py`) shows each pipeline's
latest signals, runs by status, failures by class and every recommendation with its decision.

## Next

The root-cause rung with its judge, the span export, and dropping this repo's copy of the module for the package
(it needs `duration_drift` and the runbook's fix text upstream first), so a second project of a different shape can
adopt it and report the same metrics (spec 027 US6, US7, T023).
