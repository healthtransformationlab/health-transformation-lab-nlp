---
pr: 761
branch: docs/738-030-docs-earlier-build-figures
title: "030 DOCS2: bring the other docs in line with the 223-chart build"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: independent read-only reviewer subagent (two passes) + coordinator verification; the Superpowers plugin was not installed in this session
verdict: approve-with-nits
---

# PR Review: bring the other docs in line with the 223-chart build

## Summary
After #637 fixed the scoring and standards pages, other docs still gave counts and results from earlier builds.
This PR recomputes each from a committed table. The changed files are `periodx.md`, `medgemma.md`, the EDR
page's hand-written status, `data_sources.md` and six other pages that quote counts. Records of runs on the
earlier build stay and are labelled `before #467`. A new test guards every count of review charts, notes and
held-out patients, and pins the recomputed figures. The reviewer recomputed every figure with its own code, and
all match. Two passes found four Important and eleven Minor points. All are fixed on the branch except those
deliberately left for the owner, listed below. Nothing blocks. Approve with nits.

## Scope of Change
- Files changed: 16 (+414 / -98 before this review file): 15 docs and data READMEs, 1 new test file; no data files
- Areas touched: docs / python (tests only)
- Commits:
  - `ffaf98b` Bring the other docs in line with the 223-chart build
  - `07d814d` Fix what the review of the docs change found
  - `dd4a014` Fix what the second review of the docs change found
- Range reviewed: `0114053..dd4a014` (first pass on `ffaf98b`, second on `07d814d`; `dd4a014` answers the second
  pass and was checked by the coordinator)

## CI Status
| Check | Status |
|---|---|
| Local `pytest -q tests` on `07d814d` | 2,634 passed, 35 skipped |
| Local doc tests on `dd4a014` (new file, scoring, standards, readme_results, wording, bench order, org references, deck claims, inventory) | 194 passed |
| GitHub checks | run on push; the head commit must be green before merge (AGENTS.md rule 6) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean. "Token" appears only as token counts and in prose about Hugging Face tokens.
- **PHI / real data:** clean. Numbers only; no data file changed.
- **Organization claims:** clean. "Diagnoser" and "Extractor" are the cited paper's own names.

## Strengths
- Every figure traces to a committed table; the PR description names the table for each.
- The tables were checked before the pages. The PerioDx and MedGemma tables were already on the current build; only
  the pages lagged, so recomputing (not relabelling) was possible for them.
- Earlier runs are kept as records and labelled, not overwritten: the first MedGemma runs, the fallback analysis,
  the storage-design dry run, the judge files.
- The guard reads what a page claims rather than one old number, so it also caught the older 237 and 2,426.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **The guard skipped `docs/edr/README.md` as generated**, though only its `results:start`/`results:end` block is.
   Its hand-written status still gave the 240-chart runs and contradicted the new `medgemma.md`. **Fixed in
   `07d814d`:** rewritten from `ladder_vs_truth.csv`; the guard now strips only the generated block.
2. **The guard skipped every nested `AGENTS.md` by file name.** **Fixed in `07d814d`:** rules files are skipped by
   path. `databricks/agents/chart_review/AGENTS.md` still says 240 and is left for the owner (issue #738).
3. **`medgemma.md` said the L3 gap is where no diagnosis is written.** L3 also holds notes whose diagnosis
   disagrees with the chart: 45 of the 64, with 19 giving none. **Fixed in `07d814d`**, on the EDR page too.
4. **`docs/code_walkthrough.md` still gave the earlier encoder and MedGemma results** on a line the guard can't
   see. **Fixed in `dd4a014`**, pinned by a test.

### 🔵 Nits / suggestions (Minor)
5. The fallback table's lead-in read as if the table described the current runs. **Fixed in `07d814d`.**
6. Only one row of the storage-design table was labelled as the earlier build. **Fixed in `07d814d`.**
7. Several new figures were unpinned (fallback rate, stage IV counts, tokens, time, the note-rules comparison,
   the encoder's L1 and L3, the 19/45 split, the negation claim). **Pinned in `07d814d`;** the negation claim is
   run in the test.
8. The PerioDx stage I sentence gave the pocket rule as the reason for all 41. **Fixed in `07d814d` and
   `dd4a014`:** 33 land in healthy or gingivitis, and the other 8 have no gum chart.
9. The model inventory's intro said Hugging Face though the MedGemma runs used Kaggle checkpoints, and it listed
   GatorTron as not run. **Fixed in `07d814d` and `dd4a014`.**
10. The judge README named the package's old path. **Fixed in `07d814d`.**
11. "Twelve encoders" sat under a table of twelve models that includes two not run and omits two that were.
    **Fixed in `dd4a014`:** the twelve are named.
12. "(3 epochs)" could not be checked: no committed file records the runs' epochs. **Dropped in `dd4a014`.**
13. Two tests were weak: the 1.5 stage IV-rule pin matched 1.5's own score, and "no 240 on the page" matched any
    substring. **Fixed in `dd4a014`.**
14. The guard is per line and matches only "N [synthetic] review(ed) charts/notes/visits" and "N held-out
    patients". "240 charts" or "240 notes" without "review" pass it. Left as is: the pins cover the pages that
    give results, and a wider pattern would catch citations of other studies.
15. `docs/evaluation_checklist.md` keeps "Updated 2026-10-31". Left as is: no status was re-assessed.

Left for the owner and listed in the PR: `databricks/agents/chart_review/AGENTS.md`, the `is_in_review`
description in `gold_model.py` (it regenerates diagrams and contracts), the two Kaggle notebooks, a comment in
`docs/claims.yaml`, and the `ladder_eval.py` docstring's "7 stage IV notes" (now 0).

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data files changed |
| No organization claims; vendors cited | ✅ | `test_no_org_references.py` passes |
| Test first | ✅ | 9 of the 11 new tests fail on `main`; the other 2 check the guard itself |
| Python and R in parity | n/a | no label, scoring, reliability or cost change |
| Simulated is labelled simulated | ✅ | no simulated figure added |
| Paths | ✅ | `DATASETS_DIR`, `REPO_ROOT` |
| Spec for big changes | n/a | docs fix with tests |
| Wording ("diagnose") and benchmark order | ✅ | `test_wording.py`, `test_bench_order.py` pass |
| Generated files not edited by hand | ✅ | `35_readme_results.py --check` up to date; only hand-written parts of the EDR page changed |
| Issue has its four parts | ✅ | #738: Problem, Done when, Contract, Read first |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Configuration, secrets register, writes, alerts | n/a | |

## Test Coverage
- `python/tests/test_docs_current_build.py` (12 tests): the guard and its two self-checks; `data_sources.md`
  counts; the PerioDx table and bullets (negation run); the MedGemma field-accuracy table, current runs and extent
  comparison; the Open Dental row (read from the `open_dental_load` job); the EDR status; the code walkthrough line.
- Not covered by a test: the EDR page's class-weight seed figures, Bio_ClinicalBERT and TF-IDF calibration (checked
  by the reviewer), and the website page (checked by a script outside the repo).

## Verdict
Approve with nits. Nothing must change before merge; the head commit needs green CI first.
