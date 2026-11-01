---
pr: 425
branch: feat/355-028-snapshots-graphs
title: "028 US4: task snapshots and code graphs (embeddings and wheels pending)"
author: Claude Code (agent session)
reviewed_at: 2026-11-01
reviewer: coordinator verification against .claude/review-rubric.md (no reviewer subagent available in this session)
verdict: approve-with-nits
---

# PR Review: 028 US4: task snapshots and code graphs (embeddings and wheels pending)

## Summary
The PR adds snapshots (git fast-export up to `base_commit`, imported into a fresh repo on `main`, packed as a
`.tgz`) and per-task code graphs (an AST walk into NetworkX node-link JSON with the dataset's keys). Both work:
116 graphs load in networkx as MultiDiGraphs, and 2 snapshots were built whose trees match their bases. The PR
is stacked on #421 and should merge after it. T010 (embeddings and wheels) is blocked on the gated
EmbeddingGemma model, so the PR uses `Refs #355`. Verdict: approve with nits. The should-fix items are owner
decisions to make before anything is published.

## Scope of Change
- Files changed (c9c96d7, excluding #421's commit and the main merge): 6 (`task_graph.py`, `test_task_graph.py`, `52_build_tasks.py`, `pyproject.toml`, `snapshot_index.csv`, `tasks.md`)
- Areas touched: python, specs, data
- Commits: c9c96d7 Build task snapshots and code graphs (028 US4, T008-T009); merge of origin/main (no conflicts)
- Range reviewed: `459c90a..c9c96d7` (the new work); #421 is reviewed in `pr-421-review.md`

## CI Status
| Check | Status |
|---|---|
| python / postgres / r-parity / bundle | not read from this session (the GitHub API token was invalid); local run below |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean. `snapshot_index.csv` holds only SHAs, counts and sizes.
- Organisation claims: clean in tracked files (`test_no_org_references.py` passes). See should-fix 1 for the
  generated snapshots.

## Strengths
- `snapshot` checks that the imported tree equals the base's tree, and removes its temporary ref in a `finally`
  block. Verified: no `refs/tasksnap/*` is left after the runs.
- Graphs are found per base even though the package was renamed (`dental_omop_nlp` → `health_transformation_lab_nlp`).
  Before this fix, 88 of 116 graphs were empty; the bug was caught by running the script, and a test now covers it.
- The node-link JSON is written without networkx. The extra exists only to load graphs, and the test skips without it.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Full-history snapshots carry the organisation name.** Verified for `htlnlp_100`'s base: the name appears
   in 2 commit messages and 12 files at that commit. Nothing is committed (snapshots are git-ignored), but
   publishing them (US5) would distribute it. Owner decision: truncate the history (one commit, as
   gemma-developer-agent `docs/dataset-format.md` describes), or rewrite messages and files before export.
   Graph `text` fields at old bases can carry it too.
2. **Snapshot head SHAs differ from `base_commit`.** git 2.43 drops GitHub's commit signatures on fast-export
   (`--signed-commits=verbatim` needs 2.46+). Verified: both snapshots report `head differs`, and their trees
   match. If the harness checks out `base_commit` by SHA, set `base_commit` to `snapshot_head_sha` (from
   `snapshot_index.csv`), or build with newer git.

### 🔵 Nits / suggestions (Minor)
1. Calls through instances (`obj.method()` where `obj` is a local variable) are not resolved; only module
   names, imports, `self.` and class names are. The edge density (about 0.8 edges per node) is in the range of
   the competition's FastAPI graph (0.57).
2. The node-id form and the `workspace/` tgz layout are unverified against a competition file, as stated in the
   module docstring and in `tasks.md`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | |
| Synthetic only, no PHI | yes | |
| No organization claims | yes in git | generated snapshots: should-fix 1 |
| Test first | mostly | graph and snapshot tests were written before the module; the package-rename test failed first |
| Python and R in parity | n/a | |
| Seeds fixed | n/a | |
| Paths | yes | `paths.REPO_ROOT` |
| Spec for big changes | yes | tasks T008 and T009 ticked with what is unverified |
| Commits | yes | |
| Idempotent writes | yes | graphs and snapshots overwritten; `snapshot_index.csv` is keyed by `instance_id` |

## Test Coverage
`test_task_graph.py` covers module names, package detection across the rename, node and edge keys, call
resolution, networkx loading, and a snapshot of a temporary repo (history only up to the base, `main`, clean
status, ref removed, tree equal). Local run: `python -m pytest -q tests` gave 1262 passed and 15 skipped;
`ruff check` was clean.

## Verdict
Approve with nits, after #421. Decide should-fix 1 and 2 before US5 publishes anything.
