---
pr: 893
branch: chore/892-access-bench-phi-fixture
title: "000 CHORE49: AccessBench folder with synthetic PHI dual fixture"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator (rubric scan + local pytest)
verdict: approve
---

# PR Review: 000 CHORE49 AccessBench folder with synthetic PHI dual fixture

## Summary
Adds `benchmarks/` for PerioBench, OralHealthBench and AccessBench, puts the access expand prompt and dual pathway+PHI fixture under AccessBench, and ships `access_phi_items` with tests. Synthetic identifiers only; routing keeps getting-care items out of OralHealthBench. Approve — no blocking findings.

## Scope of Change
- Files changed: 14 (+381)
- Areas touched: benchmarks docs, python loader, tests
- Commits: AccessBench fixture; TypeError lint fix
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| check / python / others | pending at review write; re-check before merge |

## Secrets, PHI and Claims Scan
- Secrets: clean
- PHI / real data: clean (challenge-pool names, `205-555-` phones, SSNs starting with 9)
- Organization claims: clean (generic public sources; no employer name)

## Strengths
- Clear AccessBench vs OralHealthBench routing
- Reuses `deid.leak_check` instead of a parallel leak gate
- Contract enforced in loader + tests

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
None blocking merge.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Synthetic only | yes | `is_simulated: true`; planted_phi from challenge pool |
| Bench order | yes | PerioBench → OralHealthBench → AccessBench |
| Test first | yes | `test_access_phi_items.py` |
| Spec for big changes | n/a | chore scaffolding, not a metric/label change |

## Test Coverage
Local: `pytest tests/test_access_phi_items.py` (+ wording / org / bench-order) passed; ruff clean.

## Verdict
**approve** — merge when CI is green on the latest commit.
