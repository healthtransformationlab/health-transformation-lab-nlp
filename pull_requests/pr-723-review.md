---
pr: 723
branch: fix/721-028-devset-batch-label
title: "028 BUG8: a second development-set batch reuses the first's Kaggle dataset, kernel and table"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator review of the diff against the rubric (no reviewer subagent: three functions, a help string and their tests, read line by line; the test-first run caught the one defect)
verdict: approve
---

# PR Review: 028 BUG8: a second development-set batch reuses the first's Kaggle dataset, kernel and table (#721)

## Summary
A development-set batch was always named `devset`, and `--label` was refused for it, so two agent configurations
could not be measured on the competition's development set at once: the second would push over the running kernel,
upload over its dataset and merge its rows into the baseline's table. A labelled development-set batch is now
`devset-<label>` throughout; an unlabelled one is unchanged, and a context is still refused for the development set.
Approve.

## Scope of Change
- Files changed: 3 (+51 / -17), plus this review
- Areas touched: Kaggle run tooling (`kaggle/`), python tests
- Commits: `64f39af` Give each labelled development-set batch its own dataset, kernel and table; this review
- Range reviewed: `f82c42f..HEAD` (the merge base with `main`)

## CI Status
| Check | Status |
|---|---|
| all | read on the head commit before merging |

## Secrets, PHI and Claims Scan
Secrets: none; the run's sealing key and the Kaggle token are untouched. PHI or real data: none, and nothing of the
competition's data is added. Organisation claims: none.

## Strengths
- The unlabelled names are unchanged, so the run of November 11, its table and anything that collects
  `htlnlp-offrun-devset` (the run for gemma-developer-agent pull request 98, in flight) are not affected.
- The `devset-` prefix keeps a development-set arm's table apart from a published arm with the same label.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- **Fixed before the first commit.** `kaggle/official_agent_bundle.py`, `build_competition_batch`: the loop over
  `SUBMISSION_ENTRIES` used `name`, overwriting the new parameter, so every dataset id became the last entry's
  (`htlnlp-official-adapters`). The new test caught it (`ruff` PLR1704 too); the loop variable is `entry`.
### 🔵 Nits / suggestions (Minor)
- `ruff check` on `official_agent_run.py` reports two `UP017` (`timezone.utc`), both already on `main`; left alone.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | scan above |
| Synthetic only, no PHI | yes | no data |
| No organization claims; vendors cited | yes | none |
| Test first | yes | the new test and the changed assertion failed before the change |
| Python and R in parity | n/a | no labels, scoring or cost |
| Simulated is labelled simulated | n/a | no numbers |
| Seeds, paths, prices, deck figures | n/a | not touched |
| Spec for big changes | yes | a tooling fix with regression tests; issue 721 has its four parts |
| Commits | yes | imperative, body says why, trailer |
| Configuration | yes | no settings change |
| Rule 6 (who merges) | yes | it does not itself start a run, publish or delete; the run it enables was approved separately by the owner |

## Test Coverage
`pytest -q tests/test_official_agent.py tests/test_agent_harness.py tests/test_wording.py tests/test_no_org_references.py`:
106 passed. Covered: batch names with and without a label for both sources, the label rule, the arm options (a
development-set label accepted, a development-set context refused, a label without `--batch` refused), the dataset id
of a labelled and an unlabelled development-set batch, its kernel id and its table name. Not covered: a live upload,
which the run for gemma-developer-agent pull request 100 makes next.

## Verdict
Approve. Merge when every check is green on the latest commit.
