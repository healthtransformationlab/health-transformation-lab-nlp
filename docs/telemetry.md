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

## Not yet

The pipeline doctor: classify each failure (GPU unavailable, out of memory, schema drift, data
quality, dependency), choose a recovery (retry, repair run, quarantine, escalate), notify downstream
users, and evaluate all of it on this repo's real incidents. That is the next spec; this one gives
it the record to work from.
