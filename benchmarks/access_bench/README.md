# AccessBench (exploratory)

Whether an AI answer helps someone **actually get care** (coverage, travel,
safety-net pathways, accommodations) — not only whether the facts are sound.

| Path | Holds |
|------|--------|
| `prompts/` | Authoring prompts that expand access seeds into scored items |
| `seeds/` | Short seed questions about getting care |
| `items/` | Generated scored rows (JSONL preferred) |

## What goes here vs OralHealthBench

| Put the item in… | When it is about… |
|------------------|-------------------|
| **AccessBench** (`access_bench/`) | Getting care: insurance/cost, travel, FQHC/NEMT, VA dental class, EPSDT/CHIP pathways, ADA accommodations, finding affirming or accessible providers, dropped constraints |
| **OralHealthBench** (`oral_health_bench/`) | Accurate answers at the medicine–dental seam (medicines, chronic disease, emergencies) without a binding access pathway |

If a seed has both, prefer AccessBench when the hard part is the pathway or
constraint; prefer OralHealthBench when the hard part is clinical/factual
accuracy.

## Expand seeds into scored items

1. Put seed questions in `seeds/`.
2. Run an LLM with [`prompts/expand_seed_questions.md`](prompts/expand_seed_questions.md).
3. Save each expanded row under `items/` (one JSON object per line).

Ids use an `ACC_` prefix. Rubrics cite published statutes and guidelines only.
Label simulated scores as simulated.

## Hard set: periodontal screening access (2030 stretch)

[`items/perio_screening_hard_items.jsonl`](items/perio_screening_hard_items.jsonl)
holds ten open-ended asks grounded in public forum threads and primary sources
(Medicare exclusion, state Medicaid, waiting periods, appeals, D0180 vs cleaning).
Load with `access_hard_items.load_items()`. Seeds:
[`seeds/perio_screening_hard_2030.md`](seeds/perio_screening_hard_2030.md).
Owner stretch goal only — not an affiliated program quota.

## Dual fixture: access + planted synthetic PHI

[`items/simulated_access_phi_items.jsonl`](items/simulated_access_phi_items.jsonl) plants
invented identifiers (challenge-pool names, example phones, SSNs starting with 9) inside
realistic access prompts. Use it to score:

| Gate | Pass when |
|------|-----------|
| Access pathway | `must_include` met, `red_flags` avoided |
| PHI leak | `deid.leak_check(answer, known_phi)` is empty |

```python
from health_transformation_lab_nlp import access_phi_items, deid
rows = access_phi_items.load_items()
leaks = deid.leak_check(model_answer, access_phi_items.known_phi_for_leak_check(rows[0]))
```

## Lab grader + key-point judge

`must_include` (padded with negated `red_flags` up to five) maps to the lab grader’s
key points. Use `access_keypoint_judge` for dim rows and a Databricks / OpenAI judge call
(chart phenotyping stays in `judge.py`):

```python
from health_transformation_lab_nlp import access_keypoint_judge as ak, access_phi_items
row = access_phi_items.load_items()[0]
q = ak.to_grader_question(row)          # question_id, category, level, n_key_points, …
msgs = ak.judge_messages(row, answer)   # chat for Model Serving
prompt = ak.ai_query_prompt(row, answer)  # single string for ai_query
scored = ak.score_verdict(ak.parse_verdict(raw, n_key_points=q["n_key_points"],
                                           n_red_flags=len(row["red_flags"])),
                          n_key_points=q["n_key_points"])
```

Difficulty: optional `level` on the row; else `L3` when `knowledge_cutoff_sensitive` or
the id ends `_H1`/`_H2`, otherwise `L2`. Category is always Access to care.

## Databricks batch (spec 043)

Job **Access LLM batch** (`databricks/notebooks/16_access_llm_batch.py`) scores a question set
(`fixture`: `phi`, the five planted-detail asks, by default; `perio_screening`, the ten hard screening asks; or
`all`) across answering endpoints into `gold_access_bench.dim_access_question` and
`fact_access_answer`. Default `mode=simulated` (no Serving spend). Live mode uses
pay-per-token endpoints and stops when `max_usd` is exceeded.

```python
from health_transformation_lab_nlp import access_batch
out = access_batch.run(endpoints=["sim:llama"], limit=5, mode="simulated",
                       run_id="local", run_ts=..., git_commit="...")
```

Real PHI is never allowed here.
