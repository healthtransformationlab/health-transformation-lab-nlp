---
pr: 796
branch: feat/758-040-step-row-counts
title: "040 US6: pipeline steps record the rows they read and write on their spans"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-15
reviewer: a read-only reviewer subagent over d38476f..8e5a160 (rubric step 3), each finding then traced by the authoring session before acting on it (step 4)
verdict: approve
---

# PR Review: 040 US6: pipeline steps record the rows they read and write on their spans

## Summary
A `counts_rows` decorator in `telemetry.py`, placed directly under `@traced` on 17 pipeline steps, records
`row_in_count` and `row_out_count` on each step's own span, so a statement written from a failing run's telemetry
(spec 040) can show a filter that drops rows. The reviewer found nothing blocking: one test gap (Should fix) and five
nits. All six were checked against the code and fixed in the second commit. Nothing blocking remains.

## Scans
- **Secrets:** none. **PHI / real data:** none; no data file changes. **Organization claims:** none; no banned name or
  wording.

## Findings and what was done
| # | Severity | Finding | Checked by | Outcome |
|---|---|---|---|---|
| 1 | 🟡 Should fix | No test pinned a count of zero, the signal of a filter that drops every row: changing `is not None` to a truthiness test passed every test | the reviewer's mutation in a scratch copy; zero confirmed correct by probe | fixed: `test_a_filter_that_drops_every_row_records_zero_and_so_does_an_empty_table` (3 in, 0 out; 0 in, 0 out) |
| 2 | 🔵 Nit | Nothing enforced "directly under `@traced`": with the order reversed the counts reach the caller's span and no test noticed | the reviewer swapped the decorators on `complete_cases` and probed the enclosing span | fixed: `counts_rows` raises `TypeError` on a function already traced; `test_counts_rows_above_traced_is_refused...` |
| 3 | 🔵 Nit | In profile mode with an exporter on, `traced` called `_profiled` without clearing `_annotatable`, so counts reached the enclosing span (cause predates this PR; this PR adds 17 places that would hit it) | read `traced` and `_profiled` (`telemetry.py`); not reachable today (`39_telemetry_levels.py` sets telemetry off) | fixed: the profile branch clears `_annotatable` as the below-level branch does; `test_in_profile_mode_no_count_lands_on_the_enclosing_span` failed before, passes after |
| 4 | 🔵 Nit | The first argument passed by name was never tested | the reviewer's mutation (`kwargs.get(first)` → `None` passed) | fixed: `test_the_first_table_is_found_when_it_is_passed_by_name` |
| 5 | 🔵 Nit | "not called by `test_study.py`" is wrong: `build_study`, which the tests call, runs `apply_deid`, `read_methods` and `pick_review` | `study.py` lines 302-307; `test_study.py` calls `build_study` | fixed in `plan.md` ("only through `build_study`, never directly") and a dated line on #758; the 17 are unchanged, the rule being a direct call |
| 6 | 🔵 Nit | The docs row sat under spec 014's "Agent runs, offline (US6)", and `ROW_COUNTED` lists the 17 only once their modules are imported | `docs/telemetry.md` section headings | fixed: moved to "Every call, with a common header" as a paragraph, saying "once their modules are imported" |

## Compliance
| Rule | Result |
|---|---|
| Test first | the first commit's test failed 5 of 6 before the code (the sixth, telemetry off, held before); the second commit's order and profile tests failed before their fixes |
| No row values, note text or paths on spans | only integers, through `annotate`'s filter |
| Every public function `@traced`, signatures kept | `test_telemetry_calls` passes; `__wrapped__` chain is traced, then `counts_rows`, then the function, on all 17 |
| Spec before code | `specs/040-telemetry-tasks/spec.md` names #758; `plan.md` lists the 17; `tasks.md` T001 to T003 ticked |
| Python and R parity | no label, scoring, reliability or cost change; `r-parity` green |
| Docs | `docs/telemetry.md` updated |
| Configuration, secrets, writes, alerts | none changed |

## Checks
- `pytest -q -n auto tests`: 2,756 passed, 37 skipped (2,752 on the first commit; 4 tests added).
- The six modules' tests and the telemetry tests: 152 passed, 1 skipped.
- `ruff check` on the changed files: one finding, `S110` at `telemetry.py:182`, already on `main` and not in this diff.
- CI on 8e5a160 (first commit): all eight jobs green. CI on the second commit is read before merge.

## Should fix
- Nothing before merge.
- For US2: the injector reads its targets from `telemetry.ROW_COUNTED` after importing the six modules. `study.py`'s
  `apply_deid`, `read_methods` and `pick_review` are exercised through `build_study` and could be added later if the
  injector needs more targets; each would need its own direct test first.

## Secrets, Real Data and Claims Scan
Secrets: none. Real data: none. Claims: none; no number is presented as a result.
