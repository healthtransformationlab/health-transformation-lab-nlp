# PR 895 review: our own repos' traces no longer say "error" when only the kernel's grading was missing (#894)

Reviewed against `AGENTS.md`, `CLAUDE.md` and `.claude/review-rubric.md`.

| Check | Result |
|---|---|
| One issue with its four parts, branch `fix/894-041-no-test-spec-not-error`, `Closes #894` | yes |
| Regression test first | two new tests and the changed root-span test failed on main, then passed: 38 passed with `test_forward_run_telemetry.py` |
| Contract | `_run_error`, tag `kernel_grade_code` (`graded`, `no_test_spec`), as the issue names them |
| Data names | `kernel_grade_code` has the `_code` suffix for a value from a fixed set |
| Shared code | `forward_run_telemetry._error` is unchanged, so the Azure forwarder behaves as before |
| Real data | c31be8-nlp25 now reads 17 ended_itself, 5 call_cap, 3 time_cap; before, 22 read error |

## Findings

- **Not blocking:** traces already in the experiment keep the old ending until they are reloaded. The owner approved deleting and reloading them (November 21); that is done after merge, with the same official verdicts.

Nothing blocking.
