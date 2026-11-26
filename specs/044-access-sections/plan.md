# Implementation Plan: AccessBench sections (spec 044)

**Branch**: `feat/<issue>-044-...` · **Date**: 2026-11-25

## Summary

A `section_code` on every AccessBench item, carried to `dim_access_question`; a new oral question set on discounts and
vouchers; seeds for the planned medical and mental sections.

## US1: sections (#938)

| Piece | Location |
|---|---|
| Sections and the check | `python/health_transformation_lab_nlp/access_sections.py`: `SECTIONS`, `FIRST_SECTION`, `validate_section` |
| Items | `section_code: "oral"` on the 15 items in both JSONL files; both `validate_item` call `validate_section` |
| Gold | `dim_access_question.section_code` in `access_batch.run`, `gold_names`, `gold_model` (diagrams via `gold_erd.py`), contract via `scripts/73_build_contracts.py`; `mergeSchema` leaves old rows null |
| Decision | `docs/adr/0014-accessbench-oral-medical-mental-sections.md` |
| Words | `benchmarks/access_bench/README.md`, `benchmarks/README.md`, the README's AccessBench section (80 lines kept) |

## US2: discount and voucher questions (#939)

`benchmarks/access_bench/items/discount_voucher_items.jsonl` (`ACC_DISC_*`), drafted from official pages opened on the
day and reviewed by the owner. `access_discount_items.py` loads and validates them like the screening set (3–5 points,
1–3 red flags, `https://` `source_thread_url`), plus `resources` and `evidence_urls`. `access_batch.FIXTURES` gains
`discount_voucher`; `all` takes every set. `80_access_review.py` gains the file in `FILES`.

## US3: seeds (#940)

`benchmarks/access_bench/seeds/medical_discounts.md` and `mental_discounts.md`, one official source per seed.

## US4: veterans' dental questions (#979)

`benchmarks/access_bench/items/veteran_dental_items.jsonl` (`ACC_VETS_*`, domain `veteran_dental`), loaded and validated
by `access_veteran_items.py` exactly as the discount set is (3–5 points, 1–3 red flags, resources, source fields).
`access_batch.FIXTURES` gains `veteran_dental` and `all_items()` includes it; the notebook's dropdown, the bundle
variable's description and `80_access_review.py` `FILES` list it. The VA and eCFR hosts were unreachable when the items
were drafted (2026-11-26): `source_verified_date` is null and `evidence_source` says so, until the pages are opened.

## Constitution check

- Synthetic only; no real people; every resource opened before it enters a key.
- Test first.
- Names follow AGENTS.md ("SQL and data names"): `section_code` is a coded value from a fixed set.
