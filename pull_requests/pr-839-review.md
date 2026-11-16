---
pr: 839
branch: docs/838-deck-claims-n-in-m
title: "000 DOCS23: the deck claims test finds \"N in M\" figures; register the pitch's \"1 in 3\", \"1 in 7\" and \"1 in 11\""
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-16
reviewer: independent read-only reviewer subagent (one pass, on the first two commits) + coordinator verification; the Superpowers plugin was not installed in this session
verdict: approve-with-nits
---

# PR Review: the deck claims test finds "N in M" figures

## Summary
`test_every_figure_on_a_slide_is_registered` never asked for figures written "1 in 7", so the pitch showed four of them
with no entry in `docs/claims.yaml`. This PR extends `FIGURE` to find them and registers all four from GlobalDentBench,
arXiv 2605.24636v2 (the latest version), re-read today. Every number and every quote matches the paper. The reviewer
found two slide sentences that claim more than the paper shows. Fixing them changes the published deck, so they are
#840, a separate PR that waits for the owner. It also found edge cases in the new pattern, fixed in the third commit.
Nothing blocks. Approve with nits. The PR changes only a test and the register, so it publishes nothing and the agent
may merge it once CI is green (AGENTS.md rule 6).

## Scope of Change
- Files changed: 2 (+38 / -3), no data files; this review file is the third
- Areas touched: python (one test file) / docs (the claims register)
- Commits:
  - `fbc38a1` Deck claims test: find figures written "N in M"
  - `85706a9` Register the pitch's "1 in 3", "1 in 7" and "1 in 11" (GlobalDentBench)
  - `2cfd8c3` Deck claims test: catch "1&nbsp;in&nbsp;7", leave "3-in-1" and "2.5 in 10" alone
- Range reviewed: `e93e50f..2cfd8c3`. The reviewer read `e93e50f..85706a9`; `2cfd8c3` answers its regex findings and
  was checked by the coordinator.

## CI Status
| Check | Status |
|---|---|
| All checks | not yet reported on `2cfd8c3` when this was written; the head commit must be green before merge (AGENTS.md rule 6) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. The diff adds a regex, a test and register text; no data files.
- **Organization claims:** clean. The only names are the paper's authors and the models and judge it names. The version
  and authors were checked against the PDF.

## Strengths
- The figures were re-derived from the paper itself, version named, with the paper's own words quoted:
  31.01% unsafe (S1 + S2) of 19,080 case-question answers, so 1 / 0.3101 = 3.2, shown as "1 in 3"; 14.15%, the mean S2
  rate in Systemic Health, Pharmacology and Safety (7.1); 8.93% in Anesthesia and Medical Emergencies (11.2).
- `covers` says what the source does not: the safety ratings are by the paper's AI judge, and section 2.6 reports
  dentists' agreement with that judge on grading answers and key points, not on the safety ratings. It also says 14.15%
  is one of 14 disciplines, not every answer that involves a medicine.
- An inconsistency in the paper is recorded: its discussion once expands AME as "Applied Medical and Basic Sciences";
  sections 2.1 and 2.5 say Anesthesia and Medical Emergencies.
- Test first: the pattern test fails on the old `FIGURE`, and the slide test fails on `main`'s register with exactly
  the four figures (`pitch/problem: ['1 in 3', '1 in 7']`, `pitch/harm: ['1 in 11', '1 in 7']`). The reviewer swapped
  the old pattern back in over every slide: only those four figures differ, so no prose on any slide in either deck is
  picked up. The EDR deck shows no "N in M" figure.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **The problem slide widens both figures** (`docs/pitch/slides/03-problem.html:9`). "Where medicines are involved,
   1 in 7 risked harm that cannot be undone" covers any answer involving a medicine, including anesthesia answers (8.93%).
   The paper gives 14.15% for one discipline, and the new entry's `covers` says so. "1 in 3 answers was rated unsafe"
   doesn't say they are answers to the case questions. Verified by reading the slide against section 2.5.
   **Fix:** #840, a separate PR, because it changes `docs/pitch/deck.html`, which publishes to the website and waits for
   the owner. This PR's register entries don't depend on it.
2. **The harm slide and its notes say "involving medicines and medical conditions"** (`docs/pitch/slides/04-harm.html:8`
   and line 20). This is the same widening, though milder: the notes name the category under "If asked for detail".
   **Fix:** in #840.

### 🔵 Nits / suggestions (Minor)
3. **Gaps in the new pattern** (`python/tests/test_deck_claims.py:24`). The reviewer confirmed each case by calling
   `figures()`: "1&nbsp;in&nbsp;7", "1 in  7" (two spaces) and a non-breaking hyphen were missed, "3-in-1 tool" came
   back as a figure, and "2.5 in 10" came back as "5 in 10". **Fixed in `2cfd8c3`**, and the cases were added to the
   pattern test. The coordinator first checked that writing whitespace as one space changes no figure on any slide
   today. One edge case is kept on purpose: "1 in 2000" without a comma is read as a year and missed ("1 in 2,000" is
   found). The comment above `FIGURE` says so.
4. **The problem slide's notes say "about one in twenty"** for 4.51%, which is 1 in 22. Speaker notes aren't scanned
   for figures. **Fix:** in #840 ("fewer than one in twenty").

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data |
| No organization claims; vendors cited | ✅ | only the cited paper's names |
| Test first | ✅ | pattern test and slide test both fail before the change |
| Python and R in parity | n/a | no labels, scoring or cost change |
| Simulated is labelled simulated | n/a | |
| Deck figures | ✅ | all four registered and re-derived (step 5); two wording findings go to #840 |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailer |
| Branch and issue | ✅ | `docs/838-...`, `Closes #838`, issue has Problem, Done when, Contract, Read first |

## Test Coverage
- `pytest -q tests/test_deck_claims.py`: 83 passed on `2cfd8c3`; 2 failed on `main`'s register as intended.
- Full suite (`cd python && python -m pytest -q tests`) on the first two commits: 2842 passed, 37 skipped. The third
  commit changes only this test file, and its tests pass.
- `ruff check python/tests/test_deck_claims.py`: clean.

## Verdict
Approve with nits. Merge once CI is green on the head commit. The slide wording (findings 1, 2 and 4) is #840.
