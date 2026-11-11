# PR 680 review: let the trace plugin's tests find pytest in the deploy job (#679)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `fix/679-028-trace-tests-user-site`, `Closes #679`; a small fix with a regression test, so no spec | ok |
| The failure is read from the deploy job's own log (run 326, job "deploy (dev)", step "Python tests before deploying"): `/usr/bin/python3: No module named pytest` in two tests of `tests/test_trace_reach.py`; 2 failed, 2,346 passed | ok |
| Cause: the tests moved `HOME` to a temp folder in the subprocess's environment, and the deploy job's pytest is in the user site under the real `HOME` (it installs with the runner's Python, without `setup-python`) | ok |
| Test first: `test_a_plugin_subprocess_keeps_this_interpreters_own_packages` was run against the old environment and failed with the temp folder's `.local` as the user base; it passes with `PYTHONUSERBASE` set | ok |
| The fix keeps the tests' small environment (nothing of the caller's but the import path, `HOME` in the temp folder) and adds one variable | ok |
| Tests only: `python/scripts/68_trace_reach.py` builds its subprocess from the caller's environment, so the committed table and its counts do not change | ok |
| `pytest -q tests/test_trace_reach.py`: 8 passed; wording, organisation-name and benchmark-order tests pass | ok |
| The fix cannot be shown on this machine as the deploy job would see it (pytest here is not in the user site). The regression test checks the mechanism; the deploy job on `main` after the merge is the proof | note |
| No secrets, no data, no settings | ok |

Nothing blocking.

## Notes
- Severity: SEV2 by AGENTS.md. Four merges went to `main` without a deploy to dev (pull requests 671, 673, 675,
  676). "Test every change" passed on each, so the pull requests looked green.
- The same pattern is in two tests of `tests/test_failure_report.py` on the branch of #674. They get the same
  environment before that branch merges.
- Worth an issue of its own: the deploy job and "Test every change" install Python differently, so a test can
  pass in one and fail in the other. One way of setting Python up in both would have caught this on the pull
  request.
