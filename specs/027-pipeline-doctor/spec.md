# Feature Specification: the pipeline doctor (DataOps: failure detection, recovery, data-quality triage)

**Feature Branch**: `027-pipeline-doctor`

**Created**: 2026-10-28

**Status**: draft; US1-US4 and the ablation have a first implementation (`doctor.py`, pandas only, 26 tests), US5-US7 are planned

**Input**: Spec 014 ended with "Out of scope (next spec): the pipeline doctor: classifying failures,
choosing a recovery, escalation and notification, and its evaluation on this repo's real incidents."
This is that spec. Every run, step and failure is now a span (spec 014); retries live in the job
definitions (spec 004); the data-quality checks exist (spec 005); the alert levels and the
failure-handling rules are written down (AGENTS.md). What is missing is the layer that *operates* the
pipelines: reads what ran, decides what kind of failure it is, picks the next action from an
allow-list, asks a person, and earns the right to act alone, one failure class at a time.

> Personal learning project; synthetic and public data only. The doctor reads tables about runs
> (names, counts, durations, error types, check results, lineage): never note text, PHI or row-level data.
> Nothing here is any organization's platform, incident or plan.

## The idea in one paragraph

Most of what breaks in production is visible in metadata before anyone reads a log, and the share is measured, not assumed. If every pipeline is a row in a config table
(owner, SLA, expectations, retry policy, downstream consumers, runbook pointer), every run is a row in
a run log (what ran, how long, counts, schema hash, which checks passed), and lineage says what fed
what, then an agent does not read logs: it reads tables. It classifies the failure from freshness,
counts, schema and job state with rules first; it asks the LLM for a root cause only where rules
cannot decide; it recommends an action from the runbook's allow-list with the impact (which gold
tables, which consumers), a severity (AGENTS.md "Alerts and severity") and a drafted notification; a
person approves. A failure class graduates to automatic only after the agent's recommendation has
matched the human's decision N times in a row and the action is reversible, and it falls back to
recommend-only after two misses. Agents recommend; code acts.

## The four tables (the agent's whole context)

Names follow AGENTS.md "SQL and data names" (singular tables, typed suffixes).

| Table (`${catalog}.gold_perio_bench`) | One row per | Columns |
|---|---|---|
| `dim_pipeline` | pipeline (job or script) | `pipeline_name`, `owner_name`, `sla_seconds`, `schedule_text`, `expectation_names` (which `dq` checks), `retry_max_count`, `retry_interval_seconds`, `runbook_name`, `data_label_code` (synthetic / public / simulated) |
| `fact_pipeline_run` | run, or step of a run | `pipeline_name`, `step_name`, `run_id`, `started_ts`, `ended_ts`, `run_status_code` (ok / failed / timed_out), `row_in_count`, `row_out_count`, `schema_sha256`, `check_passed_count`, `check_failed_count`, `error_type_name`, `error_text` (type and first line only), `duration_seconds`, `cost_usd`, `git_commit_sha`, `data_label_code` |
| `dim_lineage_edge` | edge | `upstream_name`, `downstream_name`, `edge_kind_code` (table / file / model / consumer), `pipeline_name` (the writer) |
| `dim_runbook_entry` | failure class | `failure_class_code`, `description_text`, `allowed_action_codes` (ordered allow-list), `is_reversible`, `severity_code` (SEV1-SEV4), `escalate_to_name` |

Plus `fact_remediation_decision`, one row per recommendation: `pipeline_name`, `run_id`,
`failure_class_code`, `recommended_action_code`, `decided_action_code`, `decided_by_name`, `decided_ts`,
`is_match`, `run_mode_code` (recommend_only / automatic).

Sources on Databricks: `fact_pipeline_run` from the spec 014 spans (Application Insights export) and
`system.lakeflow.job_run_timeline`; `dim_lineage_edge` from Unity Catalog system tables
(`system.access.table_lineage`); config and runbook are YAML in `ops/` deployed by the bundle. Locally
and in tests: pandas DataFrames with the same columns, from CSV fixtures under `data/ops/`.

## The six signals (observability a consumer can see)

