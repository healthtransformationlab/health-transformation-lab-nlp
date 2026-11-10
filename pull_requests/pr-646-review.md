---
pr: 646
branch: docs/645-pitch-noharm-current-version
title: "000 DOCS16: cite NOHARM's current version on the pitch's harm slide"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-10
reviewer: independent read-only reviewer subagent (one pass, on the first commit) + coordinator verification; the Superpowers plugin was not installed in this session
verdict: approve-with-nits
---

# PR Review: cite NOHARM's current version on the pitch's harm slide

## Summary
Slide 4 of the pitch gave "about 3 in 4 harmful AI errors" as omissions, from a preprint cited without an identifier.
The PR reads all four versions of that preprint (arXiv 2512.01241), replaces the figure with the current version's
"more than 80% of severe errors", and registers it. The headline figure matches its source. The reviewer found one
statement in the first commit that did not: "v3 and v4 give no exact share", when a figure in the paper gives the
split. It also found the slide's sentence wider than the study, and the same mix-up left in slide 7's notes. All three
were checked against the paper and fixed in the second commit. What is left is for the owner to decide, and nothing
blocks. Approve with nits. The merge waits for the owner: it publishes the deck to the website.

## Scope of Change
- Files changed: 8 (+69 / -14), no data files; this review file is the ninth
- Areas touched: docs (two slides, the two generated deck files, the pitch README, references, the claims register) /
  python (one test)
- Commits:
  - `8cd0055` Cite NOHARM's current version on the pitch's harm slide
  - `46eb7c6` Give the paper's own split, scope the slide's sentence, fix slide 7's notes
- Range reviewed: `167daa2..46eb7c6` (the reviewer read `167daa2..8cd0055`; `46eb7c6` answers its findings and was
  checked by the coordinator)

## CI Status
| Check | Status |
|---|---|
| `check` (branch name and issue link) | pass on `46eb7c6` |
| `changes`, `bundle`, `azure-infra` | pass on `46eb7c6` |
| `r-parity` | skipped (no R-relevant change) |
| `python`, `postgres`, `python-databricks-runtime` | running on `46eb7c6` when this was written; the reviewer read all three as passed on `8cd0055` |
| Later commits | CI runs again when this file is pushed; the head commit must be green before merge (AGENTS.md rule 6) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. No data file is in the diff; the only names are the paper's authors.
- **Organization claims:** nothing added. "Stanford-led ARISE network" was already on the slide and could not be
  checked from this session (finding 5).

## Strengths
- Every version of the source was read, not only the current one, so the PR can say where the old figure came from and
  what it counted: 76.6% of severely harmful errors in v1 and v2, where omissions were 50.2% of all harmful errors.
- The source texts were kept and the reviewer re-fetched the arXiv record and the v4 PDF: identical to the copies used.
- The notes give the earlier figure with what it counts, so a listener who saw the old deck can be answered.
- The new test fails on `main`, and the slide now shows a figure the register test recognises.

