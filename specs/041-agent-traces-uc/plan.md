# Implementation plan: Coding-agent traces live in Unity Catalog, declared in the bundle (spec 041)

## Sources of truth

- **Where traces live:** `databricks/resources/agent_traces.yml`, and nothing else. It declares the schema, the
  experiment and the table prefix. The loader's setting `AGENT_TRACE_EXPERIMENT` names the same experiment, and a
  test holds the two equal.
- **What a trace holds:** the run folders that `kaggle/forward_run_telemetry.py` already reads (`result.json` and
  `results/traces/*.json`). The loader reads them the same way, so Azure and Unity Catalog get the same steps.
- **Scrubbing:** `telemetry.scrub_value` (ADR 0010). The loader keeps no list of its own.
- **Table shape:** Databricks'. Our two views read from it; we never write to its tables directly.

## Names (copied to the issues)

| Story | Name | What it is |
|---|---|---|
| US1 #856 | `databricks/resources/agent_traces.yml` | schema key `agent_trace` (name `ops_agent_trace`); experiment key `coding_agent_runs` (name `/Shared/coding-agent-runs`); `trace_location.uc_trace_location` = catalog, schema, `table_prefix: coding_agent`; both `prevent_destroy` |
| US1 | schema grants | `dental_omop_nlp_${bundle.target}_admin`: `USE_SCHEMA`, `CREATE_TABLE`, `MODIFY`, `SELECT` |
| US1 | `databricks/setup-cli@v1.22.1` | in `ci.yml` and `deploy.yml` (1.9.0 is the first with the field; 1.22.1 is more than two weeks old) |
| US1 | `python/tests/test_agent_traces_bundle.py` | |
| US2 #857 | `kaggle/load_agent_traces.py` | `trace_key`, `task_trace`, `load_run`; command line `<runs folder> --label --agent [--limit] [--dry-run]` |
| US2 | trace tags | `trace_key`, `run_label`, `agent_name`, `instance_id`, `repo_name`, `outcome_code`, `ended_code`, `is_resolved`, `loaded_ts`, `git_commit_sha` |
| US2 | setting `AGENT_TRACE_EXPERIMENT` | `/Shared/coding-agent-runs`, the same in every environment; documented in `docs/telemetry.md` |
| US2 | `python/tests/test_load_agent_traces.py`, `python/tests/fixtures/agent_runs/` | |
| US3 #858 | `databricks/notebooks/15_migrate_agent_traces.py` | widgets `source_experiment_id`, `target_experiment_name` |
| US3 | `health_transformation_lab.ops_agent_trace.trace_migration_check` | one row per experiment and assessment name |
| US3 | `python/tests/test_migrate_agent_traces.py` | |
| US4 #859 | `databricks/setup/agent_trace_views.sql` | views `agent_task_run`, `agent_tool_call` |
| US4 | `python/tests/test_agent_trace_views.py` | |

The tables Databricks makes are `coding_agent_otel_spans`, `coding_agent_otel_logs`, `coding_agent_otel_metrics` and
`coding_agent_otel_annotations`, and its views are `coding_agent_trace_metadata` and `coding_agent_trace_unified`. The
probe confirmed the pattern on November 17.

## Why a file of its own

`test_bundle.py` holds `unity_catalog.yml`'s schemas to the bench list in `schemas.py` (spec 022). Trace storage
isn't a bench layer, so it goes in its own resource file. `include: databricks/resources/*.yml` already picks that
file up, and the bench test is left alone. `ops_billing` is the same kind of schema, but it was made by SQL
(`billing_views.sql`); this one is declared.

## What the spans look like (the probe, November 17)

`<prefix>_otel_spans` has a row for each span. Its columns are:
- `trace_id`, `span_id`, `parent_span_id`, `name`, `kind`;
- `start_time_unix_nano`, `end_time_unix_nano`;
- `attributes` (`variant`), `status` (`message`, `code`);
- `resource`, `events`, `links`, and the OpenTelemetry bookkeeping columns.

MLflow keeps a span's type, inputs, outputs and token use under `attributes` (`mlflow.spanType`, `mlflow.spanInputs`,
`mlflow.spanOutputs`, `mlflow.chat.tokenUsage`). It keeps tags and assessments in `<prefix>_trace_metadata`. US4's
views read these keys. US4 starts by listing the exact keys from the migrated spans and writes them into the view
file as comments.

## Order

1. **US1** first. Nothing can be written until the experiment exists.
   - Test first, then the YAML and the CLI pin.
   - `databricks bundle validate -t dev` with CLI 1.22.1, then the merge deploy.
   - Check the experiment's trace location through the API, and record it in the PR.
2. **US3** next. It moves what exists, and US4 needs data to check against.
   - Run the notebook once, by hand, on serverless.
   - Its cost is small but comes from the Free Edition allowance, so the PR records it from `billing_views.sql`.
3. **US2.** The loader is for runs that finish from now on. The pending Colab runs (`cpub-nlp25`, `c31be-nlp25` and
   the rest) are its first input.
4. **US4.** The views, checked against US3's counts.

## Tests first

- US1: read the YAML, check the names, prefix, grants and `prevent_destroy`; check that `ci.yml` and `deploy.yml`
  pin the same CLI and that it is at least 1.9.0; check that no other resource file declares `ops_agent_trace`.
- US2: build fixture run folders (synthetic steps, one with a planted fake secret). A fake client records what would
  be written. Check that the spans and tags match, that the secret is gone, that a second load writes nothing, and
  that a missing setting fails with its name.
- US3: parse the notebook's source: its widgets, its install line, that it never deletes the source experiment, and
  that its count query is delete-then-append by `run_id`.
- US4: parse each view's column list against the contract; check the suffixes and that each view's comment states its
  grain.

## The cleanup

The probe left the schema `health_transformation_lab.scratch_uc_trace_probe` and the experiment
`/Shared/scratch-uc-trace-probe` (made by the analysis session at 04:32 UTC on November 17). They are dropped once
US1's experiment has a trace in it. The schema's comment says it is a probe.
