---
pr: 505
branch: chore/502-028-gate-exclusions
title: "028 CHORE2: keep gate failures out of the published task set, accept KAGGLE_API_KEY"
author: johncbowyer
reviewed_at: 2026-11-03
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 028 CHORE2: keep gate failures out of the published task set, accept KAGGLE_API_KEY

## Summary
This closes spec 028's T007a: a full `57_gate_tasks.py` run, or `--apply-only` on the committed `task_gates.csv`,
writes `tasks_gated.jsonl` with only the tasks that pass both gates and lists each failure in `tasks_excluded.csv`
(today 114 kept, `htlnlp_127` excluded). The competition check now reads the cloud environment's `KAGGLE_API_KEY`,
and T009 records that our snapshot, graph and embedding formats match the competition's own files. The first
review round found two Important issues (stale gate rows becoming exclusions; a rebuild wiping the gate's rows and
leaving a stale gated set); both are fixed in `9736262` with tests, and verified end to end. Approve with nits.

## Scope of Change
- Files changed: 12 (+180 / -19, excluding generated data); plus `data/tasks/tasks_excluded.csv` (+1 row)
- Areas touched: python, docs, specs, data, ops
- Commits:
  - f956b6b 028 CHORE2: keep gate failures out of the published task set, accept KAGGLE_API_KEY
  - b87c9b0 028 CHORE2: say which extras the gates need
  - 3c76fd6 Merge remote-tracking branch 'origin/main' into chore/502-028-gate-exclusions
  - f8e7132 028 CHORE2: use min() for the example id (ruff FURB192)
  - 9736262 028 CHORE2: one exclusion per task, and a rebuild keeps the gate's rows
- Range reviewed: `b0ad6ca..9736262`

## CI Status
| Check | Status |
|---|---|
| CI on `9736262` | see the PR's checks; local runs below |

## Secrets, PHI and Claims Scan
- Secrets: clean. The Kaggle token is read from the environment and passed to the library; no value is in the
  diff, the register entry names only the variable. `@traced` records no argument values, so passing `os.environ`
  to `kaggle_token` puts nothing in spans (checked in `telemetry.py`).
- PHI / real data: clean. The diff is code, docs and one exclusion row (an instance id and a reason).
- Organization claims: clean. The competition is described from its own files; no organisation named.

## Strengths
- The published set is a separate file, so `tasks.jsonl` keeps every candidate and re-gating is stable.
- Partial runs (`--sample`, `--limit`, `--instance-ids`) never change the set; `--apply-only` refuses them and
  refuses a gate file missing any task.
- Verified against the real data: the rebuild with `55_build_tasks.py` reproduced the committed manifest,
  exclusions and sample byte for byte, and a full re-gate matched every committed verdict.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
Fixed in this PR (first review round):
1. `57_gate_tasks.py` / `task_gate.gate_exclusions`: a gate row for a task no longer built became an exclusion,
   and `merge_exclusions` could list one task twice. Verified by calling `gate_exclusions` with a stale id. Fixed:
   `gate_exclusions(..., task_ids=)` and one row per task, the builder's reason winning
   (`test_a_stale_gate_row_for_a_task_no_longer_built_is_not_an_exclusion`, `test_one_row_per_task_and_the_builders_reason_wins`).
2. `55_build_tasks.py:277`: a rebuild rewrote `tasks_excluded.csv` without the gate's rows and left a stale
   `tasks_gated.jsonl`. Fixed: `carried_gate_rows` keeps the gate rows of tasks still built, and the gated set is
   deleted so it must be gated again (`test_a_rebuild_carries_the_gate_rows_of_tasks_it_still_builds`; end to end:
   rebuild kept `htlnlp_127`'s row and removed the file, `--apply-only` wrote it again).

### 🔵 Nits / suggestions (Minor)
1. Fixed: the task set's folder is now `paths.TASKS_DIR` (was hard-coded in 46, 55 and 57).
2. Open: `apply_gates` and the `--apply-only` guards have no unit test; only the package functions do. Both were
   run by hand here (idempotent, guards trigger).
3. Open: `AGENTS.md`'s credentials table names only `KAGGLE_API_TOKEN` for the Kaggle token; the cloud variable
   `KAGGLE_API_KEY` is in `ops/secrets_register.yaml`. Left alone: changing AGENTS.md is the owner's call.
4. Open: T011 should publish `tasks_gated.jsonl` under the competition's file name, `tasks.jsonl`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | code and ids only |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | 9 new tests, each seen failing first |
| Python and R in parity | n/a | no labels, scoring, reliability or cost-effectiveness change |
| Simulated is labelled simulated | n/a | |
| Seeds fixed | n/a | |
| Paths | ✅ | `paths.TASKS_DIR` |
| Spec for big changes | ✅ | spec 028 tasks.md T007a, T009 updated |
| Prices | n/a | |
| Deck figures | n/a | |
| Commits | ✅ | imperative, why in body, co-author trailer |
| Docs | ✅ | script docstrings and tasks.md |
| Configuration | ✅ | token checked before any network call; no environment changes |
| Secrets register | ✅ | Kaggle entry names the cloud variable |
| Idempotent writes | ✅ | both outputs overwritten whole; `--apply-only` twice gives the same files |
| Alerts | n/a | |

## Test Coverage
New: `tests/test_task_gate.py` (8) and `tests/test_competition_check.py` (1). Run locally: `pytest -q tests`
1653 passed, 15 skipped; `ruff check` on changed files clean; `55_build_tasks.py` rebuild, a full
`57_gate_tasks.py` re-gate (with `.[dev,tasks,ml]`), `--apply-only` twice, and `56_competition_check.py` with only
`KAGGLE_API_KEY` set. Not run: R parity (nothing it covers changed).

## Verdict
approve-with-nits. Nothing blocking; the open nits can follow.
