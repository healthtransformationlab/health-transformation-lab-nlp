# PR 667 review: the coding agent's runs are traced too, offline to a file (#666)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `feat/666-014-agent-run-telemetry`, `Closes #666`; spec 014 has US6 with the issue number and a dated revision with its tasks | ok |
| Test first: `test_telemetry_agent.py` had 17 of its first 18 tests failing before any code (the 18th pins the official kernel as it is), then 2 more for the runner; all 20 pass | ok |
| `DENTAL_TELEMETRY=file` writes one JSON line a span to `DENTAL_TELEMETRY_FILE`, children first, with the common header; `file` without a path warns and runs with telemetry off (an optional setting: warn and carry on) | ok |
| The file is opened for writing, not appending: a rerun replaces it (AGENTS.md, idempotent writes) | ok |
| `annotate()` keeps numbers, booleans and short `_name`/`_code`/`_id` labels (at most 64 characters) and drops other text, so no prompt, reply, command or patch reaches a span (AGENTS.md: never note text or row-level data in spans) | ok |
| `annotate()` writes on the span the current function made, and on nothing when it made none (telemetry off, its level, or past `DENTAL_TELEMETRY_MAX_CALLS`); a test shows it never lands on the caller's span | ok |
| Each model turn: prompt, cached and output token counts, seconds, and whether it hit the context limit; each tool call: a known tool's name (never what the model typed) and its error type | ok |
| The bundle ships `kaggle/bundle_telemetry.py`, not the package's module, which tasks change (`touched_shipped` is unchanged); it uses the standard library only (the existing `-I` import test passes) and writes the SDK's JSON layout, checked key for key against a span from the package's `file` exporter | ok |
| The bundle's tracer keeps what the package keeps (a test passes the same attributes to both) and records an error by its type, never its message | ok |
| The local-harness kernel writes `/kaggle/working/telemetry.jsonl` beside `result.json`; the runner clears the kernel's output folder before each download and keeps one file a task under `data/tasks/agent_runs/telemetry/<model>/` | ok |
| The official evaluator's kernel is unchanged and keeps `OTEL_SDK_DISABLED`, so its runs stay comparable with the competition's | ok |
| Pipelines: `setup()` now shuts down (flushes) the providers it made before making new ones, and at exit after the run span ends; the existing telemetry tests pass | ok |
| Harness behaviour is unchanged: annotations are no-ops with telemetry off, and the harness, model and bundle tests pass | ok |
| Fast checks before pushing: telemetry, harness, bundle, official-agent, wording, organisation-name and benchmark-order tests, 182 passed | ok |
| No secrets: nothing reads or writes the Application Insights key; merging starts no run and publishes nothing | ok |

## Notes
- Not in this PR (spec 014 T607, T608): a script that sums the files into a cost-and-performance table, and sending
  the files to Application Insights. The connection string is only in the Databricks secret scope, so the owner
  chooses between a Databricks job and a GitHub environment secret.
- The full suite was still running when this was pushed; its result goes on the PR.
