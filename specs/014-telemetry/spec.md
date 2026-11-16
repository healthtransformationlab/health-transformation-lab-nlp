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

### US7 - Leaderboard entries and the GPU runs' spans reach Azure (P2) #791
The competition's work reaches Application Insights. A leaderboard entry runs on Kaggle's machines with no code of
ours, so it can't be traced: the API gives its status, score and dates, and the submissions list hides a pending entry.
A watcher keeps a ledger of this team's entries and sends one span per status change; an entry that turns to error
fails the watch (SEV2). The development-set runs on Kaggle and Colab GPUs write their spans to `telemetry.jsonl` with the
internet off; collecting a run now sends that file on, each span with its own times. Telemetry off stays the default.

Acceptance scenarios:

1. **Given** the ledger holds a pending entry the submissions list leaves out, **when** `kaggle/submission_watch.py`
   runs, **then** it looks the entry up by ref, writes `data/tasks/leaderboard_entries.csv` (one row per entry,
   overwritten), and sends one `leaderboard_entry` span (`submission_ref_id`, `status_code`, `public_score_ratio`)
   per status change; a second run with nothing new changes nothing and sends none.
2. **Given** an entry turns to error, **when** the watcher runs, **then** it writes the ledger and ends non-zero.
3. **Given** a `telemetry.jsonl`, **when** `telemetry.forward_spans(path)` runs with an exporter set up, **then** each
   span is sent with its original start and end times, attributes (numbers and short labels) and parent, and the count
   is returned; with the exporter off it sends none.
4. **Given** a collected run, **when** `kaggle/official_agent_run.py --collect` finishes collecting, **then** it has set
   telemetry up and forwarded the run's `telemetry.jsonl`.
5. **Given** `.github/workflows/leaderboard-watch.yml`, **then** it runs every two hours and on demand in the `dev`
   environment with `KAGGLE_API_TOKEN` and, if set, `APPINSIGHTS_CONNECTION_STRING` (missing: a warning, telemetry off,
   the ledger still updated), and ledger changes go to a `kaggle-results/leaderboard-entries-<run_id>` branch and a
   pull request.
6. **Given** `ops/secrets_register.yaml`, **then** it lists the GitHub secret `APPINSIGHTS_CONNECTION_STRING`.

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
- [x] T608 send the files to Application Insights: a GitHub secret, through `telemetry.forward_spans` (US7, #791)

## Revision 2026-11-15: telemetry off is an alert, not only a warning (BUG1, #792)

Every job had asked for `azure` since this spec, but the Application Insights resource was never created, so no
connection string existed and telemetry was off everywhere, with one log warning per run. US2's rule stands (a
missing secret never fails a pipeline); what changes is that off-when-asked is now seen:

- `telemetry.status()`: `asked_exporter_name`, `active_exporter_name`, `reason_text` (no value ever)
- one stderr line from `setup()` / `use_databricks_secret` naming the setting, the reason and the fix (a
  `::warning::` annotation under GitHub Actions)
- `digests.telemetry_alerts(statuses)` and `digests.register_alerts(register, scope_keys)`: SEV3s in the daily
  digest (`14_pipeline_digest.py`), the second for a registered Databricks-scope secret the scope lacks

### US8 - Development runs on Modal, Colab and Kaggle reach Azure (P2) #830
A development run on any of the three writes its per-task results, and with `--telemetry` the agent's spans, into a
private Kaggle results dataset. The agent sessions that collect runs hold no secrets, so until now nothing from these
runs reached Application Insights. A manual workflow in the `dev` environment downloads a finished run's results and
sends them, so every platform's runs sit beside the watcher's and Databricks' spans.

Acceptance scenarios:

1. **Given** a results folder with `tasks/*/result.json`, **when** `kaggle/forward_run_telemetry.py <dir> --label <label>
   --platform <modal|colab|kaggle>` runs with an exporter set up, **then** it sends one `run_forward` span (label,
   platform, task count) and one `agent_task` span per task (instance id, agent seconds, tool calls, patch made,
   resolved, error kind), never task text or a patch, forwards any `telemetry.jsonl`, and prints the export result.
2. **Given** `.github/workflows/forward-run-telemetry.yml`, **then** it runs on demand in `dev` with the Kaggle token and,
   if set, `APPINSIGHTS_CONNECTION_STRING` (missing: a warning, telemetry off).

### US9 - A coding-agent run's full trace reaches Azure on request (P2) #850
US8's spans hold counts and short labels, so a failed task still has to be diagnosed from the trace file inside a
private Kaggle dataset. The owner asked on November 16, 2026 for the data a diagnosis needs: "none of this is public
you can make it an override setting but for these repos we can log everything except password". One setting,
`DENTAL_TELEMETRY_CONTENT`, turns a coding-agent run's own content on for the forwarder: `labels` (the default, as
before) or `full`. Dental-record code never sends text, whatever the setting (ADR 0010).

Acceptance scenarios:

1. **Given** `DENTAL_TELEMETRY_CONTENT` unset or `labels`, **when** the forwarder runs, **then** it sends what US8 sends,
   with no `agent_step` span and no text; every span of the forwarding carries one `forward_id`.
2. **Given** `DENTAL_TELEMETRY_CONTENT=full` (or `--content full`), **then** each task with a trace also gets one
   `agent_step` span per step: the step's message, each tool call's name and arguments, the tool's output, the token
   counts and the times; the task's `agent_task` span holds the patch and the agent's error text.
3. **Given** any other value, **then** the forwarder stops at once, naming `DENTAL_TELEMETRY_CONTENT` and its two values.
4. **Given** a secret in any text (a Kaggle, Hugging Face, GitHub or `sk-` token, an AWS access key id, a `Bearer`
   token, an Azure connection string's key, a quoted value assigned to a name such as `password` or `api_key`, or the
   value of one of the forwarder's own secret environment variables), **then** `[REDACTED]` is sent in its place;
   ordinary code such as `password: str` is unchanged.
5. **Given** a text longer than 8,000 characters, **then** the span holds its first part and `<key>_part_count`, and
   each further part is a child span `<name>_part` (`field_name`, `part_num`, `part_text`); the parts joined give the
   scrubbed text.
6. **Given** the workflow "Forward a development run's telemetry to Azure", **then** it has a `content` input, `full` by
   default, passed as `DENTAL_TELEMETRY_CONTENT`.

