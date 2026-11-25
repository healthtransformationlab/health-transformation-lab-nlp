# Feature Specification: AccessBench 5-question LLM batch on Databricks

**Feature Branch**: `spec/<issue>-043-access-llm-batch` (spec); one `feat` branch per user story

**Created**: 2026-11-23

**Status**: draft

**Input**: Owner asked whether AccessBench questions can run in small batches of 5 across LLMs
on Databricks, then approved design A: gold tables in `gold_access_bench`, Python batch module,
notebook job, default `simulated` mode. Design:
[`docs/superpowers/specs/2026-11-23-access-llm-batch-design.md`](../../docs/superpowers/specs/2026-11-23-access-llm-batch-design.md).

> Personal learning project, not affiliated. Synthetic access prompts with planted identifiers
> only. We find whether an answer helps someone get care in the record of the run; we do not
> diagnose patients.

## Why

AccessBench is exploratory: empty UC schemas, three dual-fixture items, and a key-point judge
mapper exist, but no job asks Foundation Model endpoints and writes scored rows. A five-question
batch across pay-per-token LLMs on Databricks (Free Edition–safe, dry-run by default) is the
smallest path that produces checkable, simulated-labelled results in gold.

## User stories

### US1 - Five synthetic Access fixtures, stable for a batch (P1) #917

- `simulated_access_phi_items.jsonl` has at least five items with the existing contract
  (`ACC_…`, planted PHI, `must_include` / `red_flags`, `is_simulated: true`).
- Two new domains stay on the access side (pathway / constraint), not OralHealthBench clinical
  accuracy.
- **Independent test:** `access_phi_items.load_items()` returns ≥5 unique ids; existing PHI and
  validate tests still pass.

### US2 - Offline batch builds scored answer rows without calling models (P1)

- `access_batch.run(...)` with `mode="simulated"` scores `limit` questions × answering
  endpoints into frames for `dim_access_question` and `fact_access_answer`.
- Each fact row has score, harm, PHI-leak flag, `is_simulated=true`, and provenance fields.
- **Independent test:** pytest with no network: 5×N simulated rows; leaky stub → `is_phi_leak`;
  scores in `[0, 1]`.

### US3 - Gold names and Unity Catalog comments for `gold_access_bench` (P1)

- `gold_names.TABLES` and `diagrams/_build/gold_model.py` declare `dim_access_question` and
  `fact_access_answer`; `table_comments.GOLD_SCHEMA` maps them to `gold_access_bench`.
- **Independent test:** `to_gold` accepts the batch frames; `declared` returns comments for both
  tables under `gold_access_bench`.

### US4 - Databricks job runs the batch and writes gold idempotently (P2)

- Notebook + job **AccessBench LLM batch**: widgets `endpoints`, `limit`, `judge_endpoint`,
  `max_usd`, `mode`, `run_id`, `git_commit`. Default `mode=simulated`.
- Live mode uses OpenAI-compatible Serving; stops before a call that would exceed `max_usd`.
- Writes via `delta.replace_batch` keyed on `run_id`.
- **Independent test:** bundle lists the job; notebook imports the module; a simulated path
  writes (or a unit test of the write helper with a fake spark).

### US5 - The ten periodontal-screening questions run in the batch (P1) #929

- `access_batch.load_batch(limit, fixture=...)` picks the question set: `phi` (the five planted-detail questions,
  the default), `perio_screening` (the ten hard periodontal-screening questions, #919) or `all` (both, 15).
- A question with no planted details gets `is_phi_leak = false`: there is nothing to leak.
- The notebook widget `fixture` and the bundle variable `access_llm_fixture` (default `phi`) pass it to the job.
- **Independent test:** `test_access_batch.py` loads 10 and 15 questions, rejects an unknown fixture, and scores the
  screening set in simulated mode with no leak flagged; `test_bundle.py` checks the variable and job parameter.

### US6 - Answers are not cut off, and a cut-off answer is marked (P1) #931

- The answering client gets `answer_max_tokens` (default 1500, set by the widget `answer_max_tokens` and the bundle
  variable `access_answer_max_tokens`), not the chart reader's 300. On 2026-11-24, 37 of 60 live answers hit 300.
- Each answer row records `is_truncated`: true when its output tokens reached the cap.
- **Independent test:** with a stub client, `run(..., mode="live", answer_max_tokens=1500)` builds the client with
  that cap; an answer whose output tokens equal the cap is `is_truncated`; `to_gold` maps the column.

## Requirements

- **FR-001** Default batch size is 5; `limit` may be smaller but not larger than the fixture
  count without an explicit error.
- **FR-002** Default `mode` is `simulated`; live calls need an explicit widget/CLI value.
- **FR-003** Every answer is checked with `deid.leak_check` against planted PHI for that item.
- **FR-004** Judge scoring reuses `access_keypoint_judge` (prompt version `access-keypoints-v1`).
- **FR-005** Writes are idempotent by `run_id` (repair replaces the matrix for that run).
- **FR-006** Tables live in `gold_access_bench`; names follow AGENTS.md column suffixes.
- **FR-007** Simulated rows and methods are labelled `is_simulated=true`; never presented as
  real model results.

## Success criteria

- A developer can run a simulated 5×endpoint matrix in pytest without credentials.
- After deploy, the owner can start **AccessBench LLM batch** with `mode=simulated` and see
  rows in `gold_access_bench.fact_access_answer` for that `run_id`.
- A live run with one pay-per-token endpoint and `max_usd` set does not continue past the budget.

## Out of scope

- Wiring results into the Lab grader dashboard / Genie.
- OralHealthBench items or medicine–dental accuracy scoring.
- Publishing Access results to Kaggle or Hugging Face.
- Growing the fixture set beyond five in this spec.

## Risks

- Free Edition fair-use / spend: mitigated by default simulated mode and `max_usd`.
- Same endpoint for answer and judge: allowed; both names stored on the row.
