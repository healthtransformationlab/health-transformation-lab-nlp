---
pr: 455
branch: feat/453-028-task-gate
title: "028 US3: our own fail-to-pass gate for the task set (114 of 115 pass)"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator self-review against the rubric (no reviewer subagent available in this session), findings verified
verdict: approve-with-nits
---

# PR Review: 028 US3: our own fail-to-pass gate for the task set (114 of 115 pass)

## Summary
The competition's evaluator (swegemma) isn't distributed (#449), so this PR adds our own gate that follows the
harness's documented verification. `task_gate.py` strips protected files from `patch` and runs the target tests in a
temporary `git worktree` at `base_commit`, first with `test_patch` alone (must fail) and then with the stripped
`patch` plus `test_patch` (must pass, read from the JUnit XML). `57_gate_tasks.py` gates every row into
`data/tasks/task_gates.csv`. On all 115 tasks: 114 valid, 1 invalid (`htlnlp_127`). I reran that task by hand and
the verdict is correct: its fix needs a `pyproject.toml` change that the harness strips. Approve with nits. The one
should-fix (a leaked file descriptor) is fixed in this PR.

## Scope of Change
- Files changed: 7 (+517 / -7, excluding `data/tasks/task_gates.csv`, 116 lines)
- Areas touched: python, specs, data
- Commits:
  - 8d49026 Gate the task set with our own fail-to-pass check
  - fc6590d Merge remote-tracking branch 'origin/main' into feat/453-028-task-gate
  - (this review commit) Fix a leaked descriptor in the gate; add PR 455 review
- Range reviewed: `c62b36f..HEAD`

## CI Status
| Check | Status |
|---|---|
| changes, check (PR conventions), bundle, azure-infra | success |
| python, postgres, r-parity | in progress at review time |

## Secrets, PHI and Claims Scan
- Secrets: clean. A grep for token, secret, password, key and `hf_`/`ghp_` patterns finds only the old T007 text.
- PHI / real data: clean. `task_gates.csv` holds instance ids, commit SHAs, exit codes, counts and seconds. No note text.
- Organization claims: clean. The competition is described only by its own harness documentation. The
  organisation name CLAUDE.md forbids appears nowhere (`test_no_org_references.py` passes).

## Strengths
- The worktree is removed in `finally`, and a test proves it even when a run raises. After the full run,
  `git worktree list` shows no gate worktrees left.
- On a timeout the whole process group is killed, so a pytest that started child processes can't hang the run.
- `DENTAL_*` variables are dropped from the child environment, so no data root leaks in from outside.
- The docs say plainly that this is not the competition's sandbox and that official scoring stays on Kaggle.
- The one failure was traced to its cause, not just counted.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. ~~`task_gate.py` `run_tests`: `tempfile.mkstemp` returns an open descriptor that was never closed, so 230 runs
   leaked 230 descriptors.~~ Verified by reading the code (only `[1]` of the tuple was used). **Fixed in this PR**:
   the descriptor is now closed before pytest runs, and the gate tests still pass (14 passed).

### 🔵 Nits / suggestions (Minor)
1. `python/tests/test_task_gate.py`, `test_runs_use_the_given_python`: this passes `sys.executable`, the default, so
   it doesn't prove the parameter is used. A fake interpreter path would. Low risk: the parameter is passed straight
   to the command.
2. An exit code of 5 (no tests collected) before the fix counts as "fails without the fix". That matches the
   harness's rule (any non-zero exit), but if the harness treated 5 differently we would differ. 0 of 115 tasks had
   exit 5 before the fix (39 had exit 2, a collection error, the usual result for new code), so nothing changes today.
3. Gate failures are listed in `task_gates.csv` but not yet dropped from `tasks.jsonl`. This is tracked as T007a, and
   the PR uses `Refs #354` for that reason.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | Scan clean |
| Synthetic only, no PHI | Yes | Code diffs and counts only |
| No organization claims; vendors cited | Yes | |
| Test first | Yes | 14 tests in `test_task_gate.py`, written and failing before the module |
| Python and R in parity | N/A | No label, scoring, reliability or cost change |
| Simulated is labelled simulated | N/A | Real runs; the docs name the environment they used |
| Seeds fixed | N/A | Nothing random |
| Paths | Yes | `REPO_ROOT` from `paths` |
| Spec for big changes | Yes | spec 028 spec, plan and tasks updated (T007 done, T007a added) |
| Prices | N/A | |
| Deck figures | N/A | |
| Commits | Yes | Imperative subject, body says why, co-author trailer |
| Docs | Yes | Script and module docstrings, plus the spec |
| Configuration | Yes | No new settings; inputs and `--timeout` are checked before work starts |
| Secrets register | N/A | No credential used (GitHub REST unauthenticated for 55) |
| Idempotent writes | Yes | `task_gates.csv` is overwritten whole |
| Alerts | N/A | |
| `@traced` | Yes | Every public function in `task_gate.py`; `test_telemetry_calls.py` passes |
| Script numbers unique | Yes | 57 is free on main and on open PRs; `test_script_numbers.py` passes |

## Test Coverage
What the tests cover:
- the protected-path list
- whole-block stripping of protected files
- choosing the target tests: excludes conftest and deleted files
- JUnit parsing
- a valid task
- tests that already pass at the base
- a fix that doesn't fix
- a fix that lives only in a stripped `conftest.py`
- no target tests
- a patch that doesn't apply
- no tests collected
- a timeout
- worktree cleanup when a run raises

What was run locally:
- the full suite: 1538 passed, 15 skipped
- the tests touching tasks and naming after the merge with main: 77 passed
- `ruff check` on the changed files: clean
- the real run on 115 tasks, and on the 3-row sample

Not covered: the competition's sandbox image.

## Verdict
Approve with nits. Nothing blocks the merge, and the should-fix is done.
