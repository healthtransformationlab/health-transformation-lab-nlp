# PR 862 review: a committed loader writes a finished run's traces to the Unity Catalog experiment

Closes #857. Range: `origin/main..feat/857-041-agent-trace-loader`. Files: `kaggle/load_agent_traces.py` (new),
`python/tests/test_load_agent_traces.py` (new), `python/tests/fixtures/agent_runs/` (new, synthetic),
`docs/telemetry.md`, `specs/041-agent-traces-uc/plan.md`, `specs/041-agent-traces-uc/tasks.md`.

## Scans

- **Secrets:** none committed. The fixture holds the placeholder `__FAKE_TOKEN__`; the test builds a token-shaped
  string in memory and checks the scrubber removes it from every span. The loader reads the workspace from
  `DATABRICKS_HOST` and `DATABRICKS_TOKEN` and never prints either.
- **Real data:** none in the repository. The fixtures are made up. The traces the loader writes (to the workspace,
  not the repository) are coding-agent runs on public code, scrubbed under ADR 0010; they carry the competition's
  practice task texts, which stay in the workspace.
- **Organization claims:** none.

## Findings (verified)

- 🔴 Found and fixed in this PR: the first real write (to the probe experiment) was dropped by MLflow with no error,
  because spans were started with only `experiment_id`. Routed through `set_experiment(trace_location=...)` they
  arrive. A test with a client that drops every write checks the loader reports them as `unconfirmed`.
- 🟡 Should fix (not blocking): `confirm()` waits up to 5 minutes and searches by `run_label`. A run label
  with thousands of traces would page through them all; today's largest is 33.
- 🟡 Should fix (not blocking): a turn with two tool calls gives the second call the observation whose tool name
  matches, else the next one in order. Two calls of the same tool in one turn are matched in order. That holds
  for every trace read so far.
- 🔵 Nit: tool spans sit beside their turn under the task, not inside it, because a tool call starts when the turn
  ends. plan.md says so.

## Compliance

| Rule | Result |
|---|---|
| Test first | ✅ the 14 first tests failed (no module); the drop and GenAI-name tests failed before their fixes |
| Idempotent writes | ✅ `trace_key` skip; a second load of 33 wrote 0 |
| Batch key on every row | ✅ `loaded_ts`, `git_commit_sha`, and `mlflow.sourceRun` naming the load's MLflow run |
| Settings checked first | ✅ `DATABRICKS_HOST`, the runs folder, the label's characters, and that the experiment exists with a Unity Catalog location |
| Secrets scrubbed (ADR 0010) | ✅ `telemetry.scrub_value` on every text |
| Changed names recorded on the issue | ✅ dated lines on #857 for the span shape, `--model`, `built` and `call_cap` |

## Checks

- `pytest -q tests/test_load_agent_traces.py`: 16 passed.
- `pytest -q tests --deselect tests/test_mlops.py`: 3002 passed, 25 skipped.
- Real load: `devset-m31be-c1`, 33 written and confirmed, then 0 written and 33 skipped.

## Verdict

Ready to merge once CI is green.
