# PR 884 review: a missing module refuses a resolve count only when the grader is broken (#883)

Reviewed against `AGENTS.md` and `.conventions/AGENTS-common.md`.

| Check | Result |
|---|---|
| One issue, branch `fix/883-verify-missing-module`, `Closes #883` | yes |
| Test first | `test_verify_env_guard.py` and `test_telemetry_forward.py`: 20 passed. The new cases failed before the change (the task-package case had no `environment_faults`; a missing telemetry file still imported the package) |
| Contract | `pytest`, or any module the reference patch also cannot import, refuses the count (oracle grade exits 2). A module only the agent patch misses is an ordinary failure. The collector runs the reference check before it prints a resolve count. A launch imports `health_transformation_lab_nlp` and `swegemma` first and names the module if either is missing. No telemetry file skips that import; a telemetry file with the package missing is reported and grading continues |
| Secrets / PHI | none |
| Docs | none required for this fix |

## Findings

Nothing blocking. The guard still matches the text `No module named` only. Other environment faults stay ordinary failures until they use those words.
