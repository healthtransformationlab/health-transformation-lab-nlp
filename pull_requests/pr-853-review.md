# Review: verifier checks on all 129 development tasks, and of patches agents had along the way

Closes #853. Range: `origin/main..data/853-028-verifier-checks`. Files: `kaggle/official_controls_run.py`, `kaggle/official_controls_kernel.py`, `python/tests/test_official_agent.py`, `data/tasks/official_agent_runs/devset_controls.csv` (all 129 tasks), `data/tasks/official_agent_runs/devset_patch_checks.csv` (new, 48 rows).

## Scans

- **Secrets:** none. **Real data:** none; ids, verdicts, exit codes, seconds, and errors cut to 200 characters, never test output. **Organization claims:** none.

## Findings (verified)

- 🟡 Should fix (not blocking): the kernel's sandbox differs from the agents' (the 31B solved requests_7309 and requests_7315 on Modal; their reference fails here). The PR description and #853 say so; readers of `devset_controls.csv` should read "passable" as reference passes here or a recorded run solved it.
- 🔵 Nit: the patches checked are rebuilt from traces, trusted only when the rebuilt final patch equals the saved one; the replay script is not in this PR (it reads traces outside the repo). Its rule is stated in #853.

## Compliance

| Rule | Result |
|---|---|
| Test first | ✅ three tests (rounds, row, kernel) failed before the change |
| Idempotent writes | ✅ both tables merge by key |
| No secrets | ✅ |
| Commits | ✅ |
| Others | n/a |

## Checks

- `pytest -q tests -k "official or dataset_docs or controls"`: 187 passed, 2 skipped.
- Kernel runs: controls on 129 tasks (complete, 2026-11-17T02:03:59Z); 48 given patches in 9 rounds (complete, 21.9 min).

## Verdict

Ready when CI is green. CPU only; publishes nothing outside this repo.
