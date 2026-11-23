# PR 918 review: AccessBench LLM batch into gold_access_bench (#917)

Closes #917. Refs #916 (043 EPIC1). Range: tip of `feat/917-043-access-llm-batch` vs `main`.

## Verdict

**Ready to merge** once CI is green. No blockers found in the local review.

## What it does

- Adds two Access fixtures (ADA accommodation, CHIP/EPSDT) so the batch has five synthetic dual PHI items.
- Adds `access_batch.run` with default `mode=simulated`, PHI leak gate, key-point judge reuse, and `max_usd` stop for live calls.
- Declares `dim_access_question` / `fact_access_answer` under `gold_access_bench` (gold_names, gold_model, table_comments, ODCS/ODPS).
- Wires Databricks notebook `16_access_llm_batch.py` and job **Access LLM batch** (≤20-char name).

## Rubric

| Check | Result |
|-------|--------|
| Spec / issue contract | Matches #917 Done when / Contract |
| Synthetic only / wording | Simulated labelled; access pathway language; no diagnosis wording |
| Bench order | AccessBench after the others; schemas already ordered |
| SQL names | Suffixes and singular tables in `gold_access_bench` |
| Tests first | access_phi (≥5), access_batch, gold_model, bundle, contracts/products updated |
| Idempotent write | `replace_batch` by `run_id` |
| Default no spend | `access_llm_mode` default `simulated` |

## Non-blocking notes

- Live mode still meters answer tokens only for `max_usd` (judge tokens not added); fine for a first ship.
- Lab grader dashboard is out of scope (as designed).
