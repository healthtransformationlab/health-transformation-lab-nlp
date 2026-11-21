# Pipeline telemetry: OpenTelemetry → Azure Application Insights

Every script run is a trace, and every pipeline step is a span inside it, with the step's name, its
data label (synthetic, public, simulated), counts and duration. A failure is recorded on its span,
with the error type and message, and added to a failure counter. Data-quality pass rates go out as
metrics, one point per check per run. This is the record that failure detection, root-cause
assessment and recovery are built on: see [dataops.md](dataops.md), the pipeline doctor (spec 027). Spec 014.

Telemetry never carries note text or row-level data: names, counts, durations, rates and error
types only.

## One switch

| `DENTAL_TELEMETRY` | Where it goes | Needs |
|---|---|---|
| `off` (default) | nowhere: tests, CI, laptops | nothing |
| `console` | printed spans and metrics | nothing |
| `azure` | Application Insights, through the Azure Monitor OpenTelemetry distro | `APPLICATIONINSIGHTS_CONNECTION_STRING`; `pip install -e "python[azure]"` |
| `otlp` | any OpenTelemetry backend (self-hosted Grafana Tempo/Loki, Jaeger, SigNoz) | `OTEL_EXPORTER_OTLP_ENDPOINT`; `pip install -e "python[otlp]"` |

`azure` without a connection string runs with telemetry off: a missing secret never fails a pipeline.
Off is not quiet, though (014 BUG1, #792: every job asked for `azure` for weeks while the Application Insights
resource had never been created, and only a log warning said so):

- `telemetry.status()` returns what was asked (`asked_exporter_name`), what is on (`active_exporter_name`) and why
  they differ (`reason_text`: no connection string, malformed connection string, no secret, no file), never a value.
