# Tasks: the repo's history as a task set

**Tests**: required (test-first) for the module; the scripts are verified by running them.

## US1 - Every PR and direct commit is a row in a manifest #352
- [x] T001 Failing tests in `python/tests/test_task_mine.py`: issue from branch or body, squash subject → PR, spec from text, candidate rule, tiers, ids, manifest row shape
- [x] T002 Implement `task_mine.py`; `scripts/46_mine_tasks.py` writes `data/tasks/task_manifest.csv` (197 rows after #357 merged; 116 candidates: 49 A, 45 B, 22 C); the organisation name CLAUDE.md forbids is redacted from old titles and branch names; ids are unique when two PRs close one issue

## US2 - Every candidate without an issue gets a backfilled record #353
- [x] T003 Failing test: `backfill_issue()` quotes the text verbatim, names the source, carries the label
- [x] T004 `--backfill-issues`: label `backfilled`, title key continues the count, closed on creation with a comment; 67 issues (#278-#344); manifest updated

## US3 - `tasks.jsonl` rows with `patch`, `test_patch` and the two gates #354
- [x] T005 Failing tests: split a diff into `patch` (non-test) and `test_patch` (`python/tests/`); statement from issue / PR / commit by tier; `created_at`; `base_commit` = the PR's merge base with `main` (PR review #358, should-fix 1), recorded in the manifest (`base_commit_source_code`: 130 `merge_base`, 67 `parent`)
- [x] T006 `scripts/55_build_tasks.py` (47 was taken) writes `data/tasks/tasks.jsonl` (git-ignored, 62 MB: 115 ungated rows, 48 A, 45 B, 22 C, after #435 dropped `htlnlp_91`), `tasks_excluded.csv` (1 row since #435, the task whose patch names the organisation; before it, 0 rows: the manifest already drops fixes only in grader-stripped files) and a 3-row committed `tasks_sample.jsonl`; that row is now excluded (#435), and the build fails if any row still names the organisation
- [ ] T007 Gates with the competition's evaluator (`swegemma eval --skip-agent-patch`, then with `patch`); drop and list failures. Blocked (Nov 1, 2026): `swegemma` is not on PyPI; it ships only in the competition's Kaggle wheelhouse, which a cloud session can't download without a Kaggle token

## US4 - Snapshots, graphs, embeddings, wheels #355
- [x] T008 Snapshots: the files at `base_commit` as one commit → fresh repo on `main` → `.tgz` (`task_graph.snapshot`, `55_build_tasks.py --snapshots N`; git-ignored; `snapshot_index.csv` committed). First built from `git fast-export` history; since #435 there is no history, so no old commit message or file comes along. The tree always equals the base's (checked); the head SHA is the snapshot's own (fixed author, date and message "Snapshot of <base_commit>"), so the index maps `base_commit` to `snapshot_head_sha`. Text files at the base that name the organisation CLAUDE.md forbids have it replaced with `[org]` (`redacted_paths` in the index; every other file is the base's byte for byte, checked); a task whose patch or test patch names it is excluded, with the reason in `tasks_excluded.csv` (one task, `htlnlp_91`)
- [x] T009 AST graph → NetworkX node-link JSON with the dataset's keys (`task_graph.build_graph`, `--graphs`; 116 graphs when built, 115 tasks since #435, median 488 nodes and 397 `calls` edges, 49 MB, git-ignored; the package is found per base, since it was renamed). Keys follow gemma-developer-agent `docs/dataset-format.md`; no competition graph file was compared (Kaggle download not possible from a cloud session), so the node-id form and tgz layout are unverified
- [ ] T010 Embeddings with EmbeddingGemma at 256 dims (named; parity unverified); wheels for the 3.13 sandbox. Blocked (Nov 1, 2026): `google/embeddinggemma-300m` is gated on Hugging Face and the session's token has not accepted the Gemma licence (403); wheels can be downloaded from PyPI but belong with the embeddings run

## US5 - Published as a dataset and scored with the competition's own evaluator #356
- [ ] T011 Kaggle dataset publish (spec 025 workflow); `swegemma eval` run with the agent in gemma-developer-agent
- [ ] T012 Results and tier-wise fidelity in the paper
