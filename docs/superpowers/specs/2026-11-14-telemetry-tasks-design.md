# Design: telemetry-grounded tasks, a second source beside the 93 history tasks

Draft, 2026-11-14; its three open questions were settled on 2026-11-15 ("Decisions", at the end). Not yet a spec:
it becomes one (`specs/NNN-telemetry-tasks/`) next. Personal learning project, not affiliated; every record here is
synthetic.

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

## Decisions (2026-11-15)

The owner asked for the recommended answers to be taken (#736). The spec that follows can reopen any of them.

### 1. Two hundred injected tasks, 50 per fault class, sized before any run

- **The number.** 200 tasks, 50 for each operator (`schema_drift`, `volume_anomaly`, `quality_fail`, `config`). An
  operator that cannot reach 50 faults an existing test catches keeps the ones it has, and the shortfall is
  reported. No test is added and no class is filled from another.
- **Why 200, not 150.** The registered test is the exact McNemar test, and its power depends on the share of tasks
  where the two conditions disagree. Two runs of the same arm on the same 93 tasks already disagree on 3, all among
  the 17 of the core split (the tasks whose statement gives what their tests need): 18% of those 17
  (`data/tasks/official_agent_runs/README.md`, "Two runs of the same baseline" and "The core split"). A real
  difference adds to that. Power to detect a 10-point difference, two-sided, alpha 0.05:

  | Tasks | 15% disagree | 20% | 25% | 30% |
  |---|---|---|---|---|
  | 150 | 0.88 | 0.75 | 0.64 | 0.56 |
  | 200 | 0.96 | 0.88 | 0.79 | 0.70 |
  | 250 | 0.99 | 0.94 | 0.88 | 0.80 |

  150 tasks keep 80% power only while at most 17% of tasks disagree; 200 keep it up to 24%, 250 up to 30%. Each
  cell is exact: the number of disagreeing tasks is binomial, and so is the split of those tasks between the two
  conditions.
- **A pilot first, outside the 200.** 20 more tasks, 5 per operator, one run per condition. They check the injector
  and the statement writer end to end and measure how often the conditions disagree. If more than 24% do, the
  pre-registration either adds tasks (250) or names the larger difference 200 can find (12 points at 30%), decided
  before any of the 200 runs. The pilot's tasks are never counted.
- **Repeats.** Three seeded runs per task and condition. The registered test counts a task as resolved under a
  condition when at least two of its three runs resolve it; each run's own result is reported beside it.
- **Cost.** 200 tasks, 2 telemetry conditions and 3 runs are 1,200 task-runs. At the 76 GPU-seconds a task that
  `colab-statement` measured on one A100, that is about 25 GPU-hours, about 47 USD at the 1.87 USD an A100 hour in
  `ops/cost_settings.yaml`: a rental estimate, not what Colab charges, and without loading the model. One task per
  Kaggle kernel, as on November 10 (21 kernels in 3.2 hours), would take about 183 kernel-hours, six weeks of the
  account's 30-hour weekly allowance. So cost does not limit the size; how many faults existing tests catch does.
- **Revisit** if the pilot's disagreement is above 24%, or if fewer than about 30 faults per operator pass the
  gates.

### 2. The doctor's classification waits for a later paper

- **Kept out.** This design asks one question, whether a statement written from telemetry helps a small local agent
  fix the code, and scores every task one way: the competition's evaluator runs its tests. Naming the failure class
  and runbook action from spans is scored by exact match against `data/ops/incident.csv`, in another format, by
  another harness (spec 027). One paper would split its words and its runs between two questions.
- **What carries over.** The span files and the statement writer this design builds are what a classification task
  would read, so spec 027 can reuse them.
- **Revisit** once the telemetry comparison is reported, or if spec 027 needs the injected faults as its cases.

### 3. Injected tasks get a dataset of their own; history tasks' telemetry statements go beside the 93

- **Injected tasks: their own dataset.** The published task dataset's card says each task "is a real change: the
  issue or pull-request text written at the time, the code patch, and the tests that went with it"
  (`kaggle/cards/tasks.md`), and `tier_code` says which of those texts the statement is. An injected fault is
  neither: its patch reverts a seeded change and a program writes its statement. Mixed in, it would make that
  sentence false and give `tier_code` a value it was not built for. On its own it is versioned separately (spec
  039) and meets "Publishing datasets" in `AGENTS.md` like any other: a card, a cover, every file and column
  described, a public notebook.
- **History tasks: beside the 93.** A telemetry statement for a history task is a second statement for the same
  task, not a new task. It goes in the existing dataset as an added file keyed by `instance_id`, and the
  person-written `problem_statement` stays as it is, so the card stays true.
- Publishing either still waits for the owner, as every publish does.
- **Revisit** if the spec finds a reader needs both sets in one place: add a notebook that loads both, not a combined
  dataset.
