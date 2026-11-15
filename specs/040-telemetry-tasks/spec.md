# Feature Specification: Coding-agent tasks whose statements are written from a failing run's telemetry

**Feature Branch**: `spec/752-040-telemetry-tasks` (spec); one `feat` or `data` branch per user story

**Created**: 2026-11-15

**Status**: draft

**Input**: the design `docs/superpowers/specs/2026-11-14-telemetry-tasks-design.md` (#714, #716) and its "Decisions
(2026-11-15)" (#736). The owner asked for the recommended next step to be taken. Epic #752.

The 93 history tasks (spec 028) have one source of problem statements, people, and most statements leave out what the
tests need. An AI screen found 76 of the 93 whose tests need a name, path or text the statement never gives. Over five
runs a small local model resolved 26 of 85 task-runs on the other 17 and 1 of 380 on those 76
(`data/tasks/official_agent_runs/README.md`, "The core split"). Since #712 every pipeline run sends telemetry naming
the step, the function, the data label, the counts in and out, and the error type. This spec asks one question:
**does a statement written from a failing run's telemetry let a small local agent fix more than one that only says
what went wrong?**

> Personal learning project, not affiliated. Every record is synthetic. Telemetry carries no note text or row-level
> data, and no statement here may carry a source line, a path or a value.

## What changed between the design and this spec

The design asked that the history tasks be counted first (its "Risks"). The count was made on November 15, 2026, and
with what the repository has already run it changes three things.

1. **The registered test moves to the injected tasks.**
   - 23 of the 93 history tasks have a function the fix edits in their failing test's trace
     (`data/tasks/trace_reach.csv`, `is_edited_in_trace`), and 7 on a failure's traceback.
   - But that trace comes from the task's hidden test. `68_trace_reach.py` says so: it is "not a fair benchmark
     condition".
   - The repository has already given an agent that kind of context. The `report` arm of spec 028 gave each task the
     hidden test's errors plus the public functions its spans recorded. On all 93 tasks against the plain statement,
     both resolved 3, the plain statement alone 1, the report alone 1, neither 88: exact McNemar p = 1.0
     (`data/tasks/official_agent_runs/README.md`, "The paired tests").
   - A fair telemetry statement for a history task needs a failing run that does not use the task's own tests. Most
     history tasks are features: 4 of the 30 screened are fixes (`data/tasks/screening/agent_screen.csv`). So few can
     have one, the paired history comparison cannot carry a test, and US4 describes it instead.
2. **The injected tasks get a baseline.**
   - Injected tasks have no person-written statement, so the design's two conditions for them (`span_names`,
     `span_names_message`) could only be compared with each other.
   - This spec adds `symptom`: the step and what a person would see go wrong, with none of the names telemetry adds.
     `symptom` against `span_names` is the registered test; it asks the spec's question.
