# Feature Specification: pipeline telemetry with OpenTelemetry and Azure Application Insights

**Feature Branch**: `014-telemetry`

**Created**: 2026-10-27

**Status**: implemented (Azure resources deployed by the owner)

**Input**: "Implement [MLOps telemetry] on Azure": Application Insights through the Azure Monitor
OpenTelemetry distro, kept inside the free allowance. First step towards self-healing pipelines
(failure detection, root cause, recovery), which need a record of every run, step and failure.

> Personal learning project; synthetic and public data only. Telemetry carries step names, counts,
> durations, pass rates and error types: never note text, PHI or row-level data.

## User stories

### US1 - Every pipeline step is traced (P1)
A step is a span with its name, data label (synthetic / public / simulated) and counts; a failure
records the exception type and message on the span and adds to a failure counter, then re-raises.

### US2 - One switch chooses where telemetry goes (P1)
`DENTAL_TELEMETRY` = `off` (default; tests and CI), `console`, `azure` (Application Insights via
the Azure Monitor OpenTelemetry distro, `APPLICATIONINSIGHTS_CONNECTION_STRING`) or `otlp` (any
OpenTelemetry backend, e.g. self-hosted Grafana Tempo/Loki, Jaeger, SigNoz). `azure` without a
connection string warns and runs with telemetry off: a missing secret never fails a pipeline.

### US3 - Stays inside the free allowance (P1)
- Log Analytics daily cap 0.16 GB (under the 5 GB/month free ingestion per billing account).
- Application Insights retention 90 days (included); workspace retention 30 days.
- Sampling ratio configurable (`DENTAL_TELEMETRY_SAMPLING`, default 1.0: a batch run is a few hundred
  spans, kilobytes, and a dropped failure trace defeats the purpose).
- Only INFO and above from the package logger; no DEBUG.
- Live Metrics on (not billed as ingestion).

### US4 - Infrastructure as code (P2)
`infra/azure/*.tf` (Terraform, azurerm provider): Log Analytics workspace with the daily cap, workspace-based Application
Insights. CI checks formatting and validates it (`terraform fmt -check`, `terraform validate`). Connection string goes to the Databricks secret scope `dental`, key
`appinsights_connection_string`; Databricks jobs read it and pass it to the scripts.

### US5 - Queries for the questions DataOps asks (P2)
`docs/telemetry.md`: KQL for failures by step and error type, step duration trends, data-quality
pass-rate trends, and the last successful run per pipeline.

### US6 - The coding agent's runs are traced too, offline (P2) #666
Each model turn (prompt, cached and output tokens, seconds) and each tool call (its name, and its error type if any)
is a span, with the run's own span around them. A Kaggle kernel has no internet, so `DENTAL_TELEMETRY=file` writes
one JSON line a span to `DENTAL_TELEMETRY_FILE`; `file` without a path warns and runs with telemetry off. The Kaggle
bundle ships a dependency-free tracer with the same calls and the same layout, since tasks change this module.
`annotate()` puts numbers and short `_name`/`_code`/`_id` labels on the span of the function it is called from,
never on its caller's, and never text: no prompt, reply, command or patch reaches a span. The competition's own
evaluator keeps tracing off, so its runs stay comparable. Sending the files to Application Insights is the next step
(the connection string is only in the Databricks secret scope).

## Out of scope (next spec)
The "pipeline doctor": classifying failures, choosing a recovery, escalation and notification, and
its evaluation on this repo's real incidents.

## Revision 2026-10-27: Terraform instead of Bicep
The infrastructure moved from Bicep (Azure-only) to Terraform with the azurerm provider: the same
resources and limits, one tool that also manages Databricks (the Databricks Terraform provider) and
other clouds. Terraform also creates the resource group. Its state file holds the connection string,
so it is git-ignored.

## Revision 2026-10-28: every call, with a common header
As cdh-lava-core does (`with tracer.start_as_current_span(...)` in every method, service and cloud-role
names built from data product and environment): every public function and method in the package
carries `@traced`, the decorator form of `with trace_call(...)`, which yields a logger with the same
header. Header on every span and log line: `data_product_id`, `environment`, `service.namespace`;
resource `service.name` is the data product. A per-parent budget (3 spans per function, the rest
counted) keeps hot loops from flooding the free allowance; with telemetry off the decorator is a direct
call. A test fails if a public function is missing `@traced`.

## Revision 2026-10-28: verbosity levels
`DENTAL_TELEMETRY_LEVEL` = `step` (scripts and pipeline steps), `call` (default: also pipeline-level
functions) or `detail` (also per-item helpers). Each function's level is measured by
`scripts/39_telemetry_levels.py` (each pipeline in its own process under `DENTAL_TELEMETRY_PROFILE`:
calls per parent call and time per call) and kept in `telemetry_levels.yaml`; hand edits marked
`manual: true` survive reruns. Below the chosen level `@traced` is a direct call. Site build: 1 / 6 /
20,691 spans at step / call / detail. `37_cal_reliability.py` now writes its gzip without a timestamp,
so reruns don't change the committed file.

## Revision 2026-11-11: agent runs (US6, #666)

The owner asked for cost and performance tracking for the coding agent, whose Kaggle runs had a stub that recorded
nothing. Done in #666:

- [x] T601 `file` exporter and `DENTAL_TELEMETRY_FILE` (`telemetry.py`); `file` without a path warns, then off
- [x] T602 `annotate()`: numbers and short labels on the current function's span; nothing when it made no span
- [x] T603 each model turn and each tool call annotated (`gemma_agent.py`, `agent_harness.py`)
- [x] T604 `kaggle/bundle_telemetry.py`, shipped as the bundle's `telemetry.py`; the same layout as the SDK's
- [x] T605 the local-harness kernel writes `/kaggle/working/telemetry.jsonl`; the runner keeps one file a task
- [x] T606 `docs/telemetry.md`, "Agent runs, offline"
- [ ] T607 a script that sums the files into a cost-and-performance table a task and a fix
- [ ] T608 send the files to Application Insights (a Databricks job, or a GitHub secret: the owner's choice)
