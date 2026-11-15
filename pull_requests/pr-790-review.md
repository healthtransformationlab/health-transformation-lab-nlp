---
pr: 790
branch: chore/784-placeholder-in-register
title: "000 AI5: record that DATABRICKS_TOKEN now holds a placeholder"
author: jcbowyer (agent session)
reviewed_at: 2026-11-15
reviewer: an independent read-only reviewer subagent (given the diff, the rubric, AGENTS.md and CLAUDE.md, not the author's conclusions; Superpowers isn't installed in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 000 AI5: record that DATABRICKS_TOKEN now holds a placeholder

## Summary
The register said the cloud environment's `DATABRICKS_TOKEN` still held the 15-day token that expired on
2026-11-11, until #784 set a placeholder (ADR 0006). The owner set it on 2026-11-15, and this pull request records
that, with a test.

The reviewer found it consistent with ADR 0006 and AGENTS.md, and no conflict with pull request 789. There are no
critical or important findings; two minor ones are fixed and one is said plainly in the pull request. Approve with
nits.

## Scope of Change
- Files changed: 3: `ops/secrets_register.yaml`, `python/tests/test_operations_rules.py` and this review
- Areas touched: ops, python (a test)
- Commits:
  - `9595b10` Record that DATABRICKS_TOKEN now holds a placeholder
  - the review fixes, and this file
- Range reviewed: `69ff005..9595b10` by the reviewer; the fixes by the coordinator

## CI Status
| Check | Status |
|---|---|
| `check`, `changes`, `postgres`, `bundle`, `azure-infra` | pass on `9595b10` |
| `python`, `python-databricks-runtime` | running on `9595b10` when this was written |
| `r-parity` | skipped (no R-relevant change) |
| the fix commit and this file | CI runs again on push; the head must be green before merge |

## Secrets, PHI and Claims Scan
- **Secrets:** clean. No value is written anywhere, and the placeholder is not a secret.
- **PHI / real data:** clean.
- **Organization claims:** clean.

## Strengths
- A one-sentence, accurate register update, attributed to the owner and the issue.
- It matches ADR 0006 and AGENTS.md, and nothing else in the repository still says the variable holds the expired token.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **Fixed:** the new assertion guarded one phrase, "still holds", which rewording would get past.
   - It now checks the entry says neither "expired" nor "15-day".
   - `main`'s register text fails it, and this branch's passes.
2. **Said plainly in the pull request:** the commit's "a call sending the placeholder as the variable succeeds"
   shows the proxy replaces whatever value is sent. It doesn't show the owner's change.
   - The register rests on the owner's word, as it should.
   - This session started before the change and can't see the new value, since variables load at session start.
   - A session started after it can confirm, without printing the value.
3. **Fixed:** the register didn't say what form the placeholder takes. It now says no code checks its form, only
   that it is set, so a shape check added later must accept it.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | the assertion failed on the register before the edit, and its broader form fails on `main`'s |
| Secrets register | ✅ | the entry gives the rule and the current state, citing #784 and ADR 0006 |
| Configuration | ✅ | no change by merging; the owner changed the agent's cloud environment |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Python and R parity, idempotent writes, alerts, seeds, paths, prices, deck figures, spec | n/a | |

## Test Coverage
- **Tests after the fixes:** `test_operations_rules` and `test_digests`, 27 passed and 2 skipped.
- **The register:** parses, with one 480-character `stored_in` string (the reviewer checked nothing cuts it short).
- **Combined with pull request 789:** no conflict, and the whole suite passes on an indexed export (the reviewer).
- **Not verifiable here:** the variable's new value (by design).

## Verdict
Approve with nits. Nothing must change before merge. Merging runs the deploy (`ops/` isn't in its path filter), and
the owner said "merge" on 2026-11-15.
