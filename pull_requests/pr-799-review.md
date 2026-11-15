---
pr: 799
branch: feat/753-040-span-statement
title: "040 US1: write a task statement from a failing run's spans, at three levels"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-15
reviewer: a read-only reviewer subagent over 0bb3c7d..0bd8a00 (rubric step 3), each finding then reproduced by the authoring session before acting on it (step 4)
verdict: approve (after the second commit; the first had one blocking finding)
---

# PR Review: 040 US1: write a task statement from a failing run's spans, at three levels

## Summary
`span_statement.py` turns a failing run's spans into the three statements of spec 040. The reviewer asked for
changes: one blocking finding (the masking let note text and values through on realistic messages), four Should-fix
and two nits. Each was reproduced against the code and fixed in the second commit, with a test that fails without
the fix. Nothing blocking remains.

## Scans
- **Secrets:** none. **PHI / real data:** none; every note-like string in the tests is invented. **Organization
  claims:** none.

## Findings and what was done
| # | Severity | Finding | Reproduced by | Outcome |
|---|---|---|---|---|
| 1 | 🔴 Blocking | `_mask` let note text and values through: pandas prints a date it cannot parse unquoted (a whole note came through); a quote left open by telemetry's 500-character cut; apostrophes put quotes out of step (`can't parse '...'`); `\b` missed `V3437`, `patient_3437`, timestamps, `1.5e-3`, minus signs; file names with other extensions | `pd.to_datetime([note])` and each string run through the first commit's `_mask` | fixed: everything after the first `": "` is `<value>`; a quote starts only where no word precedes it and an open quote runs to the end; numbers are masked inside identifiers and with exponents; any short extension is a file name. Tests: the real pandas error and eight parametrized messages |
| 2 | 🟡 Should fix | The innermost failure could be one the code caught: a caught KeyError was named while the run ended on a sibling's ValueError | a real file-exporter run with a caught exception | fixed: follow the failed spans down from the outermost, taking the failed child that ended last; test on a real run |
| 3 | 🟡 Should fix | The step name was not tied to the failure: with several roots or several pipeline steps, the first to start was named even if it succeeded | hand-made spans, two roots and two steps | fixed: the script run span, else the step around the failure, else its outermost span; tests for both, and for a script span over an inner step |
| 4 | 🟡 Should fix | `read_spans` raised on a cut-off last line, which a killed run leaves | a file ending mid-line | fixed: lines that do not decode are skipped; test with a metrics line and a cut-off line |
| 5 | 🟡 Should fix | Nine mutations of the module left all 9 tests passing | the reviewer's mutations | fixed: 17 tests added; the same nine mutations (no ordering, no file names, single quotes only, integers only, no script preference, first-ended, a cap of one, metrics lines kept, no colon rule) now each fail at least one test |
| 6 | 🔵 Nit | A message that embeds a traceback kept its source line | a status message with a traceback | fixed: such a message is left out; test |
| 7 | 🔵 Nit | `attributes: null` raised `AttributeError` | a span with null attributes | fixed: read as empty; test |

## Residual risk, stated in the plan
A message that is a bare value with no `": "` and no quotes cannot be told from an error sentence. The six target
modules raise none such (their messages interpolate file names, counts and settings), and the span already carries
the same text, which `telemetry` keeps under its own rule (no note text in spans). The plan says so.

## Compliance
| Rule | Result |
|---|---|
| Test first | the first commit's tests failed before the module existed; each fix in the second commit has a test that fails without it (shown by the mutations) |
| No path, value, source line or note text in a statement | the masking cases above; never an exception event (FR-010) |
| Every public function `@traced` | `read_spans`, `write_statement`; `test_telemetry_calls` passes |
| Spec before code | spec names #753; plan describes the writer, now with the failure, step and masking rules; tasks T005, T006 ticked |
| Parity, seeds, paths, settings, secrets, writes, alerts | not touched |

## Checks
- `tests/test_span_statement.py`: 26 passed. Whole suite, `pytest -q -n auto tests`: 2,794 passed, 37 skipped.
- `ruff check` on both files: clean.
- CI on 0bd8a00 (first commit): green where it had finished; CI on the second commit is read before merge.

## Should fix
- Nothing before merge.

## Secrets, Real Data and Claims Scan
Secrets: none. Real data: none. Claims: none.
