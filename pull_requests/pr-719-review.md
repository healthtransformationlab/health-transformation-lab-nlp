---
pr: 719
branch: fix/718-pr-check-reads-a-linked-pull-request
title: "000 BUG7: the pull-request check reads a linked pull request as the issue"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: read-only reviewer subagent over the range, with this rubric and AGENTS.md + coordinator verification
verdict: approve
---

# PR Review: 000 BUG7: the pull-request check reads a linked pull request as the issue (#718)

## Summary
The check added by pull request 701 read the first link in a description, `Refs` included, as the issue, and
GitHub's issues endpoint answers for pull requests too. A description that refers to an earlier pull request before
its closing link therefore held that pull request to an issue's four parts and, because pull request titles copy
their story's key, to a spec's files; the real issue was never read. This reads the closing link first, flags a
linked pull request, and reports one opened from November 14, 2026 once, as a pull request. The review also found
that a closing link written with a colon (`Closes: #712`) was not read at all, which is the same case; it is fixed
here, with a dated line added to issue 718. Approve.

## Scope of Change
- Files changed: 3 (+79 / -11 in the script and its tests, plus this review)
- Areas touched: CI check (`.github/scripts/`), python tests, review record
- Commits: `a584854` Read the closing link first, and name a linked pull request as one; then the colon form, the
  docstring, the success line and this review
- Range reviewed: `6583337..HEAD` (the merge base with `main`)

## CI Status
| Check | Status |
|---|---|
| check (branch, link and issue) | success on the first commit: it read issue 718, which is in the four-part form |
| python, python-databricks-runtime, postgres, bundle, azure-infra | python and postgres were running at the time of writing; read again before merging |
| r-parity | skipped (no R or scoring change) |

## Secrets, PHI and Claims Scan
Secrets: none; the workflow's read-only token is still passed by environment and never printed. PHI or real data:
none. Organisation claims: none.

## Strengths
- The fix is in the check only; AGENTS.md, the template and the workflow are unchanged, so no rule changes.
- A three-element issue tuple behaves exactly as before, so callers and the existing tests are untouched.
- A linked pull request opened before the rule's date passes as it did, so no older pull request starts failing.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **Fixed in this PR.** `.github/scripts/pr_conventions.py`, `LINK`, `ISSUE_NUMBER`, `CLOSING_NUMBER`: a colon after
  the keyword (`Closes: #712`) was not read, so `Refs #705` before it still won, and `Closes: #712` alone was not a
  link. Verified: `linked_issue_number("Refs #705\n\nCloses: #712")` returned 705 before the fix and returns 712
  after; `issue_link("Closes: #712")` was false and is now true. Tests added; they failed first.

### 🔵 Nits / suggestions (Minor)
- **Fixed.** When the link names a pull request opened before November 14, the success line said "its issue" though
  no issue was read; it now says so.
- **Fixed.** The module docstring now says a closing link is read before a `Refs` link, and that a colon is allowed.
- **Left as is.** `check` given an issue tuple with only a Jira key in the description could name "#None" as a pull
  request. CI never reaches it: the script fetches only when the description has a number.
- **Left as is.** A cross-repository link (`Closes owner/repo#712`) is not read as this repository's issue; the
  check reads issues of this repository only, as before.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | scan above |
| Synthetic only, no PHI | yes | no data files |
| No organization claims; vendors cited | yes | none |
| Test first | yes | 5 tests for the first commit and 7 for the colon form failed before each change |
| Python and R in parity | n/a | no labels, scoring, reliability or cost change |
| Simulated is labelled simulated | n/a | no numbers |
| Seeds, paths, prices, deck figures | n/a | not touched |
| Spec for big changes | yes | a bug in a CI check with regression tests: no spec needed. Issue 718 has the four parts and a dated line for the added scope |
| Commits | yes | imperative subjects, bodies say why, co-author trailer |
| Configuration | yes | no setting changes; only this repository's pull-request check changes |
| Secrets register, idempotent writes, alerts | n/a | not touched |
| Rule 6 (who merges) | yes | changes how the check reads a rule, not a rule; no run, publish or deletion; may be merged when green |

## Test Coverage
New tests: the closing link is read before a `Refs` link, with and without a colon; a colon after the keyword counts
as a link; a linked pull request is named as one, not held to an issue's parts or a story's spec, and an older one
passes; `fetch_issue` reports whether the number is a pull request (network call replaced). Run locally:
`pytest -q tests/test_pr_conventions.py tests/test_agent_docs.py tests/test_no_org_references.py tests/test_wording.py`
93 passed; `ruff check` on both files clean; the script run end to end without a token exits 0 for this branch with
`Closes: #718`. Not tested: a live call to GitHub from the test suite (the reviewer made one by hand: `/issues/705`
returns a `pull_request` field).

## Verdict
Approve. Merge when every check is green on the latest commit.
