---
pr: 902
branch: feat/901-019-access-keypoint-judge
title: "019 CHORE1: map AccessBench items to grader key-point judge"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator (rubric scan + local pytest)
verdict: approve
---

# PR Review: 019 CHORE1 map AccessBench items to grader key-point judge

## Summary
Adds `access_keypoint_judge`: maps Access JSONL rubrics to lab-grader question rows and a key-point
LLM judge payload (`judge_messages` / `ai_query_prompt`) with parse/score helpers. Chart phenotyping
stays in `judge.py`. Approve — no blocking findings; merge when CI is green.

## Scope of Change
- Files changed: 4 (+301 README/module/tests + this review)
- Areas touched: python, benchmarks docs, pull_requests
- Commits: mapper + tests + AccessBench README note
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| check / python / python-databricks-runtime | pending at review write; re-check before merge |

## Secrets, PHI and Claims Scan
- Secrets: clean
- PHI / real data: clean (no new fixtures; reuses synthetic Access items)
- Organization claims: clean

## Strengths
- Reuses grader `KEY_POINTS = 5` and dim column names
- Separates Access Q&A judging from perio chart `judge.py`
- Prompt version tagged (`access-keypoints-v1`); score = covered / n

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- Commit lacks a Co-authored-by trailer (AGENTS.md agent commits).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Synthetic only | yes | Maps existing simulated fixtures |
| Test first | yes | `test_access_keypoint_judge.py` failed on missing module first |
| Spec for big changes | n/a | Chore mapper under 019 grader shape; no new metric definition |
| Wording | yes | Access pathway language; no diagnose claims |

## Test Coverage
Local: `pytest tests/test_access_keypoint_judge.py` (8 passed) plus wording / org / bench-order /
telemetry `@traced`; ruff clean on new files.

## Verdict
**approve** — merge when CI is green on the latest commit.
