# Implementation Plan: AccessBench LLM batch (spec 043)

**Branch**: `feat/<issue>-043-access-llm-batch`  
**Date**: 2026-11-23  
**Design**: `docs/superpowers/specs/2026-11-23-access-llm-batch-design.md`  
**Agent plan**: `docs/superpowers/plans/2026-11-23-access-llm-batch.md`

## Summary

Five synthetic Access fixtures → `access_batch.run` (simulated or live Serving) →
`gold_access_bench.dim_access_question` / `fact_access_answer` via notebook job
**AccessBench LLM batch**. Default `mode=simulated`.

## Technical approach

| Piece | Location |
|-------|----------|
| Fixtures | `benchmarks/access_bench/items/simulated_access_phi_items.jsonl` |
| Batch | `python/health_transformation_lab_nlp/access_batch.py` |
| Judge | reuse `access_keypoint_judge` |
| Gold | `gold_names.py`, `diagrams/_build/gold_model.py`, `table_comments.GOLD_SCHEMA` |
| Job | `databricks/notebooks/16_access_llm_batch.py`, `databricks/resources/jobs.yml` |

## US5: question sets (#929)

`access_batch.FIXTURES = ("phi", "perio_screening", "all")`. `load_batch(limit, fixture)` reads
`access_phi_items.load_items()` and/or `access_hard_items.load_items()` in file order (phi first for `all`); `limit`
still may not exceed the set's size. The leak check uses an item's `planted_phi` when it has one, and nothing
otherwise. The notebook adds a `fixture` widget; `databricks.yml` declares `access_llm_fixture` (default `phi`); the
job passes it as `fixture`. No table or column changes: `dim_access_question` already holds domain, persona, level,
key-point count and evidence source, which the screening items carry.

## Constitution check

- Synthetic only; planted PHI; `is_simulated` labelled.
- Test-first.
- No PHI in telemetry attributes.
- SQL names follow AGENTS.md; schema `gold_access_bench`.
