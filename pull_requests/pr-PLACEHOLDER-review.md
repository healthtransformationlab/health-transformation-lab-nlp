# PR review: 033 BUG1, record full reruns on the rebuilt notes (#550)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Issue and branch | `Closes #550`; branch `fix/550-467-record-after-rebuild` |
| Test first | `test_a_full_run_on_rebuilt_notes_replaces_a_larger_file_from_the_old_notes` failed before the fix; `test_a_file_already_on_the_current_notes_still_sets_the_bar` guards the old rule |
| Real data | `kaggle/record_results.py` on the MedGemma 1.5 Kaggle output (223 notes) now records it (rc 0) into a scratch copy |
| Scope | one condition in `results_store.record`; a test run on the current notes is still refused |
| Parity, wording, org names | not touched |

Nothing blocking.