## Findings
### 🔴 Blocking (Critical)
1. **"v3 and v4 give no exact share" did not match the paper** (`docs/claims.yaml` `pitch.harm` source,
   `docs/references.md` item 89, the first commit's message, issue #645). The text has no pooled number, but
   Extended Data Fig. 3b of v4 (PDF page 36) gives the split by quarter of systems, best performers to weakest:
   omission only in 77%, 80%, 82% and 87% of cases with a severe error; both an omission and a commission in 13%,
   13%, 8% and 7%; commission only in 11%, 7%, 9% and 6%. The figures are images, so the text extract of the PDF that
   the author searched does not show them. Verified by the coordinator on a rendering of the page. The figure on the
   slide was not affected: the abstract's "more than 80%" is what the slide shows. **Fixed in `46eb7c6`:** the
   register, the references entry and the notes give the split; the PR description and the issue are corrected and
   say so. The first commit's message still carries the statement; history was not rewritten.

### 🟡 Should fix (Important, non-blocking)
2. **The slide's sentence claimed more than the entry's `covers`** (`docs/pitch/slides/04-harm.html`). "The pattern
   in medicine: more than 80% of AI's severe errors were things it left out" read as a claim about AI in medicine.
   The source is one benchmark of doctors' questions to specialists, and the paper says its findings "may not
   generalize to inpatient hospitalizations or straightforward primary care visits". **Fixed in `46eb7c6`:** "in a
   study of 24 AI systems, more than 80% of the errors that could cause severe harm were things the AI left out, not
   wrong advice it gave". The label "The pattern in medicine" is the owner's framing and is kept; `covers` now names
   the case set.
3. **Slide 7's notes carried the claim this PR corrects** (`docs/pitch/slides/07-ask.html`): "they have found that
   most harmful errors are things AI leaves out". **Fixed in `46eb7c6`:** "most of the severe errors".
4. **Left for the owner, same sentence of slide 7's notes:** "their cases come from primary care and emergency
   rooms". NOHARM's own cases are "outpatient electronic consultations, generally reflecting low acuity". Its other
   mentions of emergency care are example actions, the fields of the physicians in its randomized study (21 of 101
   in emergency medicine), an affiliation and a citation of another group's benchmark. Whether the network has
   emergency-room cases elsewhere was not checked, and the sentence carries the argument for the partnership, so it
   is not reworded here.

### 🔵 Nits / suggestions (Minor)
5. **"Stanford-led ARISE network"** (both slides) is not something the paper says: it thanks "the ARISE network" and
   hosts its leaderboard on the network's site; its first author is at Harvard and its senior authors at Stanford and
   Harvard. The network's own pages are outside this session's allowed hosts. Unchanged; to check against the
   network's own description.
6. **"It tested 20 large language models and 4 clinical AI tools"** (slide 4's notes): the paper ran 45 LLMs and its
   "primary analyses focused on 20 recent notable LLMs and all 4 clinical RAG systems". **Fixed in `46eb7c6`:** "Its
   main analysis covers".
7. **The pitch README linked the unversioned arXiv page while naming version 4.** **Fixed in `46eb7c6`.**
8. **"No oral health cases"** holds at the level of the 10 specialties (none is dentistry) and no dental term is in
   the text; the cases themselves are not in the PDF. The references entry now says "none is dentistry"; the notes
   keep the deck's phrase.
9. **The new test pinned one sentence**, so any rewording broke it, and its lookups failed without a message.
   **Fixed in `46eb7c6`:** it checks the claim's version and that every sentence on the harm slide that gives the
   share of errors says severe, and names what is missing.
10. **Outside the issue:** "1 in 7" and "1 in 11" on this slide, and "1 in 3" and "1 in 7" on the problem slide, are
    cited figures the register test does not see, as "3 in 4" was not. They are not in `docs/claims.yaml` and were
    not re-checked. A follow-up was suggested to the owner.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data files changed |
| No organization claims; vendors cited | ✅ | nothing added; finding 5 is on text already there |
| Test first | ✅ | the new test fails on `main` (no `harm` entry in the register); test and fix share a commit, so the order they were written in can't be read from history |
| Python and R in parity | n/a | |
| Simulated is labelled simulated | n/a | a cited figure, labelled a preprint on the slide |
| Seeds fixed, paths, spec, prices | n/a | docs and one test |
| Deck figures | ✅ | "80%" is in `docs/claims.yaml` with its source and `checked: 2026-11-10`; re-derived from the v4 abstract and Extended Data Fig. 3b by the reviewer and the coordinator; the sentence read against `covers` (finding 2) |
| Wording ("diagnose") and benchmark order | ✅ | `test_wording.py`, `test_bench_order.py` pass |
| Generated files not edited by hand | ✅ | `python docs/build_decks.py` leaves the tree unchanged |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Docs | ✅ | `docs/references.md` and the pitch README updated |
| Configuration, secrets register, idempotent writes, alerts | n/a | |

## Test Coverage
- New `test_the_pitch_cites_noharm_by_version_and_for_severe_errors`: the register entry names arXiv 2512.01241v4 and
  quotes the abstract; every sentence on the harm slide that gives the share of errors says severe; the old wording
  ("3 in 4", "most harmful errors", "1,100 real medical cases") is gone from every pitch slide and its notes.
- Not covered by a test: that the figure is true (the register's `checked` date records the reading), and "1 in N"
  figures (finding 10).
- Run locally: `python -m pytest -q tests` on `8cd0055`, 2,235 passed, 35 skipped, and 2 failed in
  `tests/test_digests.py` for a missing package (`databricks-sdk`, which CI installs); with it installed, that file
  passes (16). On `46eb7c6`, `test_deck_claims.py`, `test_decks.py`, `test_wording.py`, `test_no_org_references.py`,
  `test_bench_order.py` and `test_copy_decks_to_site.py`: 155 passed. `ruff check` on the changed test file: clean.
- The slide was rendered at 1920 × 1080 with the deck's fonts: the sentence takes two lines and is clear of the footer.

## Verdict
Approve with nits. Nothing must change before merge. Findings 4, 5 and 10 are the owner's to decide or to follow up.
The head commit needs green CI first, and the merge waits for the owner either way: it changes `docs/pitch/deck.html`
on `main`, which copies the deck to the website (AGENTS.md rule 6).
