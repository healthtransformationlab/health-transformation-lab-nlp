# Tasks: the repo's history as a task set

**Tests**: required (test-first) for the module; the scripts are verified by running them.

## US1 - Every PR and direct commit is a row in a manifest #352
- [x] T001 Failing tests in `python/tests/test_task_mine.py`: issue from branch or body, squash subject → PR, spec from text, candidate rule, tiers, ids, manifest row shape
- [x] T002 Implement `task_mine.py`; `scripts/46_mine_tasks.py` writes `data/tasks/task_manifest.csv` (197 rows after #357 merged; 116 candidates: 49 A, 45 B, 22 C); the organisation name CLAUDE.md forbids is redacted from old titles and branch names; ids are unique when two PRs close one issue

## US2 - Every candidate without an issue gets a backfilled record #353
- [x] T003 Failing test: `backfill_issue()` quotes the text verbatim, names the source, carries the label
- [x] T004 `--backfill-issues`: label `backfilled`, title key continues the count, closed on creation with a comment; 67 issues (#278-#344); manifest updated

## US3 - `tasks.jsonl` rows with `patch`, `test_patch` and the two gates #354
- [ ] T005 Failing tests: split a diff into `patch` (non-test) and `test_patch` (`python/tests/`); statement from issue / PR / commit by tier; `created_at`; `base_commit` = the PR's merge base with `main` (PR review #358, should-fix 1), recorded in the manifest
- [ ] T006 `scripts/47_build_tasks.py` writes `data/tasks/tasks.jsonl`; excludes fixes only in grader-stripped files
- [ ] T007 Gates with the competition's evaluator (`swegemma eval --skip-agent-patch`, then with `patch`); drop and list failures

## US4 - Snapshots, graphs, embeddings, wheels #355
- [ ] T008 Snapshots by `git fast-export` to `base_commit` → fresh repo on `main` → `.tgz`
- [ ] T009 AST graph → NetworkX node-link JSON with the dataset's keys; compare one of the competition's files first
- [ ] T010 Embeddings with EmbeddingGemma at 256 dims (named; parity unverified); wheels for the 3.13 sandbox

## US5 - Published as a dataset and scored with the competition's own evaluator #356
- [ ] T011 Kaggle dataset publish (spec 025 workflow); `swegemma eval` run with the agent in gemma-developer-agent
- [ ] T012 Results and tier-wise fidelity in the paper
