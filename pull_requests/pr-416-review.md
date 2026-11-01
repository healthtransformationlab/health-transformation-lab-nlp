---
pr: 416
branch: feat/198-023-medical-features
title: "023 US1: the synthetic visits carry seeded medical-record features"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent run)
verdict: approve
---

# PR Review: 023 US1: the synthetic visits carry seeded medical-record features

## Summary
This implements spec 023 US1 (#198; T001–T004). `medical_record.py` gives every synthetic person a synthetic
medical record, and `build_study` writes it as `data/datasets/medical_record.csv`.

**What the record holds:**
- Hypertension, CKD, cardiovascular disease and COPD, each from one declared, cited table (`CONDITIONS`).
- Diabetes, reused from the generator's HbA1c ≥ 6.5.
- Blood pressure, from the NCHS definition and control shares.
- ASA class.
- An `is_synthetic` flag on every row.

**How it is drawn:** each condition depends only on periodontal status and age band. So the age-adjusted
(Mantel–Haenszel) odds ratio is the cited one by construction, and the test recovers it on 10,000 people.

**Effect on committed data:** the record has its own random stream (`f"{seed}:medical"`), drawn after every study
draw. A rebuild leaves every committed dataset byte-identical and adds only the new file, and a test enforces this
(FR-001, SC-001).

This meets US1 acceptance scenarios 1–4. Approve.

## Tests
- `test_medical_record.py` has 12 tests, written first and failing on import.
- They cover sources, seeding, the global random state, naming, types and ranges, diabetes = HbA1c, base rates,
  Mantel–Haenszel odds ratios, the latest-visit rule, the byte-identical rebuild and the data card.
- Full suite: 1259 passed, 15 skipped.
- `ruff` is clean on the new files.
- R parity was not run: US1 changes no scoring and has no R twin (FR-006 covers the US3 metrics).

## Secrets, PHI and Claims Scan
Clean.
- **Data:** every value is generated, and the data card and every row say so. The paper's patient-level data is
  not used.
- **Sources:** each rate and odds ratio was read from its source's abstract or key findings (PubMed or the CDC
  page) before use. `plan.md` lists them.
  - **ASA definitions:** read from secondary copies. The ASA's own page was unreachable from the session.
  - **Cardiovascular disease:** the cited figure is a relative risk, used as an odds ratio. This is said in the
    source text.
- **Claims:** the data card calls the links built-in associations, not causes.
- **Wording:** `test_wording.py` passes.

## Findings
None blocking.
- **Haematologic and endocrine conditions other than diabetes** are left out. The plan allows this when no source
  has been checked. A later PR can add them with sources.
- **Sources changed from the plan's candidates:**
  - CKD: Kapellas 2019 replaces Chambrone 2013, because Kapellas gives a pooled odds ratio in its abstract.
  - Cardiovascular disease: Janket 2003 replaces the Sanz 2020 consensus report.

  Neither replaced paper was checked. `plan.md` records both changes.
- **Hypertension exposure:** "moderate–severe periodontitis" (Muñoz Aguilera) is mapped to stages II–IV. This is a
  repo choice, stated in the source text.
- **ASA class:** chronic kidney disease counts as II, and three or more class III findings stand in for class IV.
  These are repo choices, stated in `ASA_SOURCE`.
- **Blood-pressure range ends:** the outer ends of each uniform blood-pressure band are a repo choice, so marked;
  the thresholds are sourced.
- **Pre-existing lint:** `ruff` reports C408 at `study.py:95`, outside this change.
- **`_mmhg` suffix and gold names:** the suffix row in AGENTS.md and the gold names in `gold_names.py` are deferred
  until results go to gold, as the spec says.

## Rubric
- Every new public function is `@traced`. Paths go through `paths.py`.
- Seeds are fixed (seed 42, the stream `f"{seed}:medical"`).
- The data file was rebuilt with `scripts/10_build_study.py`, not edited by hand.
- A spec exists (023); its tasks are ticked.
- `Closes #198`. The branch name follows `feat/<issue>-<slug>`.
- Environments: none change.
