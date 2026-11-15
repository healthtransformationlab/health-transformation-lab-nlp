---
pr: 750
branch: feat/748-028-colab-e2b-arm
title: "028 AI12: E2B against the Colab baseline, pre-registered, with its sealed bundle and run-list entry"
author: claude (agent session)
reviewed_at: 2026-11-15
reviewer: coordinator review against .claude/review-rubric.md (no separate reviewer subagent was available in this session)
verdict: approve-with-nits (hold: not mergeable until the run is collected and the branch pointers return to main)
---

# PR Review: 028 AI12: E2B against the Colab baseline

## Summary

This PR prepares one new arm, `colab-e2b-statement`. It is the Colab baseline `colab-statement` again, with only the agent's two `model:` lines changed to E2B.

- **Pre-registration.** The arm is registered in addendum 4, and the addendum's hash is recorded on #748 before any run.
- **Helper.** `kaggle/colab_official.py` can now mount the model that a run-list entry names, and keeps E4B as the default.
- **Run list.** The entry is added and `stop` is false.
- **Notebook and helper branch.** Both read this branch while the run is made.
- **Bundle.** It is built and uploaded, and its order and settings match the baseline's bundle.

The code change is small and tested, and the old entries behave as before. No kernel or GPU run was started.

The verdict is approve-with-nits on content. The PR must still not merge before two things happen:

- the owner makes and collects the run (AGENTS.md rule 6: limited compute);
- `BRANCH` and `BRANCH_FILES` go back to `main` and `stop` returns to `true`.

`test_once_merged_the_notebook_and_the_helper_read_main` enforces the second point, so it fails now by design.

## Scope of Change

- Files changed: 6 (+282 / -14)
- Areas touched: kaggle (helper, run list, notebook), python tests, specs
- Commits:
  - `b2bca0d` Pre-register the E2B arm against the Colab baseline (addendum 4)
  - `442992e` Let a run-list entry name the model a Colab run mounts
  - `520a5f0` List the colab-e2b-statement arm and point the notebook at this branch
- Range reviewed: `origin/main (0114053)..520a5f0`

## CI Status

| Check | Status |
|---|---|
| python | expected to fail on one test: `test_once_merged_the_notebook_and_the_helper_read_main` (by design while the branch points at itself) |
| PR conventions | branch `feat/748-...`, `Closes #748`; the issue has all four parts |
| postgres, r-parity, bundle | not affected by this change |

## Secrets, PHI and Claims Scan

- **Secrets:** clean. A grep of the diff for token patterns found nothing. The keyed kernel file went only to its private dataset, and the local copy was removed by the runner (`shutil.rmtree(k)`). No `SEAL_KEY` is left in the work folder.
- **PHI / real data:** clean. Only task ids, hashes and dataset names.
- **Organization claims:** clean.

## Strengths

- **The design isolates the model.** It uses the same 93 ids, seed, 255-minute deadline, telemetry, kernel file (`6f2500de…`) and `tasks.jsonl` (`c98d4b53…`). The new bundle's `official_batch.json` was checked against the baseline's on Kaggle and is equal entry by entry. The agent variant is two lines away from `b95b235`.
- **The decision rule is fixed in advance.** It is set before the run, tied to the run-to-run noise the README documents (3 tasks), and kept separate from the significance claim.
- **The default is safe.** `listed_model` follows the `listed_gpu` pattern, so an entry with no `model` gets E4B. Unlike the GPU, an unreadable list stops the run, because a guessed model would not match the submission.
- **Earlier arms are passed by.** Their results datasets were checked to read as `finished` (93 each), so a fresh A100 notebook does not resume them.

## Findings

### 🔴 Blocking (Critical)

None in content. Merging is held for the reasons in the Summary.

### 🟡 Should fix (Important, non-blocking)

- **The collection step must use the variant checkout.** `official_agent_run.py:743` records `agent_commit_sha` from `git -C <agent-dir> rev-parse HEAD`. Collecting with the agent repository on `main` would write the wrong SHA into the settings, and verify with the wrong submission folder. This was verified by reading `run_batch`. The fix is procedural: collect with `--agent-dir` checked out at `8f4541f`, as the PR body says.

