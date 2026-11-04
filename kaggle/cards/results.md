# Dental periodontal note classifier benchmark results

What rule-based methods, classical machine learning (TF-IDF with logistic regression), fine-tuned encoders
(BERT, ModernBERT, clinical and biomedical variants) and large language models (MedGemma, Llama) answered on
the same 223 synthetic dental review notes, with their scores against the generator's truth. Pair it with the
notes dataset (*Synthetic dental periodontal notes and charts*) to compare a new model without rerunning these.

**These are measurements on synthetic notes**, made by a personal learning project that is **not affiliated**
with any employer, institution or company. They are exercises, not findings: not evidence about any model,
product or population, and **not for clinical use**. Simulated dry-run outputs are left out. Cost columns
(`corpus_usd_illustrative` in `ladder/`, `usd` in `judge/judge_run.csv`) are **illustrative**: placeholder
rates from the repo's `costs.yaml` and the judge endpoint's per-token price at the time, not quotes.

## Files

- **Per model:** `ai_predictions_<model>.csv`. One row per review note, with the predicted status and, where
  the model gives them, class probabilities. `llm_details_<model>.csv` holds the LLM readers' raw answer,
  quoted evidence, quote-gate result, tokens and latency.
- **Leaderboard:** `ladder/ladder_vs_truth.csv`. Accuracy with a 95% CI, stage IV recall, unsafe-error rate
  and calibration error per method. The other `ladder/` files hold the merged predictions and the MedGemma vs
  encoder comparison, overall and by difficulty level.
- **Judge:** `judge/`. An LLM judge's reading of the same charts and the metrics computed against it
  (judge scorecard).

Join on `visit_id` with `review_key.csv` from the notes dataset for the truth and difficulty.

## How it was made

[github.com/healthtransformationlab/health-transformation-lab-nlp](https://github.com/healthtransformationlab/health-transformation-lab-nlp), `python/scripts/11_ai_predict.py`
(one run per model), `28_ladder_vs_truth.py` and `36_judge_scorecard.py`. Models, prompts and settings are in
the repo's `models.yaml`.

## Licence and citation

CC BY 4.0 (these files; each model keeps its own licence). Please cite: Bowyer J., *health-transformation-lab-nlp:
synthetic dental notes, OMOP and periodontal status benchmark*, https://github.com/healthtransformationlab/health-transformation-lab-nlp.
