# Tasks: AccessBench LLM batch (spec 043)

- [x] T001 Five synthetic Access fixtures (`ACC_ADA_PHI_001`, `ACC_EPS_PHI_001`) — #917
- [x] T002 `access_batch.load_batch` / `run` with simulated mode and `max_usd` gate — #917
- [x] T003 Gold names + `gold_model` + `table_comments.GOLD_SCHEMA` + ODCS — #917
- [x] T004 Notebook `16_access_llm_batch.py` + job `access_llm_batch` (default `simulated`) — #917
- [x] T005 [US5] Failing tests: question sets in `test_access_batch.py`, variable and parameter in `test_bundle.py` — #929
- [x] T006 [US5] `access_batch.FIXTURES`, `load_batch(fixture=)`, `run(fixture=)`; leak check for items without planted details — #929
- [x] T007 [US5] Notebook widget `fixture`, bundle variable `access_llm_fixture`, job parameter — #929
- [x] T008 [US6] Failing tests: the cap reaches the client, `is_truncated`, gold mapping, bundle variable — #931
- [x] T009 [US6] `answer_max_tokens` through `run`, `_answer`, notebook, bundle and job; `is_truncated` column, contract and diagrams — #931
- [ ] T010 [US6] Rerun both question sets live and compare with the 2026-11-24 runs — #931
