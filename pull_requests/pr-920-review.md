# PR 920 review: hard AccessBench perio screening items (#919)

Closes #919. Range: `feat/919-perio-screening-hard-items` vs `main`.

## Verdict

**Ready to merge** once CI is green. No blockers.

## What it does

- Adds ten hard AccessBench rows (`ACC_PERIO_SCR_001`–`010`) with forum/source URLs for periodontal screening access traps.
- Adds `access_hard_items` loader (no planted PHI) and tests.
- Documents design/plan; README pointer. Does not change the Access LLM batch default fixture path.

## Rubric

| Check | Result |
|-------|--------|
| Synthetic only | `is_simulated: true`; no planted PHI |
| Wording | Screening / pathway language; no banned org names |
| Bench | AccessBench (getting care) |
| Contract | Matches #919 Done when / Contract |
| Scope | No gold schema change |

## Non-blocking

- Wire Access LLM batch to this file in a follow-up if desired.
