# Design: AccessBench 5-question LLM batch on Databricks

Approved 2026-11-23 (approach A / implementation path 1). Personal learning project, not
affiliated. Synthetic prompts and planted identifiers only; never real PHI.

## Why

AccessBench is exploratory: UC schemas exist and are empty; three dual-fixture items and a
key-point judge mapper live on `main`, but nothing asks Foundation Model endpoints and writes
scored rows. The owner wants small batches of five questions across LLMs on Databricks
(pay-per-token), with a default dry-run that does not bill.

## Decision

| Choice | Decision |
|--------|----------|
| Destination | New gold tables in `health_transformation_lab.gold_access_bench` |
| Run shape | Python module + Databricks notebook job (same pattern as de-id AI / judge) |
| Default mode | `simulated` (no model calls); `live` calls answering + judge endpoints |
| Batch size | Five items (add two synthetic fixtures to the existing three) |
| Out of scope | Lab grader dashboard remap, OralHealthBench, Kaggle/HF publish, >5 items |

## Data

### Fixtures

Keep `benchmarks/access_bench/items/simulated_access_phi_items.jsonl`. Add two rows with the
same contract (`ACC_…`, `must_include`, `red_flags`, `planted_phi`, `is_simulated: true`):

- one **ADA / accommodation** pathway (e.g. wheelchair-accessible dental visit)
- one **FQHC / safety-net finding** or **CHIP/EPSDT child pathway** (access, not clinical
  accuracy — OralHealthBench stays for medicine–dental facts)

### `dim_access_question`

Grain: one row per `question_id`.

| Analysis name | Gold name | Type |
|---------------|-----------|------|
| question_id | question_id | string |
| domain | domain_code | string |
| persona | persona_name | string |
| level | level_code | string |
| n_key_points | key_point_count | bigint |
| evidence_source | source_text | string |
| is_simulated | is_simulated | boolean |
| run_id, run_ts, git_commit | run_id, run_ts, git_commit_sha | … |

### `fact_access_answer`

Grain: one row per `(question_id, answering_endpoint_name, run_id)`.

| Analysis name | Gold name | Type |
|---------------|-----------|------|
| question_id | question_id | string |
| endpoint | answering_endpoint_name | string |
| answer | answer_text | string |
| key_points_covered | covered_key_point_count | bigint |
| score | score_ratio | double |
| harm | harm_code | string |
| red_flag_hit | red_flag_hit_text | string (JSON list) |
| is_phi_leak | is_phi_leak | boolean |
| judge_endpoint | judge_endpoint_name | string |
| prompt_version | prompt_version_code | string |
| latency_s | latency_seconds | double |
| input_tokens | input_token_count | bigint |
| output_tokens | output_token_count | bigint |
| cost_usd | cost_usd | double |
| is_simulated | is_simulated | boolean |
| error | error_text | string |
| run_id, run_ts, git_commit | run_id, run_ts, git_commit_sha | … |

Writes use `delta.replace_batch` keyed on `run_id` (and answering endpoint when a job run
writes one endpoint at a time — prefer one batch key `run_id` for the whole job so a repair
replaces the full matrix).

## Runtime

Module `health_transformation_lab_nlp.access_batch`:

1. `load_batch(limit=5)` → first `limit` fixtures (stable order by `id`).
2. For each item × answering endpoint: get an answer (`simulated` → fixed scrubbed stub;
   `live` → OpenAI-compatible Serving chat).
3. PHI gate: `deid.leak_check(answer, known_phi_for_leak_check(row))` → `is_phi_leak`.
4. Judge: reuse `access_keypoint_judge` (`judge_messages` / parse / score). In `simulated`, a
   deterministic fake verdict. In `live`, call `judge_endpoint`.
5. Enforce `max_usd`: refuse to start the next live call if estimated spend would exceed it.
6. Return DataFrames ready for `gold_names.to_gold` + `replace_batch`.

Notebook `databricks/notebooks/16_access_llm_batch.py` + job **AccessBench LLM batch** in
`databricks/resources/jobs.yml`:

- Widgets: `endpoints` (comma list), `limit` (default 5), `judge_endpoint`, `max_usd`,
  `mode` (`simulated` \| `live`), `run_id`, `git_commit`, `telemetry`.
- Serverless / CPU only; pay-per-token endpoints only (Free Edition).
- Default endpoint list: one Foundation Model chat (e.g. Llama 3.3 70B) so a live run is
  cheap; the widget accepts more.

## Testing

- Expand fixture count test: `load_items()` length ≥ 5; ids unique; PHI contract holds.
- `access_batch` unit tests: simulated 5×2 matrix, scores in `[0,1]`, `is_simulated` true,
  leaky stub sets `is_phi_leak`, `max_usd` stops further live calls (mock client).
- Bundle declares the job; `gold_names` + `gold_model` + `table_comments.GOLD_SCHEMA` know
  both tables under `gold_access_bench`.

## Risks

- Free Edition quota / spend: default `simulated`; live needs an owner-started job.
- Judge and answerer the same endpoint: allowed; document that the row still stores both
  names.
- Lab grader tables stay separate until a later story maps Access gold into the dashboard.

## Self-review

- No placeholders left for open product choices (destination A approved).
- Scope capped at five fixtures + one job; no dashboard / publish.
- Naming follows AGENTS.md suffixes; schema is `gold_access_bench`.
