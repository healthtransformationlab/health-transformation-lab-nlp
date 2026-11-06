# PR 623 review: drop the 20 agent rows the harness emptied (#621)

| Check | Result |
|---|---|
| Branch `data/621-...`, `Refs #621` | ok |
| Only those 20 rows go: every one `agent_patch_bytes` 0, run_ts after the workflow's start (asserted when dropped) | ok |
| Evidence: transcripts show successful edits; published snapshot reproduces the empty diff | ok |
| Remaining 36 rows unchanged | ok |

## Blocking
None. Deletes data: waits for the owner's "merge", after PR 622.
