# Design: telemetry-grounded tasks, a second source beside the 93 history tasks

Draft, 2026-11-14. Not yet a spec: it becomes one (`specs/NNN-telemetry-tasks/`) once the open questions at the end
are settled. Personal learning project, not affiliated; every record here is synthetic.

## Why

The task set mined from this repository's history (spec 028) has one source of problem statements: issues, pull
requests and commit messages. An AI screen found that the tests of 76 of the 93 published tasks need a name, path or
text the statement never gives, and over five runs a small local model resolved 26 of 85 task-runs on the other 17
tasks and 1 of 380 on those 76 (`AGENTS.md`, "What an issue says"). The statement, not the code, is the bottleneck.

Since spec 014 and #712, every pipeline script and Python job sends telemetry: a run span per script, a span per
`@traced` function, and failures recorded with their error type on the span that raised them. A failing run's spans
already name what a statement often leaves out: the step, the function, the data label, the counts in and out, and
the error type. Telemetry never carries note text or row-level data, so a statement written from it is safe to
publish.

So a second source of statements, written from the telemetry of a failing run, tests one question with this
repository's own tasks: **does a statement written from telemetry let a small local agent fix more than one written
by a person?** It also gives the paper a second kind of evidence beside the history tasks, from a different source
in the same repository.

## The tasks

Each task has the same format as spec 028's (`tasks.jsonl`, `snapshots/`, `graphs/`, `embeddings/`), so the same
harness, the competition's evaluator (`swegemma`) and the same gates apply: the tests fail on the snapshot with the
test patch alone and pass with the reference patch.

Two ways to make them:

1. **From history (few, real).** The history tasks whose fix touched an instrumented pipeline step. Rerun the step at
   `base_commit` with `DENTAL_TELEMETRY=file`, keep the failing run's spans, and write the telemetry statement from
   them. The person-written statement stays as it is, so these tasks are paired.
2. **From injected faults (many, controlled).** Take a passing snapshot. Apply one seeded fault to a pipeline
   function, from operators modelled on the failure classes in `data/ops/incident.csv` that code can cause:
   - a renamed or dropped column (`schema_drift`);
   - a filter that drops rows (`volume_anomaly`);
   - a wrong threshold or unit (`quality_fail`);
   - a setting read under the wrong name (`config`).

   The `platform` and `cost_anomaly` classes are left out, since no code change fixes them. The reference patch
   reverts the fault, and the tests are the existing ones that the fault makes fail. A fault no existing test catches
   is dropped, not given a new test.

## The statement conditions

Each task is run under each condition, so every comparison is paired:

| Condition | The agent is given |
|---|---|
| `person` | the person-written statement (history tasks only) |
| `span_names` | from the failing run's spans: the step, the function, the data label, counts in and out, the error type |
| `span_names_message` | as `span_names`, plus the error message, with paths and values masked |

The difference between `span_names` and `span_names_message` measures how much of any gain comes from the message,
which can hint at the fix.

## How it is measured

- The resolve rate per condition, with 95% intervals.
- Paired comparisons by exact McNemar test, pre-registered before the runs, as in spec 028's failing-test-report
  preregistration.
- Several seeded runs per task and condition, so run-to-run variation is reported, not hidden.
- The history tasks and the injected tasks are reported apart. The headline is the paired history comparison; the
  injected tasks show whether it holds when the fault is known.

## What already exists

- `DENTAL_TELEMETRY=file`, which writes spans offline, one JSON line each (spec 014 US6).
- The harness, gates, snapshots and evaluator check (spec 028, `task_gate.evaluator_verified`).
- The failure classes and owner decisions in `data/ops/incident.csv` (spec 027), for the fault operators.
- `69_failure_report.py` and `68_trace_reach.py`, which already turn failing tests and traces into what an agent
  can be given.

New work: a fault injector (seeded, one operator per fault), a statement writer from span files, and the runs.

## Risks

- **Injected faults are easier than real ones.** Mitigated by modelling operators on real incident classes, keeping
  the history tasks as the headline, and reporting the two sets apart.
- **The statement gives the answer away.** The masked message condition is there to measure it. `span_names` never
  includes source lines, paths or values.
- **Too few history tasks touch an instrumented step.** Count them first. If there are fewer than about 20, the
  history comparison becomes descriptive and the injected set carries the test.

## Open questions

1. How many injected tasks? Enough for the McNemar test to detect a 10-point difference, about 150 to 200, is the
   working target.
2. Should the doctor's classification (failure class and runbook action from spans, spec 027) be a second task kind
   in the same paper, scored by exact match, or kept for a later one?
3. Should the injected tasks be published as a dataset on their own, or only beside the history tasks?
