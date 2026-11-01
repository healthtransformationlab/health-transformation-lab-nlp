---
pr: 427
branch: feat/202-024-periodx-notes
title: "024 US2: PerioDx Extractor: status, stage and grade from notes by keyword, as Patel et al. 2022"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent available in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 024 US2: PerioDx Extractor from notes (Patel et al. 2022)

## Summary
This adds `periodx.note_status`, the paper's two-step keyword program. It keeps a note only if it names a
diagnosis term, then reads extent, stage and grade by stemming and `difflib` similarity. The output is the most
specific status the words support, or `no_diagnosis`.

Negation is off by default, as published, with a switch to turn it on. Every term in the word list names its
source, and none comes from real notes. The PR builds on #423 and changes no dataset or output.

Verdict: approve with nits.

## Scope of Change
- Files changed: 4 (+~250 / -5), excluding the US1 commits this branch carries
- Areas touched: python, docs, specs
- Commits:
  - 1dd2181 Add failing tests for the PerioDx Extractor (Patel et al. 2022)
  - 0da23dc Read status, stage, extent and grade from notes by keyword as Patel et al. 2022
- Range reviewed: `92bcd07 (head of #423)..0da23dc`

## CI Status
| Check | Status |
|---|---|
| python | pending at review time; local run green |
| r-parity | not affected (no R or scored output changes) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. Every snippet is synthetic and written in the note templates' forms.
- **Organization claims:** clean. The paper is cited for its method only.

## Strengths
- The two steps follow the paper. The one substitution (difflib for gensim word vectors) is named in the module,
  the doc and the PR.
- The published error modes are measurable. Acceptance 2 shows missed negation reading "no evidence of bone loss"
  as periodontitis with negation off, and gingivitis with it on.
- "Perio" alone is only a stage cue, so the common "perio charting done" and "perio consult" don't turn every note
  into periodontitis. A test checks this.
- The per-word helpers are cached and untraced. Public `stem` / `similar` stay `@traced`, so the 4,343-visit build
  in US3 isn't slowed by millions of spans.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- **"bone loss" in findings.** `PERIODX_TERMS` includes "bone loss" as periodontitis evidence, so notes whose
  findings say "mild horizontal bone loss" read as unstaged periodontitis.
  - Verified: on the 240 review notes, about a fifth have no scorable status, mostly for this reason.
  - This is the published behaviour the spec asks to measure, and unstaged periodontitis has no label, so US3 falls
    through to the chart. Keep it, and say so beside the US3 results.
- **Extent is bag-of-words.** "Localized ... with Generalized Recession" reads as generalized, because the most
  severe extent wins.
  - Verified with the `extent_then_trap` pattern form.
  - This is consistent with a keyword method and with the paper's stated limits. A note in the doc would help.
- **No R twin.** That is by design (plan item 6: the Extractor's parity is on its outputs, checked in US3).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims | ✅ | |
| Test first | ✅ | tests committed before the code (1dd2181) |
| Python and R in parity | ✅ (n/a) | NLP output parity is in US3 per the plan |
| Seeds fixed | n/a | deterministic, no sampling |
| Paths | n/a | |
| Spec for big changes | ✅ | T004–T006 ticked |
| Words rule / @traced | ✅ | `note_status`, not `extract` or `diagnose`; telemetry test passes |
| No new dependency | ✅ | stdlib `difflib`, `re` |
| Commits | ✅ | |

## Test Coverage
- `tests/test_periodx_notes.py` (32 tests): the three acceptance scenarios, 2017 and short forms, typos, severity
  terms, health and gingivitis, copy-forward, two stages, the negation window, and the term sources.
- Run locally: full suite 1379 passed, 15 skipped; `ruff check` clean.

## Verdict
Approve with nits. Merge after #423.
