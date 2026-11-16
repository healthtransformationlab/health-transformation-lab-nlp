# PR 846 review: raise Modal's monthly auto-start limit to 60 USD for the 31B-e full run (#845)

| Check | Result |
|---|---|
| Branch `chore/845-028-modal-monthly-60`, `Closes #845`, issue with its four parts before the first commit | ok |
| A spending rule (ADR 0008) changed only on the owner's own word in this session ("Raise limit") | ok |
| One setting, with its source and date; the per-run cap is unchanged at 10 USD | ok |
| Settings change by PR, naming environments: the Modal workflow's cost gate (it reads main) | ok |
| `tests/test_modal_official.py` reads the limits from the file | 25 passed |

## Findings

None blocking.

- **Noted.** Above the Starter plan's 30 USD credit, the owner pays up to 30 USD more this month. Every run still
  stops at its own 10 USD time limit.
- **Noted.** A run branch must match main's gating files. The 31B-e run branch (`data/842-028-modal-31be-full`)
  takes this merge from main before its next chunk is dispatched, or that chunk waits for a reviewer.

## Verdict

Approve. The owner asked for exactly this change. Merge when the checks are green.
