# Feature Specification: MedGemma as a note reader, judge candidate and fine-tune target

**Feature Branch**: `004-medgemma-reader`

**Created**: 2026-10-25

**Status**: v1 implemented (reader, judge family rule, LoRA script); not yet run on real MedGemma weights

**Input**: "Use MedGemma and possibly extend it." See [docs/medgemma.md](../../docs/medgemma.md).

> **Exploratory, for learning and training.** Personal learning project; public
> information only; not affiliated with Google. Synthetic notes only.

## Context

MedGemma (Google HAI-DEF) is an open medical LLM family: 4B multimodal and 27B
text, with MedGemma 1.5 4B released January 2026. It has not been reported on
dental notes. The repo's ladder has encoders and rules but no generative reader
that can run inside our own environment.

## User Scenarios & Testing

### User Story 1 - Zero-/few-shot MedGemma note reader (P1)

As the data scientist, I want MedGemma to read each de-identified note and
return status, grade and extent as JSON, scored like every other rung.

**Independent Test**: `11_ai_predict.py --rung medgemma-4b-it --backend simulated`
writes predictions; the reader's parsing, gate and fallback are unit-tested.

1. **Given** a valid JSON answer whose quote is in the note, **Then** the status is used and `gate_ok` is true.
2. **Given** invalid JSON, an unknown status, or a quote not in the note, **Then** the prediction falls back to `note_rules` and the row is flagged (`fallback`, `error`).
3. **Given** a note where the residual PHI scan finds anything, **Then** it is not sent to the model (fallback, flagged).
4. **Given** `--shots k`, **Then** k synthetic training notes per status are included as examples, chosen by seed.

### User Story 2 - Several ways to run it (P1)

`hf` (local transformers, GPU or CPU), `openai` (any OpenAI-compatible endpoint:
Databricks Model Serving, vLLM, Ollama), `simulated` (dry run, no model, files
prefixed `simulated_`).

### User Story 3 - Judge family rule (P2)

When a MedGemma rung's predictions are being judged, a Gemma-family judge is
not selected. Families come from `models.yaml`.

### User Story 4 - Fine-tune ("extend") (P2)

A LoRA script trains MedGemma on `train.csv` in the reader's prompt/answer
format, saving an adapter that the `hf` backend can load.

### User Story 5 - Reference answers per field (P1) #130

As the data scientist, I want the correct answer for every field the reader returns (status, grade, extent) on
every review visit, so each field can be scored. The synthetic generator already decides these before writing
the note, so the reference comes from its truth (no manual review, no anchoring on the model's answers).

**Independent Test**: `51_reference_answers.py` writes `answer_key/reference_answers.csv`; a test checks one row
per review visit, grade and extent `NA` unless periodontitis, and that the committed file matches the answer key.

1. **Given** the answer key, **Then** the table has one row per `visit_id` and one column per reader field, with its source on every row.
2. **Given** a note whose stated status differs from the truth, **Then** the reference keeps the truth and `note_stated_status` shows the note's.
3. **Given** a field the reader doesn't return (pocket depths, bleeding), **Then** the table has no column for it.

### User Story 6 - MedGemma accuracy per field (P1) #132

As the data scientist, I want accuracy per field (status, grade, extent) with n and a 95% CI for each MedGemma
run, so I can see which fields the reader gets right and which it doesn't.

**Independent Test**: `52_medgemma_field_accuracy.py` writes `ladder/medgemma_field_accuracy.csv`; unit tests
cover the scoring rules, the Wilson CI and the MLflow metric names; `r/tests/test_parity.R` recomputes the table
in base R (1e-9).

1. **Given** a complete run, **Then** status is scored on every visit from the rung's answer (after fallback), equal to its headline accuracy.
2. **Given** a visit whose truth is not periodontitis, **Then** it is left out of grade and extent; **given** a fallback row, **Then** its grade and extent count as wrong.
3. **Given** a partial (`--limit`) run, **Then** it is not scored.
4. **Given** a reader run with MLflow on, **Then** `field_accuracy_<field>` and `field_n_<field>` are logged.

### Edge Cases

- Model wraps JSON in prose or code fences: parse the first `{...}`.
- Prompt sensitivity: two prompt variants, selectable.
- Long notes: truncated only by the model context (128K), so no truncation needed here.

## Requirements

- **FR-001**: `llm_reader.py`: prompt (shared status criteria with the judge), parser, gate, fallback, PHI pre-check.
- **FR-002**: Backends hf / openai / simulated behind one interface; per-note details (raw output, quote, tokens, latency, fallback, error) written alongside predictions.
- **FR-003**: `make_rung` builds an `LLMReader` for any `role: llm` model in `models.yaml`.
- **FR-004**: Costs: MedGemma entries in `costs.yaml` (assumed GPU throughput, ILLUSTRATIVE) and simulated predictions in `14_benchmark_cost.py --simulate-missing`.
- **FR-005**: `15_judge.py` adds families of evaluated LLM rungs to the excluded judge families automatically.
- **FR-006**: `17_medgemma_lora.py` + `llm_reader.sft_records`.
- **FR-007**: Databricks notebook running the reader on Free Edition serverless GPU.
- **FR-008**: R parity unaffected: predictions are CSV in the existing format.
- **FR-009**: `reference_answers.py` + `51_reference_answers.py`: reference answers per reader field from the generator's truth (US5).
- **FR-010**: `reference_answers.field_accuracy` + `52_medgemma_field_accuracy.py`: per-field accuracy with a 95% Wilson CI per run, R twin `r/R/17_spec004.R`, logged to MLflow (US6).

## Success Criteria

- **SC-001**: Unit tests cover parse, gate, fallback, PHI check, few-shot selection, OpenAI request/response, simulated backend, SFT records, family rule.
- **SC-002**: Simulated dry run produces predictions and appears in the cost frontier as `sim:medgemma-*`.
- **SC-003**: Real-weights run (later, on GPU) reports agreement, kappa, unsafe rate and by-level results, plus gate-fail and fallback rates.

## Assumptions

- Simulated error rates by difficulty (L1 5%, L2 12%, L3 30%) are placeholders for the dry run only.
- MedGemma weights need a Hugging Face account that has accepted the HAI-DEF terms.
