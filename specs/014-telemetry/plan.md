# Implementation plan: pipeline telemetry (spec 014)

US1 to US6 were built before this repository kept a plan beside each spec; their tasks are in `spec.md`'s revisions.
This plan covers US7 and US8.

## US7 - Leaderboard entries and the GPU runs' spans reach Azure (#791)

### Sources of truth

- **Spans** are what `telemetry.py` writes under `DENTAL_TELEMETRY=file`, and what `kaggle/bundle_telemetry.py` and
  `kaggle/official_agent_kernel.py` write in the same layout: one OpenTelemetry span a JSON line. One reader handles
  all three; no second format.
- **Where spans go** stays the one switch, `DENTAL_TELEMETRY`, with `APPLICATIONINSIGHTS_CONNECTION_STRING` for
  `azure`. The workflow maps its secret onto that name; nothing reads a second name.
- **An entry's status, score and dates** come from the Kaggle API only. Its run on Kaggle's machines can't be traced:
  no code of ours runs there.

### Names (copied to the issue)

| Name | What it is |
|---|---|
| `kaggle/submission_watch.py` | `entry_rows(submissions: list[dict], ledger: list[dict], now_ts: str) -> list[dict]`, `status_changes(old: list[dict], new: list[dict]) -> list[dict]`, `main(argv=None) -> int`; run as `python kaggle/submission_watch.py --competition gemma-4-developer-agent --ledger data/tasks/leaderboard_entries.csv` |
| `data/tasks/leaderboard_entries.csv` | one row per entry: `ref`, `description`, `submitted_ts`, `status`, `public_score`, `first_seen_ts`, `completed_ts`, `scoring_hours`, `agent_commit_sha` |
| span `leaderboard_entry` | attributes `submission_ref_id`, `status_code`, `public_score_ratio` (and `previous_status_code`), under the run span `submission_watch` |
| `health_transformation_lab_nlp.telemetry.forward_spans(path: Path) -> int` | sends a `telemetry.jsonl` through the configured exporter; returns the count sent |
| `kaggle/official_agent_run.py` `forward_run_telemetry(out: Path) -> int` | called by `--collect` after a run's output is read; the run span `official_agent_run` |
| `.github/workflows/leaderboard-watch.yml` | `cron: '0 */2 * * *'` and `workflow_dispatch`, environment `dev` |
| GitHub secret `APPINSIGHTS_CONNECTION_STRING` (environment `dev`) | in `ops/secrets_register.yaml` |

### Approach

1. **The ledger.** `entry_rows` merges what the API returns now with the ledger, by ref: one row per entry, entries
   the API left out kept as they were, overwritten whole (idempotent). `first_seen_ts` is the first watch that saw an
   entry; `completed_ts` the first watch that saw it complete (the API gives no completion time, so it is within two
   hours of the real one), empty for an entry already complete when first seen; `scoring_hours` is the difference
   from `submitted_ts`. `agent_commit_sha` is a 7 to 40 character hex commit after `main ` in the description.
2. **Hidden pending entries.** The submissions list hides a pending entry, so each ledger entry not complete that the
   list leaves out is fetched by ref (`KaggleApi.get_submission` in kaggle 2.2.5).
3. **Spans.** `status_changes` lists new entries and changed statuses; each becomes one `leaderboard_entry` span
   (ref, status and score; never the description).
4. **Alert.** An entry that turns to error ends the run with exit code 1 after the ledger is written: SEV2, the
   workflow fails and GitHub emails the owner. It fails again on each watch until the ledger recording it is merged.
5. **Forwarding.** `forward_spans` reads the span lines (metrics lines and a cut-off last line left out), sorts them by
   start time, starts each span with its original start time under its parent's new span (a span whose parent isn't
   in the file starts its own trace), then ends them, children first, with their original end times and statuses.
   Attributes keep numbers, booleans and text of at most 64 characters. Exporter off or no file: 0.
6. **The runner.** `--collect` calls `telemetry.setup()` and opens the run span; after a batch's output is read,
   `forward_run_telemetry` forwards its `telemetry.jsonl` (a run without `--telemetry` has none).
7. **The workflow** copies `kaggle-medgemma.yml`'s results PR (a `kaggle-results/*` branch from `main`; a PR opened by
   the workflow token starts no CI). The watch step records its exit code; the PR step runs after it; a last step fails
   the job when an entry is in error. Without the connection-string secret: `::warning::`, telemetry off.

### Tests (no network)

- `python/tests/test_leaderboard_watch.py`: `entry_rows`, `status_changes`, `main` with a stand-in API (hidden pending
  entry looked up, ledger written once, one span per change, a rerun idempotent, an error ends non-zero, no token
  stops at once), the committed ledger, the workflow, the register, this spec and plan.
- `python/tests/test_telemetry_forward.py`: `forward_spans` with the `memory` exporter (times, attributes, parents,
  status; the `file` exporter's own output; skipped lines; exporter off; no file) and the runner's `--collect`.

## US8 - Development runs on Modal, Colab and Kaggle reach Azure (#830)

- **Where it runs:** a `workflow_dispatch` workflow in the `dev` environment, because only it holds
  `APPINSIGHTS_CONNECTION_STRING`; agent sessions never do.
- **What it sends:** `kaggle/forward_run_telemetry.py` reads `tasks/*/result.json` under the downloaded results dataset
  and sends `run_forward` with one `agent_task` child per task through `telemetry.pipeline_step`, numbers and short
  labels only; `telemetry.forward_spans` sends any `telemetry.jsonl` (US7's reader, no second format).
- **Contract:** `task_attrs(result, instance_id)`; spans `run_forward`, `agent_task`; workflow inputs `results_dataset`,
  `label`, `platform`.
- **Tests:** `python/tests/test_forward_run_telemetry.py` (memory exporter; no task text or patch in any attribute).

