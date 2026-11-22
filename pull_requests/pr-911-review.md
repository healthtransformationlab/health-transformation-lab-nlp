---
pr: 911
branch: feat/859-041-agent-trace-views
title: "041 US4: SQL views for coding-agent traces (#859)"
author: cursor-agent
reviewed_at: 2026-11-22
reviewer: coordinator (rubric scan + local pytest + warehouse check)
verdict: approve
---

# PR Review: 041 US4 agent trace views

## Summary
Adds `agent_task_run` and `agent_tool_call` over UC coding-agent spans, with a
contract test. Applied on Free Edition; 1611 task-run rows match metadata.
Approve — no blocking findings.

## Scope of Change
- `databricks/setup/agent_trace_views.sql`
- `python/tests/test_agent_trace_views.py`
- `specs/041-agent-traces-uc/tasks.md`

## Secrets / PHI / claims
Clean (no credentials; synthetic/public task ids only in verification notes).

## Findings
None blocking.

## Verdict
**approve** — merge when CI is green.
