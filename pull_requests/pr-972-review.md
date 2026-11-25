---
pr: 972
branch: fix/963-028-own-repo-package-path
title: "028 AI24: let our own repo's tasks import the repo's package in the agent's sandbox"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: claude-code (in-session checklist against .claude/review-rubric.md; local pytest; checked in swegemma's own SubprocessManager)
verdict: approve-with-nits
---

# PR Review: let our own repo's tasks import the repo's package in the agent's sandbox

## Summary

Closes #963. For this repository's own tasks, the kernel now adds a `.pth` to each agent sandbox's venv. The file puts
the task's `python/` folder first on `sys.path`, so the agent's commands can import the package under either of its
names. The competition's own tasks are unchanged. The run tables' README lists the 16 tasks (87 task runs) that were
affected before the fix.

## Checks against the rubric

| Item | Result |
|---|---|
| Test first | Both new tests failed before the code: the functions were missing. |
| The competition's harness is unchanged | Only `SubprocessManager.start` is wrapped, only inside the block, and only when `own_repo_dirs` returns folders. A test checks that nothing is written for a competition repository and that `start` is restored. |
| Works where it runs | The `.pth` line is checked on Python 3.11, 3.12 and 3.13. In swegemma's real `SubprocessManager`, both package names import the task's copy after the fix. |
| The right copy wins | The folder goes first on `sys.path`. A test puts a host copy earlier on the path, and the task's copy still wins. |
| Failures say how they ended | Not touched. |
| Contract changes recorded | Dated lines were added to #963 for the names and for the changed checks (a path in place of an install; a sandbox check in place of a GPU rerun). |
| Organization names, wording, bench order (CLAUDE.md, AGENTS.md) | Not touched. `test_no_org_references.py`, `test_wording.py` and `test_bench_order.py` pass. |
| Old project names (spec 021) | CI's full suite caught the package's old name in the kernel's docstring and the new test (`test_rename.py`). Both now describe it without naming it, and the test uses a stand-in second package, which checks the same thing: the folder goes on the path, not a name. `test_rename.py` passes; the guard is unchanged. |

## Findings

- Blocking: none.
- Nit: dependencies still come from the host's packages, as before. The 7 `pandas` misses happened on hosts without
  pandas, and this change doesn't touch them.
- Nit: open-navigator's tasks (3 runs missing `scrapers`) aren't in `own_repo_dirs`. Its packages sit under
  `packages/*/src`, and the mapping can take that pattern if those tasks are run again.
- Nit: the effect on scores isn't measured; that needs a GPU rerun. The README says runs from before the fix are kept
  as they were.

## Verdict

**approve-with-nits**