Every run publishes **freshness** (seconds since the pipeline's last successful run, against
`sla_seconds`), **volume** (`row_out_count` against the trailing median of recent ok runs), **schema**
(`schema_sha256` against the last ok run), **quality** (share of checks passed), **duration** and
**cost** (both against the trailing median). Duration and cost come from two OpenTelemetry metrics the
spec 014 spans already carry the header for: `pipeline.run.duration_seconds` and `pipeline.run.cost_usd`
(serverless DBU estimate plus judge tokens at the scorecard's price per million), recorded per step with
`service.name`, `data_product_id` and `environment`, so the full cost of a run across the stack is one
group-by. They are computed from `fact_pipeline_run` by `doctor.signals`, shown on the grader dashboards
(spec 019), and are the first thing the classifier looks at.

## The ladder (in order; a run stops at the first rung that resolves it)

1. **Deterministic** (no AI): retry with backoff; rerun an idempotent step; hold downstream when a
   source is late. Already in the job definitions (spec 004) and `runlog.py`; the doctor records what
   they did.
2. **Classify** (rules), configuration-management classes first because they page people and hide in
   logs: `credential_expiry`, `vulnerability`, `deprecation`, `config_drift`, `config` (missing secret, bad
   parameter); then `platform` (GPU not available, Python died, storage), `schema_drift`, `volume_anomaly`,
   `quality_fail`, `cost_anomaly`, `source_late`, `unknown`, in that order. Rules on the six signals and `error_type_name` decide; `unknown` is the only
   class the LLM sees.
3. **Root cause** (LLM, `unknown` only): the agent gets the run row, the pipeline's last N runs,
   lineage one hop each way and the runbook; it returns a root-cause hypothesis, the evidence rows it
   used, and a confidence. It never sees note text.
4. **Recommend**: the first allowed action for the class, the impact (downstream tables and consumers
   from `dim_lineage_edge`), the severity, and a drafted notification. On-call approves or overrides in
   one step; the decision is a row in `fact_remediation_decision`.
5. **Automate**: a failure class runs unattended when the last N recommendations (default 5) matched
   the human's decision and the action is reversible; two misses in a row send it back to
   recommend-only. The rule is code (`doctor.graduation`), not a prompt.

## User stories

### US1 - Every failure is classified from the tables, rules first (P1) #345
Given a run row and the pipeline's recent runs, `doctor.classify` returns the failure class and the
signals it used. Rules cover the incidents this repo has actually had (see evaluation); only `unknown`
goes to the LLM.

### US2 - Every recommendation comes from the runbook's allow-list with its impact (P1) #346
`doctor.recommend` returns the action code (never free text), the downstream names it affects, whether
it is reversible, the severity, the owner, and a one-paragraph notification drafted from the row. An
action not on the runbook's list for that class is never returned.

### US3 - A failure class earns automation and can lose it (P1) #347
`doctor.graduation` reads `fact_remediation_decision` and says `automatic` or `recommend_only` per
class, by the rule above. A class whose runbook entry is not reversible never graduates.

### US4 - The doctor is measured against the repo's own incidents (P1) #348
`data/ops/incident.csv` holds the incidents this repo has had, as run rows with the action the owner
actually took. `doctor.evaluate` reports, per class: classification accuracy, recommendation agreement
with the owner's decision, and the share of incidents resolved without the LLM, with 95% intervals like
every other result here. Never presented as production numbers.

### US7 - The doctor is a separate, reusable package adopted by two projects (P2) #349
`doctor.py` imports nothing from this repo but `paths` and `telemetry`, so it lifts out into its own
package (`healthtransformationlab/pipeline-doctor`: the four tables as a contract, the ladder, the eval and the
ablation). Two implementation projects adopt it, this repo and a second project of a different shape
(a plain SQL/Spark warehouse pipeline, the TPC-H demo, kept in the same organisation), each contributing its own incident set,
config and runbook. The paper compares the same success metrics on both: classification accuracy,
action agreement, share resolved without the LLM, impact known, and the fields handed to the LLM. One
repo is an anecdote; two with the same package is a result.

### US5 - The doctor runs as a job and writes its decisions (P2) #350
A `pipeline_doctor` job runs after each pipeline job (Lakeflow Jobs `run_if` on failure, or on a
schedule), appends to `fact_pipeline_run` and `fact_remediation_decision`, and raises a notification at
the runbook's severity (job system notification; approval is a job parameter until an approval UI
exists). The root-cause rung calls the judge endpoint already in the bundle (`var.judge_endpoint`) under
the same `max_usd` budget as the scorecard.

### US6 - The LLM rung is evaluated like any other model here (P2) #351
Root-cause answers on the incident set are scored with the MLflow GenAI judge pattern from spec 012
(`make_judge`, a Guidelines scorer on the runbook's rules, a deterministic no-PHI scorer on every
trace), and a sample of production traces is scored the same way.

