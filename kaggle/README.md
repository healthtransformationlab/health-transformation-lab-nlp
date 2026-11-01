# Kaggle: free GPUs, public datasets

This folder runs the GPU work on Kaggle's free GPUs, for when Databricks Free Edition has none, and publishes
the synthetic data and results as Kaggle datasets. Everything is started from GitHub Actions, never from a
laptop, so each Kaggle run or version matches a commit. Everything on Kaggle is public: it holds synthetic
data only, and no token is ever stored in it.

## What's on Kaggle

| On Kaggle (user `jcblearning`) | What it is | Made by (Actions tab) | Files here |
|---|---|---|---|
| Notebook `perio-bench-medgemma-reader` | MedGemma 1.5 4B reads the 240 review notes | *Run MedGemma on a free Kaggle GPU* | `medgemma_reader.ipynb`, `keras_to_hf.py`, `hf_config/`, `gemma3_chat_template.jinja` |
| Notebook `perio-bench-encoder-gpu` | Fine-tunes the large encoders (ModernBERT-large, Longformer, GatorTron) | *Fine-tune the GPU encoders on a free Kaggle GPU* | `encoder_gpu.ipynb` |
| Dataset `perio-bench-notes` | Synthetic notes, labels, structured visits, 240-note review set and answer key | *Publish datasets (Kaggle and Hugging Face)* | `publish.py`, `cards/notes.md` |
| Dataset `perio-bench-results` | Every model's answers on the review set, the leaderboard, the judge scorecard | *Publish datasets (Kaggle and Hugging Face)* | `publish.py`, `cards/results.md` |
| Notebook `perio-bench-quickstart` (spec 025) | Loads both datasets, trains a baseline on a CPU in about a minute, scores it beside the leaderboard | *Publish datasets (Kaggle and Hugging Face)* | `../notebooks/perio_bench_quickstart.ipynb`, `prepare_kernel.py --job quickstart` |
| Benchmark task `perio-bench` (Kaggle Benchmarks) | The reader task Kaggle's leaderboard runs: read a note, name the status, quote it; a judge checks it (`docs/kaggle_benchmarks.md`) | *Run PerioBench on Kaggle Benchmarks* | `perio_bench_task.py`, `../python/health_transformation_lab_nlp/kbench.py` |
| Model `perio-bench-note-classifier` (spec 020 US3) | The top fine-tuned note classifier, ModernBERT-base class-weighted, in transformers format (Apache 2.0) | *Fine-tune the GPU encoders on a free Kaggle GPU* with `save_model` | `publish_model.py`, `cards/model.md` |

The notebook `dental-omop-medgemma-keras-test` was a one-off comparison (MedGemma through Keras vs converted to
transformers; the decision is in PR #99) and can be deleted.

**Renamed in spec 022.** Kaggle can't rename a notebook or dataset, so the next run of each workflow creates it
under the new name. Then delete the old ones on kaggle.com (each page's ⋮ menu → *Delete*): the notebooks
`health-transformation-lab-medgemma-reader` and `dental-omop-encoder-gpu`, the datasets
`synthetic-dental-perio-notes` and `dental-perio-benchmark-results`, and the collection "Dental OMOP NLP".

## One-time setup

1. Kaggle account with a **verified phone number** (needed for GPUs and internet).
2. Kaggle → Settings → API → **Generate New Token**. Save it as the secret `KAGGLE_API_TOKEN`, and your Kaggle
   username as the variable `KAGGLE_USERNAME`, in the GitHub environment **`dev`** (repo Settings → Environments).
   Delete the token on Kaggle when you no longer need it.

No Hugging Face token: MedGemma comes from Kaggle Models (`keras/medgemma`) and is converted on Kaggle; the
encoders are public.

## Running the GPU notebooks

Actions → pick the workflow → **Run workflow**:

- **`limit` 10** is a test (10 notes; encoders train 1 epoch). It takes 10-15 minutes and is never committed.
- **`limit` 0** is the full run: all 240 notes, a few hours. With `open_pr` on, the workflow opens a pull
  request with `ai_predictions_<model>.csv` (and `llm_details_` for MedGemma). Once it's merged, the dev
  deploy's **Load results** job puts them in the Delta tables (spec 016).
- If it runs longer than the workflow can wait, run again with **`collect_only`** to fetch the outputs of the
  last Kaggle run.

The workflow prints the end of the Kaggle log (`show_log.py`) and keeps the outputs as an artifact.

## Publishing the datasets

Actions → *Publish datasets (Kaggle and Hugging Face)* → Run workflow, with `platform` `both` or `kaggle`
and `dataset` `both`, `notes` or `results`. With `both` datasets, it also pushes the quickstart notebook and
waits for its run on Kaggle (a minute or two), which proves it works there. The same datasets go to Hugging Face
from the same workflow ([huggingface/README.md](../huggingface/README.md)). The first run creates
each dataset, public and CC BY 4.0; later runs add a version that names the commit. `publish.py` lists
exactly which files go in. Nothing from `data/external/` (others' datasets) and no `simulated_*` file is ever
included. The cards in `cards/` become the dataset pages; edit them there, not on kaggle.com, or the next
version overwrites your edit.

## Publishing the note classifier

Actions → *Fine-tune the GPU encoders on a free Kaggle GPU* → Run workflow with **`rungs`** `modernbert-base+cw`,
**`lr_overrides`** empty, **`save_model`** `modernbert-base+cw` and **`limit`** `0`. The notebook keeps that rung's
fine-tuned weights (`/kaggle/working/model`), and after the full run the workflow publishes them with
`publish_model.py`: the model `perio-bench-note-classifier` public the first time, its transformers instance
`modernbert-base-cw`, then a new version per run. The card is `cards/model.md` plus the scores of that same run's
review-set predictions (the leaderboard's scoring); a test run (`limit` 10) is never published. The weights go to
Kaggle, not the workflow artifact. A full run takes hours: to collect it later, run the workflow again with
**`collect_only`** on and the same `save_model` and `limit` 0. The card names the commit the notebook trained.

## The collection

A Kaggle collection is a private list: kaggle.com offers no setting to make one public, and Kaggle's API can't
make collections. So the shared starting point is the table under [What's on Kaggle](#whats-on-kaggle), and every
item there is public on its own. For your own list, on kaggle.com: your profile → **Collections** → **New
collection** "Health Transformation Lab: Perio Bench", then add the three notebooks, the two datasets and the model
`perio-bench-note-classifier` (each page's ⋮ menu → *Add to collection*). It's optional (issue #270).

## When something fails

| Symptom | Cause and fix |
|---|---|
| "Kaggle rejected the credentials" | Regenerate the token; check `KAGGLE_USERNAME` is the name in kaggle.com/<username>, not your email |
| Run stops at "phone verification" or has no GPU | Verify your phone on Kaggle; GPU quota is about 30 hours a week |
| Status `error` | Read the log the workflow printed; the full log is in the run's artifact |
| Still running after the wait | Run again with `collect_only` |
| The results PR has no CI | PRs opened by the workflow token don't start CI: push any commit to the branch |

## Other files

- `prepare_kernel.py` fills a notebook's settings and writes `kernel-metadata.json` (GPU, internet, the
  MedGemma model source).
- `record_results.py` copies a full run's prediction files into `data/datasets/` and notes their source in
  `results_manifest.csv`.
- `show_log.py` prints a Kaggle log without the warnings.

More: `docs/medgemma.md` (why Kaggle, how MedGemma is loaded), spec 016 (results into Delta), spec 020
(publishing).
