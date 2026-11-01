---
pr: 361
branch: feat/360-025-kaggle-benchmarks-task
title: "025 AI1: PerioBench as a Kaggle Benchmarks task"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-29
reviewer: coordinator verification (full test suite, lint and a dry run; no reviewer subagent run)
verdict: approve
---

# PR Review: 025 AI1: PerioBench as a Kaggle Benchmarks task

## Summary
Wraps PerioBench in Kaggle's `kaggle-benchmarks` SDK so Kaggle's leaderboard can run it against every model
behind its proxy. Nothing of ours is reimplemented: the reader prompt (`llm_reader.PROMPTS`), the quote gate
(`parse_answer`), the judge prompt and gate (`judge.SYSTEM`, `judge.gate`), the six labels and the
`eval/score.py` metrics are called as they are, and a parity test holds the metrics to 1e-9. The task file
runs end to end without credentials on a scripted model and says SIMULATED. Approve.

## Scope of Change
- Files changed: 8 (+609), plus this review
- Areas touched: python (new module, tests, extra), kaggle (task file, README row), docs, AGENTS.md, .gitignore
- Commits: 3632335 Add PerioBench as a Kaggle Benchmarks task; this review
- Range reviewed: `origin/main..feat/360-025-kaggle-benchmarks-task`

## CI Status
| Check | Status |
|---|---|
| python, bundle, postgres, PR conventions | pending when written; see the PR |

## Secrets, PHI and Claims Scan
- Secrets: clean. Credentials come from `kaggle b init` into a gitignored `.env`; none in the diff.
- PHI / real data: clean. The task reads the committed synthetic `review_key.csv`; the dry run uses a scripted model.
- Organization claims: clean. The grant checklist states what the repo has, not what anyone has agreed to.

## Strengths
- `score_rows` is tested against `eval/score.py` on the same inputs, so the Kaggle number and the repo's
  leaderboard number cannot drift apart.
- The judge step reuses `judge.gate`, so a judge that does not quote the note is `not_determinable` on Kaggle
  exactly as it is in the scorecard.
- `ScriptedReader` is named `sim:` and `perio_bench` returns `is_simulated`, so a dry run cannot be mistaken
  for a result; the task file prints the label in capitals.
- The SDK's `*.run.json` is written where the task runs; tests chdir to a temp folder and the pattern is
  gitignored, so no run files can land in the tree.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- The push is by hand for now. AGENTS.md says Kaggle work starts from GitHub Actions; a workflow next to the
  publish one is the follow-up, after the CLI flow has been exercised once (noted in the issue and the doc).
### 🔵 Nits / suggestions (Minor)
- `kbench.py` deliberately has no `from __future__ import annotations` (the SDK reads the real return
  annotation); the comment says so, but a test that imports the module and checks
  `read_note.result_type is results.Dictionary` would guard it. `test_task_file_dry_runs_on_a_scripted_model`
  fails if that ever regresses, so it is covered indirectly.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | |
| Synthetic only, no PHI | Yes | review set only; scripted models in tests |
| No organization claims; vendors cited | Yes | Kaggle's own blog and CLI docs are linked |
| Test first | Yes | 15 tests in `test_kbench.py`; the parity and gate tests fail without the module |
| Python and R in parity | n/a | no change to labels or scoring; the metrics are consumed, not changed |
| Simulated is labelled simulated | Yes | `sim:` names, `is_simulated`, SIMULATED in the dry-run output |
| Seeds fixed | Yes | `eval_frame(n, seed=0)` |
| Paths | Yes | `paths.DATASETS_DIR` |
| Spec for big changes | n/a | no dataset, metric or label-rule change; the issue is `025 AI1` |
| Commits | Yes | imperative subject, body says why, co-author trailer |
| Docs | Yes | `docs/kaggle_benchmarks.md`, `kaggle/README.md` row, AGENTS.md map and command |
| Configuration | Yes | no settings change; the SDK's `.env` is documented and gitignored; no environment changes |
| Secrets register | n/a | no new credential; `KAGGLE_API_TOKEN` is already registered |
| Telemetry | Yes | every public function and method in `kbench.py` is `@traced` (`test_every_public_function_in_the_package_is_traced`) |
| Branch and issue | Yes | `feat/360-025-kaggle-benchmarks-task`, `Closes #360` |

## Test Coverage
`cd python && python -m pytest -q tests`: 1083 passed, 15 skipped. `ruff check` on the three new Python
files: clean. `python kaggle/perio_bench_task.py` from a clean folder: 240 notes, 0 errored, 483 run files,
output labelled SIMULATED. Not run here: the real push to Kaggle (needs `kaggle b init` on a laptop).

## Verdict
Approve. It can merge once CI is green.
