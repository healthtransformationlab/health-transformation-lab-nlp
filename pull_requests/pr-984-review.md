---
pr: 984
branch: docs/981-045-access-data-card
title: "045 DOCS1: AccessBench licence, data dictionary and validity check"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: claude-code (in-session checklist against .claude/review-rubric.md; local pytest; row-by-row diff of the rewritten JSONL)
verdict: approve
---

# PR Review: AccessBench licence, data dictionary and validity check

## Summary

Closes #981. Adds a CC BY 4.0 licence for AccessBench's questions, keys and control answers with a source-by-source
rationale; a data dictionary covering every field, kept complete by a test; a canary GUID on every row; and a page
answering what counts as the right answer, whether grading is consistent, and whether the data could be in training
sets. The gaps it names are filed (#982, #983) or already tracked (the owner review protocol, the veterans sources).
Approve.

## Scope of Change

Three new documents, a README paragraph, one constant, one field added to all 45 JSONL rows, and one test file.

## CI Status

Pending at review time; local `pytest -k "access or wording or no_org or bench_order or conventions"`: 309 passed.

## Secrets, PHI and Claims Scan

No secrets or personal data. The licence describes the Reddit-prompted questions as paraphrased with no post text or
username; the rows hold only the thread URL. Every figure on the validity page names its source: 30 of 75 points from
the external reviews page, 6 of 10, 12 of 15 and 8 of 15 from the judge-controls record, 30 of 30 time-sensitive
counted from the files, 40 sampled answers from the review protocol.

## Strengths

- The dictionary can't drift: a new field without a description fails CI.
- The JSONL rewrite was checked row by row: only `canary_text` was added, key order kept.
- The validity page says what is not done as plainly as what is.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- The licence's statement that the Reddit-prompted questions copy no post text rests on how they were written; a
  side-by-side check against the threads (not reachable from this session) would make it verified rather than stated.

## Repo-Rule Compliance

| Rule | Status |
|---|---|
| No secrets | ✅ |
| Synthetic only, no PHI | ✅ |
| Test first | ✅ the new tests failed before the change (12 failed) |
| Simulated is labelled simulated | ✅ no new result |
| Spec for big changes | ✅ documentation and one non-scoring field; issue has the four parts |
| Telemetry | ✅ no new function |
| Commits | ✅ |

## Test Coverage

Licence content, dictionary completeness per file, canary on every row and its GUID form, and the validity page's
three headings.

## Verdict

approve
