---
pr: 740
branch: fix/737-028-record-submission-output-budget
title: "028 BUG9: the run tables record the evaluator's default output budget, not the submission's"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator review of the diff against the rubric (no reviewer subagent: one reader, one merge helper, two keyword arguments and four call sites, read line by line)
verdict: approve
---

# PR Review: 028 BUG9: the run tables record the evaluator's default output budget, not the submission's (#737)

## Summary
The run tables took `max_output_tokens` and `thinking_budget` from the evaluator's fallback (`generation_defaults`),
never from the submission. Every committed run's submission set the fallback's own values, so no committed table is
wrong; the first run with a different value (gemma-developer-agent pull request 100, 8,192) would have been recorded
as 16,384. The runner now reads the uploaded `agent.yaml` and records what each call was given, keeping the fallback
beside it. Approve.

## Scope of Change
- Files changed: 2, plus this review
- Areas touched: Kaggle run tooling (`kaggle/official_agent_run.py`), python tests
- Commits: `dc6a30d` Record the output budget the submission used, not the evaluator's fallback; this review
- Range reviewed: `0114053..HEAD` (the merge base with `main`)

## CI Status
| Check | Status |
|---|---|
| all | read on the head commit before merging |

## Secrets, PHI and Claims Scan
Secrets: none. PHI or real data: none. Organisation claims: none.

## Strengths
- Backward compatible: without `generation`, `row_for` and `settings_for` return what they did, so the colab path and
  every existing caller and test are unchanged.
- A batch reads the submission from its own bundle (`work/<batch>/bundle/submission`), so `--collect` records what the
  kernel was given even if the agent folder has moved on since.
- The value it fixes was checked against the run itself: in `rich_3930` one call's prompt was 17,155 tokens and was
  served, which a 16,384 reservation in a 32,768-token window would refuse.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `submission_generation` resolves `!include` from the submission's root, as the competition's compiler resolves a
  skill's path; an include written relative to a sub-agent's folder would not be found. No submission here has one.
- A YAML tag other than `!include` in `agent.yaml` raises, which stops the tabulation with the error rather than
  record the fallback silently.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | |
| Synthetic only, no PHI | yes | no data |
| No organization claims; vendors cited | yes | |
| Test first | yes | both new tests failed before the change |
| Python and R in parity | n/a | |
| Simulated is labelled simulated | n/a | no numbers |
| Spec for big changes | yes | a fix with regression tests; issue 737 has its four parts |
| Commits | yes | imperative, body says why, trailer |
| Configuration | yes | no settings change |
| Rule 6 (who merges) | yes | starts no run, publishes nothing, deletes nothing |

## Test Coverage
`pytest -q tests/test_official_agent.py tests/test_agent_harness.py tests/test_colab_official.py tests/test_wording.py
tests/test_no_org_references.py`: 152 passed. Covered: the budget from an included file, inline, and absent; rows and
settings with and without `generation`; the difference listed with its source; an unchanged thinking budget not
listed. Exercised for real by tabulating the pull request 100 run with `--collect --reuse-output`.

## Verdict
Approve. Merge when every check is green on the latest commit.
