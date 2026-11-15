# Tasks: Coding-agent tasks whose statements are written from a failing run's telemetry (spec 040)

## US6 - pipeline steps record their rows in and out (#758)

- [ ] T001 [US6] Failing test `python/tests/test_step_row_counts.py` (plan, "Tests first")
- [ ] T002 [US6] List the targeted functions in the six modules (plan, "Steps the injector can target") in the PR
- [ ] T003 [US6] Record `row_in_count` and `row_out_count` on each listed function's span

## US1 - a statement from a failing run's spans (#753)

- [x] T004 [US1] Add the dated line to #753 that drops the "checks failed" outcome (plan, "How the writer reads a span
  file")
- [ ] T005 [US1] Failing test `python/tests/test_span_statement.py` with fixture span files
- [ ] T006 [US1] `health_transformation_lab_nlp.span_statement`: `read_spans`, `write_statement`, `CONDITIONS`, all
  `@traced`

## US2 - 200 injected tasks and a 20-task pilot (#754)

- [ ] T007 [US2] Failing test of the injector on a fixture module
- [ ] T008 [US2] `python/scripts/74_inject_faults.py`: the four operators, the gates, the span file, the three
  statements, one seeded shuffle for the pilot then the main set
- [ ] T009 [US2] Commit `injected_task_manifest.csv` and `fault_attempts.csv`, with each operator's kept count and
  shortfall in the PR

## US3 - pilot, pre-register, run (#755)

- [ ] T010 [US3] Pilot run: 20 tasks × 3 conditions × 1 run (owner's word first)
- [ ] T011 [US3] Write and freeze `preregistration-injected-run.md`; record its SHA-256 on #755
- [ ] T012 [US3] Failing test, then `70_context_pairs.py` reads `injected_runs.csv` with the majority-of-three rule
- [ ] T013 [US3] Main run: n × 3 × 3 (owner's word first); `injected_runs.csv` and `telemetry_runs/README.md`

## US4 - history tasks, described (#756)

- [ ] T014 [US4] `history_eligibility.csv`: all 93 classed, with a reason each
- [ ] T015 [US4] Statements and runs for the eligible tasks (owner's word first); `history_runs.csv`; described in the
  README, apart from the injected result

## US5 - publish (#757)

- [ ] T016 [US5] Card, cover, `dataset_docs.yaml` entries, version and changelog, and a notebook for the injected
  dataset
- [ ] T017 [US5] `telemetry_statements.csv` in the existing task dataset, with a MINOR version bump
- [ ] T018 [US5] Publish both, on the owner's word

## Across the spec

- [ ] T019 One PR per user story, each `Closes #<issue>`, with a review in `pull_requests/pr-<n>-review.md`
- [ ] T020 `/speckit-analyze` to cross-check spec, plan and tasks before the first `feat` branch