### 🔵 Nits / suggestions (Minor)

- **The E4B arms now depend on reading the run list.** `kaggle/colab_official.py`, `listed_model`: an E4B arm also stops when the run list can't be read three times, where before it went ahead. That is acceptable: 3 tries, 15 s apart, and no listed arm is still to run.
- **A comment still names E4B.** In the agent variant, the `agent.yaml` comment still says "Small-model bonus: gemma-4-e4b-it-qat-w4a16-ct". It was left on purpose so that only the model changes. It is harmless, but it may confuse a reader of the branch.
- **A fresh notebook re-checks the earlier arms first.** It reinstalls the pins and downloads each earlier arm's results (about 2 MB each) before it reaches the E2B arm. That costs a few minutes and nothing else.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | scan clean |
| Synthetic only, no PHI | yes | |
| No organization claims | yes | |
| Test first | yes | 12 new or changed tests failed before the helper change, then passed |
| Python and R in parity | n/a | no label, scoring, reliability or cost logic |
| Simulated labelled | yes | no result is claimed; the addendum says no E2B run exists |
| Seeds fixed | yes | 20261110, as the baseline |
| Paths | yes | no new `data/` paths |
| Spec for big changes | yes | spec 028 addendum 4, `tasks.md` T029 |
| Commits | yes | imperative subjects, bodies say why, co-author trailer |
| Configuration | yes | the new optional run-list field is documented in the code and in the list's note; no environment changes |
| Secrets register | n/a | no new credential; the Colab secrets are the existing ones |
| Idempotent writes | yes | a re-upload creates a new dataset version; results resume as before |

## Test Coverage

Run locally (Python 3.13):

- `pytest tests/test_colab_official.py tests/test_wording.py tests/test_no_org_references.py tests/test_bench_order.py tests/test_telemetry_*.py tests/test_official_agent*.py`: 169 passed, 1 failed (the expected branch-pointer test).
- `ruff check` on both changed Python files: clean.

Covered by tests: the per-entry model with an E4B default, an unreadable list, a malformed handle, `fetch` mounting only the named model, `run_one` passing the listed or explicit model, and the exact E2B entry.

Not testable here: that vLLM serves E2B on Colab with the kernel's unchanged arguments. The kernel already allows E2B (`ALLOWED_MODELS`). The addendum says what happens if the server does not start.

## Verdict

Approve-with-nits. Merge waits for all of these:

1. the owner runs the arm;
2. it is collected with `--agent-dir` at `8f4541f`;
3. the table and settings are committed;
4. `BRANCH`, `BRANCH_FILES` and `stop` are restored, so that `test_once_merged_the_notebook_and_the_helper_read_main` passes;
5. the owner says "merge".

## Update, 2026-11-15 (commit `7d23e7c`)

The owner moved the comparison to Kaggle as two paired arms. This commit withdraws the Colab arm before any session made it:

- the `colab-e2b-statement` entry is off the run list;
- `stop` is `true`;
- `BRANCH` and `BRANCH_FILES` read `main` again.

**Why the entry is removed, not just stopped.** The notebook makes every run the list names, whatever `stop` says. An entry left with `stop` set would still be made once this merges. The new test `test_the_superseded_e2b_colab_arm_is_not_listed` checks this.

**Tests.** `test_once_merged_the_notebook_and_the_helper_read_main` passes again. `test_colab_official`, `test_wording`, `test_no_org_references` and `test_bench_order` give 86 passed, and `ruff` is clean.

**Still before merge:**

- **🟡 E4B is hard-coded for Kaggle kernels.** `kaggle/official_agent_run.py:303` attaches `MODEL_SOURCE` (E4B) to every Kaggle kernel. A `kaggle-e2b-statement` kernel would mount no E2B model, and the kernel's model glob would fail. It needs a tested change that attaches the submission's declared model.
- **The Kaggle pair's addendum** has to be written and its hash recorded on #748 before any kernel starts.
- **Kernels wait on two things.** The account's weekly GPU quota (30.19 of 30 h used, resets 2026-11-21 00:00 UTC; the Colab Pro+ hours not yet shown) and both GPU session slots being free.

The verdict is unchanged: hold.
