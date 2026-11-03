---
pr: 503
branch: fix/501-000-register-hash-comments
title: "000 BUG3: stop the secrets register's issue references being read as YAML comments"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: coordinator (small fix with a regression test; checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: the secrets register's issue references

## Summary
Four unquoted register values held ` #N`, which YAML reads as the start of a comment, so each value was cut short.
One of them turned `main` red. They now say "issue N", and a test guards against it.

## Checks against the rubric
- **Test first:** the guard test failed on the old file; the failing CI test now passes.
- **No secret values:** register prose only; `test_register_holds_no_secret_values` passes.
- **Scope:** text changes only; no setting or environment changes.

## Findings
None.

## Verdict
Approve.
