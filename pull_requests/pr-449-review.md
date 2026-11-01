---
pr: 449
branch: chore/439-028-competition-check
title: "Check the task set against the competition's own files, and find swegemma"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator verification (small, read-only chore; no reviewer subagent run)
verdict: approve-with-nits
---

# PR Review: Check the task set against the competition's own files, and find swegemma

## Summary
Adds a manual, read-only workflow and a tested script. Together they list the Gemma 4 Developer Agent competition's
files, download only the small ones, and print how the competition's formats compare with spec 028's:
- snapshot layout;
- graph and embedding formats;
- where `swegemma` comes from.

The workflow keeps nothing. It uses the existing `dev` Kaggle credentials, and the register now lists it. Approve
with nits.

## Scope of Change
- Files changed: 6
  - the workflow;
  - `competition_check.py`, `56_competition_check.py`, `test_competition_check.py`;
  - `ops/secrets_register.yaml`;
  - this review.
- Areas touched: ci, python, ops.

## Secrets, PHI and Claims Scan
- Secrets: clean. Credentials are read from the environment and masked; no value is printed.
- PHI: clean.
- Organisation claims: clean.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important)
None.

### 🔵 Nits (Minor)
- **Untested against Kaggle.** The Kaggle calls (`competition_list_files`, `competition_download_file`) can't be run
  here: there are no credentials, and kaggle.com is outside the container's network. Their signatures and response
  fields were checked against the pinned `kaggle==2.2.5` source. The first workflow run is the real test.
- **Pagination.** `page_size=200` with page tokens covers the 524 files; if Kaggle caps the page size lower, the
  token loop still covers everything.

## Test Coverage
- `test_competition_check.py` covers:
  - file selection (small files, harness wheels, smallest task's snapshot, graph and embedding);
  - snapshot layout, telling a root folder from files at the root;
  - the graph and embedding summaries;
  - the comparison lines.
- The full suite passed: 1522 passed, 15 skipped. `ruff check` is clean.
- With no credentials, the script exits before any network call and names the missing settings.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | Existing secrets, masked |
| Synthetic only, no PHI | ✅ | Reads public competition files; keeps none |
| Test first | ✅ | |
| Check settings before work | ✅ | Missing credentials fail at once, naming them; the one cheap listing call says how to fix a refusal |
| Secrets register | ✅ | Kaggle token's `used_by` updated |
| Configuration | ✅ | No new setting; no environment changes |
| `@traced` on public functions | ✅ | |
| Script numbers | ✅ | 56 is free on main and open PRs |

## Verdict
Approve with nits. Before running it, the owner needs to join the competition with the token's Kaggle account.
