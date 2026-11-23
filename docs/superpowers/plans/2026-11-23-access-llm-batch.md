# AccessBench LLM Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run five synthetic AccessBench questions across Databricks Foundation Model endpoints (or a simulated dry-run) and write scored rows to `gold_access_bench`.

**Architecture:** Expand the JSONL fixture to five items; add `access_batch.run` that answers, PHI-gates, and key-point-judges each item×endpoint; declare `dim_access_question` / `fact_access_answer` in gold_names + gold_model under `gold_access_bench`; wire notebook `16_access_llm_batch.py` and job **AccessBench LLM batch**.

**Tech Stack:** Python 3.12, pytest, Databricks Asset Bundle, pay-per-token Model Serving (`OpenAIChat`-style urllib), `delta.replace_batch`, `@traced`.

## Global Constraints

- Synthetic only; planted PHI from the challenge name pool; label every simulated row `is_simulated=true`.
- Benchmark order: PerioBench, OralHealthBench, AccessBench.
- Default job `mode=simulated`; live needs explicit widget value and respects `max_usd`.
- Column names follow AGENTS.md suffixes; tables singular in `gold_access_bench`.
- No CareQuest / org affiliation language; no clinical “diagnosis” wording.

---

### Task 1: Five Access fixtures

**Files:**
- Modify: `benchmarks/access_bench/items/simulated_access_phi_items.jsonl`
- Modify: `python/tests/test_access_phi_items.py` (assert `len >= 5`)
- Test: `python/tests/test_access_phi_items.py`

**Interfaces:**
- Consumes: existing `access_phi_items` contract
- Produces: ≥5 validated rows; new ids `ACC_ADA_PHI_001`, `ACC_EPS_PHI_001`

- [ ] **Step 1: Write the failing test**

```python
def test_simulated_access_phi_items_file_exists_and_loads():
    rows = api.load_items()
    assert len(rows) >= 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && pytest -q tests/test_access_phi_items.py::test_simulated_access_phi_items_file_exists_and_loads -v`
Expected: FAIL (only 3 items)

- [ ] **Step 3: Add two JSONL rows** (ADA accommodation + EPSDT/CHIP pathway; names from `CH_FIRST`×`CH_LAST`; phones/SSNs reserved shapes)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python && pytest -q tests/test_access_phi_items.py`

- [ ] **Step 5: Commit** (when the owner asks)

---

### Task 2: `access_batch` simulated runner

**Files:**
- Create: `python/health_transformation_lab_nlp/access_batch.py`
- Create: `python/tests/test_access_batch.py`

**Interfaces:**
- Consumes: `access_phi_items.load_items`, `access_keypoint_judge`, `deid.leak_check`, optional chat callable
- Produces:
  - `load_batch(limit: int = 5) -> list[dict]`
  - `run(*, endpoints: list[str], limit: int = 5, mode: str = "simulated", judge_endpoint: str = "sim:judge", max_usd: float = 1.0, run_id: str, run_ts, git_commit: str, chat=None, usd_per_million_in: float = 0.0, usd_per_million_out: float = 0.0) -> dict[str, pd.DataFrame]` with keys `dim_access_question`, `fact_access_answer`
  - Analysis column names as in the design doc (before `to_gold`)

- [ ] **Step 1: Failing tests** for simulated 5×2 matrix, leaky stub → `is_phi_leak`, `limit > n` raises, `mode` default simulated

- [ ] **Step 2: Implement `access_batch.py`** with scrubbed simulated answers and deterministic simulated judge verdicts

- [ ] **Step 3: pytest `tests/test_access_batch.py` green**

---

### Task 3: Gold declarations

**Files:**
- Modify: `python/health_transformation_lab_nlp/gold_names.py`
- Modify: `diagrams/_build/gold_model.py`
- Modify: `python/health_transformation_lab_nlp/table_comments.py` (`GOLD_SCHEMA`)
- Test: extend `python/tests/test_access_batch.py` or `test_gold_model.py` / `test_table_comments.py`

**Interfaces:**
- Produces: `to_gold(df, "dim_access_question")`, `to_gold(df, "fact_access_answer")`; comments under schema `gold_access_bench`

- [ ] **Step 1: Failing test** that `to_gold` knows both tables and `declared("gold_access_bench", …)` works

- [ ] **Step 2: Add TABLES + gold_model Table entries + GOLD_SCHEMA map**

- [ ] **Step 3: Tests green**

---

### Task 4: Databricks notebook + job

**Files:**
- Create: `databricks/notebooks/16_access_llm_batch.py`
- Modify: `databricks/resources/jobs.yml`
- Modify: `databricks.yml` if new vars needed (`access_llm_endpoints`, etc.)
- Test: `python/tests/test_bundle.py` asserts job `access_llm_batch` exists with expected widgets/params

**Interfaces:**
- Widgets: `endpoints`, `limit`, `judge_endpoint`, `max_usd`, `mode`, `run_id`, `git_commit`, `telemetry`
- Writes: `health_transformation_lab.gold_access_bench.{dim_access_question,fact_access_answer}` via `replace_batch(..., {"run_id": run_id})`

- [ ] **Step 1: Failing bundle test** for job name and notebook path

- [ ] **Step 2: Add notebook + job YAML**

- [ ] **Step 3: Bundle + access tests green**

- [ ] **Step 4: Update `specs/043-access-llm-batch/plan.md` + `tasks.md`; README note under AccessBench folder**

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| US1 five fixtures | 1 |
| US2 simulated batch | 2 |
| US3 gold names / comments | 3 |
| US4 job + idempotent write | 4 |
| FR-001–007 | 1–4 |

## Self-review

- No TBD placeholders in interfaces.
- Analysis vs gold names match the design doc.
- Default mode simulated throughout.
