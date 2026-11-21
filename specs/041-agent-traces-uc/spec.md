# Feature Specification: Coding-agent traces live in Unity Catalog, declared in the bundle

**Feature Branch**: `spec/855-041-agent-traces-uc` (spec); one `feat` branch per user story

**Created**: 2026-11-17

**Status**: draft

**Input**: The owner asked on November 17, 2026 for this: "we should use dabs and deploy our traces to unity catalog".
They sent Databricks' banner for it ("unlimited storage, fine-grained access controls, Genie & Genie Code support, and
traces you can query from notebooks, SQL, and dashboards"). They also sent the experiment's Tool calls tab, which reads
"Tool call metrics require Unity Catalog trace storage". Epic #855.

> Personal learning project, not affiliated. The traces are coding-agent runs on public code (the competition's
> practice tasks and this repository's own history). They hold no dental records, and their text is scrubbed of
> secrets (ADR 0010).

## Why

The coding-agent traces sit in MLflow's default storage. There are 414 today: the practice-set runs of our 31B agent
and of the public bundle, plus the small-model runs. They live in the experiment `/Shared/gemma-agent-runs`, loaded by
a script that exists only in one cloud session. That storage leaves out what the analysis now needs:

- **The experiment's own charts.** The Tool calls tab, the latency percentiles (p50, p90, p99) and the token and cost
  charts all need Unity Catalog trace storage.
- **SQL, dashboards and Genie.** The root-cause analysis of November 17 read every trace through Python, from files.
  In Delta tables, a question about failed edits or time per step is one query that anyone can rerun.
- **A declaration.** Nothing in a repository says where the traces live, so a rebuilt workspace would lose them, and
  the loader can't be reviewed.

## What was checked on November 17

1. **The dev workspace (Free Edition) accepts it.**
   - `mlflow.set_experiment(..., trace_location=UnityCatalog("health_transformation_lab", "scratch_uc_trace_probe",
     "probe"))` created an experiment. A trace written to it was read back by `mlflow.search_traces` and by SQL on the
     starter warehouse.
   - Databricks made four tables (`probe_otel_spans`, `_otel_logs`, `_otel_metrics`, `_otel_annotations`) and two
     views (`probe_trace_metadata`, `probe_trace_unified`).
   - Databricks' docs say traces "cannot be written to default storage catalogs". Our catalogs use the workspace's
     default storage, and the probe still worked. That limit may yet be enforced (Risks).
2. **The bundle can declare it.**
   - The Databricks CLI's bundle schema has `experiments.<key>.trace_location.uc_trace_location` (`catalog`,
     `schema`, `table_prefix`) from version 1.9.0, released July 22, 2026. It is marked Private Preview, and it
     "cannot be updated after the experiment is created".
   - CI pins `databricks/setup-cli@v1.3.0`, whose schema doesn't have it.
3. **Existing traces can be copied.**
   - `databricks.migrations.migrate_traces_to_uc.run(source_experiment_id, target_experiment_id, start_time_ms=None)`
     ships in `databricks-agents>=1.10.1` and runs from a notebook.
   - It copies traces, spans, assessments, tags and metadata, leaves the source as it was, and can be rerun.
   - It does not copy runs, datasets or labelling sessions.
4. **Permissions.** Writing needs `USE_CATALOG`, `USE_SCHEMA`, `CREATE TABLE`, and `MODIFY` and `SELECT` on the trace
   tables. Databricks says `ALL_PRIVILEGES` alone isn't enough.

## User stories

### US1 - The bundle declares the agent-trace schema and an experiment bound to it (P1) #856

- A merge deploys the schema `ops_agent_trace` and the experiment `/Shared/coding-agent-runs`, with its traces bound
  to that schema under the table prefix `coding_agent`. Nobody makes them by hand.
- CI's CLI is new enough to read the field.
- **Independent test:** the bundle test reads `databricks/resources/agent_traces.yml`. `databricks bundle validate -t
  dev` passes with the pinned CLI. After the merge deploy, the experiment exists with its trace location set.

### US2 - A committed loader writes a finished run's traces there, once per task-run (P1) #857

