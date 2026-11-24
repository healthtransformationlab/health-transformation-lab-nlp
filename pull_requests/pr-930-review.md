# PR 930 review: the ten periodontal-screening questions run in the AccessBench batch

Closes #929. Range: `origin/main..feat/929-043-screening-batch`. Files: `access_batch.py`, the notebook
`16_access_llm_batch.py`, `databricks.yml` (`access_llm_fixture`), `databricks/resources/jobs.yml` (`fixture`),
`test_access_batch.py`, `test_bundle.py`, `benchmarks/access_bench/README.md`, `specs/043-access-llm-batch/` (US5).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none. No credential or setting holds a secret.
- **Real data:** none. Both question sets are synthetic and already committed (#892, #919).
- **Settings:** one new bundle variable, `access_llm_fixture` (default `phi`), declared once with a description. The
  same name applies in every target, and the default keeps today's behaviour.

## Findings (verified)

1. **The leak check would have crashed on screening questions:** `known_phi_for_leak_check` indexes
   `row["planted_phi"]`, and those items have none. The batch now skips the check for them and records
   `is_phi_leak = false`. A test scores the ten in simulated mode and expects no leak and no error.
2. **No schema change:** the screening items carry everything `dim_access_question` needs (domain, persona, evidence
   source; the level comes from `infer_level`), so `to_gold` and the ODCS contracts are unchanged.
3. **Spec first:** US5 was in the spec, plan and tasks before the code. The tests failed (5 of them) before the code
   was written.

## Checks

- `pytest tests/test_access_batch.py tests/test_bundle.py tests/test_telemetry_calls.py tests/test_access_hard_items.py
  tests/test_access_phi_items.py`: 67 passed.

## Verdict

Approve. Merging once CI is green. The live run that follows uses pay-per-token endpoints under a $1 cap, as the
owner asked.
