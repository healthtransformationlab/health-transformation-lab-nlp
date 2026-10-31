# PerioBench results: what rules, encoders and LLMs answered on 240 review notes

Every method's answers on the same 240 synthetic dental review notes, and their scores against the truth:
rule-based methods, TF-IDF with logistic regression, fine-tuned encoders (BERT, ModernBERT, clinical and
biomedical variants) and large language models (MedGemma, Llama). Use it to compare a new model without rerunning
these. Part of [PerioBench](https://healthtransformationlab.org) from the Health Transformation Lab.

## Quick start

```python
from datasets import load_dataset

board = load_dataset("healthtransformationlab/perio-bench-results", "leaderboard", split="train").to_pandas()
print(board.sort_values("accuracy", ascending=False)[["method", "accuracy", "acc_lo", "acc_hi"]].head(10))
```

Score your own model on the test notes of
[healthtransformationlab/perio-bench-notes](https://huggingface.co/datasets/healthtransformationlab/perio-bench-notes)
and put it beside these. **Try it in your browser:** [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/healthtransformationlab/health-transformation-lab-nlp/blob/main/notebooks/perio_bench_quickstart.ipynb)
The same results are on Kaggle:
[kaggle.com/datasets/jcblearning/perio-bench-results](https://www.kaggle.com/datasets/jcblearning/perio-bench-results).

## What's inside

| Config | What it is |
|---|---|
| `leaderboard` (default) | One row per method: accuracy with a 95% CI, stage IV recall, unsafe-error rate, calibration error |
| `predictions` | Every method's answer per review note, one column per method; join on `visit_id` |
| `probabilities` | Class probabilities, where a method gives them |
| `llm_details` | The LLM readers' raw answers, quoted evidence, quote-gate result, tokens and latency |
| `judge_metrics` | An LLM judge's reading of the same charts and the metrics computed against it |

The `raw/` folder holds the original files, as on Kaggle, including one `ai_predictions_<model>.csv` per model.

**Everything here is synthetic**: measurements on synthetic notes, scored against the generator's truth, not
clinical performance. A score here is agreement with the synthetic answer key, which the repo's own 2017 rules made, so
methods that use those rules (marked † on the leaderboard) start with an advantage, and 13 of the 240 notes can't be
staged at all. How scoring works, and how real records would be scored: [docs/scoring.md](https://github.com/healthtransformationlab/health-transformation-lab-nlp/blob/main/docs/scoring.md). This is a personal learning project, **not affiliated** with any employer, institution or
company. The results are exercises, not findings: not evidence about any model, product or population, and
**not for clinical use**. Simulated dry-run outputs are left out. Cost columns are **illustrative** placeholder
rates, not quotes.

## How it was made

[github.com/healthtransformationlab/health-transformation-lab-nlp](https://github.com/healthtransformationlab/health-transformation-lab-nlp),
`python/scripts/11_ai_predict.py` (one run per model), `28_ladder_vs_truth.py` and `36_judge_scorecard.py`.
Models, prompts and settings are in the repository's `models.yaml`; where each method comes from is in
`docs/algorithms.md`.

## Licence and citation

CC BY 4.0 (these files; each model keeps its own licence). Please cite: Bowyer J., *health-transformation-lab-nlp:
synthetic dental notes, OMOP and periodontal status benchmark*, https://github.com/healthtransformationlab/health-transformation-lab-nlp.
