# Implementation Plan: the repo's history as a task set

**Branch**: `spec/352-028-dataops-task-set` (on top of spec 027) | **Date**: 2026-10-29 | **Spec**: [spec.md](spec.md)

## Summary
A pure module (`task_mine.py`) tiers every change and decides candidates; a script (`46_mine_tasks.py`)
does the IO: REST for PRs and issues, git for diffs, a manifest CSV, and the backfilled issues. A later
script builds `tasks.jsonl`, snapshots, graphs and embeddings from the manifest; a third verifies the two gates
with our own check of the harness's documented verification, since the competition's evaluator (swegemma) isn't
distributed (#449, #453). Official swegemma scoring happens only on Kaggle (US5).

## Technical context
- Python 3.12, pandas; `gh api` (REST only; GraphQL is unavailable from cloud sessions); git with
  `--depth=1000` history on main. No new dependencies for US1-US2. US4 adds networkx and an embedding model.
- Tests: pytest on the pure module; the script is exercised by running it.

## Design
| Piece | File |
|---|---|
| Tiering, candidate rule, ids, backfill-issue text | `python/health_transformation_lab_nlp/task_mine.py` |
| Manifest and issue backfill (REST + git) | `python/scripts/46_mine_tasks.py` |
| The manifest (committed; re-runnable, keeps issue numbers) | `data/tasks/task_manifest.csv` |
| `tasks.jsonl` builder, snapshots, graphs, embeddings, gates (US3-US4); 47 was taken by spec 029 | `python/scripts/55_build_tasks.py` |
| The two gates in a temporary `git worktree` per base commit (strip protected files, run the target tests, read the JUnit XML) | `python/health_transformation_lab_nlp/task_gate.py` |
| Gate every task; `data/tasks/task_gates.csv` (committed, one row per task) | `python/scripts/57_gate_tasks.py` |
| `tasks.jsonl` (git-ignored, ~62 MB of patches), the excluded list and a 3-row sample (committed) | `data/tasks/` |
| Publish as a Kaggle dataset (US5) | `.github/workflows/kaggle-publish.yml` (spec 025 pattern) |

Squash merges appear as single-parent commits on `main` whose subject ends `(#n)`; merge commits name the
PR in `merge_commit_sha`. Both map to their PR; what is left is a direct commit (tier C).

## Constitution check
Synthetic data only (the manifest holds titles, shas and counts). No metric or label change. Test-first
for the module. Honest outputs: tiers and counts come from the manifest; backfilled issues are labelled and
quote the original text verbatim.
