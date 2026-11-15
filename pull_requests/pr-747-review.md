---
pr: 747
branch: chore/743-secrets-register-dates
title: "000 CHORE46: record dental-omop-ci's expiry and the workspace token agent sessions now use (held for the owner)"
author: jcbowyer (agent session)
reviewed_at: 2026-11-15
reviewer: an independent read-only reviewer subagent (given the diff, the rubric, AGENTS.md and CLAUDE.md, not the author's conclusions; Superpowers isn't installed in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 000 CHORE46: record dental-omop-ci's expiry and the workspace token agent sessions now use

## Summary
The register had `expires: unknown` for the CI service principal's secret, and a 15-day agent token that expired on
2026-11-11. This pull request fills in what the dev workspace's APIs showed on 2026-11-15: the secret expires on
2027-01-24, and the replacement token lives in a network secret and expires on 2027-10-12. It also records that the
replacement's one-year lifetime breaks the register's 15-day rule.

The review found one important gap: the open decision about that token pointed at the issue this pull request
closes. It now has its own action item, #749. Three minor wording findings were fixed on the branch, and one is
noted below. Approve with nits. It waits for the owner, because merging runs the deploy.

## Scope of Change
- Files changed: 2: `ops/secrets_register.yaml` (+8 / -6 in total) and this review
- Areas touched: ops
- Commits:
  - `4e89f9b` Record dental-omop-ci's expiry and the workspace token agent sessions now use
  - the fixes from this review, and this file
- Range reviewed: `0114053..4e89f9b`, then the fixes on top

## CI Status
| Check | Status |
|---|---|
| `check` (pull-request conventions, which read issue #743's four parts) | pass on `4e89f9b` |
| `changes`, `postgres`, `bundle`, `azure-infra` | pass on `4e89f9b` |
| `r-parity` | skipped (no R-relevant change) |
| `python`, `python-databricks-runtime` | running when this was written; CI runs again on the fix commits |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
  - The diff matches no token pattern (dapi, hf_, ghp_, github_pat, AKIA, PEM blocks, credentialed URLs).
  - `test_register_holds_no_secret_values` passes.
  - Only dates and places are written, never a value.
- **PHI / real data:** clean. No data file is touched.
- **Organization claims:** clean.
  - The replacement token's comment names an organization, and it is not written anywhere.
  - Neither the workspace host nor the organization id appears in the diff.

## Strengths
- Turns an `unknown`, which the register counts as a finding, into a date, with where and when it was read.
- Records the lifetime breach openly rather than dropping the rule quietly.
- Clears a stale SEV1 forecast for a token agent sessions no longer use.
- Follows the existing pattern of giving the made date and a renew-by date in `lifetime`. Adds no field, no value and no organization name.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Fixed on the branch.** The decision about the one-year token pointed at #743, which this pull request closes
   (`ops/secrets_register.yaml`, the token's `lifetime`).
   - Why it matters: nothing open would have tracked it. The forecaster won't raise the token until 2027-07-14, 90 days before it expires.
   - Verified: `Closes #743` is in the commit, and `credential_forecast` for 2026-11-15 gives no row for the token.
   - Fix: action item #749 (keep or replace the token, and the AGENTS.md row); the register now cites it.

### 🔵 Nits / suggestions (Minor)
2. **Fixed on the branch.** The `stored_in` advice to remove `DATABRICKS_TOKEN` contradicted itself ("can be removed;
   the Databricks CLI then needs a placeholder value there") and would have broken the repository's own code.
   - Verified with `git grep`: `databricks_ai.py:93` reads `os.environ["DATABRICKS_TOKEN"]`, `scripts/36_judge_scorecard.py:69` does the same, and `llm_reader.py:187` uses it as the API key.
   - It now says to keep the variable set to a placeholder, never a real token.
   - The issue's text gave the same advice and has a dated correction.
3. **Accepted, and moved to #749.** The register and AGENTS.md's credentials table now disagree on where the
   workspace token lives (a network secret against the variable).
   - Changing AGENTS.md is a rules change, which waits for the owner (rule 6).
   - `test_every_credential_in_agents_md_is_in_the_register` still passes, because it matches names only.
4. **Fixed on the branch.** The secret's date didn't say which workspace it came from. It now says it is the dev
   secret and the only one, since only dev exists today (`deploy.yml`).
5. **Noted in the pull request.** The commit message understates the forecaster change. Verified with
   `pipeline_doctor.forecast` for 2026-11-15:
   - Before: the workspace token expired 4 days ago (SEV1), and `dental-omop-ci` was SEV4 with no date.
   - After: only `dental-omop-ci`, SEV4, dated 70 days out.

The coordinator's first fix for finding 2 put a colon inside an unquoted value, so the YAML didn't parse. The
re-run of the register's tests caught it (6 failed) before anything was pushed, and it was reworded.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean; dates and places only |
| Synthetic only, no PHI | ✅ | no data files |
| No organization claims; vendors cited | ✅ | the token's comment is left out |
| Test first | n/a | no behaviour change; the register's existing tests and the forecaster were run |
| Python and R in parity | n/a | |
| Configuration | ✅ | no setting changes; the pull request says which environments change (none) |
| Secrets register | ✅ | this pull request is the register update; the lifetime breach is recorded and tracked in #749 |
| Commits | ✅ | imperative subject, a body that says why, co-author trailer |
| Docs | ✅ | AGENTS.md's credentials table is left for the owner (#749) |
| Idempotent writes, alerts, seeds, paths, prices, deck figures, spec | n/a | |

## Test Coverage
- **YAML:** parses, every `expires` is a date, `never` or `unknown`, and both entries keep exactly ten fields. `git diff --check` is clean.
- **Tests, run from this branch's checkout** (the package imported from it): `test_operations_rules`, `test_hf_publish`, `test_copy_decks_to_site`, `test_catch_up`, `test_wording`, `test_no_org_references` and `test_digests`, 120 passed and 2 skipped.
- **Arithmetic** (checked by the reviewer with Python dates): 2026-10-26 + 90 days = 2027-01-24; 14 days before that is 2027-01-10; 2026-10-12 to 2027-10-12 is 365 days.
- **Not verifiable from the repository:** the dates themselves. They come from the dev workspace's token and service principal secrets APIs, read on 2026-11-15.

## Verdict
Approve with nits. Nothing must change before merge. It waits for the owner: `ops/` isn't in the deploy workflow's
path filter, so merging runs the deploy and tries to start Load results on the Free Edition workspace (AGENTS.md
rule 6). That workspace refuses new runs at the moment (#742).
