---
pr: 788
branch: docs/787-000-devset-to-colab
title: "000 DOCS21: AGENTS.md no longer keeps development-set runs on Kaggle once #780 lands"
author: claude
reviewed_at: 2026-11-15
reviewer: coordinator verification against .claude/review-rubric.md
verdict: approve (owner merges: it changes AGENTS.md)
---

# PR Review: AGENTS.md sends development-set mechanism runs to Colab

Stacked on PR 786 (#780): its base is that branch, so the diff shows one sentence of AGENTS.md and one test. Test first:
`test_agents_md_sends_development_set_mechanism_runs_to_colab` failed on the old sentence and passes. Wording and
operations-rules tests pass (37). It changes the agent rules, so it waits for the owner's "merge", after PR 786.
Nothing blocking.
