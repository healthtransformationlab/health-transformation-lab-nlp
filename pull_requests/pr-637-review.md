---
pr: 637
branch: docs/635-030-scoring-standards-223-charts
title: "030 DOCS1: bring the scoring and standards pages in line with the 223-chart results"
author: jcbowyer
reviewed_at: 2026-11-10
reviewer: independent read-only reviewer subagent (two passes) + coordinator verification; the Superpowers plugin was not installed in this session
verdict: approve-with-nits
---

# PR Review: bring the scoring and standards pages in line with the 223-chart results

## Summary
`docs/scoring.md` and `docs/standards.md` still quoted the note set from before #467 (240 review charts, 4,343
visits). The PR replaces each stale figure with the committed tables' value, makes the generator of `standards.md`
score the two orders as the leaderboard does (207 and 176, not 205 and 169), and adds tests that pin both pages to
the tables. The reviewer recomputed every figure from the tables with its own code: all match. Two passes found one
Important and ten Minor points, and all are fixed on the branch. One figure outside the issue is left as it is and
flagged for the owner (the Open Dental extract's size). Nothing blocks. Approve with nits.

## Scope of Change
- Files changed: 6 (+198 / -31), no data files
- Areas touched: docs / python (one doc generator, its script's docstring, two test files)
- Commits:
  - `31f7a62` Bring the scoring and standards pages in line with the 223-chart results
  - `45f56db` Say only what the tables show about charts that can't be staged
  - `cbf7827` Say "radiograph reading" for the charts that can't be staged
- Range reviewed: `b12e2e0..cbf7827` (first pass on `31f7a62`, second pass on `45f56db`; `cbf7827` answers the
  second pass and was checked by the coordinator)

## CI Status
| Check | Status |
|---|---|
| `check` (branch name and issue link) | pass on `31f7a62` |
| `python` | pass on `31f7a62` |
| `postgres`, `bundle`, `azure-infra`, `changes` | pass on `31f7a62` |
| `r-parity` | skipped (no R-relevant change) |
| `python-databricks-runtime` | still running on `31f7a62` when this was written |
| Later commits | CI runs when they are pushed with this file; the head commit must be green before merge (AGENTS.md rule 6) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. No data file is in the diff; the tests read only committed synthetic tables.
- **Organization claims:** clean. The only names added are the published classifications already cited on the page.

## Strengths
- Every figure traces to a committed table, and the PR description names the table for each.
- The sentence that the new data no longer supports was rewritten, not renumbered: the page had said that on every
  chart that can't be staged the note states exactly the true status.
- The standards test cross-checks two artifacts made by different scripts (`seed_stability.csv` seed 42 and the
  leaderboard rows in `results.md`).
- The new tests fail on `main` where they should: 6 failed and 7 passed there, 13 pass on the branch.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`docs/scoring.md`, "Some records can't be staged": "A method that is right there has only repeated what the note
   or the codes say" claimed more than the data shows.** Of the keyword rules' 14 right answers on the 17 charts, one
   (visit 2745) has no diagnosis written and was staged from findings the note quotes, and the exam form also answers
   on 14 of the 17. Verified by running the note reader's two steps on the 17 notes and by counting each source's
   answers in `review_key.csv`. **Fixed in `45f56db`:** the sentence is gone, and the bullet names the note, the exam
   form and the codes as what gives a status there.

### 🔵 Nits / suggestions (Minor)
2. **One sentence mixed two match rules** (12 is an exact match, 14 is at five status groups; at five groups the note
   states the true status on 13). **Fixed in `45f56db`:** "Scored at five status groups, the keyword rules get 14".
3. **`docs/standards.md` named only half of "scored as the leaderboard is".** Grouping alone gives 207 and 180; the
   176 also needs a treatment plan with no gum-disease code read as healthy or gingivitis. Verified: grouping alone
   207 / 180, the re-read alone 205 / 164, both 207 / 176. **Fixed in `45f56db`:** the sentence names both.
4. **`standards_doc.py` used the answer key's length for "the review charts the methods are scored on".** **Fixed in
   `45f56db`** (it uses the scored count). The second pass then found the test still counted the answer key: **fixed
   in `cbf7827`**.
5. **Docstrings said "nothing is re-run"** although scoring now reads the codes again from the seeded build. **Fixed
   in `45f56db`.** The page's own header comment still says "from committed files", as the leaderboard's does: left.
6. **`test_scoring_doc.py` searched hard-wrapped text for multi-word phrases**, so re-wrapping a paragraph could fail
   a count. **Fixed in `45f56db`** (prose is matched with the wrapping removed) and the last bare `next()` in
   `cbf7827`.
7. **A hard-coded `data/sites` path in the new standards test.** **Fixed in `45f56db`** (`sd.SITES`).
8. **The lead-in said both points "make the gap bigger" and that "the leaderboard now shows both".** The split by
   stageable is in `ladder_by_stageable.csv`, not on the leaderboard page, and the bullet's own numbers (82% on both
   sets) show no bigger gap. **Fixed in `45f56db`:** "bigger or harder to see, and the results now show both".
9. **5 of the 17 charts do have a radiograph whose image could not be read** (`radiograph_summary` in
   `review_key.csv`; `rad_present` is 0 for them, which is what `ladder_eval.stageable` reads). The page said "no
   radiograph". **Fixed in `cbf7827`:** "no radiograph reading".
10. **"Each method's score" was wider than `ladder_by_stageable.csv`**, which holds the 43 note-reading runs and no
    row for the rule orders or the single sources. **Fixed in `cbf7827`:** "Each note-reading method's score".

Left as it is, and not a reviewer finding: **"Open Dental extract: 2,000 patients"** traces to no committed table (it
is the generator's default; the committed sample has 200 patients and the tooth-loss results use 6,000). It is not a
240-chart figure and which number belongs there is the owner's choice; the PR description flags it.

Other docs still mention 240 charts (`medgemma.md`, `evaluation_checklist.md`, `gold_tables.md`, `periodx.md` and
others). They are outside issue #635 and were not checked for which are stale and which record earlier runs.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data files changed |
| No organization claims; vendors cited | ✅ | `test_no_org_references.py` passes |
| Test first | ✅ | the new tests fail on `main` (6 of 13); tests and fix share a commit, so the order they were written in can't be read from history |
| Python and R in parity | n/a | labels, scoring, reliability and cost-effectiveness unchanged; the generator calls the existing `study.scored_review` and `ladder_eval.grouped` |
| Simulated is labelled simulated | ✅ | no simulated figure added; both pages say synthetic |
| Seeds fixed | n/a | |
| Paths | ✅ | `paths` module and `sd.SITES` |
| Spec for big changes | n/a | a docs fix with regression tests; the scoring it applies is spec 032 US8's |
| Wording ("diagnose") and benchmark order | ✅ | `test_wording.py`, `test_bench_order.py` pass |
| Generated files not edited by hand | ✅ | `48_standards_doc.py --check`: up to date |
| Telemetry | ✅ | `_order_scores` is private; `test_telemetry_calls.py` passes |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Docs | ✅ | the website's two short pages are updated to match in healthtransformationlab.github.io pull request 25, which waits for the owner |
| Configuration, secrets register, idempotent writes, alerts | n/a | |

## Test Coverage
- New `test_scoring_doc.py` (7 tests): the visit, patient, training, review, charted and held-out counts; 207 vs 176;
  the charts that can't be staged; the seed ranges; and that no figure from the 240-chart notes is left.
- `test_standards_doc.py` (3 new tests): the review-chart count, the charted visits out of every visit, and the two
  orders against `seed_stability.csv` and `results.md`.
- Not covered by a test: the "Open Dental extract" row, and the website pages (checked by a script outside the repo).
- Run locally: `pytest -q tests` on `45f56db`, 2,233 passed and 35 skipped; on `cbf7827`, the two doc test files with
  `test_readme_results.py`, `test_wording.py`, `test_bench_order.py` and `test_no_org_references.py`, 95 passed;
  `ruff check` on the changed Python files, clean.

## Verdict
Approve with nits. Nothing must change before merge. The head commit needs green CI first (AGENTS.md rule 6); the
website pull request waits for the owner either way.
