---
pr: 978
branch: fix/977-045-judge-harm-definition
title: "045 BUG2: grade AccessBench harm from what an answer says, with a reasoning judge"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: claude-code (in-session checklist against .claude/review-rubric.md; local pytest; control answers re-graded live on the dev workspace)
verdict: approve-with-nits
---

# PR Review: grade AccessBench harm from what an answer says, with a reasoning judge

## Summary

Closes #977. The v3 judge graded incomplete answers as harm, against its own definition (6 of 10 controls as
expected). The PR moves the harm rule to "what the answer says or recommends" (prompt v4, ADR 0015), makes the judge
quote the harmful words first, lets `OpenAIChat` read a reasoning model's list of content parts, gives the judge
8,000 tokens and 600 seconds, and adds five control answers for a third question as a check the prompt wasn't fitted.
The run record shows the current judge doesn't follow the rule on the new controls and the reasoning judge does
(12 of 15 against 8 of 15). Approve, with the nits below.

## Scope of Change

Judge prompt and parser (`access_keypoint_judge.py`), judge limits (`access_batch.py`), the client
(`llm_reader.py`), 5 control rows, ADR 0015 and the ADR index, a measured run record, a dated line in spec 045 US2,
two READMEs and two bundle-variable descriptions (no default changes). Tests in three files.

## CI Status

Pending at review time; local `pytest tests --ignore=tests/test_doctor_job.py` passed 3,262, with 14 collection
errors from the container's older `pipeline_doctor` (no `pipeline_doctor.billing`), which `main` shows here too.

## Secrets, PHI and Claims Scan

No secrets: the live checks used the proxy-injected workspace credential with a placeholder token, and nothing of it
is in the diff. The control answers are synthetic and say so (`is_simulated: true`). No organization is named. Every
number in the ADR and the record comes from the runs the record describes, labelled as single passes on 15 synthetic
answers.

## Strengths

- The rule change is backed by a held-out check, and the record reports that the cheaper fix (prompt only) failed it.
- `harm_span` makes a harm grade auditable the same way the point verdicts are.
- The client fix is general (any reasoning endpoint), with a local-server test.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

- `harm_span` is parsed but not yet written to `fact_access_answer`, so the MLflow view can't show it. Adding a gold
  column touches `gold_names.py`, `gold_model.py` and the contracts; worth a follow-up issue rather than this fix.

### 🔵 Nits / suggestions (Minor)

- The reasoning judge is a recommendation in the bundle variable's description and the ADR; the default stays
  `sim:judge`, so a live run still has to pass it. That matches how the judge was chosen before.
- 12 of 15 is one pass; the next live run's control rows will add a second reading at no extra design work.

## Repo-Rule Compliance

| Rule | Status |
|---|---|
| No secrets | ✅ |
| Synthetic only, no PHI | ✅ control answers synthetic |
| Test first | ✅ five new or changed tests failed before the change (5 failed, 72 passed) and pass after |
| Simulated is labelled simulated | ✅ measured runs labelled as such; nothing simulated presented as a result |
| Spec for big changes | ✅ metric change recorded in spec 045 US2 with a dated line, and ADR 0015 |
| Configuration | ✅ no new setting; two descriptions change; no environment's values change |
| Commits | ✅ imperative subject, body says why, trailer |
| Telemetry | ✅ no new public function |
| Python and R parity | n/a: no label, metric formula or reliability code changes |

## Test Coverage

The prompt's new rule and ordering, the `harm_span` parse (and its default for older verdicts), the judge's token and
time limits, and a reasoning model's content list are tested. The judge's behaviour itself is measured in the run
record, not unit-tested, which is right for a live model.

## Verdict

approve-with-nits
