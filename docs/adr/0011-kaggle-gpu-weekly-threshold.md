# ADR 0011: Kaggle GPU runs may start under a weekly threshold

Date: 2026-11-19 · Status: accepted · Issue: #886

Amends ADR 0007's rule that every Kaggle GPU run needs a fresh owner yes. The rest of ADR 0007 stands
(leaderboard for score questions, traces and CPU first, Colab by default, one change per entry).

## Context

ADR 0007 made the Kaggle GPU pool a reserve and required the owner's explicit yes for each Kaggle GPU run.
That stopped overnight and autorun tools (and agent sessions) from chaining mechanism checks without waking
the owner, even when tens of hours were left above the reserve.

The owner asked on November 19, 2026 to turn that per-run yes into a **weekly threshold**, so rounds can
start on their own while the pool stays above the reserve floor. Modal already has a parallel pattern
(ADR 0008: start under a cost cap; wait above it).

Colab remains the default for GPU work that does not need the competition's own hardware or image.

## Decision

- **Reserve floor.** Until the last two days before the weekly refresh (Saturday 00:00 UTC), keep about
  **10 hours** unused. In those last two days the floor is **0**.
- **Above the floor, Kaggle GPU runs may start without a fresh yes** — by hand, from an agent session, or
  from overnight/autorun — when all of these hold:
  - `python kaggle/gpu_quota.py` shows hours left strictly above the floor;
  - no other GPU run is in progress on the account (one at a time; tell other sessions first);
  - the question could not be answered from recorded traces or CPU;
  - Colab was considered first; Kaggle is used only when the competition's hardware or image decides the answer.
- **At or below the floor, each Kaggle GPU run needs the owner's explicit yes** in the session that starts
  it. "Do what you recommend" does not spend the reserve.
- **Leaderboard submissions always need the owner's explicit yes** for that submit. The weekly threshold
  covers compute only, never a board entry.
- **Read the quota before and after every run** and put the cost in the run's record. A run that would
  cross the floor stops and waits for yes unless the owner already approved spending the reserve.
- **Colab stays the default** (ADR 0007). This ADR does not pre-approve burning Colab compute units without
  the owner having a tab or queue open for that work.

## Consequences

- Overnight/autorun and agent sessions can chain Kaggle mechanism checks while the week still has headroom
  above the floor, without a ping for every kernel.
- The reserve still protects a late-week change that matters.
- Dual bookkeeping stays: Colab for most work; Kaggle only when the image or hardware is the question.
- If autorun drains toward the floor faster than expected, tighten by raising the floor in a follow-up ADR,
  not by silent per-session caps.

## Revisit when

- The weekly allowance or Colab-linked hours change.
- Autorun spends more than about half the week's non-reserve hours without a board gain.
- The competition ends (December 2, 2026).
