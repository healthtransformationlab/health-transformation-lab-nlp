---
pr: 716
branch: docs/714-028-telemetry-tasks-design
title: "Draft the design for tasks whose statements come from telemetry"
author: claude
reviewed_at: 2026-11-14
reviewer: coordinator verification (docs-only change, one file)
verdict: approve
---

# PR Review: Draft the design for tasks whose statements come from telemetry

## Summary
This PR adds one design document. It proposes making coding-agent tasks whose statements are written from a failing
run's telemetry, both from history and from seeded faults, and comparing them, paired, with person-written statements.
Every figure and source it cites checks out, and it passes the repo's wording, organization-name and benchmark-order
tests. It changes no code, data or settings. Verdict: approve. It is marked as a draft with open questions for the
owner, so it should be merged as a draft or held until the owner has read it.

## Scope of Change
- Files changed: 1 (+~110 / -0)
- Areas touched: docs
- Commits: the design draft (Closes #714)
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| all | running at review time; docs-only, so python, postgres, r-parity and bundle are unaffected |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean. The doc names no records.
- Organization claims: clean. It says the project is personal and not affiliated.

## Strengths
- It grounds its motivation in the repo's own measured result (76/93 tasks, 26/85 vs 1/380 task-runs), quoted
  exactly from `AGENTS.md`.
- The paired design, with a masked-message condition, measures how much a gain comes from the message giving the
  answer away.
- It reuses what exists: the file exporter, the spec 028 gates and evaluator check, and the spec 027 incident classes.
- It leaves out the failure classes no code change can fix (`platform`, `cost_anomaly`).

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. **The target of 150–200 injected tasks for detecting a 10-point difference is a rough working figure, not a
   computed power analysis.** The doc lists it as an open question, which is right. The spec should replace it with
   a calculation, using the discordant-pair rate from the history runs.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims; vendors cited | ✅ | |
| Test first | n/a | No behaviour change |
| Python and R in parity | n/a | |
| Simulated is labelled simulated | ✅ | No numbers presented as results beyond the cited measured ones |
| Spec for big changes | ✅ | A design ahead of a spec, as `CLAUDE.md`'s workflow puts it |
| Commits | ✅ | Imperative subject, body says why, Closes #714, co-author trailer |
| Docs | ✅ | |

## Test Coverage
`tests/test_wording.py`, `tests/test_no_org_references.py` and `tests/test_bench_order.py` were run on the branch:
37 passed. These read every tracked file.

## Verdict
Approve. Nothing blocking. Its open questions are for the owner.
