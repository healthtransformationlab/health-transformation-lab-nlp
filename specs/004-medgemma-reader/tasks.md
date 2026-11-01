# Tasks: MedGemma reader

## Phase 1: Setup
- [x] T001 Public model facts (variants, terms, MedGemma 1.5 id); docs/medgemma.md
- [x] T002 Spec, plan, constitution check

## Phase 2: Tests first
- [x] T003 [P] [US1] parse / gate / fallback / PHI pre-check
- [x] T004 [P] [US1] few-shot selection seeded, k per status
- [x] T005 [P] [US2] OpenAI-compatible backend against a local fake server; simulated backend
- [x] T006 [P] [US3] families of evaluated LLM rungs
- [x] T007 [P] [US4] SFT records in the reader format
- [x] T008 judge prompt text unchanged after sharing criteria

## Phase 3: Implementation
- [x] T009 `llm_reader.py`, `judge.CRITERIA`
- [x] T010 `make_rung` + registry fields + MedGemma 1.5 entry
- [x] T011 `11_ai_predict.py` backends; simulated dry run
- [x] T012 costs.yaml entries; `14_benchmark_cost.py` simulated MedGemma
- [x] T013 `15_judge.py` automatic family exclusion
- [x] T014 `17_medgemma_lora.py`; Databricks notebook 03

## Phase 4: Later (needs GPU + HAI-DEF terms accepted)
- [ ] T015 Run 4B zero-shot on the review set (Free Edition serverless GPU); record gate-fail and fallback rates
- [ ] T016 Measure real throughput; replace assumed notes/sec in costs.yaml
- [ ] T017 Two prompt variants: report prompt sensitivity
- [ ] T018 LoRA fine-tune on train.csv; compare with BERT ladder and on the cost frontier
  - [x] T018a Comparison script `29_medgemma_vs_bert.py` (paired CI vs best encoder, by difficulty, fallback, cost), tagged output files per variant, R twin; notebook 03 runs LoRA + comparison. Dry run only so far.
- [ ] T019 27B text via a paid GPU endpoint, if 4B is promising
- [x] T020 No-token Kaggle runs: KerasHub backend vs Kaggle Models weights converted to HF (`kaggle/keras_to_hf.py`), #97.
  Kaggle, 2026-10-28, 10 synthetic notes, bfloat16 on one T4: same prediction on 10/10 notes, gate pass 100% for
  both, agreement with the answer key 7/10 for both, 35.5 s/note keras vs 28.3 hf. Kept the converted-HF path
  (one backend, faster); the KerasHub backend was not merged. Ten notes only: not a result.

## Phase 5: Per-field accuracy (#130, #132)
- [x] T021 [US5] Reference answers per reader field (status, grade, extent) from the generator's truth:
  `reference_answers.py`, `51_reference_answers.py`, `answer_key/reference_answers.csv`; test first (#130).
  The reader returns no pocket depths or bleeding, so there is nothing to score them against.
- [x] T022 [US6] Accuracy per field (n, accuracy, 95% Wilson CI) for each committed MedGemma run:
  `reference_answers.field_accuracy`, `52_medgemma_field_accuracy.py`, `ladder/medgemma_field_accuracy.csv`;
  R twin `r/R/17_spec004.R` + parity check 9e; MLflow metrics from the script and from `11_ai_predict.py` (#132)
