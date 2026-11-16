# PR 835 review: cap each agent command's memory in the kernel

Closes #834. Range: `origin/main..fix/834-agent-command-memory`. Files: `kaggle/official_agent_kernel.py` (+35), `python/tests/test_official_agent.py` (+46).

## Scans

- **Secrets:** none. The diff holds no keys, tokens or credentialed URLs.
- **PHI / real data:** none. The tests allocate bytes; no notes or names.
- **Organization claims:** none. The only external source cited is the competition's own HARNESS_README (section 4.1, Docker memory limit 4 GiB).

## Findings (verified)

- 🔵 Nit: `cap_child_memory` swaps `subprocess.Popen` for the whole process while a task runs, so a process another thread starts in that window is capped too. Inside `run_task` only the evaluator starts processes (the GPU sampler and vLLM start before it), so nothing else is affected today. Noted in the docstring's scope; no change.
- 🔵 Nit: `RLIMIT_AS` counts virtual memory, so 8 GiB is looser than Docker's 4 GiB resident limit. Checked: numpy, pandas and pytest run under it (this repo's 52 kernel tests pass in a capped child). A task's tests that need more than 8 GiB of address space would fail here and not on the host; none of the development set's repositories (fastapi, rich, requests, httpx) come near it.

Nothing blocking or should-fix.

## Compliance

| Rule | Result |
|---|---|
| No secrets | ✅ scan clean |
| Synthetic only, no PHI | ✅ |
| No organization claims; vendors cited | ✅ |
| Test first | ✅ three tests, two failed before the change (the asyncio test was not selected in the first run; it fails without `cap_child_memory` because the helper asserts the function exists) |
| Python and R in parity | n/a: no labels, scoring or metrics |
| Simulated is labelled simulated | n/a |
| Seeds fixed | n/a |
| Paths | ✅ no `data/` paths |
| Spec for big changes | n/a: a bug fix with regression tests |
| Commits | ✅ imperative subject, why in the body, co-author trailer |
| Configuration | ✅ one constant, `AGENT_COMMAND_MEMORY_MIB`; no environment changes |
| Idempotent writes | n/a |

## Checks

- `pytest -q tests/test_official_agent.py`: 52 passed.
- `pytest -q tests -k "official or kernel or colab or modal or wording or org_ref or bench_order"`: 249 passed, 2 skipped.
- `ruff check` on the changed files: the new tests are clean. Three warnings that were already on main remain (SIM115 twice in the kernel, UP017 once in the tests).
- Not checked here: rich_4006 ending with the limit's error. That needs the evaluator, so the next Modal run checks it.

## Verdict

Ready to merge when CI is green.