- When they differ, `setup()` (and `use_databricks_secret`, when the secret isn't in the scope) carries on and prints
  one line to stderr naming the setting, the reason and the fix (create the resource with `infra/azure`, then put the
  connection string in `APPLICATIONINSIGHTS_CONNECTION_STRING` or the Databricks secret
  `health_transformation_lab/appinsights_connection_string`); under GitHub Actions the line is a `::warning::`
  annotation. The log warning is still written too.
- It is a **SEV3 in the daily digest** (`digests.telemetry_alerts`, owner and fix included), built by
  `databricks/notebooks/14_pipeline_digest.py`. The jobs' own statuses aren't recorded anywhere yet (the doctor's run
  table comes from the spans, so with telemetry off it has no rows), and every job reads the same switch and secret,
  so the digest notebook's own status stands for the whole workspace.
- The same notebook checks the secrets register: each credential in `ops/secrets_register.yaml` whose `stored_in` is
  the Databricks secret scope must have its key in the scope (`digests.register_alerts`, reading the scope with
  `dbutils.secrets.list`, key names only); one that is missing is a SEV3 in the daily digest too.

`DENTAL_TELEMETRY_CONTENT` (`labels`, the default, or `full`) says whether a coding-agent run's own content may be
sent ("A run's steps in full" below); it changes nothing for dental-record code, which never sends text.
`DENTAL_TELEMETRY_SAMPLING` (0–1, default 1.0) sets trace sampling;
`DENTAL_ENVIRONMENT` (default `dev`) is recorded on every span.

Code: `python/health_transformation_lab_nlp/telemetry.py`. In a script, two lines:

```python
from health_transformation_lab_nlp import telemetry
telemetry.setup()                                           # from the environment
telemetry.start_script("20_data_quality", data_label="synthetic")
with telemetry.pipeline_step("transitions", pairs=len(pairs)):   # optional finer steps
    ...
telemetry.record_value("data_quality.pass_rate", 0.97, check="cal_range")
```

Every script in `python/scripts/` calls `telemetry.setup()` and opens a run span named for itself with
`telemetry.start_script("<script name>", data_label=...)`: `synthetic`, `public` (MACCROBAT, the
competition's tasks, the agent runs) or `simulated` (a dry run: `--simulated`, `15_judge.py --backend simulated` or `--simulated-review`, `14_benchmark_cost.py --simulate-missing`, the simulated grader).
`_trace_plugin.py` is a pytest plugin, not a script, and is the one file left out.
`python/tests/test_telemetry_scripts.py` fails CI when a script is missing either call or its data label.

Every Databricks job task that runs a Python notebook passes the switch (`telemetry: ${var.telemetry_exporter}`,
default `azure`), and its notebook reads it and the connection string from the secret scope
(`telemetry.use_databricks_secret`), so the scripts it starts inherit them. The notebooks that also run the
package's code in their own process (`01_run_benchmark`, `07_judge_scorecard`, `10_load_results`,
`11_migrate_gold_names`, `12_load_open_dental`, `13_pipeline_doctor`, `14_pipeline_digest`) call `telemetry.setup()`,
open a run span named for themselves and end it with `telemetry.end_script()`, since a notebook's process may not run
`atexit`. A notebook's error is handled by IPython, not `sys.excepthook`, so a failed notebook doesn't mark its run
span failed: the failure is on the span of the `@traced` function that raised it. The `llm_judge` job is a SQL
notebook, which the Python tracer can't reach. The same test checks the jobs and these notebooks.

## Every call, with a common header

Every public function and method in `python/health_transformation_lab_nlp/` (282 of them) carries `@traced`, which
runs its body inside a `with` statement, the pattern cdh-lava-core uses in every method:

```python
from .telemetry import trace_call, traced

@traced                                   # the usual form: one line above the def
def label_chart(chart): ...

def build_study(seed=7):
    with trace_call("study.build_study") as log:      # the explicit form, same thing
        log.info("built %d visits", n)                 # the log line carries the header too
```

**Common header.** Every span and every log line carries `data_product_id` (default
`health_transformation_lab`, `DENTAL_DATA_PRODUCT_ID`), `environment` (`DENTAL_ENVIRONMENT`) and
`service.namespace` (`health-transformation-lab-nlp`); spans add `code.namespace` (module) and `code.function`. The
resource names the data product as the service, so in a shared Application Insights resource one
data product and one environment are a filter away (`customDimensions.data_product_id`,
`cloud_RoleName`).

**Budget.** A function called many times under the same parent (staging every chart, reading every
note) makes a span for its first 3 calls only (`DENTAL_TELEMETRY_MAX_CALLS`); the rest are counted
in the `function.calls` metric and failures still count. The whole site build (thousands of calls)
sends 28 spans. With telemetry off, `@traced` is a plain function call: the test suite runs as fast
as before.

**Rows in and out.** A pipeline step that takes a table and returns one can carry `@counts_rows` directly under
`@traced` (spec 040 US6, #758). Its span then records `row_in_count`, the rows of its first argument (the sum over a
dict of tables), and `row_out_count`, the rows it returns (the first item of a tuple); a step that fails records
`row_in_count` only. Counts only, never a row's values. Seventeen steps carry it (`specs/040-telemetry-tasks/plan.md`);
once their modules are imported, `telemetry.ROW_COUNTED` names them. Put above `@traced`, it raises `TypeError`.

A test (`tests/test_telemetry_calls.py`) fails if a new public function lacks `@traced`.

### Verbosity levels

`DENTAL_TELEMETRY_LEVEL` sets how far down the call tree spans go:

| Level | What gets a span | Site build (22_build_sites), spans |
|---|---|---|
| `step` | script runs and `pipeline_step` blocks | 1 |
| `call` (default) | also functions marked `call`: the pipeline-level work | 6 |
| `detail` | also functions marked `detail`: per chart, per note, per site helpers | 20,691 (before the per-parent budget) |

Below the chosen level `@traced` is a direct call, so hot helpers cost nothing even with telemetry on.

Each function's level is **measured, not guessed**: `python scripts/39_telemetry_levels.py` runs
representative pipelines, each in its own process, with `DENTAL_TELEMETRY_PROFILE` set, counts every
traced call (calls per parent call, time per call) and marks a function `detail` when it is called
more than 20 times under one parent call, or costs under 0.5 ms and is called that often. The result
is `python/health_transformation_lab_nlp/telemetry_levels.yaml`, one entry per function with the measured reason.
Edit a level by hand and add `manual: true` to keep it; functions the runs don't reach default to
`call`. Rerun the script after adding pipelines or changing hot paths.

Why measured and not an LLM: the question is how often a function runs and how long it takes, which a
profiler answers exactly, for free and the same way every time. An LLM reading function names would
guess. AI is better spent on what the telemetry is for: reading failures and suggesting a fix (the
next spec, the pipeline doctor).

## Set up Azure (once, from your laptop)

The Azure resources are Terraform in `infra/azure/` (the azurerm provider). You need an Azure
subscription (a free account works), the Azure CLI and Terraform 1.6 or later. Sign in with
`az login`; Terraform uses that sign-in, so no token is created or copied.

```bash
export ARM_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
terraform -chdir=infra/azure init
terraform -chdir=infra/azure apply -var budget_email=you@example.com   # budget_email is optional
```

It creates, in resource group `rg-health-transformation-lab-telemetry`:

- a Log Analytics workspace `health-transformation-lab-nlp-logs` with a **daily cap of 0.16 GB** (31 days × 0.16
  = 4.96 GB, under the 5 GB/month free ingestion per billing account), 30-day retention;
- workspace-based Application Insights `health-transformation-lab-nlp-appi`, **90-day retention** (included);
- optionally a 1 USD monthly budget on the resource group that emails on any actual charge.

`terraform -chdir=infra/azure destroy` removes all of it.

**State.** Terraform records what it created in `infra/azure/terraform.tfstate`. That file holds
the connection string in plain text, so it is git-ignored and stays on your laptop. To share or
automate the deployment later, move the state to an Azure Storage backend (a `backend "azurerm"`
block) rather than committing it.

Put the connection string straight into the Databricks secret scope, without printing it:

```bash
databricks secrets create-scope health_transformation_lab          # skip if it exists (it holds hf_token too)
databricks secrets put-secret health_transformation_lab appinsights_connection_string --string-value \
  "$(terraform -chdir=infra/azure output -raw connection_string)"
```

The connection string lets a holder *send* telemetry to this resource; it can't read anything. It
doesn't expire, so treat it as a secret anyway: secret scope only, never in a job parameter, a file
or chat. Stricter, later: turn off local authentication on the resource and send with a Microsoft
Entra ID identity instead.

Locally: `export DENTAL_TELEMETRY=azure APPLICATIONINSIGHTS_CONNECTION_STRING=...` in your shell
(from your password manager), then run any instrumented script.

## Staying inside the free allowance

| Guard | Where | Setting |
|---|---|---|
| Daily cap | Log Analytics workspace (Terraform) | 0.16 GB/day; ingestion stops for the day at the cap |
| Budget alert | resource group (Terraform, optional) | email on any actual charge |
| Sampling | `DENTAL_TELEMETRY_SAMPLING` | 1.0: a batch run is a few hundred spans (kilobytes), and a sampled-away failure is the one you needed. Lower it only for high-volume services |
| Log level | `telemetry.setup()` | INFO and above from the `health_transformation_lab_nlp` logger; no DEBUG |
| Live Metrics | on | real-time view, not billed as ingestion |

How much has gone in this month (`Usage` reports MB):

```kusto
Usage
| where TimeGenerated > startofmonth(now()) and IsBillable
| summarize GB = sum(Quantity) / 1000.
```

## Queries for the questions DataOps asks

Spans the scripts send are internal spans, so in the workspace they are rows of `AppDependencies`
(`Name` = step, `Success`, `DurationMs`, attributes in `Properties`). Exceptions are in
`AppExceptions`, metrics in `AppMetrics`, log lines in `AppTraces`.

Every call of one data product in one environment (the common header):

```kusto
AppDependencies
| where TimeGenerated > ago(1d)
| where tostring(Properties["data_product_id"]) == "health_transformation_lab" and tostring(Properties["environment"]) == "dev"
| summarize calls = count(), failures = countif(Success == false), p95_ms = percentile(DurationMs, 95)
    by function = Name
| order by calls desc
```

What failed this week, and how:

```kusto
AppDependencies
| where TimeGenerated > ago(7d) and Success == false
| extend step = tostring(Properties["pipeline.step"]), error = tostring(Properties["error.type"])
| summarize failures = count(), last = max(TimeGenerated) by step, error
| order by failures desc
```

Is a step getting slower:

```kusto
AppDependencies
| where TimeGenerated > ago(30d)
| summarize runs = count(), p50_s = percentile(DurationMs, 50) / 1000, p95_s = percentile(DurationMs, 95) / 1000
    by step = Name, day = bin(TimeGenerated, 1d)
| order by step asc, day asc
```

Data-quality pass rate per check over time (input for anomaly detection):

```kusto
AppMetrics
| where Name == "data_quality.pass_rate"
| extend check = tostring(Properties["check"])
| summarize pass_rate = sum(Sum) / sum(ItemCount) by check, day = bin(TimeGenerated, 1d)
```

When did each pipeline last succeed (freshness):

```kusto
AppDependencies
| where tostring(Properties["pipeline.kind"]) == "script" and Success == true
| summarize last_success = max(TimeGenerated) by script = Name
| extend hours_since = datetime_diff("hour", now(), last_success)
```

## Agent runs, offline (US6)

The coding agent's runs are traced too (spec 014 US6, #666). A Kaggle kernel has no internet, so its spans go to a file,
one JSON line a span, children first:

- **On Kaggle.** The local-harness kernel (`kaggle/agent_kernel.py`) sets `DENTAL_TELEMETRY=file` and
  `DENTAL_TELEMETRY_FILE=/kaggle/working/telemetry.jsonl`, beside `result.json`. The runner
  (`python/scripts/60_kaggle_agent.py`) keeps each task's file as
  `data/tasks/agent_runs/telemetry/<model>/<instance_id>.jsonl`; a rerun replaces it.
- **The bundle's tracer.** The bundle can't ship this module, because tasks change it and the agent could read a fix
  beside its task. So it ships `kaggle/bundle_telemetry.py` as `htl_agent/telemetry.py`: the same calls, the standard
  library only, and the layout the SDK's `file` exporter writes, so one reader handles both. It keeps every call (a
  file costs nothing to ingest); the package caps repeats at `DENTAL_TELEMETRY_MAX_CALLS` for the Azure allowance.
