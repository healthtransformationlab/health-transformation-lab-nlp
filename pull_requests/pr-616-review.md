# PR 616 review: run the Kaggle agent batch from GitHub Actions (#615)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `ci/615-...`, `Closes #615` | ok |
| Test first: retry, persistent failure, workflow shape (`test_gemma_agent.py`) | ok |
| Settings checked before work: cap range, Kaggle credentials and one cheap call | ok |
| Retries explicit (4 tries, 60 s), only for a failure that passes on its own (a dropped upload) | ok |
| Writes idempotent: rows merged by `instance_id`; the commit step runs `always()` | ok |
| No secret in a parameter, file or log (tokens via `$GITHUB_ENV`, masked) | ok |
| No leak: only the published, gated set goes in; bundles are still one task each | ok |
| Full suite | 2216 passed, 4 skipped |

## Notes
- Untested on a GitHub runner: the AppArmor `sysctl` and `unshare` check fail the job early if the runner refuses
  them, before any GPU is used.
- The job's 355-minute limit and the 5.5 h cap leave room for the last kernel's wait; a timed-out job still
  commits the rows it finished.
- Pushing back to the dispatch branch with the workflow token doesn't start CI there; the results PR needs a push
  to run its checks, as the MedGemma workflow says.

## Blocking
None. Adds a workflow without running it; dispatching it uses the Kaggle allowance and is the owner's call.
