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
| `fact_pipeline_run` | run or step: timings, counts, schema hash, checks, error type, duration, cost | spec 014 spans + `system.lakeflow.job_run_timeline` | a pandas frame with the same columns |
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
   `schema_drift`, `volume_anomaly`, `quality_fail`, `cost_anomaly`, `source_late`, `unknown`.
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

## Next

The job (`pipeline_doctor`, after a failed run), the root-cause rung with its judge, and extracting the
module into its own package so a second project of a different shape can adopt it and report the same
metrics (spec 027 US5-US7).