- `kaggle/load_agent_traces.py` reads the same run folders as the Azure forwarder and writes one trace per task-run.
  A rerun writes nothing new.
- Every text is scrubbed first. Every trace carries its batch key and the commit it was loaded from.
- **Independent test:** load fixture runs twice with a fake client. The second load writes nothing, and every trace
  carries the tags in the contract.

### US3 - The 414 traces and their assessments move there, with the counts checked (P2) #858

- US2's loader writes the same runs again into the new experiment, in the trace shape the experiment's charts can
  group (`plan.md`, "What a trace looks like"). The code scorers and the grounding judge then score them again.
- The counts of traces and of assessments by name match the old experiment, or the gap is listed.
  `/Shared/gemma-agent-runs` stays as the backup.
- Databricks' migration is the fallback for any run whose folder is gone. It would keep the step-numbered span names.
- **Independent test:** the count table has equal counts for both experiments, or rows that explain the gap.

### US4 - SQL views answer which tools, how long and how many tokens, per task-run (P2) #859

- `agent_task_run` (one row per task-run) and `agent_tool_call` (one row per tool call) turn the span attributes
  into typed columns that follow "SQL and data names".
- The experiment's Usage and Tool calls tabs show data.
- **Independent test:** `agent_task_run` has as many rows as the experiment has traces, and its solved counts match
  the counts already recorded for those runs.

## Requirements

- **FR-001** One declaration for each name: the bundle declares the schema, the experiment and the table prefix, and
  the loader's experiment setting matches them.
- **FR-002** The tables and views Databricks makes keep Databricks' names (`<prefix>_otel_*`, `<prefix>_trace_*`), as
  OMOP's do. Our own views follow "SQL and data names".
- **FR-003** No trace holds a secret. Text goes through `telemetry.scrub_value` before it is written (ADR 0010), and a
  secret found in a span is a SEV1.
- **FR-004** Writes are idempotent. The loader skips a `trace_key` already present, and the migration's count table
  is delete-then-append by `run_id`.
- **FR-005** The old experiment is kept until US3's counts match. Retiring it is a later decision, recorded as an ADR. Retired on November 21, 2026: [ADR 0012](../../docs/adr/0012-retire-the-old-trace-experiment.md).
- **FR-006** The traces are the same in every target, and each target has its own workspace. Only dev holds runs
  today.

## Success criteria

- **SC-001** The merge deploy creates the experiment with its trace location in dev, with no step by hand.
- **SC-002** All 414 traces and their assessments are queryable in SQL, and the counts match the source.
- **SC-003** A new run's traces reach Unity Catalog with one committed command, and a second run of it adds nothing.

## Assumptions

- The Private Preview field keeps working on Free Edition. The probe used the MLflow client, so US1's deploy is the
  first test of the field itself.
- The starter warehouse (serverless) serves the MLflow UI's trace queries. It starts on demand, as it did for the
  probe.
- Both the loader and the migration run as the owner, through the agent session's workspace token, or as the CI
  principal. Both are in the admin group the catalog grants.

## Out of scope

- A Genie space over the views. It goes to the backlog once US4's views exist.
- Forwarding to Azure, which stays as it is (spec 014). This spec adds a second destination and replaces nothing.
- Live tracing from inside the agent while it runs. The agent runs on Kaggle and Colab, and the traces are loaded
  after a run finishes.

## Risks

- **Default storage.** Databricks' docs exclude default storage catalogs, and the probe still worked. If a later
  release enforces the limit, the deploy fails at the experiment. The fallback is a catalog with an external location,
  which Free Edition may not allow. US1's PR records which happened.
- **Private Preview.** The field can change. CI pins the CLI version and validates on every PR.
- **uat and prod.** Each merge also deploys uat. A workspace without the preview would fail at the experiment, and
  the PR would need the resource under the dev target only (as the legacy schemas are) until that preview is turned on.
- **One-way binding.** An experiment's trace location can't be changed. A wrong prefix means a new experiment, so the
  prefix is decided here (`coding_agent`) and tested.
