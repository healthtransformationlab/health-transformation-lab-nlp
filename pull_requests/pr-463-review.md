---
pr: 463
branch: feat/445-032-insurance
title: "032 US6: insurance in the synthetic extract and the consistency split"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator self-review (checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve-with-nits
---

# PR Review: insurance in the synthetic extract and the consistency split

## Summary
- The synthetic Open Dental extract gains `carrier`, `insplan`, `inssub` and `patplan`, with Open Dental's own column
  names. They are drawn on a random stream of their own, so every existing table, and every committed result, is
  unchanged.
- Each patient is private, public or none at SYNTHETIC placeholder shares (55/30/15). `open_dental.insurance_type`
  reads the type back through a declared carrier lookup.
- `tooth_loss_dq.group_consistency` takes `group_types`. `insurance_type` is available and off by default, as spec 032
  keeps every default until US8.
- The tests were written first and the defaults leave every result as it was. Approve, with the nits below.

## Scope of Change
- Files changed: 16 including this review (generated diagrams counted once):
  - `open_dental.py`, `tooth_loss_dq.py`, `dq_site.py`;
  - `test_open_dental.py`, `test_tooth_loss_dq.py`, `test_silver_erd.py`, `test_dq_site.py`;
  - `diagrams/_build/opendental_silver_model.py` and the regenerated `diagrams/silver/` sources and `data_model.md`;
  - `databricks/notebooks/12_load_open_dental.py` (description only; it already loads every table `build` returns);
  - `specs/029-tooth-loss/research.md` (the four tables' columns, read from Open Dental's public source);
  - `specs/032-analysis-options/tasks.md` (T006 ticked).

## Checks against the rubric
- **Scans:** no secrets. No PHI: carriers, groups and subscriber IDs are invented (`SYN...`). No organisation's plan or
  finding is named, and the shares say SYNTHETIC.
- **Test first:** commit e274828 adds five failing tests (tables and keys, shares, own stream, the split and its
  unchanged default, a planted fault that gets flagged). They failed with AttributeError before the code.
- **Results unchanged (SC-001):** `50_dq_site.py --check` reports up to date. `47_tooth_table.py` leaves `data/`
  clean. A test shows that changing the insurance shares changes no other table. The DQ page's checks leave the new
  tables out, because otherwise its missing-value share would move. US8 adds them.
- **Python/R parity:** not affected (no label, scoring or stage rule). `test_parity.R` passes.
- **Seeds:** the new stream is derived from the extract's seed. Its defaults are fixed in `Params`.
- **Telemetry:** `insurance_type` carries `@traced`. `_insurance` is private.
- **Names:** Open Dental tables keep their own names (AGENTS.md). The new series is `insurance_type_code`.
- **Configuration:** no new setting. The load job writes four more tables on its next run.
- **Wording, benchmark order:** unaffected.

## Findings
- **Minor (fixed on the branch):** a spouse-held plan could draw the patient as its own subscriber. It now draws
  another patient, and a test checks it.
- **Minor (fixed on the branch):** asking for `insurance_type` on tables without the insurance tables raised a bare
  KeyError. It now fails at once, naming the missing tables, and a test checks it.
- **Nit (open):** the ERD PNGs under `diagrams/silver/` were not re-rendered, because the draw.io viewer host is
  blocked from the build container. The `.drawio` and `.mmd` sources, which the tests check, are current. Render with
  `node diagrams/_build/drawio_render.js` (render.md) on a machine that reaches it.
- **Nit (by design):** insurance is drawn independently of every other trait, so on the synthetic extract the split
  flags a group only when a fault is planted. That is enough to test the check. Linking insurance to site or age would
  be a generator choice for a later spec.

## Verdict
Approve with nits.
