# Implementation plan: Coding-agent tasks whose statements are written from a failing run's telemetry (spec 040)

## Sources of truth

- **Spans** are what `telemetry.py` writes under `DENTAL_TELEMETRY=file`: one OpenTelemetry span a line, in the
  SDK's own JSON. No second format is made for this spec.
- **Statements** come from one writer (US1) for every condition and both task sets. Nothing else writes one.
- **Task format, gates and verification** are spec 028's: `task_gate.py` (including `evaluator_verified`) and the
  competition's evaluator.
- **Runs and the paired test** reuse what the context arms used: `kaggle/official_agent_run.py --label <arm>` (or
  `kaggle/colab_official.py` on Colab) and `python/scripts/70_context_pairs.py` for the exact McNemar test. Each is
  extended, not copied.

## Names (copied to the issues)

| Story | Name | What it is |
|---|---|---|
| US6 #758 | span attributes `row_in_count`, `row_out_count` | integers on the targeted steps' own spans |
| US6 | `python/tests/test_step_row_counts.py` | runs one step on a small synthetic frame under `DENTAL_TELEMETRY=file` |
| US1 #753 | `python/health_transformation_lab_nlp/span_statement.py` | `read_spans(path: Path) -> list[dict]`, `write_statement(spans: list[dict], condition: str) -> str`, `CONDITIONS = ("symptom", "span_names", "span_names_message")`; every public function `@traced` |
| US1 | `python/tests/test_span_statement.py` | |
| US2 #754 | `python/scripts/74_inject_faults.py --seed <int> --per-operator 50 --pilot-per-operator 5` | 74 is the next free script number on `main` on November 15, 2026 |
| US2 | `data/tasks/injected/injected_task_manifest.csv` | one row per kept task: `instance_id`, `fault_operator_code`, `is_pilot`, `step_name`, `function_name`, `snapshot_commit_sha`, `fault_seed_num` |
| US2 | `data/tasks/injected/fault_attempts.csv` | one row per fault tried: `fault_attempt_num`, `fault_operator_code`, `step_name`, `function_name`, `fault_seed_num`, `is_kept`, `drop_reason_code` (`no_test_fails`, `revert_fails`, `no_span_file`, `target_reached`) |
| US3 #755 | `specs/040-telemetry-tasks/preregistration-injected-run.md` | frozen before the main run; SHA-256 on #755 |
| US3 | `data/tasks/telemetry_runs/injected_runs.csv` | one row per task, condition and run: `instance_id`, `statement_condition_code`, `run_seed_num`, `is_resolved`, `is_pilot`, then the run columns of `data/tasks/official_agent_runs/` tables |
| US3 | `data/tasks/telemetry_runs/README.md` | the result, written as `official_agent_runs/README.md` is |
| US4 #756 | `data/tasks/telemetry_runs/history_eligibility.csv` | one row per published history task: `instance_id`, `is_pipeline_failure`, `eligibility_reason_code` |
| US4 | `data/tasks/telemetry_runs/history_runs.csv` | as `injected_runs.csv`; `statement_condition_code` in `person`, `span_names`, `span_names_message` |
| US5 #757 | Kaggle dataset `health-transformation-lab-injected-fault-tasks` | slug confirmed on #757 before the first publish |
| US5 | `kaggle/cards/injected_tasks.md`, `kaggle/covers/health-transformation-lab-injected-fault-tasks.png` | |
| US5 | `telemetry_statements.csv` in the existing task dataset | `instance_id`, `statement_condition_code`, `statement_text` |

`statement_condition_code` takes `person`, `symptom`, `span_names` or `span_names_message`.

## Steps the injector can target

These modules each have their own test file and `@traced` functions that take or return a table. Four of them
match pipelines in `data/ops/incident.csv`:

| Module | Its tests | Incident it is modelled on |
|---|---|---|
| `results_store.py` | `test_results_store.py` | `load_results` / `load` (`schema_drift`); `kaggle_medgemma` / `record_results` (`volume_anomaly`) |
| `nhanes.py` | `test_nhanes.py` | `nhanes_perio` / `load` (`config`) |
| `study.py` | `test_study.py` | `study_benchmark` / `build_and_benchmark` (`quality_fail`) |
| `completeness.py` | `test_completeness.py` | |
| `tooth_loss_dq.py` | `test_tooth_loss_dq.py` | |
| `dq_site.py` | `test_dq_site.py` | |

