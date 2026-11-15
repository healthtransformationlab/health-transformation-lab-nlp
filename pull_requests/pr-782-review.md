---
pr: 782
branch: docs/749-workspace-token-one-year
title: "000 AI4: record the decision to keep a one-year workspace token for agent sessions (held for the owner)"
author: jcbowyer (agent session)
reviewed_at: 2026-11-15
reviewer: an independent read-only reviewer subagent (given the diff, the rubric, AGENTS.md and CLAUDE.md, not the author's conclusions; Superpowers isn't installed in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 000 AI4: record the decision to keep a one-year workspace token for agent sessions

## Summary
The owner chose on 2026-11-15 to keep the one-year workspace token that agent sessions use ("keep", #749), against
the rule's 15 days. This pull request writes the choice down:
- **ADR 0006**, added to the ADR index;
- **the register's lifetime**, which now cites it;
- **AGENTS.md's credentials table**, which says the token is a network secret and the variable holds only a placeholder;
- **a test** that ties the register to the ADR and to AGENTS.md.

The reviewer found two important content problems, both fixed in `9255d44`:
- the ADR claimed the workspace holds synthetic data only, which nothing supports;
- the register and AGENTS.md disagreed about the variable.

Approve with nits. It waits for the owner: it changes AGENTS.md, and merging runs the deploy.

## Scope of Change
- Files changed: 6: `docs/adr/0006-...md` (new), `docs/adr/README.md`, `AGENTS.md`, `ops/secrets_register.yaml`, `python/tests/test_operations_rules.py` and this review
- Areas touched: docs, ops, python (a test)
- Commits:
  - `d6093e5` Record the decision to keep a one-year workspace token for agent sessions
  - `9255d44` Say what the kept token can reach, and track the placeholder in its own issue
  - this file
- Range reviewed: `cd002e4..d6093e5` by the reviewer; `d6093e5..9255d44` by the coordinator, from the findings

## CI Status
| Check | Status |
|---|---|
| `d6093e5`, `9255d44` and this file | CI runs on push; the head must be green before merge |

## Secrets, PHI and Claims Scan
- **Secrets:** clean. The diff has no token value, workspace host or organization id; `test_register_holds_no_secret_values` passes.
- **PHI / real data:** clean. The ADR names the John Snow Labs file only to say it wasn't in the workspace.
- **Organization claims:** clean. The token's comment, which names an organization, appears nowhere. The workspace's
  other groups, which name other projects, aren't named either.

## Strengths
- Follows `template.md` and the README's rules, and adds the index row.
- Records the breach of the old rule openly instead of quietly loosening it, and doesn't invent the owner's reasons.
- The test guards against a duplicate ADR number and finds AGENTS.md's indented row.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Fixed in `9255d44`: the ADR said the dev workspace holds synthetic data only, and understated a leak.**
   - Problems:
     - Nothing in the repository supports the claim; the repository's own rules cover the repository, not the workspace.
     - Its closing clause read as the owner's reason, though the owner gave none.
   - Checked read-only by the coordinator on 2026-11-15:
     - The token's owner is in the workspace's `admins` group, and the workspace has groups for other projects.
     - The landing volume `landing_perio_bench/data` holds labels, logs, NHANES and OMOP folders, and no copy of the `jsl48` file.
   - What the ADR now says:
     - What a leaked token could do: read the secret scope, start jobs, call serving endpoints, make other tokens.
     - That it reaches the whole workspace, not only this repository's tables.
     - What was checked on the volume.
     - That the owner gave no reason beyond "keep".
     - A new revisit point at renewal.
2. **Fixed in `9255d44`: the register said `DATABRICKS_TOKEN` still holds the expired token, while AGENTS.md says it
   holds only a placeholder.**
   - The variable does still hold it.
   - The register now gives both the rule (ADR 0006) and today's state, and cites action item #784, which sets the placeholder.
   - The lists of code that reads the variable now agree in the ADR and the register.
3. **Process:** it changes AGENTS.md, and `ops/` triggers the deploy, so it waits for the owner's "merge" (rule 6).

### 🔵 Nits / suggestions (Minor)
4. **Fixed:** AGENTS.md's bullet "give ... a short lifetime" sat above a row allowing a year. It now names the exception (ADR 0006).
5. **Fixed:** the ADR turned "keep" into a standing policy. It now says why (the owner's choice, no other reason) and
   adds "the token is renewed (by 2027-09-28): keeping a year then is a new choice" as a revisit point.
6. **Fixed:** the test's `next(...)` calls failed with a bare `StopIteration`. They now fail with a message naming the missing entry or row.
7. **Opened as #785:** `test_every_credential_in_agents_md_is_in_the_register` checks nothing.
   - Since the table was indented (`8cadc13`), its pattern matches only the header.
   - Verified: it returns `['Credential']`.
   - Older than this pull request.
8. **Noted in the pull request:** 0006 is the next free ADR number on `main`. Pull request 734's `0005-...` already
   collides with `main`'s 0005, so it needs a new number either way (0007).
9. **Fixed:** issue #749 has a dated line naming what the test checks: `ADR 0006` in the register's lifetime,
   `Status: accepted`, and `network secret`, `placeholder` and `ADR 0006` in AGENTS.md's row.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | |
| No organization claims; vendors cited | ✅ | the token's comment and other projects' group names are left out |
| Test first | ✅ | the new test failed on the base (`assert adr`) and passes on the branch |
| Decisions and action items | ✅ | the decision is an ADR; the work it leads to (the placeholder) is #784 |
| Configuration | ✅ | no environment changes by merging; the owner changed the agent's cloud environment on 2026-11-15 |
| Secrets register | ✅ | the entry cites the ADR, the expiry and the renew-by date (2027-09-28) |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Python and R parity, idempotent writes, alerts, seeds, paths, prices, deck figures, spec | n/a | |

## Test Coverage
- **The repository's tests:** `test_operations_rules`, `test_agent_docs`, `test_colab_official`, `test_digests`, `test_wording`, `test_no_org_references` and `test_bench_order`: 132 passed, 2 skipped, on `9255d44`.
- **The register:** parses, and every field is intact.
- **Arithmetic:**
  - 2027-10-12 minus 14 days is 2027-09-28.
  - 90 days before expiry is 2027-07-14, matching the forecaster's SEV4 step.
- **Not verifiable from the repository:** the token facts, read from the workspace on 2026-11-15.

## Verdict
Approve with nits. Nothing must change before merge. It waits for the owner: it changes AGENTS.md (rule 6), and
`ops/` isn't in the deploy workflow's path filter, so merging runs the deploy and its Load results.
