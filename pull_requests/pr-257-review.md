---
pr: 257
branch: fix/255-025-hf-token-check
title: "Say which Hugging Face secret was read and what is wrong with it"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-29
reviewer: read-only reviewer subagent + coordinator verification
verdict: approve
---

# PR Review: Say which Hugging Face secret was read and what is wrong with it

## Summary
Five *Publish datasets* runs to Hugging Face stopped at the token check without saying which secret they had read
or what was wrong with its value. The check now ignores the usual paste mistakes, names the secret the workflow
read (`HF_TOKEN_SOURCE`), and describes a bad value by its length and shape without printing it. The reviewer found
no critical or important defects and one minor gap: a whole `NAME=value` line wrapped in quotes wasn't cleaned. I
reproduced that gap with a failing test and fixed it on this branch. Approve.

## Scope of Change
- Files changed: 4 code and docs files, plus this review
- Areas touched: huggingface, ci (workflow), python tests, docs
- Commits: 2e8758a Say which Hugging Face secret was read and what is wrong with it; a follow-up that strips
  quotes around a whole `NAME=value` line; this review
- Range reviewed: `origin/main..fix/255-025-hf-token-check`

## CI Status
| Check | Status |
|---|---|
| python, PR conventions | pending when written; see the PR |

## Secrets, PHI and Claims Scan
- Secrets: clean. The tests use made-up `hf_abc` values. No error message contains any part of the token: the
  reviewer traced every `SystemExit` path.
- PHI / real data: clean.
- Organization claims: clean.

## Strengths
- A wrong value is described, never echoed. The likeliest mistake, pasting a secret's name, gets its own hint.
- Hugging Face only ever receives the cleaned token, in both the check step and `main()`. A test asserts this.
- No new setting: `HF_TOKEN_SOURCE` is derived from which secret exists.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `huggingface/publish.py` `clean_token`: `"HF_TOKEN=hf_abc"` (quotes around the whole line) stayed
  `HF_TOKEN=hf_abc`. Reproduced by adding it to `test_the_token_check_forgives_paste_mistakes`, which failed.
  **Fixed** on this branch: quotes are stripped before and after the `NAME=` prefix.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | no token characters in any message |
| Synthetic only, no PHI | Yes | |
| Test first | Yes | three tests failed before the change; the follow-up's test failed before its fix |
| Python and R in parity | n/a | |
| Configuration | Yes | no new setting; the PR says only the `dev` publish workflow changes |
| Secrets register | n/a | no credential made or rotated |
| Commits | Yes | imperative subjects, bodies say why, co-author trailer |
| Branch and issue | Yes | `fix/255-025-hf-token-check`, `Closes #255` |

## Test Coverage
New tests cover the paste mistakes (seven forms), the description of a wrong value (all capitals, plain wrong
value, `Bearer `) with no characters leaked, and the workflow's `HF_TOKEN_SOURCE` on both steps. Local run:
`cd python && python -m pytest -q tests`: 1050 passed, 15 skipped. `ruff check` on the changed files is clean.

## Verdict
Approve. After merge, rerun *Publish datasets* with platform `huggingface`: it either publishes, or says which
secret it read and what is wrong with it.
