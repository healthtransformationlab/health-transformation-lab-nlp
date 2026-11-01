# Feature Specification: the repo's history as a coding-agent task set, in the competition's format

**Feature Branch**: `028-dataops-task-set`

**Created**: 2026-10-29

**Status**: draft; US1 (the manifest) and US2 (backfilled issues) implemented first

**Input**: Build, from this repo's own history, a task set in the exact format of the Gemma 4 Developer
Agent Competition dataset (`tasks.jsonl`, `snapshots/`, `graphs/`, `embeddings/`, `wheels/`), so the same
agent can be scored on the competition's development set and on this repo's incidents and changes, and the
results compared. The competition curated its hidden test set from private repositories the same way; a
task set from a data-pipeline repository is the same kind of object and the paper's "new resource".

> Personal learning project; synthetic data only. Task text is the repo's own issues, PR descriptions and
> commit messages, written at the time of the work. No problem statement is written after the fact.

## Fidelity tiers (every task carries one)

| Tier | Source of `problem_statement` | Source of `hints_text` | Count (Oct 29, 2026) |
|---|---|---|---|
| A | the issue body (branch `<type>/<issue>-<slug>` or "Closes #n" in the PR) | the PR body and `pull_requests/pr-<n>-review.md` | 54 PRs |
| B | the PR title and body (session branches before the issue rule, issue #116) | the review file if present | 71 PRs |
| C | the commit subject and body, plus the spec user story it names | the spec's plan and tasks | 68 direct commits |

A PR or commit is a **candidate task** when its diff changes non-test code and files under
`python/tests/`, which is the competition's own mining rule. Docs-only and data-only changes are kept in
the manifest (they are real history) but are not tasks.

## User stories

### US1 - Every PR and direct commit is a row in a manifest (P1) #352
`python/scripts/46_mine_tasks.py` reads the merged PRs (REST) and the first-parent commits on `main` and
writes `data/tasks/task_manifest.csv`: `instance_id`, `tier_code`, `pr_number`, `issue_number`,
`merge_commit_sha`, `base_commit_sha`, `created_ts`, `merged_ts`, `branch_name`, `title_text`,
`statement_source_code` (issue / pr / commit), `spec_number`, `changed_file_count`, `is_code_changed`,
`is_tests_changed`, `is_candidate`. Re-runnable; rows are keyed by `instance_id`.

### US2 - Every candidate without an issue gets a backfilled record (P1) #353
For tier B and C candidates, `46_mine_tasks.py --backfill-issues` creates one GitHub issue per task that
quotes the contemporaneous text verbatim, links the PR or commit, carries the label `backfilled`, follows
the title key (`<spec> <kind><n>: ...`, spec `000` when none is named), and is closed on creation with a
comment naming the merged PR or commit. The manifest's `issue_number` is filled in. Nothing is reworded.

### US3 - `tasks.jsonl` rows with `patch`, `test_patch` and the two gates (P1) #354
For each candidate: `patch` = the diff excluding test files; `test_patch` = the diff of `python/tests/`;
`problem_statement` and `hints_text` from the tier's source; `created_at` from the issue or PR. A task is
written only if, in the competition's sandbox image, the tests fail on `base_commit` without `patch`
(fail-to-pass) and the suite passes with `patch` and `test_patch` (pass-to-pass). Tasks whose fix lives in
files the grader strips (`conftest.py`, `pytest.ini`, `pyproject.toml`, test files) are excluded and listed.

The gates run with our own check (`task_gate.py`, `scripts/57_gate_tasks.py`, #453), not `swegemma eval`: the
competition's evaluator isn't distributed (no wheel among its files, and its docker/ and sandbox/ don't install
it; found by #449's run). The check follows the harness's documented verification: `test_patch` alone at
`base_commit` makes the target tests (the test files `test_patch` touches) fail; `patch` with protected files
stripped (test files; `conftest.py`, `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, `.pytest.ini`,
`sitecustomize.py`, `usercustomize.py`, `*.pth`) plus `test_patch` makes them exit 0 with passed > 0 and no
failures or errors in the JUnit XML. It runs with this environment's Python and packages, not the competition's
sandbox image; official swegemma scoring happens only on Kaggle (US5).

### US4 - Snapshots, graphs, embeddings, wheels (P2) #355
Snapshot: the files at `base_commit` as one commit in a fresh repo on `main`, as a `.tgz`, with no history, so no old commit message comes along; text files that name the organisation CLAUDE.md forbids have it replaced with `[org]`, like the statements, and a task whose patch names it is left out (#435). Graph: an AST walk
over the package into NetworkX node-link JSON with the dataset's keys. Embeddings: one 256-float array per
node from a named open model (EmbeddingGemma at 256 dimensions), with parity to the competition's unnamed
model stated as unverified. Wheels: the repo's dependencies for the Python 3.13 sandbox.

### US5 - Published as a dataset and scored with the competition's own evaluator (P2) #356
The set is published as a Kaggle dataset (spec 025's publish workflow) and scored with `swegemma eval`,
first `--skip-agent-patch` (the gates), then with the agent in
[gemma-developer-agent](https://github.com/healthtransformationlab/gemma-developer-agent).

## Out of scope
Rewriting any statement text; tasks from other repositories; LoRA training.

## Constitution check
Synthetic data only (task text contains no notes or PHI; the diffs are code). No metric or label change.
Test-first. `@traced` on public functions in the package (the scripts call the package). Honest outputs:
tiers are reported, counts come from the manifest, nothing is backfilled without the `backfilled` label.