- **Elsewhere** (a laptop, Colab, CI): `DENTAL_TELEMETRY=file` does the same through the SDK, and
  `DENTAL_TELEMETRY=azure` sends the spans straight to Application Insights.
- **The competition's own evaluator** (`kaggle/official_agent_kernel.py`) keeps tracing off, as the competition runs
  it; its timing and tokens are in its own run table.

What a span holds, each with its start and end time:

| Span | Attributes |
|---|---|
| `agent_kernel` (the run) | `instance_id`, `model_name`, `load_seconds`, `is_patch_submitted`, `turn_count`, `error_type_code` |
| `gemma_agent.GemmaModel.step` (a model turn) | `model_name`, `prompt_token_count`, `prefill_token_count`, `output_token_count`, `turn_seconds`, `is_over_context` |
| `agent_harness.call_tool` (a tool call) | `tool_name`, `tool_error_code` |

Never the prompt, the reply, a command or a patch: `telemetry.annotate()` keeps numbers and booleans, and text only
as a short label (a key ending `_name`, `_code` or `_id`, at most 64 characters). An error is recorded by its type.

```python
import json
spans = [json.loads(line) for line in open("telemetry.jsonl") if line.strip()]
turns = [s["attributes"] for s in spans if s["name"].endswith("GemmaModel.step")]
print(sum(t.get("output_token_count", 0) for t in turns), "output tokens in", len(turns), "turns")
```