US6's pull request lists the exact functions: those in these modules that take or return a table and are called by
the module's own tests. Each gets `row_in_count` and `row_out_count`. The injector targets only that list.

A traced function makes a span only at or above the level `DENTAL_TELEMETRY_LEVEL` asks for (`telemetry_levels.yaml`;
the default is `call`), and `annotate` writes nothing when there is no span. So US6's test, the injector and US4 run
each step with `DENTAL_TELEMETRY_LEVEL=detail`, and the run's settings record it.

## How the writer reads a span file (US1)

- Each line's `name`, `parent_id`, `status` (`status_code`, `description`) and `attributes`: `pipeline.step`,
  `pipeline.kind`, `data.label`, `error.type`, `row_in_count`, `row_out_count`.
- **Never** an event's `exception.stacktrace` or `exception.message`. The stack trace carries paths and source lines.
  The message comes only from `status.description`, which `telemetry._record_failure` already cuts to 500
  characters.
- **`symptom`**: the run span's `pipeline.step`, and the outcome. It "stopped with an error" if any span has status
  `ERROR`; otherwise it "finished, but its output looks wrong". The issue's third outcome, "its checks failed", has
  no span attribute to come from today. It is left out, and #753 says so in a dated line.
- **`span_names`**: `symptom`, plus the innermost `ERROR` span's `name` (the function), `data.label`, `error.type`,
  and `row_in_count` and `row_out_count` when the span has them.
- **`span_names_message`**: `span_names`, plus `status.description` with every path, number and quoted value
  replaced by `<path>`, `<n>` and `<value>`, cut to 240 characters as `69_failure_report.py` cuts error lines.
- The same lines always give the same text: spans are ordered by `start_time`, and no clock or random value is read.

## How the pieces fit

1. **US6** first: counts on the targeted steps' spans.
2. **US1**: the writer, tested on fixture span files (no pipeline run needed).
3. **US2**: the injector applies each operator to a targeted function on a snapshot of a recent passing commit of
   `main`. It runs the module's tests (a fault is kept only if one fails, and all pass once it is reverted) and runs
   the step under `DENTAL_TELEMETRY=file` to get its span file. It then writes the task in spec 028's format with the
   three statements from US1. It draws the pilot and main tasks from one seeded shuffle, the pilot first.
4. **US3**: the pilot (20 × 3 conditions × 1 run) gives the disagreement between `symptom` and `span_names`. The
   pre-registration is written from it and frozen. The main run follows (n × 3 × 3). `70_context_pairs.py` gains an
   option to read `injected_runs.csv`, apply the majority-of-three rule and print the primary and secondary tables.
5. **US4** can run once US1 is done. It classes the 93 history tasks by running each base commit's pipeline step
   without the test patch, then writes and runs the statements for those that fail there.
6. **US5** last, and only on the owner's word.

## Tests first (each story)

- `test_step_row_counts.py`: one targeted step on a three-row synthetic frame writes both counts to its span. A
  step with no table writes neither.
- `test_span_statement.py`: fixture span files carrying a stack trace, an absolute path, a quoted value, a number in
  the message and a note-like string. No condition's text contains any of them, and `ValueError` names an unknown
  condition. The same file read twice gives identical text. A span with no counts gives a `span_names` without them.
- The injector: a test on a tiny fixture module with one tested function. The same seed gives the same faults; a
  fault no test catches is dropped with `no_test_fails`; a kept fault's revert passes.
- The paired test: `70_context_pairs.py`'s majority-of-three rule on a hand-made table gives the expected McNemar
  counts.

## Idempotence and safety

- The injector and the run tables are rewritten by key (`instance_id`, and `statement_condition_code` and
  `run_seed_num` for runs), never appended. Every row carries `git_commit_sha`.
- Snapshots, graphs and embeddings are built, not committed, as for the history tasks.
- **Compute.** About 45 A100 GPU-hours in all (spec, "Assumptions"). Each GPU run waits for the owner's word. If an
  allowance would stop a run, it is raised first, as `AGENTS.md` ("Failures, retries and reruns") requires.
- No secret, note text, row value or path enters a span, a statement or a table.

## Out of scope (from spec.md)

The doctor's classification; new tests for faults; the `platform` and `cost_anomaly` classes; any leaderboard claim.
