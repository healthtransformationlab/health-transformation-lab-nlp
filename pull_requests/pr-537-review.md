---
pr: 537
branch: feat/533-034-kaggle-usability
title: "034 US1: every Kaggle dataset describes its files and columns, with a cover, sources and update frequency"
author: johncbowyer
reviewed_at: 2026-11-04
reviewer: coordinator review and verification
verdict: approve-with-nits
---

# PR Review: 034 US1: every Kaggle dataset describes its files and columns, with a cover, sources and update frequency

## Summary
This gives our three Kaggle datasets everything their usability score lacked. A committed dictionary describes
every published file and column. Each dataset gets a seeded cover, its sources and an update frequency. Both
publish scripts send these after every upload, and a metadata-only path refreshes them without a new version.
AGENTS.md makes the checklist the rule. Verified by tests and by a dry run on the real data (notes, results,
and the task set's 316 live files described from Kaggle's listing), with nothing sent. CI is green. Approve with
nits. It waits for the owner's "merge", because it edits AGENTS.md and what we publish.

## Scope of Change
- Areas touched: kaggle, ci (two workflow inputs), specs, AGENTS.md, python tests
- Commits: 30ad14c (US1), a07188b (drop a duplicate wording test)
- Range reviewed: `origin/main..a07188b`

## CI Status
| Check | Status |
|---|---|
| python | success |
| python-databricks-runtime | success |
| postgres, bundle, azure-infra, check | success |
| r-parity | skipped (nothing it covers changed) |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean. The descriptions describe synthetic columns, and the covers are drawn shapes.
- Organization claims: clean. The task set's sources say it is not affiliated with Kaggle, Google or the
  competition's organisers.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. `expectedUpdateFrequency` is "monthly" for all three datasets. That's a choice, not a schedule; the owner may
   prefer another value. It's one line per dataset in `kaggle/dataset_docs.yaml`.
2. The task set still has no public notebook, so its score stays a point short. Tracked as #535.
3. Verified once, before relying on it: the column descriptions were checked against the code that writes each
   column. Several first drafts were corrected, including `unsafe_rate`, `s2_rate`, `seed_stability` and
   `ladder_proba`; the harm matrix is marked as a draft, as `harm.py` says.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets / PHI / claims | ✅ | |
| Test first | ✅ | new tests seen failing first |
| Python and R in parity | n/a | |
| Words | ✅ | `test_wording.py` scans `dataset_docs.yaml` |
| Spec for big changes | ✅ | spec 034 |
| Publishes outside the repo / changes these rules | ⚠️ | waits for the owner's "merge" (rule 6) |

## Test Coverage
`tests/test_kaggle_dataset_docs.py` (new), `tests/test_kaggle_publish_tasks.py` (3 new), `tests/test_kaggle_publish.py`
(fake API updated). CI's `python` job ran the full suite green.

## Verdict
approve-with-nits.
