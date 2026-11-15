---
pr: 798
branch: docs/797-000-gpu-decisions
title: "000 DOCS22: write down the GPU decisions: hours are a reserve, score questions go to the leaderboard"
author: claude
reviewed_at: 2026-11-15
reviewer: coordinator verification against .claude/review-rubric.md
verdict: approve (owner merges: it changes AGENTS.md)
---

# PR Review: write down the GPU decisions

ADR 0007 (context with the numbers, decision, consequences, revisit when) and three bullets in AGENTS.md's rationing
rules that cite it; the ADR index row. Test first: `test_agents_md_records_the_gpu_decisions` failed, then passed;
wording, org-reference and operations-rules tests pass (39).

Checked: the numbers match their sources (quota 42.27 of 60 at 13:50 UTC from `kaggle/gpu_quota.py`; six runs at 3 or
4 of 23 with p = 1.0 from `data/tasks/official_agent_runs/README.md`; 2.00 quota hours a run from `kaggle/README.md`).
The bullets sit beside the existing rationing rules, away from the sentence PR 788 changes, so the two merge in either
order. A decision in an ADR and the rules in AGENTS.md, as "Decisions and action items" asks.

Nothing blocking. It changes the agent rules, so it waits for the owner's "merge".
