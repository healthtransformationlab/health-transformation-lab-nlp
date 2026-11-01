# R side

Same benchmark, same notes, same patient split, same scorer output as the
Python side. A result from here and a result from `python/` land in the same
`data/results/` folder in the same columns.

## What's here

| File | What it does | Needs |
|------|--------------|-------|
| `R/labels.R` | Chart → status (R twin of `labels.py`) and the rules baseline | base R |
| `../eval/score.R` | Shared scorer (R twin of `score.py`) | base R |
| `tests/test_parity.R` | Proves R and Python agree on labels, rules predictions and metrics | base R |
| `run_ladder.R` | Runs rungs and writes results | base R for rules; tidymodels for the rest |
| `R/01_etl_synthea.R` | Full Synthea → OMOP CDM 5.4 load with OHDSI `ETLSyntheaBuilder`, plus the dental extension | ETL-Synthea, Postgres / Lakebase (or Databricks SQL), Athena vocab |
| `R/02_baselines.R` | Structured and TF-IDF baselines | tidymodels, textrecipes, glmnet |
| `R/03_encoders.R` | Encoder rungs: frozen embeddings (`text` pkg) or fine-tune via reticulate | `text` + Python env |
| `install.R` | Installs all of the above | — |

## Do I need a GPU?

No. At this sample size (~750 notes) everything runs on a laptop CPU. A GPU
only matters for the two `-large` models or for thousands of notes.

Rough CPU times (estimates, not measured):

| Step | Time |
|------|------|
| Rules, structured, TF-IDF baselines | seconds |
| Frozen embeddings (DistilBERT, BERT-base) | ~1–5 min |
| Fine-tune DistilBERT / BERT-base, 2 epochs | ~5–20 min |
| ModernBERT-large, BioClinical-ModernBERT-large | 30–60+ min; use a GPU (Free Edition's limited serverless GPU from Python, or paid compute) |

Apple Silicon Macs use the built-in GPU (MPS) for fine-tuning automatically.

## Run it locally

**Prerequisites:** R 4.2+ (RStudio optional), Python 3.10+, Git. Java 11+
only for the optional Synthea / full-OMOP path (step 6).

1. **Clone and open** the repo in RStudio. The working directory must be the
   repo root; every script uses paths relative to it.

   ```bash
   git clone https://github.com/healthtransformationlab/health-transformation-lab-nlp
   ```

2. **Build the data once.** The note generator is Python-only for now:

   ```bash
   cd python
   pip install -e .
   python scripts/01_build_dataset.py --n-people 300
   python scripts/02_split.py
   python scripts/export_rules_predictions.py
   cd ..
   ```

   This writes `data/labels/labeled_notes.csv` and `split.csv`. R reads only
   those files from here on.

3. **Install R packages and check parity** (should end with `parity OK`):

   ```bash
   Rscript r/install.R
   Rscript r/tests/test_parity.R
   ```

4. **Baselines:**

   ```bash
   Rscript r/run_ladder.R rules_baseline structured_baseline tfidf_logreg
   ```

5. **BERT models.** One-time setup in R (creates a separate Python env with
   torch + transformers; several minutes):

   ```r
   text::textrpp_install()
   text::textrpp_initialize(save_profile = TRUE)
   ```

   Then:

   ```bash
   Rscript r/run_ladder.R distilbert-base+frozen     # start here: cheap, all R
   Rscript r/run_ladder.R distilbert-base+finetune   # same numbers as the Python side
   ```

   `+finetune` needs `pip install -e "python[models]"` in the Python that
   reticulate uses. If it picks the wrong one, set `RETICULATE_PYTHON` to the
   right interpreter before starting R.

6. **Optional: full OMOP CDM from Synthea.** Not needed for the baselines.

   ```bash
   ./synthea/run_synthea.sh 500
   # download vocabularies from https://athena.ohdsi.org into data/vocab/
   Rscript r/R/01_etl_synthea.R
   ```

Results from both languages land in `data/results/`; that folder is the
combined leaderboard.

## Two kinds of encoder result

- `<model>+frozen` — embeddings from the pretrained model, glmnet on top.
  Pure R, cheap, tells you what the pretraining already knows. **Not**
  comparable to the Python fine-tuned numbers.
- `<model>+finetune` — calls the Python trainer through reticulate, so the
  number is the same experiment as the Python rung. Use this when the two
  leaderboards must line up.

## Databricks

Databricks Free Edition serverless runs Python and SQL only, so the R side
runs locally or in Posit. The Delta tables the notebook writes
(`health_transformation_lab.gold_perio_bench.dim_study_note`, `benchmark_metric`) can be read from R
with `sparklyr` / Databricks Connect when that's useful. In a paid workspace
with classic compute, these scripts run in an R notebook unchanged.

## Status

Tested here: `labels.R`, `score.R`, `test_parity.R`, `run_ladder.R rules_baseline`
(R and Python agree on all 754 notes and every metric to 1e-16).
Written but not yet run: `01_etl_synthea.R`, `02_baselines.R`, `03_encoders.R`
— they need packages this repo's CI doesn't install yet. Expect the first run
of steps 4–6 to need a fix or two; open an issue with the error.
