# PR 932 review: AccessBench answers are not cut off, and a cut-off answer is marked

Closes #931. Range: `origin/main..fix/931-043-answer-token-cap`. Files: `access_batch.py`, `gold_names.py`,
`diagrams/_build/gold_model.py` and the rebuilt gold diagrams, `contracts/gold_access_bench/fact_access_answer.odcs.yaml`,
the notebook `16_access_llm_batch.py`, `databricks.yml`, `databricks/resources/jobs.yml`, the two test files, and
`specs/043-access-llm-batch/` (US6).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none.
- **Real data:** none.
- **Settings:** one new bundle variable, `access_answer_max_tokens` (default `1500`), declared once with a
  description, with the same name in every target.

## Findings (verified)

1. **Root cause:** `_answer` built `OpenAIChat(model=endpoint)`, which inherits the chart reader's `max_tokens=300`.
   In the 2026-11-24 live runs, 37 of 60 answers hit that cap. Gemma 3 12B and gpt-oss-120b hit it on all 15, and
   one gpt-oss answer was 33 characters long. Those scores are biased toward short answers. The two runs stay in
   gold under their run ids; the reruns get new ones.
2. **The judge's client is unchanged.** It still uses 300, which is enough for its short JSON verdict; the parse
   errors in those runs were zero.
3. **The schema change is additive:** `is_truncated` is declared in `gold_names`, `gold_model` (diagrams rebuilt with
   `gold_erd.py`) and the ODCS contract. `delta.replace_batch` writes with `mergeSchema`, so the existing table gains
   the column, which is null on old rows.
4. **Spec first:** US6 was in the spec, plan and tasks before the code. The 4 new and changed tests failed first.

## Checks

- `pytest tests/test_gold_model.py tests/test_docs_current_build.py tests/test_data_contracts.py
  tests/test_table_comments.py tests/test_sql_conventions.py tests/test_access_batch.py tests/test_bundle.py
  tests/test_telemetry_calls.py`: 181 passed.

## Verdict

Approve, merging once CI is green. The reruns that follow (T010) use pay-per-token endpoints under a $1 cap, as the
owner asked on 2026-11-24.
