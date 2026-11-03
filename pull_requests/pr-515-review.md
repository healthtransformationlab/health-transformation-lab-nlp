---
pr: 515
branch: feat/356-028-publish-task-set
title: "028 US5: publish the task set on Kaggle, public, in the competition's file names"
author: johncbowyer
reviewed_at: 2026-11-04
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 028 US5: publish the task set on Kaggle, public, in the competition's file names

## Summary
This adds a hand-run workflow and `kaggle/publish_tasks.py` that publish spec 028's gated task set as a public,
CC BY 4.0 Kaggle dataset in the Gemma 4 Developer Agent competition's layout. Snapshots are named by instance id;
graphs and embeddings are renamed to the competition's `<repo name>_<base_commit>`, the names the harness looks up.
The review found one Important problem: each snapshot is the whole tree, so most carry the MACCROBAT case reports
(not synthetic, CC BY 4.0) and a course's files with no stated redistribution licence, while the card said the
data was synthetic and MIT. It is fixed: the card names the third-party files and licences, and, on the owner's
decision, the course files are withheld from every snapshot and the task that added them is excluded. Rehearsed on
the real data without uploading: 113 tasks, 316 files, 1.55 GB, no organisation name and no withheld file in it.
It publishes outside the repo, so it waits for the owner's "merge" (AGENTS.md rule 6).

## Scope of Change
- Files changed: 12 (excluding `data/tasks/*.csv`)
- Areas touched: python, kaggle, ci (one workflow), specs, ops, data
- Commits:
  - 5d5313a 028 US5: publish the task set on Kaggle, public, in the competition's file names
  - (snapshot index) 028 US5: the snapshot index for all 115 tasks
  - 780e5b8 028 US5: keep the register's new notes inside their YAML values
  - 99a9a45 028 US5: the card names the snapshots' third-party files; graphs are checked too
  - 8b140f2 028 US5: withhold the course files from every snapshot, and the task that added them
- Range reviewed: `origin/main..8b140f2`

## CI Status
| Check | Status |
|---|---|
| CI on the head | see the PR's checks; local runs below |

## Secrets, PHI and Claims Scan
- Secrets: clean. Secrets reach the workflow only through `env` and `GITHUB_ENV`; the register names variables,
  never values.
- PHI / real data: the published snapshots carry MACCROBAT (published, de-identified case reports, CC BY 4.0, the
  constitution's public-dataset exception), now stated on the card with its citation. The course files without a
  stated licence are withheld. Nothing new is committed to the repo.
- Organization claims: clean. The card says the set is not affiliated with Kaggle, Google or the organisers.

## Strengths
- Only `tasks_gated.jsonl` can be published; `check()` runs before anything is copied and refuses a failed task,
  a missing file, a row or graph naming the organisation, and a row or snapshot carrying a withheld file.
- The competition's naming was taken from its own `tasks.jsonl` and file listing, all 129 tasks.
- Rehearsed end to end on the real data, with a scan of every text file in every snapshot.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
Fixed in this PR:
1. `kaggle/cards/tasks.md`: said the data was synthetic and the snapshots the repo's own MIT files; 86 bases carry
   `data/external/maccrobat/` (not synthetic, CC BY 4.0, plus `course/` with no stated licence) and 100 the MIT
   icon set with its own copyright. Verified with `git ls-tree` over the bases. Fixed: the card names them, and
   `course/` is withheld (`task_graph.WITHHELD_PATHS`, tested), with `htlnlp_pr18` excluded.

### 🔵 Nits / suggestions (Minor)
1. Fixed: `check()` now also scans graphs for the organisation name (graph node text is unredacted source).
2. Fixed: tests cover `main()` without `--upload` (Kaggle never imported) and with it (the message carries the
   commit).
3. Open: the job's `GH_TOKEN` is `contents: read`; `55_build_tasks.py`'s REST reads of public issues and PRs should
   work with it, but a 403 would fail the build (it only falls back on 401). The first run will show it.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | MACCROBAT under the public-dataset exception, stated; course files withheld |
| No organization claims | ✅ | |
| Test first | ✅ | each new test seen failing first |
| Python and R in parity | n/a | |
| Paths | ✅ | `paths.TASKS_DIR` |
| Spec for big changes | ✅ | spec 028 tasks.md T011, T011b, T009 |
| Commits | ✅ | |
| Configuration | ✅ | the Kaggle token checked with one call before the build; `HF_TOKEN` checked by 55 before any work |
| Secrets register | ✅ | both credentials name the workflow; no new credential |
| Idempotent writes | ✅ | the build folder replaced whole; Kaggle versions on later runs |
| Publishes outside the repo | ⚠️ | waits for the owner's "merge" (rule 6); the dataset goes live only when the workflow is run |

## Test Coverage
New or extended: `tests/test_kaggle_publish_tasks.py` (19), `tests/test_task_graph.py` (2), `tests/test_task_mine.py`
(1). Local: the full suite (see the PR); `ruff check` clean. Rehearsal: `55_build_tasks.py --snapshots --graphs
--embeddings`, `57_gate_tasks.py --apply-only`, `publish_tasks.py` without `--upload`. The workflow itself runs
after merge.

## Verdict
approve-with-nits. Nothing blocking; merge waits for the owner because it publishes outside the repo.
