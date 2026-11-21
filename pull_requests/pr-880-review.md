---
pr: 880
branch: docs/879-edr-cost-quality
title: "000 DOCS26: the PerioBench deck shows each question's cost beside its quality and pass bar"
author: jcbowyer
reviewed_at: 2026-11-17
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 000 DOCS26: the PerioBench deck shows each question's cost beside its quality and pass bar

## Summary

The PR replaces the PerioBench deck's single cost slide with one slide per question: finding gum disease, tooth
loss and de-identification. Each method's synthetic score and its 95% interval sit beside its cost for a million
notes, and each slide states that question's pass bar. The main deck shrinks to 7 slides, and the details move
to an appendix. The slides say plainly that nothing has passed: the specialist acceptance test has not been run,
and tooth loss and de-identification have no bar set. A review subagent re-derived every figure from its source
file and found none that disagrees. It raised two Important wording findings: a wrong count in the speaker notes,
and a de-identification safeguard described more broadly than its source allows. The coordinator verified both,
and both are fixed in 01463f9. The verdict is approve-with-nits. The PR is outward (the deck goes to the website),
so it waits for the owner's "merge". It is stacked on #870, which merges first.

## Scope of Change

- Files changed: 23 (+651 / -51, excluding the generated `deck.html` and `full_text_and_notes.md`, and the
  `main` merge)
- Areas touched: docs (deck slides, `docs/claims.yaml`), python (one test)
- Commits:
  - d5d1c56 000 DOCS26: PerioBench deck puts each question's cost beside its quality and pass bar
  - 7bd1343 Merge remote-tracking branch 'origin/main' into docs/879-edr-cost-quality
  - 01463f9 Scope the deck's de-identification check and top-group claims to what the sources show
