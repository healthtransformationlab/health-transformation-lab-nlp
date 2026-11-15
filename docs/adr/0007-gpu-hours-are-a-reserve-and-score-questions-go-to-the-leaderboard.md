# ADR 0007: GPU hours are a reserve; score questions go to the leaderboard

Date: 2026-11-15 · Status: accepted · Issue: #797

## Context

The Kaggle account's GPU hours are one weekly pool for every session (60 hours with the linked Colab subscription;
it refreshes Saturday 00:00 UTC). A four-L4 kernel counts each hour as two (2.00 quota hours for a 61-minute run,
`kaggle/README.md`). By 13:50 UTC on November 15, the second day of the week, 42.27 hours were used and 17.73 left;
three approved runs had already been refused once that day for an empty pool.

Six development-set runs of agent changes on the same 23 tasks (PR 98's prompt, PR 100's 8,192 tokens, PR 60, main
at 8,192, PR 107, and the November 11 baseline) resolved 3 or 4 each, and every paired exact McNemar test gave
p = 1.0 (`data/tasks/official_agent_runs/README.md`). Twenty-three tasks can't show the one-to-three-task gains being
chased; the runs cost about 12 quota hours to learn that. What they did show were mechanisms: context-window endings
gone at 8,192 and 12,288, scratch files gone from patches, and 37% of edits failing "old_string not found".

Two cheaper sources answer most questions:

- **The leaderboard**: an entry runs on the host's machines, not our pool, and scores about 58 hidden tasks; one a day
  until December 2.
- **Recorded traces and offline data**: a kernel's output (its traces) downloads for free, and the competition's graphs
  and embeddings run on CPU. On November 15 these answered, with no GPU: why edits fail (119 failures classified by
  cause), which anchors fail (backslashes 50%, p = 0.015), and whether regex, embeddings or the code graph find the code
  to fix (129 tasks; `gemma-developer-agent` docs/localization-study.md).

## Decision

- **The Kaggle GPU hours are a reserve.** A Kaggle GPU run starts only on the owner's explicit yes for that run, given
  in the session that starts it; a general "do what you recommend" doesn't approve one. One run at a time across all
  sessions, with the quota read before and after (`kaggle/gpu_quota.py`).
- **"Did the score go up" is answered by leaderboard entries**, one change per entry, booked in a shared plan so two
  sessions don't spend the same day. A development-set run is never started to compare resolve counts.
- **A question goes to recorded traces and CPU first**: replay it on the traces already downloaded, or on the
  competition's offline data. A GPU run only when they can't answer it.
- **Every GPU run goes to the owner's Colab by default** (one L4; ADR 0005, #779, #780), this repository's and
  getcommunityone/open-navigator's alike, so the Kaggle pool isn't spent. A Kaggle GPU run is an exception, for what
  only the competition's own hardware or image decides, and needs the owner's yes for that run. The Colab compute
  units are one subscription shared by both projects, so a Colab run also reads its usage before and after.
- **For the week of November 15**: no further Kaggle GPU run is planned; the 17.73 hours left are the reserve.
- **The final two submissions**: one is the best E2B/E4B entry (the small-model bonus requires it), chosen on all the
  evidence, not the single best public score. The other is the owner's choice.

## Consequences

- A change waits a day for its leaderboard score, and the score is noisy (about ±1.6 of 58 tasks between identical
  submissions): one change per entry, and the final choice pools every entry and trace.
- Mechanism checks get cheaper and faster: a trace replay takes seconds.
- An idea that needs a GPU to test waits for a Colab session the owner opens by hand, so each costs the owner a few
  minutes; the Kaggle pool stays nearly untouched.

## Revisit when

- The pool refreshes (Saturday, November 21) and the leaderboard has scored entries 5 to 8.
- The first Colab development-set run (#780) shows whether one L4 reproduces Kaggle's results.
- The competition ends (December 2).
