# PR 848 review: check what a Colab tab would run before opening one (#847)

Reviewed by the author session against `AGENTS.md` and `.claude/review-rubric.md`.

| Check | Result |
|---|---|
| Branch `feat/847-028-colab-status`, `Closes #847`, issue with its four parts before the first commit | ok |
| Test first: `test_colab_status.py` failed on import before `kaggle/colab_status.py` existed | ok |
| Read only: it downloads `session.json` and the run list, and starts nothing | ok |
| No credential in code or output; the Kaggle client's URL printing is silenced | ok |
| A rules change (AGENTS.md), asked for by the owner in this session ("add to agent.md") | ok |
| Wording, organisation names, operations rules | the checks pass |

## Findings

None blocking.

- **Noted.** `running` means an upload in the last 20 minutes. A run between uploads (one every eight minutes) can't
  read as stale sooner than that, and one that dropped reads as `running` for up to 20 minutes.
- **Noted.** The VPN is "suspected", not shown: the tabs that dropped left no error. The rule's other advice, the check
  and an awake laptop, holds either way.

## Verdict

Approve. It starts no run and publishes nothing. Merge when the checks are green.