Next: a script that sums the files into a cost-and-performance table (tokens, seconds and tool calls a task and a
fix). Sending the files on is below.

## The competition's runs and entries (US7)

Where the Gemma 4 Developer Agent competition's telemetry goes (spec 014 US7, #791):

- **Development-set runs on a Kaggle or Colab GPU.** The kernel writes its spans to `telemetry.jsonl` with the internet
  off (`--telemetry`). `kaggle/official_agent_run.py --collect` sets telemetry up, opens the run span
  `official_agent_run`, and after reading the run back sends the file on with `telemetry.forward_spans(path)`: each span
  keeps its own start and end time, status and attributes (numbers and text of at most 64 characters), and a child
  keeps its parent under new span ids. Run the collect with `DENTAL_TELEMETRY=azure` and the connection string set to
  send them to Application Insights; off by default, as everywhere else.
- **Leaderboard entries.** An entry runs on Kaggle's machines with no code of ours, so it can't be traced: the API
  gives its status, score and dates, nothing more. `.github/workflows/leaderboard-watch.yml` runs
  `kaggle/submission_watch.py` every two hours. It keeps `data/tasks/leaderboard_entries.csv` (one row per entry; a
  pending entry, which the submissions list hides, is looked up by its ref) and sends one span `leaderboard_entry`
  per status change, with `submission_ref_id`, `status_code` and `public_score_ratio`, under the run span
  `submission_watch`. The ledger's changes go to a `kaggle-results/leaderboard-entries-<run_id>` pull request. An
  entry that turns to error fails the workflow (SEV2: GitHub emails the owner).
