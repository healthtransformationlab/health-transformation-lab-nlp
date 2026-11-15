---
pr: 750
branch: feat/748-028-colab-e2b-arm
title: "028 AI12: E2B against E4B as two paired Kaggle arms, pre-registered and ready to start"
author: claude (agent session)
reviewed_at: 2026-11-15
reviewer: coordinator review against .claude/review-rubric.md (no separate reviewer subagent was available in this session)
verdict: approve-with-nits (hold: the kernels have not run; results and the paired test are still to come)
---

# PR Review: 028 AI12: E2B against E4B as two paired Kaggle arms

## Summary

This PR prepares, but does not run, a paired comparison of E2B and E4B on the 93 published tasks. It does five things:

- **Addendum 5** is frozen, and its hash is on #748. It sets out two Kaggle arms on the same machine shape and image, one test (exact McNemar, two-sided) and a decision rule. The rule switches to E2B only if E2B gains 4 or more tasks, beyond the documented 3-task noise, and p < 0.05.
- **`official_agent_run.py`** now attaches the model the submission declares, instead of always E4B. The E4B kernel metadata is byte for byte unchanged.
- **The Colab plan is withdrawn untested.** That was addendum 4, its run-list entry and the notebook pointers.
- **`colab_official.py`** gains an optional per-entry `model` field, with E4B as the default.
- **The PR body and the addendum** give the start and collection commands.

The code is small and tested, and the design is sound. The PR is held because the arms have not run: their tables and the paired test belong in this PR before it merges. Starting them needs the owner's word and room in the GPU quota, per AGENTS.md rule 6.

## Scope of Change

- Files changed (against `main`): `kaggle/official_agent_run.py`, `kaggle/colab_official.py`, `python/tests/test_official_agent.py`, `python/tests/test_colab_official.py`, `specs/028-dataops-task-set/preregistration-colab-e2b-arm.md` (addendum 4, kept as a record), `specs/028-dataops-task-set/preregistration-kaggle-e2b-pair.md` (addendum 5), `specs/028-dataops-task-set/tasks.md`, this file. `kaggle/colab_official_run.json` and `kaggle/colab_official_agent.ipynb` end equal to `main`, apart from the run list's note.
- Areas touched: kaggle, python tests, specs.
- Range reviewed: `origin/main..7eaeab8`.

## CI Status

| Check | Status |
|---|---|
| python | the touched suites pass locally (176); the branch-pointer test passes again |
| PR conventions | branch `feat/748-…`, `Closes #748`; the issue has all four parts |
| postgres, r-parity, bundle | not affected |

## Secrets, PHI and Claims Scan

- **Secrets:** clean. No tokens are in the diff. The command block reads the token from the environment and never echoes it.
- **PHI / real data:** clean.
- **Organization claims:** clean.

## Strengths

- **The E4B arm is unchanged.** `declared_model` and `model_source` are tested for E2B, for a mixed declaration, for an unknown model, for no declaration, and for the runner's allowed list matching the kernel's. The E4B kernel metadata was compared against `main`'s module output for three labels, with and without image and machine shape, and was identical.
- **Only the model differs between the arms.** Same ids, seed, order, budgets, kernel file, image, machine shape and kernel limits. Session variation falls inside the pair, not between the arms.
- **The decision rule is fixed before the run.** It is tied to the README's measured noise and also needs significance.
- **The withdrawal is safe.** The Colab entry is removed, not just stopped, because the notebook makes every listed run. A test checks this.

## Findings

### 🔴 Blocking (Critical)

None in content. Merging is held until both arms are collected and the paired test is committed.

### 🟡 Should fix (Important, non-blocking)

- **Collecting needs the competition's evaluator installed** on the collecting machine (`swegemma`, `adk-submission`, `adk-eval-core` from `metric/gemma-4-developer-agent-wheelhouse`). This session doesn't have it. The PR body and the addendum point to `data/tasks/official_verifier/README.md` for the install. If the start processes run without it, collect with `--collect` once it is installed.

### 🔵 Nits / suggestions (Minor)

- **`ruff` flags UP017** (`datetime.UTC`) at `official_agent_run.py:276` and `test_official_agent.py:402`. Both lines were already on `main` and are not changed here.
- **Handle version.** `model_source` assumes version 2 for every allowed model. That is true on November 15, 2026 for all four, but a newer Kaggle version would not be picked up. This is intended, because the pinned version makes runs repeatable.
- **Addendum 4 stays in the tree** as the record of a withdrawn plan. Addendum 5 names it and its hash.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | scan clean |
| Synthetic only, no PHI | yes | |
| No organization claims | yes | |
| Test first | yes | the new tests failed before each change (6 for the runner, 12 for the Colab helper) |
| Python and R in parity | n/a | no label, scoring, reliability or cost logic |
| Simulated labelled | yes | no result is claimed; both addenda say no E2B run exists |
| Seeds fixed | yes | 20261110 |
| Spec for big changes | yes | spec 028 addenda 4 and 5, T029 |
| Commits | yes | imperative subjects, bodies say why, co-author trailer |
| Configuration | yes | no environment changes; the new run-list field and the runner behaviour are documented in code |
| Secrets register | n/a | no new credential |

## Test Coverage

Run locally: `pytest tests/test_official_agent*.py tests/test_colab_official.py tests/test_wording.py tests/test_no_org_references.py tests/test_bench_order.py tests/test_telemetry_*.py` gives 176 passed.

Both arms were dry-run with `--plan-only` from worktrees at `b95b235` and `8f4541f`: 93 tasks each, and the right handles.

Not testable here: that vLLM serves E2B with the kernel's unchanged arguments on 4×L4. If it does not, addendum 5 says the E2B arm has no outcome and nothing is changed to work around it.

## Verdict

Approve-with-nits on content. Merge waits for all of these:

1. the owner's go-ahead and room in the quota;
2. both kernels run;
3. both arms are collected, with their tables, settings and the paired McNemar committed here;
4. the owner says "merge".
