# PR 622 review: empty agent patches from published snapshots; ship the code graphs (#621)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `fix/621-...`, `Closes #621` | ok |
| Test first: other-owner snapshot, failing diff raises, graph under either name, missing graph stops the run, workflow keeps outputs | ok |
| Reproduced on the real published snapshot (`htlnlp_pr56.tgz`): 0 bytes before, 566 after | ok |
| Fails loudly: a bad diff raises; missing graphs stop before any upload (no allowance spent) | ok |
| Shipped code: `agent_harness.py` goes to Kaggle; no task's patch touches it (`test_no_task_changes_the_code_the_bundle_ships`) | ok |
| Tar extraction keeps the `tar` filter's safety checks; only the owner changes | ok |
| `@traced` on public functions (new helpers are private or in a script) | ok |
| Full suite | 2244 passed, 4 skipped |

## Notes
- Anyone extracting the published snapshots as a different user hits the same git refusal. The next publish could
  tar with owner 0 too; not needed for our runs now.
- The prompt opens "You are evaluating a software engineering task", and some problem statements read as finished
  work; 6 tasks ended with no tool call because the model took the task as done. Left as is: the wording mirrors the
  competition harness's documented prompt.

## Blocking
None.
