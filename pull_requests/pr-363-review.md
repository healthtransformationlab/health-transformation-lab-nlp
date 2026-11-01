---
pr: 363
branch: ci/362-025-kaggle-benchmark-workflow
title: "025 AI2: push and run the PerioBench Kaggle Benchmarks task from GitHub Actions"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-29
reviewer: coordinator verification (full test suite, YAML parse, CLI check; no reviewer subagent run)
verdict: approve
---

# PR Review: 025 AI2: push and run the PerioBench Kaggle Benchmarks task from GitHub Actions

## Summary
Moves the Kaggle Benchmarks push, run and publish into a manual workflow, as AGENTS.md requires for everything
on Kaggle. Credentials follow the publish workflow exactly; the Model Proxy credentials the CLI fetches stay in
the runner. The validate step guards the SDK's silent no-op (a task without `.run()` pushes fine and records
nothing). Approve; the first real run is the test this review cannot do.

## Scope of Change
- Files changed: 4 (+1 workflow), plus this review
- Areas touched: .github/workflows, kaggle (task file, README), docs
- Commits: ab10aef Push and run the PerioBench Kaggle Benchmarks task from Actions; this review
- Range reviewed: `origin/main..ci/362-025-kaggle-benchmark-workflow`

## CI Status
| Check | Status |
|---|---|
| python, bundle, postgres, PR conventions | pending when written; see the PR |

## Secrets, PHI and Claims Scan
- Secrets: clean. The credentials step masks values; `.env` is written to the runner only and is gitignored;
  the step summary prints model slugs and quota, never keys.
- PHI / real data: clean.
- Organization claims: clean.

## Strengths
- `kaggle b quota` is the one cheap authenticated call before any work, and a missing `MODEL_PROXY_API_KEY`
  in the written `.env` fails the run at once, naming it.
- Validation on 3 notes with the real default model costs cents and catches the one failure the push cannot:
  no run file.
- The dataset is re-specified on every push; the doc says why.
- The `.env` export is deliberate and documented: the SDK's `dotenv.find_dotenv()` walks up from its own
  install path when running a script, so a `.env` in the working directory is not loaded (verified locally).

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- The task file installs the package on Kaggle with `pip install git+https://...`, which needs internet in
  the benchmark kernel. If Kaggle's benchmark kernels run without it, the fix is to attach the package as a
  second dataset; the first run will say.
### 🔵 Nits / suggestions (Minor)
- `kaggle b t download` is allowed to fail (`|| true`) so a run with nothing finished yet still ends green with
  an empty artifact; the status step above it shows the real state.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | |
| Synthetic only, no PHI | Yes | |
| Test first | Yes | the workflow rules in `test_setup_script.py` cover it (manual trigger, name, action versions); the task-file change is covered by `test_kbench.py` |
| Configuration | Yes | no new setting; reuses `KAGGLE_USERNAME` and `KAGGLE_API_TOKEN` from `dev`; the PR says no environment changes |
| Secrets register | n/a | no new credential; the Kaggle token's entry already covers Kaggle runs |
| Commits | Yes | imperative subject, body says why, co-author trailer |
| Docs | Yes | `docs/kaggle_benchmarks.md` and `kaggle/README.md` updated |
| Branch and issue | Yes | `ci/362-025-kaggle-benchmark-workflow`, `Closes #362` |

## Test Coverage
`cd python && python -m pytest -q tests`: 1123 passed, 15 skipped. YAML parses with four inputs and twelve
steps. `kaggle==2.2.5` exposes `benchmarks {tasks, auth, init, quota, leaderboard, topics}`. Not run: the
workflow on GitHub.

## Verdict
Approve. Merge once CI is green, then start it from the Actions tab with `push` and `validate` on.
