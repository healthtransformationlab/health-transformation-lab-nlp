---
pr: 841
branch: docs/840-pitch-globaldentbench-scope
title: "000 DOCS24: the pitch says which answers GlobalDentBench's \"1 in 3\" and \"1 in 7\" count"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-16
reviewer: independent read-only reviewer subagent (one pass, on the first two commits) + coordinator verification; the Superpowers plugin was not installed in this session
verdict: approve-with-nits
---

# PR Review: the pitch says which answers GlobalDentBench's "1 in 3" and "1 in 7" count

## Summary
The pitch's problem and harm slides gave GlobalDentBench's 14.15% as the rate for answers "where medicines are
involved". The paper gives it for one discipline, Systemic Health, Pharmacology and Safety. The problem slide also gave
the 31.01% unsafe rate as "1 in 3 answers", when it counts only answers to the case questions. This PR scopes both
sentences and their speaker notes, fixes the notes' "about one in twenty" for 4.51% (that is 1 in 22), and makes the
harm slide's headline say which harm it ranks by. Every figure was re-derived from arXiv 2605.24636v2 and matches. The
reviewer found nothing blocking, and all three of its minor points are fixed: two in the third commit, and the headline
on the owner's go-ahead. Approve with nits. **The merge waits for the owner:** it
changes `docs/pitch/deck.html`, which publishes to the website (AGENTS.md rule 6).

## Scope of Change
- Files changed: 5 (+46 / -16), no data files; this review file is the sixth
- Areas touched: docs (two slides, the two generated pitch files) / python (one test)
- Commits:
  - `dd82add` Test that the pitch scopes GlobalDentBench's 1 in 7 and 1 in 3
  - `498eccb` Pitch: say which answers GlobalDentBench's 1 in 3 and 1 in 7 count
  - `50cf2d4` Pitch notes: say the AI judge rated the answers, and which answers count
  - `19f4e9c` Merge `main` (#839, which adds the register entries these sentences are checked against)
  - `bd6f3dd` Review record for PR 841
  - `e8aa064` Test that the harm slide's headline says which harm it ranks by
  - `43ca9f7` Harm slide: "Where AI most often risked permanent harm"
- Range reviewed: `e93e50f..43ca9f7`. The reviewer read `e93e50f..498eccb`; `50cf2d4` answers its
  findings, and `e8aa064` and `43ca9f7` its headline point; the coordinator checked both. The merge was clean: #839 and this PR edit different parts of
  `test_deck_claims.py`.

## CI Status
| Check | Status |
|---|---|
| All checks | not yet reported on the head commit when this was written; it must be green before merge |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. No data files or notes.
- **Organization claims:** clean. The only names are GlobalDentBench and the model makers it lists, as before; nothing
  is added about any organization.

## Strengths
- Each changed sentence was checked against section 2.5 of the paper: 31.01% gives "1 in 3"; 4.51% gives "fewer than
  one in twenty"; 14.15% for Systemic Health, Pharmacology and Safety gives "one in seven"; 8.93% for Anesthesia and
  Medical Emergencies gives "1 in 11". The reviewer noted that the mean across models equals the pooled rate here,
  because every model answered all 1,590 case questions (19,080 = 12 × 1,590).
- The harm slide's two cards now read alike: "answers on medicines and medical conditions" and "answers on anesthesia
  and medical emergencies".
- The generated files differ from `main` only by the slide edits: `python docs/build_decks.py` on the branch leaves
  nothing to commit. The EDR deck is unchanged.
- At 1920×1080 the problem slide's longer card text and the harm slide's two-line headline still fit (rendered with
  Playwright; nothing overflows either slide).

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **The test passed with the notes' new figures deleted** (`python/tests/test_deck_claims.py`). The slide's own
   "1 in 7" satisfied `assert sentences`, and "14.15" and "fewer than one in twenty" were never checked. The reviewer
   deleted them from a scratch copy and the test still passed. **Fixed in `50cf2d4`:** the slide and the notes are now
   checked apart. Against the slides of `main` the test fails (`pitch/problem slide: 'medicines are involved'`), and
   against those of `498eccb` too (`pitch/problem notes: 'rated unsafe by the study's AI judge'`).
2. **The notes said "31 percent of case answers were unsafe"** with no rater (`docs/pitch/slides/03-problem.html:15`).
   The paper's AI judge assigned the safety ratings. Section 2.6 checks that judge against dentists on grading answers
   and key points, not on the safety ratings, and #839's `covers` says so. **Fixed in `50cf2d4`:** "were rated unsafe
   by the study's AI judge".
3. **The harm slide doesn't say its rates are of case answers, and its headline says "medicines and emergencies"**
   (`docs/pitch/slides/04-harm.html:4`, `:8`, `:20`). **Fixed in part in `50cf2d4`:** the notes' "If asked for detail"
   now says "of the answers to case questions". The headline "Where AI is most dangerous: medicines and emergencies"
   ranks the disciplines by their rate of irreversible harm (S2), which is how the paper ranks them ("most
   concentrated"), but doesn't say so: by overall unsafe rate, Orthodontics is highest (44.30%). It also left out
   medical conditions. **Fixed in `43ca9f7`, on the owner's go-ahead:** "Where AI most often risked permanent harm:
   medicines, medical conditions and emergencies", and the notes "most often risked permanent harm in two areas".
   `e8aa064` adds the check first; it fails on the old headline.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data |
| No organization claims; vendors cited | ✅ | nothing new |
| Test first | ✅ | `dd82add` adds the test before the slides change; it fails on `main` |
| Deck figures | ✅ | every changed figure re-derived from v2 (step 5); register entries are in #839 |
| Generated files | ✅ | rebuilt with `docs/build_decks.py`, not edited by hand |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailer |
| Branch and issue | ✅ | `docs/840-...`, `Closes #840`, issue has the four parts and a dated line for the added notes fix |
| Merge rule | ⏸ | publishes to the website: waits for the owner |

## Test Coverage
- `pytest -q tests/test_deck_claims.py tests/test_decks.py tests/test_wording.py tests/test_copy_decks_to_site.py`:
  141 passed on `50cf2d4`, 142 on `43ca9f7`; `tests/test_deck_claims.py tests/test_decks.py` 99 passed after merging `main`, so the
  register entries from #839 and these slides agree.
- Full suite (`cd python && python -m pytest -q tests`) on `498eccb`: 2842 passed, 37 skipped. The third commit
  and later commits change only the two slides, the generated files and this test.
- `ruff check python/tests/test_deck_claims.py`: clean.

## Verdict
Approve with nits. It waits for the owner's "merge", because it publishes the pitch deck to the website.