3. **Pipeline steps must record their row counts first.**
   - The design's `span_names` gives a failing step's counts in and out, and that is what shows a filter that drops
     rows (`volume_anomaly`).
   - No pipeline span records a row count today. `telemetry.pipeline_step(name, rows=...)` accepts one, but only its
     docstring and `test_telemetry.py` call it, and the run spans from `start_script` (#712) carry none.
   - US6 adds them to the steps the injector can target, before any injected task is built.

The other decisions stand: 200 injected tasks and a 20-task pilot, three seeded runs, the doctor's classification
left for later, and the injected tasks in a dataset of their own.

## The statement conditions

| Condition | Given to the agent | Used on |
|---|---|---|
| `person` | the statement as published | history tasks |
| `symptom` | the step's name and what a person would see without telemetry: it stopped with an error, or it finished but its output looks wrong | injected tasks |
| `span_names` | `symptom`, plus the function that failed, the data label, the counts in and out (US6), the error type | both |
| `span_names_message` | `span_names`, plus the error message with paths, numbers and quoted values masked | both |

## User stories

### US1 - Write a task statement from a failing run's spans, at three levels (P1) #753

- One writer turns the span file of a failing run (`DENTAL_TELEMETRY=file`) into the `symptom`, `span_names` and
  `span_names_message` statements, so the conditions differ only in what they include.
- No statement carries a source line, a file path, an unmasked value or note text. The same span file always gives the
  same text.
- **Independent test:** feed span files that carry each forbidden kind of text and check none comes through; feed the
  same file twice and get the same three statements.

### US2 - Build 200 injected-fault tasks and a 20-task pilot, each gated like spec 028's (P1) #754

- A seeded injector applies one fault to one pipeline function of a passing snapshot. It has four operators, modelled
  on the code-caused classes of `data/ops/incident.csv`: `schema_drift`, `volume_anomaly`, `quality_fail`, `config`.
- A fault is kept only if an existing test fails with it and passes once it is reverted, and a run of the faulted step
  writes a span file. No test is added for a fault.
- 200 main tasks (50 per operator) and 20 pilot tasks (5 per operator), disjoint, all drawn before any agent run.
- **Independent test:** the same seed gives the same tasks; every kept task fails with its fault and passes with its
  revert under the competition's evaluator, as spec 028's tasks do.

### US3 - Pilot, pre-register and run the injected comparison under the competition's evaluator (P1) #755

- The pilot measures how often `symptom` and `span_names` disagree. A pre-registration is then frozen before any main
  run. It fixes the primary test (`symptom` against `span_names`, exact McNemar, two-sided, alpha 0.05), the size (200,
  or the rule for more), the majority-of-three rule and the secondary comparison (`span_names` against
  `span_names_message`).
- The main run gives every task each condition three times, with the competition's evaluator.
- **Independent test:** the pre-registration's SHA-256 on #755 predates the first main-run row; the result table has one
  row per task, condition and run, and the reported p is recomputed from it.

### US4 - History tasks whose failure shows in a pipeline run, described against their person-written statements (P2) #756

- Every published history task is classed by whether a pipeline run at its base commit, without its own tests, fails
  or gives a wrong count where the fix is. For each that does, `person`, `span_names` and `span_names_message` are
  each run three times.
- Described, never tested, and reported apart from the injected tasks. No history statement comes from a hidden
  test's trace.
- **Independent test:** the eligibility table lists all 93 with a reason each; no eligible task's spans come from a run
  that loaded its test patch.

### US5 - Publish the injected tasks as their own dataset, and the history tasks' telemetry statements beside the 93 (P3) #757

- The injected tasks become a Kaggle dataset of their own, meeting "Publishing datasets" in `AGENTS.md`. The history
  tasks' telemetry statements become an added file in the existing task dataset, keyed by task, with the person-written
  statement unchanged.
- **Independent test:** `test_kaggle_dataset_docs.py` and `test_dataset_version.py` pass with both. Publishing waits
  for the owner.

### US6 - Pipeline steps record the rows they read and write on their spans (P1) #758

- Each pipeline step the injector can target records its rows in and out on its own span, as numbers only, so
  `span_names` can give counts. This comes before US2.
- **Independent test:** run one such step on a small synthetic table with telemetry written to a file, and find both
  counts on that step's span.

### Edge cases

- **A faulted step that writes no failing span.** For example, a wrong threshold that only a test notices. The fault is
  kept if a test catches it, and its span file comes from the step's run as it is. `symptom` then says "its output looks
  wrong". If no span file is written at all, the fault is dropped and counted.
- **An error message that names the fix.** `span_names_message` masks paths, numbers and quoted values but may still
  hint. That is what the secondary comparison measures; it is not hidden.
- **A span with no row counts.** For example, a step that reads or writes no table. The statement leaves counts out
  rather than guessing.
- **A fault that two operators could both produce.** Each fault carries the one operator that made it.
- **Fewer than 50 kept faults for an operator.** That operator keeps what it has, the shortfall is reported, and the
  pre-registration states the final size before the main run.

## Requirements

- **FR-001** Every statement in every condition is written by one writer from span files, and none carries a source
  line, a path, an unmasked value or note text.
- **FR-002** Every injected task passes spec 028's gates under the competition's evaluator: it fails with its fault and
  passes with the revert.
- **FR-003** The pilot and the main tasks are disjoint and drawn, with a fixed seed, before any agent run.
- **FR-004** The pre-registration is frozen, with its SHA-256 recorded on #755, before any main-run row exists.
- **FR-005** The primary test is `symptom` against `span_names` on the injected tasks. A task counts as resolved under
  a condition when at least two of its three runs resolve it.
- **FR-006** History and injected results are never pooled. The history comparison is described, not tested.
- **FR-007** No history task's statement is written from a run that used its hidden tests.
- **FR-008** Every GPU run waits for the owner's word, and every publish does too.
- **FR-009** Every step the injector can target records its rows in and out on its own span before any injected task
  is built. No span gains row-level values, note text or paths.
- **FR-010** A statement never reads a span's stack trace. The error message comes only from the span's status, and is
  masked.

## Key entities

- **Injected task**: a spec 028 task whose reference patch reverts one seeded fault. It has one operator, one step,
  one function, a seed, and its three statements.
- **Span file**: the JSON lines one failing run writes under `DENTAL_TELEMETRY=file`. Names and counts only.
- **Statement condition**: one of `person`, `symptom`, `span_names`, `span_names_message`.
- **Run row**: one task, one condition, one seeded run, and its verdict from the competition's evaluator.

## Success criteria

- **SC-001** At least 180 injected tasks (90% of 200) pass the gates, with any shortfall reported per operator.
- **SC-002** Across every statement written, no source line, path, unmasked value or note text appears. A scan over all
  statements finds none.
- **SC-003** The pre-registration predates the first main-run row, as shown by the SHA-256 and timestamp on #755.
- **SC-004** The result reports each condition's resolve rate with its 95% interval, the primary McNemar table and p,
  and the secondary comparison, all recomputable from the committed run table.
- **SC-005** Every history task is classed in or out with a reason, and the eligible ones are described with no test
  claimed.

## Assumptions

- **Cost.** The main run is 200 tasks × 3 conditions × 3 runs = 1,800 task-runs. With the 60-run pilot and up to
  about 270 history runs, the total is about 45 A100 GPU-hours, about 84 USD. That is a rental estimate at the 76
  GPU-seconds a task `colab-statement` measured and the 1.87 USD an hour in `ops/cost_settings.yaml`, without loading
  the model. Adding `symptom` raises the decisions' 1,200 main task-runs to 1,800. Power is unchanged: the primary test
  still pairs two conditions on 200 tasks (design, "Decisions" 1).
- **Agent, model and harness** are those of spec 028's latest pre-registration unless US3's pre-registration names
  others: `gemma-4-e4b-it-qat-w4a16-ct`, `swegemma` 0.2.11, the agent's own budgets.
- **Snapshots** for injected tasks are built from a recent passing commit of `main`, so the pipeline steps send spans
  (#712). They are built, not committed, as for the history tasks.
- This spec names contracts (files, columns, functions) in its issues, as `AGENTS.md` ("What an issue says") requires.

## Out of scope

- The doctor's classification of failures from spans (spec 027); left for a later paper (design, "Decisions" 2).
- New tests to catch a fault. A fault no existing test catches is dropped.
- The `platform` and `cost_anomaly` incident classes: no code change fixes them.
- Any claim about the competition's leaderboard. These are this repository's tasks.

## Risks

- **Injected faults are easier than real ones.** Mitigated by operators modelled on real incident classes, by
  reporting the two sets apart, and by stating that a gain on injected faults may not carry over.
- **`symptom` is a template, not a person.** It stands for the statement that says what went wrong without the names
  the tests need, which the screen found in 76 of 93. It is not a measurement of people's statements, and the results
  will say so.
- **Too few kept faults.** The pre-registration states the final size, and the power table in the design says what
  that size can find.
