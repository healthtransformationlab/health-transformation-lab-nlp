---
pr: 517
branch: data/467-032-rebuild-notes-adults
title: "033 US3: rebuild the benchmark notes for adults from 2021-04-01 at the published risk shares"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: self-review (agent), against .claude/review-rubric.md and AGENTS.md
verdict: approve-with-nits (hold for the owner: it starts no run, but it changes what the external runs score)
---

# PR Review: rebuild the benchmark notes for adults from 2021-04-01 at the published risk shares

## Summary
The study build now defaults to adults' visits from 2021-04-01, the spec 032 US8 defaults (#467). It also draws
smoking and diabetes at spec 033 US2's published shares (#486). Every local result was rerun with the repo's scripts.
The committed external runs (the GPU encoders, MedGemma on Kaggle and Databricks, Llama 3.3 70B, the real LLM judge)
were made on the old notes. They are kept, recorded with that note set (`note_set.py`,
`data/datasets/prediction_note_sets.csv`), and shown as "rerun pending on the new notes" instead of being scored
against the new answer key. The scoring-time filter stays as a no-op check.

## Scope of Change
- 194 files, most of them regenerated CSVs.
- Code:
  - `study.py`: build defaults and `STUDY_RISK_KWARGS`.
  - new `note_set.py`.
  - `results_store.record`: stamps the note set and refuses visits outside the review set.
  - `readme_results.py`: pending rows and the pending judge section.
  - scripts 10, 11, 13, 15, 25, 28, 29, 36 and 54.
  - `kaggle/publish.py`, `huggingface/publish.py`.
- R: `r/tests/test_parity.R` skips the two stale real-run sections.
- Tests: new `test_note_set.py` and build tests. Tests that pinned 240, 3,484 or the old committed runs now follow
  the build.
- Docs:
  - `presets.md`: a new #467 section and the updated preset table.
  - `synthetic_data.md`, `scoring.md`, `algorithms.md`, the landing README.
  - EDR slides 3, 4, 8 and 9, `claims.yaml`, the cards and notebooks.
  - specs 032 and 033, with 033 T005 ticked.
  - generated: `results.md`, `edr/README.md`, `standards.md`, `site/data-quality.json`, the decks.

## CI Status
Not yet read on the PR head. Locally:
- `pytest -q tests -n 4`: 1936 passed, 16 skipped.
- `Rscript r/tests/test_parity.R`: OK in every section.
- `35_readme_results.py`, `42_build_dashboards.py` and `50_dq_site.py` are up to date.

## Secrets, PHI and Claims Scan
- **Secrets:** none.
- **PHI / real data:** none. The rebuilt files come from the seeded synthetic generator. Raw notes with fake PHI stay
  in git-ignored `data/raw/`.
- **Organisation claims:** none.
- **Wording:** the wording, organisation-reference and benchmark-order tests pass.
- **Simulated output:** every simulated output keeps its `simulated_` name.

## Strengths
- No committed prediction is deleted or silently rescored. Each one says which notes it read.
- The leaderboards, the published datasets, the R parity test and the record step all honour the same register.
- A collected run whose visits aren't the review notes is refused at record time.
- The rebuild is reproducible: script 10 after the merge with main gave byte-identical files.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
- **The review set is 223 charts, not 240.** Under the new risk draw only 12 people's latest visit is stage IV, below
  the stratum's target of 29, and the sampling rule (unchanged) doesn't top up. Stage IV metrics now rest on 12
  charts. If the owner wants 240, the top-up rule has to change, with a spec note, **before** the external runs are
  redone.
- **Gold tables in dev.** Load results will put the new answer key beside stale external predictions that are
  already loaded. Joins in gold views will mismatch until the reruns land. Carrying `note_set_sha256` into gold is a
  follow-up.

### 🔵 Nits / suggestions (Minor)
- The TF-IDF rungs also move a little from this container's scikit-learn, so their before/after mixes the new notes
  with environment drift. `docs/presets.md` says so.
- The Kaggle collect step stamps the notes on `main` at record time. That is right as long as runs start after this
  merges, and a mismatch in visits is refused.
- EDR slides 4 and 9 lose their encoder, MedGemma and judge numbers until the reruns. Slide 9 keeps the old judge
  figures, labelled as made on the old notes.

## Verdict
Approve with nits. Merge waits for the owner. It starts no paid run, but it is what the Kaggle and Databricks reruns
read, and the 223-chart question should be settled first.
