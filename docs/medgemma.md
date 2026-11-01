# MedGemma: how it could be used here (exploratory note)

> **Personal learning project.** Ideas for learning and practice, using public
> information only. Not affiliated with Google or any other organization, and
> not an organization's plan. See [DISCLAIMER](../DISCLAIMER.md).

## What MedGemma is (public sources)

- Open models from Google's Health AI Developer Foundations (HAI-DEF). MedGemma 1:
  a **4B multimodal** model (pre-trained and instruction-tuned), a **27B
  text-only** model and a **27B multimodal** model. Text and image in, text out;
  context up to 128K tokens. Images were radiology (chest X-ray, CT),
  dermatology, ophthalmology and histopathology; **dental imaging is not
  mentioned**. The image encoder is also released on its own as **MedSigLIP**,
  recommended for classification and retrieval without text generation
  ([model card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card-v1)).
- **MedGemma 1.5** (reported January 2026): 4B for offline / low-resource use,
  27B still available; adds 3D CT/MRI and whole-slide pathology, longitudinal
  X-rays, and better extraction from medical documents and EHR question
  answering; alongside a new speech model, MedASR
  ([BioPharmaTrend](https://www.biopharmatrend.com/news/google-updates-open-medical-ai-suite-with-new-imaging-and-speech-models-launches-100k-developer-hackathon-1464/)).
- **Terms and limits:** governed by the HAI-DEF terms of use; a starting point
  for developers, not intended to directly inform diagnosis or treatment;
  must be validated on representative data; prompt-sensitive; watch for data
  contamination (model card).

## Where it fits in this repo

| # | Use | How | Effort | Fits with |
|---|-----|-----|--------|-----------|
| 1 | **Note reader (LLM rung)** | Zero-/few-shot prompt: note in, JSON status / stage / grade / extent out, same schema and quote gate as the judge. 4B and 27B-text as two rungs | Low | Model ladder; difficulty levels; cost frontier |
| 2 | **Fine-tuned note reader ("extend")** | Parameter-efficient fine-tuning (e.g. LoRA) of the 4B model on `train.csv` (synthetic labels), structured JSON output. Compare against the BERT ladder: does a 4B generative model beat a fine-tuned 150M encoder enough to justify its cost? | Medium; needs a GPU | BERT ladder; harm-weighted errors |
| 3 | **Judge candidate** | Add to the judge bake-off. The same-family rule applies: if a MedGemma model is being graded, the judge must be from a different family, and vice versa | Low | `15_judge.py` bake-off |
| 4 | **Note paraphraser for synthetic data** | Rewrite generated notes in varied clinical phrasing while keeping the label (as the UTHealth team did with GPT-4), then check with the reader and judge that the label survived. Reduces the "same author wrote notes and rules" problem | Medium | Spec 001 note realism |
| 5 | **Radiograph extension ("extend", images)** | MedGemma wasn't trained on dental images. Options: (a) MedSigLIP image embeddings + a small classifier for bone loss; (b) fine-tune the 4B multimodal model on a public, licensed dental radiograph dataset. Output feeds the same structured radiograph schema as spec 003 | High; images and licences | Radiograph exploration |
| 6 | **Grade from history** | Use the long context to read several visits at once and estimate progression (grade is about rate of change) | Medium | Grade reader |

## Licence requirement

Every MedGemma model is **gated** on Hugging Face under the
[HAI-DEF terms of use](https://developers.google.com/health-ai-developer-foundations/terms).
Before any run: accept the terms on the model's Hugging Face page with your own account, then make a
read token from that account available as `HF_TOKEN` (cloud environment secret, or the Databricks
secret scope `health_transformation_lab` / `hf_token` for notebook 03). Without both, the download fails with 401/403.
The terms also govern sharing outputs and fine-tuned weights: check them before publishing a LoRA
adapter. `models.yaml` marks these entries `gated: true` with the licence link.

## Implemented (spec 004)

Uses 1 (reader), 2 (LoRA fine-tune) and 3 (judge family rule) are in the code.
The zero-shot reader has been run once on real `medgemma-1.5-4b-it` weights (CPU,
reader-v2, 240 review charts); the LoRA fine-tune has not (needs a GPU).

**First real run (synthetic notes, generator truth; not clinical performance).**
Accuracy 0.758 (95% CI 0.700-0.808) against note_rules' 0.788, paired difference
-0.029 (-0.058 to 0.000); with the note rules deciding stage IV, 0.771. By difficulty:
L1 100% (141), L2 97% (31), L3 16% (68). Gate pass 97.9%, fallback 2.1%, ~850 tokens
in and ~75 out per note, ~27 s per note on 4 CPU cores. So it reads a written
diagnosis well and does not yet stage from the chart findings when none is
written; L3 is where few-shot, prompt variants or the LoRA fine-tune would have to
help. Against the best encoder alone (`modernbert-base+cw`, 0.825) the difference is
-0.067 (-0.138 to 0.000), so on 240 charts the two can't be told apart; on L3 the encoder gets 81%. Full
tables: `data/datasets/ladder/ladder_vs_truth.csv` and `medgemma_vs_bert*.csv`.

**MedGemma 4B v1 (Kaggle, same 240 notes, #210).** Accuracy 0.779 (0.725-0.833); with the note rules
deciding stage IV, 0.817. Against `modernbert-base+cw` the difference is -0.046 (-0.104 to 0.012), so again
not distinguishable. By difficulty: L1 97%, L2 68%, L3 43%. Against 1.5 it stages more charts from their
findings when no diagnosis is written (L3 43% vs 16%) but does worse when old terms or copied-forward text
must be translated (L2 68% vs 97%). Gate pass 94.2%, fallback 5.8%. Both are measurements on synthetic
notes, not evidence about either model on real records.

MedGemma 1.5 opens with a `<unused94>thought ... <unused95>` block; the hf backend
suppresses it (it otherwise used up the 300 new tokens before the JSON) and
`parse_answer` strips one if present.

### Why some answers fell back (#134)

An answer falls back to `note_rules` when it fails the gate: bad JSON, a status outside the six, or a
quote that isn't the note's own words. Every fallback in the two committed runs (240 synthetic review
notes each, `data/datasets/llm_details_medgemma-4b-it.csv` and `llm_details_medgemma-1.5-4b-it.csv`) was
read against its note:

| Why the gate failed | 4B v1 | 1.5 | Verdict |
|---|---:|---:|---|
| Quote differs from the note only in capitals (an upper-case diagnosis line copied in lower case) | 3 | 0 | **Gate bug, fixed**: the gate now ignores capitals and runs of whitespace (`quote_in_note`) |
| "Localized" shortened to "Local" or "Localize" | 8 | 0 | Model changed a word: correct to reject |
| "Localized" respelled "Localised" | 1 | 2 | Model changed a word: correct to reject |
| A misspelling in the note ("generlized", "locallized") corrected in the quote | 2 | 0 | Correct to reject (the quote must match the record as written) |
| Quote stitched from separate places in the note, or with words added | 0 | 2 | Correct to reject |
| Diagnosis text put in the `status` field instead of one of the six labels | 0 | 1 | Correct to reject |
| **Total fallbacks** | **14** | **5** | |

No answer failed for malformed JSON, a missing field, an out-of-range grade or extent, or output cut off
at the token limit. So the 4B v1 run's fallbacks are mostly the model rewriting the word "Localized"
rather than copying it; a future prompt version could say "copy the words character for character, even
misspellings", which needs a new prompt version and a re-run to measure.

**What a re-run would show.** MedGemma was not re-run (no GPU). Re-parsing the committed raw outputs
with the fixed gate turns 3 of the 4B v1 run's 14 fallbacks into passes (visits 776, 3689, 4218): gate
pass 94.2% to 95.4%, fallback 5.8% to 4.6%. Accuracy against generator truth goes from 0.779 to 0.775,
because in one of the three (4218) MedGemma's own answer (stage II) was further from the generator's
label than the note rules' fallback was. The 1.5 run and the Llama 3.3 70B run are unchanged (no
case-only quotes). The committed files keep the gate as it ran. All of this is synthetic notes, not
evidence about either model on real records.

| Piece | Where |
|---|---|
| Note reader rung: prompt shares the judge's AAP/EFP criteria; JSON status/grade/extent + verbatim quote; falls back to `note_rules` and flags the row on any failure; never sends a note the residual PHI scan flags | `python/health_transformation_lab_nlp/llm_reader.py` |
| Backends: `hf` (local transformers, optional LoRA adapter), `openai` (Databricks serving, vLLM, Ollama), `simulated` (dry run) | same |
| Run it | `python scripts/11_ai_predict.py --rung medgemma-1.5-4b-it --backend hf [--shots 1] [--limit 40]` |
| Fine-tune | `python scripts/17_medgemma_lora.py` then `--adapter runs/medgemma-lora` |
| Judge rule | `15_judge.py` excludes judges of any evaluated LLM's family (`family: gemma` in `models.yaml`) |
| Databricks | `databricks/notebooks/03_medgemma_reader.py` (Free Edition serverless GPU) |
| Costs | `costs.yaml`: assumed GPU throughput, ILLUSTRATIVE; measure and replace |
| Compare with BERT | `python scripts/29_medgemma_vs_bert.py [--bert modernbert-base]`: each MedGemma run minus the encoder, paired bootstrap CI, stage IV recall, by difficulty, fallback rate; R twin in `10_ladder.R`. Notebook 03 runs it after the reader (set `limit` 0, `lora_train` > 0 for the fine-tuned version) |

Per-note details (gate pass, fallback, tokens, latency) go to
`data/datasets/llm_details_<rung><tag>.csv`; the tag (`+lora`, `+k<shots>`, `+terse`) keeps
zero-shot, few-shot and fine-tuned runs apart. The simulated dry run's numbers come from
placeholder error rates and say nothing about MedGemma.

## Suggested order

1. **Rung 1 first.** Cheap, and it answers the basic question: how does an
   off-the-shelf medical LLM do on these notes, by difficulty level, and at
   what cost per million notes?
2. **Then rung 2** only if rung 1 is promising but not good enough.
3. **Paraphrasing (4)** whenever the synthetic notes need more variety.
4. **Images (5)** last: it needs public dental image data with a licence that
   allows this, and GPU time.

## Running it

- **Laptop / CPU:** the 4B model, quantized, runs locally for small synthetic
  tests (slow). Synthetic data only.
- **Databricks Free Edition:** has limited serverless GPU in notebooks
  (announced June 2026; subject to capacity, fair-use limits, no published
  quota). Enough to try the 4B model on synthetic notes and possibly a small
  LoRA fine-tune of it. It does **not** offer GPU serving endpoints or custom
  models on GPU batch inference, so run MedGemma inside the notebook rather
  than as an endpoint
  ([limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations),
  [announcement](https://www.databricks.com/blog/whats-coming-next-free-edition)).
  The 27B model doesn't fit (about 54 GB of weights; see "Next: MedGemma 27B").
- **Kaggle (free GPU), when Databricks has none:** GPU access on Free Edition needs LinkedIn
  verification and free capacity, and some accounts get none, so the `medgemma_reader` job can wait and
  retry for hours without starting. [`kaggle/medgemma_reader.ipynb`](../kaggle/medgemma_reader.ipynb) runs
  the same `11_ai_predict.py` on Kaggle's free "GPU T4 x2" (about 30 GPU-hours a week): clone, install,
  convert MedGemma, a 10-note test, then all 240 notes with *Save & Run All*. No Hugging Face token: the
  weights come from Kaggle Models ([keras/medgemma](https://www.kaggle.com/models/keras/medgemma), the
  `kaggle:` handle in `models.yaml`, attached through `model_sources`), a Keras preset that
  [`kaggle/keras_to_hf.py`](../kaggle/keras_to_hf.py) exports to a `transformers` folder (keras-hub's
  exporter, plus MedGemma's chat template and stop tokens) and `--weights` loads. The reader picks
  the weights dtype for the GPU (`llm_reader.pick_dtype`: bfloat16 on A10/A100/H100, float32 on T4 x2,
  `DENTAL_LLM_DTYPE` to force one). Download the prediction CSVs from the Output tab into
  `data/datasets/`, then run `28_ladder_vs_truth.py` and `35_readme_results.py`.
  **From GitHub:** Actions → *Run MedGemma on a free Kaggle GPU* → Run workflow pushes the notebook to Kaggle
  (`kaggle kernels push --accelerator NvidiaTeslaT4`, public: synthetic notes only, no token in it), waits, and keeps the predictions and
  the Kaggle log as a workflow artifact. Needs `KAGGLE_USERNAME` and `KAGGLE_API_TOKEN` (or
  `KAGGLE_KEY`) in the GitHub environment `dev` (Kaggle → Settings → API → Generate New Token; delete it
  there when done). Nothing to set up on kaggle.com: a pushed notebook can't read Kaggle Secrets, which is
  why it no longer uses a Hugging Face token. `limit` 10 is a test; `limit` 0 reads all 240 notes (hours: turn `wait` off, then rerun with `collect_only`).
- **Paid Databricks:** register through MLflow, serve on GPU Model Serving, and
  batch-score with `ai_query`. Costs go in `costs.yaml` as a self-hosted GPU method.
- **Evaluation:** the same split, scorer, harm grading, difficulty levels and
  cost-effectiveness as every other method. Report prompt-sensitivity by running
  two or three prompt variants.

## Versions, and which have been run

Google publishes five MedGemma models on Hugging Face. They are different models, not updates of one, so
every result names the model, and since 2026-10-28 also the exact revision: `models.yaml` pins a
Hugging Face commit per model, the reader loads that commit, and each run's `llm_details_*.csv` records it in
a `revision` column. Google updated the 1.5 weights on 2026-04-13. The committed 1.5 run (October 2026)
used the pinned revision.

| Model | Kind | Pinned revision | Status here |
|---|---|---|---|
| `medgemma-1.5-4b-it` | 4B, text and images, instruction-tuned (Jan 2026) | `91850547d9f0` | **run**: 75.8% correct on the 240 review notes |
| `medgemma-4b-it` | 4B, text and images, instruction-tuned (MedGemma 1, 2025) | `290cda5eeccb` | **run** on Kaggle: 77.9% correct on the 240 review notes |
| `medgemma-27b-text-it` | 27B, text only, instruction-tuned (2025) | `5b667cf2ddcf` | not run: needs a larger GPU (below) |
| `medgemma-27b-it` | 27B, text and images (2025) | not in the registry | the text-only 27B suits notes better |
| `medgemma-4b-pt` | 4B, pretrained only | not in the registry | not instruction-tuned, so unsuited to a zero-shot reader |

**MedGemma 4B v1 against 1.5 (done, #185 and #210).** Same reader code as the 1.5 run, so the
comparison isolates the version; results are under "Implemented" above. The Kaggle notebook loads MedGemma
from Kaggle Models (`kaggle/keras_to_hf.py`), which needs two things per model, both now in place for 1.5
and 4B v1:
- the model's `kaggle:` handle in `models.yaml`, from kaggle.com/models/keras/medgemma;
- Google's `config.json` and `generation_config.json` for it in `kaggle/hf_config/`, from
  the model's Hugging Face repository (terms accepted).

Runs on Hugging Face weights instead load the pinned revision.

## Next: MedGemma 27B

**Why it matters.** The 27B is the version most likely to read notes better.
- Google's [MedGemma Technical Report](https://arxiv.org/abs/2507.05201) (Table 3) gives **87.7%** on
  MedQA for the 27B, with Google's test-time scaling, against **64.4%** for the 4B.
- In this repo, the larger general-purpose Llama 3.3 70B (83.8%) already beats MedGemma 1.5 4B (75.8%) on
  the 240 review notes.

That's an expectation, not a result. MedQA is exam questions, not dental charts, and the 27B is
**not run** here yet. Until it is, no number in this repo stands for it.

**What it needs.** 27 billion parameters at 2 bytes each (bfloat16) is about **54 GB of GPU memory** for
the weights, plus room for the prompt. The free GPUs fall short:
- Kaggle's T4 x2 has 30 GB, and no bfloat16;
- Databricks Free Edition's serverless A10 has 24 GB.

Options, best first:

| Option | Fits | Cost | What to record |
|---|---|---|---|
| One A100 80 GB or H100 (paid Databricks GPU compute, or a cloud VM) | yes, in bfloat16 | paid per GPU-hour; the 240 notes take well under an hour | `--rung medgemma-27b-text-it --backend hf`; revision, dtype, GPU |
| Serve it on GPU Model Serving (paid Databricks) and call it with `--backend openai --endpoint <name>` or `ai_query` | yes | paid; scales to zero | endpoint, revision |
| 4-bit quantization (about 15–17 GB) on Kaggle T4 x2 or an A10 | yes | free | label it `medgemma-27b-text-it+4bit`: compressed weights are a slightly different model, scored as their own row |
| Gemma 3 12B, which Databricks hosts pay-per-token (`databricks-gemma-3-12b`) | yes | pennies | not MedGemma: the general model MedGemma is built from, so a size and medical-training comparison, not a substitute |

The code already supports the first two. The 4-bit option needs a `--quantize 4bit` flag for the reader,
using `bitsandbytes`; that's a small addition when it's wanted. Whichever option is used, record the
revision, the dtype or quantization, and the hardware with the run.

## Cautions

- Not for clinical decisions (model terms). Every use here is a research exercise.
- No dental training data in MedGemma 1, so expect to need adaptation.
- If MedGemma reads the notes, don't let a Gemma-family model judge them.
- Check the HAI-DEF terms before sharing fine-tuned weights.
- Nothing identifiable goes in, ever. Synthetic notes only in this repo.