- **The connection string** for the workflow is the GitHub `dev` environment secret `APPINSIGHTS_CONNECTION_STRING`
  (`ops/secrets_register.yaml`), the same value as the Databricks secret. The workflow passes it on as
  `APPLICATIONINSIGHTS_CONNECTION_STRING` with `DENTAL_TELEMETRY=azure`; without it, a warning and telemetry off,
  and the ledger is still updated. Set it from your laptop without the value passing through a file or the chat:
  `terraform -chdir=infra/azure output -raw connection_string | gh secret set APPINSIGHTS_CONNECTION_STRING --env dev`.

```kusto
AppDependencies
| where Name == "leaderboard_entry"
| project TimeGenerated, ref = tostring(Properties["submission_ref_id"]), status = tostring(Properties["status_code"]),
          score = todouble(Properties["public_score_ratio"])
| order by TimeGenerated desc
```


**Evidence, not a switch (014 BUG2, #801).** Until November 15 the `azure` exporter's providers were never flushed at
exit, so a short script's spans could sit in the batch queue and never arrive: the watcher's first run said "telemetry
azure" and the workspace held no rows. `telemetry.flush()` now sends what is queued and says whether every provider took
it, the Azure exporter's own warnings go to stderr, and the watcher prints `telemetry export: ok` or
`telemetry export: FAILED` (a `::warning::` annotation in GitHub Actions) on every run. To check what arrived:
`union dependencies, requests, traces | where timestamp > ago(1d) | summarize count() by itemType, cloud_RoleName`
in the resource's Logs page.

**Verified end to end, November 15 (#807).** The watcher's run of 15:02 UTC (after #802) landed in the workspace:
`AppDependencies` 8 rows (the spans), `AppMetrics` 8, `AppPerformanceCounters` 32. To check from Cloud Shell, without
the portal, ask the workspace through Azure Resource Manager; its answer uses `Tables` and `Rows` with capitals, so a
lowercase `tables[0].rows` prints nothing even when rows arrived:

```bash
WS=$(az monitor log-analytics workspace list --query "[0].id" -o tsv)
az rest --method post --url "https://management.azure.com$WS/api/query?api-version=2020-08-01" \
  --body '{"query": "union AppDependencies, AppMetrics, AppPerformanceCounters | where TimeGenerated > ago(1d) | summarize count() by Type"}' \
  --query "Tables[0].Rows"
```

## Development runs on Modal, Colab and Kaggle (US8)

A run on any of the three writes its per-task results, and with `--telemetry` the agent's spans and GPU samples, into a
private Kaggle results dataset (`jcblearning/htlnlp-colab-official-<label>` for Modal and Colab). Agent sessions hold
no secrets, so the forwarding is a workflow (#830): Actions, **Forward a development run's telemetry to Azure**, with the
results dataset, the run's label and the platform. It sends one `run_forward` span and one `agent_task` span per task
(instance id, agent seconds, tool calls, patch made, resolved, error kind; never task text or a patch), forwards
`telemetry.jsonl` when the run was built with `--telemetry`, and prints `telemetry export: ok` or `FAILED`. Build new run
bundles with `--telemetry` so the agent's own spans come too.

```kusto
AppDependencies
| where Name == "agent_task"
| project TimeGenerated, label = tostring(Properties["run_label"]), platform = tostring(Properties["platform_name"]),
          task = tostring(Properties["instance_id"]), seconds = todouble(Properties["agent_seconds"]),
          calls = toint(Properties["tool_call_count"]), resolved = tostring(Properties["is_resolved"])
| order by TimeGenerated desc
```

## Not yet

The pipeline doctor: classify each failure (GPU unavailable, out of memory, schema drift, data
quality, dependency), choose a recovery (retry, repair run, quarantine, escalate), notify downstream
users, and evaluate all of it on this repo's real incidents. That is the next spec; this one gives
it the record to work from.

## Reading it back from an agent session

An agent session can query the telemetry it sends, read only, with the key in `ops/secrets_register.yaml`
("Application Insights read key for agent sessions"; issue 836). The cloud environment's proxy adds the key for host
`api.applicationinsights.io`, so a session only names the resource's application id, which it keeps in its own notes
rather than in this public repository:

```bash
curl -sS -G "https://api.applicationinsights.io/v1/apps/$APP_ID/query" \
  --data-urlencode "query=dependencies | where name == 'leaderboard_entry' | top 5 by timestamp desc | project timestamp, customDimensions"
```

Three span names answer most questions:

- `leaderboard_entry`: one per status change of a competition entry, with `submission_ref_id`, `status_code`,
  `previous_status_code` and, once scored, `public_score_ratio`, from the leaderboard watcher.
- `agent_task`: one per task of a forwarded development run, from `forward-run-telemetry`.
- `agent_step`: one per step of a task's trace, when the run was forwarded in full (next section).

## A run's steps in full (US9, #850)

A failed task can be read without downloading its trace. The workflow "Forward a development run's telemetry to
Azure" has a `content` input, `full` by default, which sets `DENTAL_TELEMETRY_CONTENT`; the forwarder's own option is
`--content full`. It works on a run that finished before this existed, since the content comes from the trace files in
the run's results dataset. The decision and its limits are in
[ADR 0010](adr/0010-agent-run-traces-may-carry-full-content.md).

| Span | One per | Holds |
|---|---|---|
| `run_forward` | forwarding | `run_label`, `platform_name`, `task_count`, `content_level_name`, `forward_id` |
| `agent_task` | task | `instance_id`, `agent_seconds`, `tool_call_count`, `is_patch_made`, `is_resolved`, `agent_error_code`; in full: `patch_text`, `agent_error_text` |
| `agent_step` | step of the trace | `instance_id`, `step_num`, `source_name` (system, user, agent), `event_type_name`, `message_text`, `tool_name`, `tool_call_count`, `arguments_text`, `output_text`, `prompt_token_count`, `completion_token_count`, `cached_token_count`, `elapsed_seconds` |
| `agent_step_part`, `agent_task_part` | further 8,000 characters of a long text | `field_name`, `part_num`, `part_text`, and the span's own numbers and labels |

- **Secrets are taken out first** (`telemetry.scrub`): `[REDACTED]` stands where one was. It knows token shapes,
  private-key blocks, values given to names such as `password`, `token` or `api_key` (quoted, or after a NAME in
  capitals as `printenv` writes them), login options and headers, `user:password@` in a URL, and the forwarder's own
  secret environment values.
- **What the scrubber cannot know:** a secret in a shape with no rule under a name that doesn't tell; a password
  that is one plain word; an unquoted YAML or ini value with no digit; a secret encoded again (base64, URL-encoded).
  It also redacts a little ordinary text, such as the `pass` in an example URL `https://user:pass@example.com`.
  A secret found in a span is a SEV1 (ADR 0010).
- **A long text is whole.** The span holds its first 8,000 characters and `<key>_part_count`; the rest are the
  `_part` spans, in `part_num` order.
- **A run forwarded twice is there twice.** Every span of one forwarding has the same `forward_id`, the kernel's own
  spans included; the queries below take the latest.
- **A task that could not be read is skipped and named** in the workflow's log, with the kind of error; the rest of
  the run is sent.
- **Not yet checked:** whether a step forwarded days after its run keeps its original time in Application Insights.

What the agent did on one task, in order:

```kusto
let run = "devset-m31be-c1";
let latest = toscalar(dependencies | where name == "run_forward" and customDimensions.run_label == run
    | where customDimensions.content_level_name == "full" | top 1 by timestamp desc | project tostring(customDimensions.forward_id));
dependencies
| where name == "agent_step" and customDimensions.forward_id == latest
| where customDimensions.instance_id == "fastapi_12942"
| project step = toint(customDimensions.step_num), tool = tostring(customDimensions.tool_name),
          seconds = todouble(customDimensions.elapsed_seconds), prompt_tokens = toint(customDimensions.prompt_token_count),
          arguments = tostring(customDimensions.arguments_text), output = tostring(customDimensions.output_text),
          message = tostring(customDimensions.message_text)
| order by step asc
```

Where a run's unresolved tasks stopped (the last tool each one called, and its patch):

```kusto
let run = "devset-m31be-c1";
let latest = toscalar(dependencies | where name == "run_forward" and customDimensions.run_label == run
    | where customDimensions.content_level_name == "full" | top 1 by timestamp desc | project tostring(customDimensions.forward_id));
dependencies
| where name == "agent_task" and customDimensions.forward_id == latest and customDimensions.is_resolved == "False"
| project instance_id = tostring(customDimensions.instance_id), error = tostring(customDimensions.agent_error_code),
          patch = tostring(customDimensions.patch_text)
| join kind=leftouter (
    dependencies
    | where name == "agent_step" and customDimensions.forward_id == latest
    | summarize arg_max(toint(customDimensions.step_num), tool = tostring(customDimensions.tool_name))
        by instance_id = tostring(customDimensions.instance_id)
  ) on instance_id
```

Every failed `edit_file` of a run, with what it tried to replace (`has`, since a step with several tool calls
names them all; add the `latest` line above for a run forwarded more than once):

```kusto
dependencies
| where name == "agent_step" and customDimensions.run_label == "devset-m31be-c1"
| where customDimensions.tool_name has "edit_file" and customDimensions.output_text has "not found"
| project tostring(customDimensions.instance_id), toint(customDimensions.step_num), tostring(customDimensions.arguments_text)
```

The key reads nothing else and changes nothing; the leaderboard watcher's ledger
(`data/tasks/leaderboard_entries.csv`) holds the same scores for a session without it.

## A run's traces in Unity Catalog (spec 041, #857)

A finished development run also goes to the MLflow experiment `/Shared/coding-agent-runs`. Its traces are stored in
the Delta tables of `health_transformation_lab.ops_agent_trace`, which the bundle declares
(`databricks/resources/agent_traces.yml`). There, the experiment's Tool calls tab, its latency percentiles and its
token charts work, and SQL, dashboards and Genie can read every step.

```bash
python kaggle/load_agent_traces.py <runs folder> --label devset-m31be-c1 --agent "ours 31B-e" --model gemma-4-31b
```

- **What gets written:** one trace per task-run. Each model turn is an `LLM` span named `model turn`, with its token
  use and the model. Each tool call is a `TOOL` span named after the tool alone, and is `ERROR` when the tool reported
  an error. That is what MLflow groups its charts by.
- **Secrets:** text is scrubbed exactly as the Azure forwarder's is (`telemetry.scrub_value`).
- **Loading twice:** delete-then-append by `trace_key` (the SHA-256 of run label, agent and task). A reload removes
  any existing trace with that key and writes a fresh one, so a run loaded twice still leaves one trace per key
  (#899). Every written trace carries `file_sha256` (of that task's `result.json`), `loaded_ts` and `git_commit_sha`.

- **Settings:** `DATABRICKS_HOST` and `DATABRICKS_TOKEN` say which workspace to write to. `AGENT_TRACE_EXPERIMENT`
  names the experiment; its default, `/Shared/coding-agent-runs`, is the bundle's and is the same in every
  environment. The loader never creates an experiment: one made outside the bundle would have no Unity Catalog trace
  location.
- **Checking first:** `--dry-run` builds every trace and writes none.
- **This repository's own tasks (#881, #899):** the kernel can't grade them ("Missing test specification"), so pass
  `--verdicts <file>`, the `--out` file of `kaggle/official_verify.py`. Each trace's solved tag then comes from that
  file, a `solved` assessment is logged with the same value, and `verdict_source_code` says which source it was
  (`official_verify` or `kernel`). A task missing from the file is not loaded. The harness note is not the run's
  error (`ended_code` comes from how the agent ended; `kernel_grade_code` is `no_test_spec`, #894).

