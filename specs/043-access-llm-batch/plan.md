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

## US6: answer length (#931)

`run(answer_max_tokens=1500)` passes the cap to `_answer`, which builds `OpenAIChat(model=endpoint,
max_tokens=answer_max_tokens)`. `is_truncated = output_tokens >= answer_max_tokens` in live mode, false in simulated.
New column `fact_access_answer.is_truncated` (boolean) in `gold_names.TABLES`, `gold_model.py` (diagrams rebuilt) and
the ODCS contract. Notebook widget `answer_max_tokens`; bundle variable `access_answer_max_tokens` (default 1500); job
parameter `answer_max_tokens`.

## US7: owner review (#933)

The review page keeps decisions in its own store (`keys/<question_id>`, `grades/<answer_id>`), readable only by
the owner. They come back through the Artifact database tool's export (one JSON file per document) into
`80_access_review.py`, which calls `access_review.apply_key_review` per item and validates the result with each
set's `validate_item`. An item whose result breaks a limit is listed, not written. `key_review.json` keeps every raw
decision, and `agreement.json` the counts. The sample of 40 answers (10 per model, every question at least twice,
seed 20261125) is committed beside them so the agreement can be recomputed.

## US8: resource specificity (#935)

`access_resources` finds links (`https?://` up to whitespace or a closing bracket, trailing punctuation stripped)
and US phone numbers (10 digits, optional +1, or a 3-digit 211/311/988-style line written as such). `check_links`
uses an injectable fetcher; the default sends HEAD, falls back to GET on 405, 8 s timeout: 2xx/3xx is True, 4xx/5xx or
an unknown host is False, and any other error is None. The batch checks links only in live mode, passes the results
to `judge_messages`, and records the counts. `parse_verdict` reads optional `resource_level` (0–3) and
`invented_contact`; a v1 verdict leaves them null. Gold columns are declared in `gold_names`, `gold_model` and the
ODCS contract; writes use `mergeSchema`, so old rows read null.

## Constitution check

- Synthetic only; planted PHI; `is_simulated` labelled.
- Test-first.
- No PHI in telemetry attributes.
- SQL names follow AGENTS.md; schema `gold_access_bench`.
