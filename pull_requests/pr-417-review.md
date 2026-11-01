---
pr: 417
branch: fix/134-004-medgemma-fallbacks
title: "004 AI4: why MedGemma answers fell back; quote gate ignores capitals"
author: claude (agent session)
reviewed_at: 2026-11-01
reviewer: coordinator self-review against .claude/review-rubric.md (no separate reviewer subagent was available in this session)
verdict: approve-with-nits
---

# PR Review: 004 AI4: why MedGemma answers fell back; quote gate ignores capitals

## Summary
Closes #134. Every fallback row in the two committed MedGemma runs (14 in 4B v1, 5 in 1.5, 240
synthetic review notes each) was read against its note. Three of the 4B v1 fallbacks were quotes that
matched the note word for word except for capitals, which is a gate bug; `llm_reader.quote_in_note` now
ignores capitals and runs of whitespace, with regression tests written first. The other 16 are the model
changing words (shortening or respelling "Localized", correcting a note's misspelling, stitching
quotes) or putting diagnosis text in `status`, which the gate is right to reject. `docs/medgemma.md`
records the cause table and the effect of re-parsing the committed raw outputs, without a re-run.
Works as described; approve with nits.

## Scope of Change
- Files changed: 4 (about +110 / -3, no generated data)
- Areas touched: python, docs, pull_requests
- Commits: b8607e7 Let the reader's quote gate ignore capitals and whitespace; plus this review and a one-line doc fix
- Range reviewed: `origin/main..fix/134-004-medgemma-fallbacks`

## CI Status
| Check | Status |
|---|---|
| check (PR conventions) | success |
| python | in progress at review time; the same suite passed locally (1245 passed, 16 skipped) |
| changes | in progress at review time |

## Secrets, PHI and Claims Scan
- Secrets: clean (diff grep for token/secret/password/key patterns finds only prose about the token limit).
- PHI / real data: clean. The test note is invented; the doc names synthetic visit ids only and quotes
  no note text beyond generic terms ("Localized", "generlized").
- Organization claims: clean. Results are labelled synthetic notes, not evidence about real records.

## Strengths
- Root cause found per row from the committed `raw` column, not inferred from the error string.
- The fix is narrow: capitals and whitespace only; tests pin that respelled, shortened, punctuation-dropped
  and number-changed quotes still fail.
- Honest about the effect: accepting the three answers lowers 4B v1 accuracy slightly (0.779 to 0.775),
  and the doc says so.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- `docs/medgemma.md:31` said the reader uses the "same quote gate as the judge", no longer true after
  this change. Verified by reading the line against `judge.py` (`gate`, `gate_status`, `gate_components`
  still use exact `in`). **Fixed in this PR.**

### 🔵 Nits / suggestions (Minor)
- The judge's gates (`python/health_transformation_lab_nlp/judge.py`) still match exactly, so reader and
  judge now differ. Left as is on purpose (changing them would shift committed judge numbers without a
  re-run); a follow-up issue could decide whether they should share `quote_in_note`.
- The committed `llm_details_*` and `ai_predictions_*` files reflect the gate as it ran; a re-run (or a
  re-parse script) would be needed to bring the 4B v1 numbers in the README/results to 95.4% gate pass.
- Arguably a gate-rule change for spec 004; treated as a small bug fix with a regression test, which
  AGENTS.md allows without a new spec.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | scan clean |
| Synthetic only, no PHI | Yes | invented test note; synthetic visit ids |
| No organization claims | Yes | |
| Test first | Yes | 3 accept cases failed before the fix, pass after |
| Python and R in parity | N/A | the gate has no R twin (labels, scoring, reliability, CE unchanged) |
| Simulated labelled | Yes | re-parse numbers stated as re-parse of committed output, not a new run |
| Seeds / paths | N/A | |
| Spec for big changes | Yes | small fix under spec 004 |
| Telemetry | Yes | `quote_in_note` is `@traced`; telemetry tests pass |
| Commits | Yes | imperative subject, body says why, co-author trailer |
| Docs | Yes | medgemma.md updated |
| Words rule | Yes | `test_wording.py` passes |

## Test Coverage
New: `test_gate_accepts_case_and_whitespace_differences` (3 cases), `test_gate_still_rejects_changed_words`
(4 cases). Run locally: `python -m pytest -q tests` 1245 passed, 16 skipped; `ruff check` on changed files
clean. Not run: MedGemma (no GPU).

## Verdict
approve-with-nits. Nothing blocking; the one should-fix was fixed in this PR.
