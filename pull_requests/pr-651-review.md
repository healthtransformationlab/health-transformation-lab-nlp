---
pr: 651
branch: fix/650-027-digest-tests-skip-without-sdk
title: "027 BUG1: skip the two digest tests that need the Databricks SDK where it is not installed (held for the owner)"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-10
reviewer: the authoring session (the failure was reproduced, the fix run with and without the SDK, and the whole suite run in the deploy step's environment; no reviewer subagent run)
verdict: approve, held for the owner
---

# PR Review: 027 BUG1: skip the two digest tests that need the Databricks SDK where it is not installed

## Summary
"Deploy to Databricks dev" has stopped at its own test step since November 5, 2026: two tests added with the
digests import the Databricks SDK, which no extra of this package declares and the deploy workflow does not
install. The fix is one test file: the two tests skip without the SDK, as the repository's other optional-package
tests do, and two new tests keep it so. The whole suite then passes in an environment without the SDK. Nothing
blocking. It waits for the owner because merging it runs the deploy, the first to reach dev since November 4.

## Scope of Change
- Files changed: 1 (+29 / -1), `python/tests/test_digests.py`; this review file is the second
- Areas touched: python (tests only)
- Commits: `519d5f7` Skip the two digest tests that need the Databricks SDK where it is not installed
- Range reviewed: `d876fa6..519d5f7`

## CI Status
| Check | Status |
|---|---|
| `check`, `changes`, `python`, `python-databricks-runtime`, `postgres`, `bundle`, `azure-infra` | pass on `519d5f7` |
| `r-parity` | skipped (no R-relevant change) |
| Later commits | CI runs again when this file is pushed; the head commit must be green before merge (AGENTS.md rule 6) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean. The deploy log was read for the failing step only; no credential appears in the diff, the
  issue or the pull request.
- **PHI / real data:** clean. No data file is in the diff.
- **Organization claims:** clean.

## Strengths
- The cause is read from the failing run's own log and reproduced locally before anything was changed: without the
  SDK, `tests/test_digests.py` gives the same two failures as run 312.
- The new test makes the SDK unimportable and expects a skip, so it tests the condition the deploy step has, on a
  machine that does have the SDK.
- A second test keeps the `track` extra in both whole-suite CI jobs, so the two tests cannot end up skipped
  everywhere.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **The deploy workflow still tests in an environment CI never builds** (`.github/workflows/deploy.yml`: no
   `actions/setup-python`, `[dev]` only). Both failures this week came through that gap: on November 4 a child
   `python3 -I` could not import `numpy`, and from November 5 the two digest tests. This fix closes the second;
   the next test that needs a package outside `[dev]` will stop the deploy again unless it skips. Whether to build
   CI's environment there, or stop running the suite a second time, is the owner's decision (issue #650).
2. **The first deploy after merging carries everything merged since November 4.** At least 22 merges that the
   workflow's path filter does not ignore. Read the deploy's plan in its log before relying on dev.

### 🔵 Nits / suggestions (Minor)
3. `ruff check` reports one finding in the file that is also on `main` (an unused name at line 103). Not touched.
4. The workflow re-ran two failed runs on its own (281, 311). A missing package fails the same way twice; a retry
   there only spends minutes.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data files changed |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | the new test was written and run before the fix: 4 failed without it (the two digest tests and the two new cases) |
| Python and R in parity | n/a | tests only |
| Configuration | ✅ | no setting changed; the pull request says merging runs the dev deploy |
| Secrets register | n/a | no credential made, rotated or newly used; sign-in was not the failure |
| Wording, benchmark order, organisation names | ✅ | `test_wording.py`, `test_bench_order.py`, `test_no_org_references.py` pass in CI |
| Commits | ✅ | imperative subject, body says why, co-author trailer |
| Spec for big changes | n/a | a bug fix with a regression test |
| Idempotent writes, alerts, seeds, paths, prices | n/a | |

## Test Coverage
- `test_a_test_that_needs_the_sdk_skips_where_it_is_not_installed` (two cases) and
  `test_ci_installs_the_sdk_so_those_tests_run_there`.
- Run locally, SDK not installed: on `main`, `tests/test_digests.py` 2 failed, 14 passed; with the new tests and no
  fix, 4 failed; with the fix, 17 passed, 2 skipped. SDK installed: 19 passed.
- The whole suite with no SDK and no `mlflow`, as the deploy step has: 2,248 passed, 37 skipped, none failed.
- Not tested: the deploy itself. It runs only on `main`.

## Verdict
Approve. Nothing must change before merge. Held for the owner: the merge starts a deploy to Databricks dev and
Load results on the workspace (AGENTS.md rule 6, limited compute).