- Range reviewed: `origin/feat/868-042-three-tests..HEAD` (base is #870's branch)

## CI Status

| Check | Status |
|---|---|
| python | running at review time (local: full suite green, see Test Coverage) |
| python-databricks-runtime | running at review time |
| changes | running at review time |
| check (PR conventions) | running at review time |

## Secrets, PHI and Claims Scan

- **Secrets:** clean. The only hits were the word "tokens" in pricing prose.
- **PHI / real data:** clean. Every figure is from synthetic records or is a list price.
- **Organization claims:** clean. The ask keeps its line that no partner has been contacted and that nothing here
  is any organization's plan. Vendor prices name their source and date.

## Strengths

- The owner's question gets a direct answer on every row: a score with its interval beside a cost, and "not run"
  where a model has no score on that question, instead of an implied equivalence.
- The slides are honest about the missing pass bars. The ask turns that gap into concrete work: set the bars
  before a real record is read.
- The tooth-loss slide shows the weak case (0.59–0.70 AUC on teeth missing at the first visit) beside the strong
  one.
- Every new figure is in `docs/claims.yaml` with its kind and source. The new test ties the quality figures on
  the cost slides to `docs/results.md` and `docs/tooth_loss.md`.
- It also registers #870's three-tests slide figures, which were failing `test_deck_claims.py` on that branch.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking): both fixed in 01463f9

1. **`docs/edr/slides/04-phenotyping-cost.html`, the aside said "Two can" rank first. It is three.**
   - Verified: `docs/results.md:28` gives `bioclinical-modernbert-large+rules4` the rank 1–9.
   - Fixed: the note now says three, names the third method (90.1, same size and cost), and keeps the table
     to two.
2. **`06-deid-cost.html` and `09-passes.html` described the final check as what protects patients.**
   - The problem: `docs/code_walkthrough.md:75-80` says the check works only because every planted identifier
     is known. On real notes only the residual scan and the human sample remain. On a deck whose ask is "from
     synthetic to real", the old wording claimed more than the source shows.
   - Verified by reading those lines.
   - Fixed: the slide, its notes and the appendix card now scope the check to synthetic notes and name what
     remains on real ones.

### 🔵 Nits / suggestions (Minor)

1. **De-identification headline** (fixed): "leaks fewest" became "in the top group". The rank 1–3 overlaps
   rank 1–4 for two other methods, and "paid services" became "Azure and Amazon", since AI mask is a paid
   service that was run.
2. **Phenotyping headline and notes** (fixed): "scored lower" became "are not in it" (the top group), because the
   point estimates' intervals overlap.
3. **Costing headline** (fixed): it now separates dated list prices from illustrative hardware prices.
4. **MedGemma versions** (open): the main cost slide uses MedGemma 1.5 4B (78.5), to match the cost row. The
   appendix results slide uses MedGemma 4B (79.8). Both are labelled correctly; no change.
5. **Test depth** (open): the new test checks that each score string appears in the results file, not that it
   sits on the matching method's row. It doesn't check the "Could rank first?" column, dental words removed, or
   the first-visit AUCs. Those were checked by hand in this review. A follow-up could parse rows by method.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | every score labelled synthetic |
| No organization claims; vendors cited | ✅ | prices cite their source and date |
| Test first | ✅ | the new test fails on the old deck (the `economics` slide is present and the new ids are missing) |
| Python and R in parity | n/a | no label, scoring, reliability or cost-effectiveness code changed |
| Simulated is labelled simulated | ✅ | the simulated reviewers are named as a dry run and shown as no result |
| Seeds fixed / Paths | n/a | |
| Spec for big changes | n/a | a deck change; no dataset, metric or label rule changed |
| Prices | ✅ | list prices dated; GPU and CPU hour prices marked illustrative |
| Deck figures | ✅ | every figure re-derived from its source by the review subagent; `test_deck_claims.py` passes |
| Wording ("we find, we don't diagnose") | ✅ | `test_wording.py` passes |
| Benchmark order | ✅ | `test_bench_order.py` passes |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailer |
| Merge | ⏸ | outward (website) and stacked on #870: waits for #870 and the owner's "merge" |

## Test Coverage

- `cd python && pytest -q tests`: 3043 passed, 37 skipped (at d5d1c56).
- After the fixes: `test_decks.py`, `test_deck_claims.py`, `test_wording.py`, `test_no_org_references.py` and
  `test_bench_order.py` gave 149 passed.
- `python docs/build_decks.py`: both decks rebuilt.
- Every slide rendered at 1920×1080 in Chromium, with no overflow or footer overlap.

## Addendum: the interactive page (3f73485)

The owner asked, through another session, for an interactive version of the deck's main picture to pan, zoom and
drill into. `docs/edr/cost_quality.html` draws one chart per question, so cost is never compared across questions.
You can pan, zoom (scroll, pinch or buttons), click a question to drill in, and click a method for its score, 95%
range, cost, whether it was run, and its sources. A method that was not run shows its price only.

- **Data and its test:** the data is embedded as JSON. `python/tests/test_cost_quality_page.py` checks it in three
  ways:
  - every score and rank against `docs/results.md` and `docs/tooth_loss.md`;
  - that a method not run has no score;
  - that the costs of run methods match the slides, and that the slides and appendix link the page.
- **Website:** `copy_decks_to_site.py` gains `PAGES`, and the workflow serves the page as
  `perio-bench/cost_quality.html`. The copy tests were updated.
- **Checked:** rendered in Chromium at 1440×900 and 390×844 with no script errors and no sideways scroll. Labels
  were checked for overlap. Deck, claims, wording, copy and page tests: 180 passed. `ruff check` is clean.
- **Findings:** none blocking. Screenshots were sent to the owner before the push. The page is published with the
  deck, so it also waits for the owner's "merge".

## Verdict

**Approve-with-nits.** Both Important findings are fixed, and the two open nits don't block. Merge waits on two
things: #870 merging first (this PR is stacked on it), and the owner's "merge", because the deck is published to
the website.