### US8 - The doctor forecasts the failures that have not happened yet, and batches the alerts (P1) #359
A log can only say what broke. The credential register (`ops/secrets_register.yaml`: expiry dates, never
values), a dependency inventory (`ops/dependency_inventory.csv`: end-of-support dates and support status
for models, runtimes, platform versions, endpoints) and the run table's trends give `forecast` rows with a
predicted failure class and date: `credential_expiry`, `deprecation`, `cost_anomaly` and `source_late` from
the cost and duration lines, `volume_anomaly` from a feed drifting toward its bounds, `schema_drift` from a
schema hash that keeps changing. Severity follows the days ladder in AGENTS.md "Alerts and severity";
unknown expiry is itself a SEV4 finding. `digest` routes every alert by that ladder (SEV1/2 now, SEV3 daily,
SEV4 weekly), one message per owner per period, each problem once with a count, repeats carried and a
repeating SEV2 flagged for level review. Implemented in the shared package
(`healthtransformationlab/pipeline-doctor` v0.4.0, `forecast.py` and `digest.py`); this repo supplies the
register and the inventory. First run on this repo's real register (2026-10-29): one credential expiring in
13 days (SEV3) and five with unknown expiry (SEV4 each); the inventory carries no invented dates (two
Python end-of-life months from their PEPs; the model and platform rows say "unknown").

## Evaluation: the incident set

The first rows of `data/ops/incident.csv` are the incidents already written down in this repo's specs,
docs and job definitions. Each is one row with the action taken and whether the owner would let it run alone:

| Incident (where it is recorded) | Class | Action taken | Reversible |
|---|---|---|---|
| Serverless GPU fails to start, no GPU free (jobs.yml, `max_retries: 6`) | `platform` | retry, 30 min apart, up to 6 | yes |
| Notebook Python dies mid-run, Py4JException, output lost (`runlog.py`) | `platform` | rerun; keep the log on the volume | yes |
| Volume cannot append to a log file, Illegal seek (`runlog.py`) | `platform` | write a new time-stamped file | yes |
| Kaggle run returns fewer rows than the committed file (spec 016 US1) | `volume_anomaly` | refuse the file; no PR | yes |
| Result file arrives with new columns (spec 016, `mergeSchema`) | `schema_drift` | append with merged schema | no |
| Telemetry connection string missing (spec 014 US2) | `config` | run with telemetry off; warn | yes |
| MLflow in a script attaches to the notebook's Py4J gateway (`runlog.py`) | `platform` | strip the gateway variables | yes |
| A `dq` conformance check fails over 5% of rows (spec 005 US4) | `quality_fail` | hold downstream; page the owner | yes |

| A judge scorecard run that reached its 5 USD budget at a sub-dollar median (`max_usd`) | `cost_anomaly` | hold downstream; page the owner | yes |

The set grows with every new incident: an incident write-up adds a row. The class, action and reversibility
columns are the record; `started_ts`, `duration_seconds` and `cost_usd` on these first nine rows are
ILLUSTRATIVE values filled in so the rows are complete (no run table existed when they happened), and the eval
does not score them. Rows added from a real run table carry real values.

## The switch-off test (an ablation): what each piece of metadata contributes

The claim behind this spec, "automated remediation is mostly a metadata problem", is tested, not
asserted. `doctor.ablation` re-runs the incident eval with one piece switched off at a time and reports
the same metrics per condition: **no_config** (no SLA, retry policy or output names), **no_conventions**
(no typed, consistently named columns: only `error_text` and row counts, as a plain log gives),
**no_lineage**, **no_metrics** (no OpenTelemetry duration or cost), **no_history** (no trailing ok runs).
First run on the nine incidents above, with the SIMULATED baseline history, the baseline for the paper:

| Condition | Class accuracy (95% CI) | Action agreement | Without the LLM | Impact known | Fields handed to the LLM |
|---|---|---|---|---|---|
| full | 1.00 (0.70-1.00) | 0.78 | 1.00 | 1.00 | 0 |
| no_config | 1.00 (0.70-1.00) | 0.56 | 1.00 | 0.00 | 0 |
| no_conventions | 0.67 (0.35-0.88) | 0.78 | 1.00 | 1.00 | 0 |
| no_lineage | 1.00 (0.70-1.00) | 0.78 | 1.00 | 0.00 | 0 |
| no_metrics | 0.89 (0.56-0.98) | 0.78 | 1.00 | 1.00 | 0 |
| no_history | 0.67 (0.35-0.88) | 0.56 | 0.67 | 1.00 | 372 |

Read: the config table decides the action and the impact; typed conventions and the run history decide
the class; without history a third of incidents fall to the LLM, each with hundreds of fields of context.
Nine incidents is a small set (the intervals say so): the numbers are a method demonstration until the
second project's incidents are in.

## Out of scope
An approval UI (a Databricks App) and chat notifications; root cause across several jobs at once; cost
anomalies; anything that changes data without a human decision recorded first.

## Constitution check
Synthetic and public data only; the doctor never reads note text or row-level data (a test fails if
`doctor.py` imports `notes`, `clinical_notes` or `note_reader`). No metric or label change (no R parity
change). Test-first. `@traced` on every public function. The eval labels dry-run numbers SIMULATED; the
incident set is a record of what happened, not a benchmark claim. Table and column names follow
AGENTS.md.
