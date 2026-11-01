---
pr: 260
branch: docs/259-problem-statement-real-world
title: "Say benchmarks test exam knowledge and cite real-world failures; drop \"harness\" and \"working name\""
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: Say benchmarks test exam knowledge and cite real-world failures; drop "harness" and "working name"

## Summary
The PR does three things:
- Replaces the problem statement "no test checks whether AI connects the mouth to the rest of the body" with
  "most benchmarks test exam knowledge, and studies of real patient cases have found AI falling short". It cites
  three studies, added to `docs/references.md` as 54–56.
- Replaces the jargon "harness" and "runners".
- Removes the last "working name", with a test that keeps it out.

The first review asked for changes. Pitch slide 4 still made the dropped claim ("no test checks whether it
connects the two"), and some wording claimed more than the studies show. Both are fixed on this branch. The
figures match their abstracts. Approve with nits.

## Scope of Change
- Files changed: 15, excluding the generated `deck.html` and `full_text_and_notes.md`.
- Areas touched: docs, decks, the Hugging Face card, a spec disclaimer, and one new test.
- Range reviewed: `origin/main...HEAD` (net diff).

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI: clean.
- Organization claims: clean. The three studies are cited with DOIs, and each figure was checked against its
  PubMed or PMC abstract.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important): fixed
- **Slide 4 kept the dropped claim** (`docs/pitch/slides/04-mdi.html`).
  - The subtitle "The tests treat it as separate" and the line "no test checks whether it connects the two",
    plus its speaker-note twin, now say that studies of real patient cases have found AI falling short on
    questions like drug interactions.
  - This also ends the contradiction with backup slide 12, where GlobalDentBench has a systemic-health category.

### 🔵 Nits / suggestions (Minor)
- **"Today's tests measure exam knowledge" is now "most benchmarks test exam knowledge": fixed.** The old wording
  contradicted GlobalDentBench's case questions in the next sentence. It changed in the README, the pitch README
  and the cover slide.
- **Wording that claimed more than the sources: fixed.**
  - "Studies of real-world use … find" is now "studies of real patient cases have found". Hager used
    retrospective hospital cases, and Al-Ashwal compared chatbots against reference tools; neither observed
    real-world use.
  - Bean's control group used "a source of their choice", not "their usual sources".
  - `docs/references.md` already notes that Al-Ashwal tested 2023-era chatbots.
- **The pitch's "Sources cited in the deck" missed the three studies: fixed.**
- **"Called the Health Transformation Lab for now" survived on the cover notes: fixed.** The test now catches
  "Health Transformation Lab for now" too.
- **The test reads one line at a time: stays as is.** A phrase split across a line wrap would slip through. The
  prose here is wrapped by hand, the phrase is two or three words, and matching across lines would add code for
  little gain.

## Deck figures (rubric step 5)
- No figures were added to any slide's visible text; the studies are named in the speaker notes.
- `test_deck_claims.py` passes, and so does the absolute-wording check.

## Test Coverage
- `cd python && python -m pytest -q tests`: 1051 passed, 15 skipped.
- The new `test_no_working_name.py` fails on `main` (`specs/019-grader-dashboards/spec.md:16`) and passes here.
- `ruff check` on the new test: clean.
- `python docs/build_decks.py`: the decks match their slides.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims; vendors cited | ✅ | Studies cited with DOIs |
| Test first | ✅ | `test_no_working_name.py` fails before, passes after |
| Python and R in parity | n/a | Wording only |
| Simulated is labelled simulated | n/a | |
| Words rule (`test_wording.py`) | ✅ | "Diagnostic" only paraphrases Hager's guideline finding |
| Deck figures | ✅ | No new slide figures |
| Commits | ✅ | `Closes #259`, co-author trailer |
| Docs | ✅ | |
| Configuration, secrets register, idempotent writes, alerts | n/a | |

## Verdict
Approve with nits. Merge once CI is green on the head.

The website is a separate repo, `healthtransformationlab.github.io`. Its landing page gets the same wording in its
own PR, and its deck copies should be refreshed from this branch after the merge.

## Second round (owner feedback, 2026-10-29)
The owner asked for three more changes. Each was checked against the files before it was made.
- **"Diagnosis" needs a doctor, so it comes out where it describes what the record or AI does.**
  - EDR slide 2 now says "rarely say plainly whether a patient has gum disease".
  - The Hager paraphrase becomes "didn't follow the clinical guidelines doctors use".
  - The agent is built "not to replace a dentist or doctor"; MedGemma supports "research and tools, not clinical
    decisions".
  - "Diagnosis codes" stays, as the name of a field in the record (what a dentist recorded), which `AGENTS.md`
    allows.
- **"Phenotype" comes off the slides.** EDR slides 3 and 8 now say "how well records identify a disease" and "the
  rules". The scientific-details page keeps the term for researchers.
- **Absolute data claims were inaccurate.**
  - "Synthetic data only" and "no real patient data" overstated it. The de-identification tools are also scored
    on clinical text that others published already de-identified: MACCROBAT, committed under its CC BY licence,
    and John Snow Labs' 48-note set, kept outside the repo.
  - The disclaimer, both READMEs, the EDR cover tag and footer, and slides 4 and 10 now say the patient records are
    synthetic and no identifiable patient data (PHI) is used.
- **The cover images still showed "working name" and the old problem line.** Both
  `docs/img/{edr,pitch}_deck_cover.png` are re-rendered from slide 1 of the built decks at 960×540, in Chromium.

Tests: 1051 passed, 15 skipped.
