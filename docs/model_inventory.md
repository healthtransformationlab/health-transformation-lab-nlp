# Model inventory: every model and AI service the repo depends on

> Personal learning project; synthetic data only. This page lists every pretrained model, hosted model
> and AI service the code can call, for an AI-use review. Licences were read from each model's
> Hugging Face card on 2026-10-28; re-check the card before approval, because cards change.
> A test (`tests/test_model_inventory.py`) fails if code or `models.yaml` names a model that isn't here.

**What runs where.** Every model in sections 1–3 downloads its weights from Hugging Face and runs
locally or on Databricks/Kaggle compute; no note text leaves that machine. Section 4 lists hosted
services that receive the text; they only ever get synthetic or de-identified notes, and the code
refuses to call one unless its endpoint is configured.

**Status** says whether real (not simulated) results are committed in `data/datasets/`.

## 1. Encoders: read a note and assign its periodontal status

| Model · paper · domain, role | Hugging Face id | Organisation | Licence (card) | Status |
|---|---|---|---|---|
| BERT base · [1810.04805](https://arxiv.org/abs/1810.04805) · general, classifier | `google-bert/bert-base-uncased` | Google | Apache-2.0 | results |
| DistilBERT · [1910.01108](https://arxiv.org/abs/1910.01108) · general, classifier | `distilbert/distilbert-base-uncased` | Hugging Face | Apache-2.0 | results |
| ModernBERT base · [2412.13663](https://arxiv.org/abs/2412.13663) · general, classifier, long context | `answerdotai/ModernBERT-base` | Answer.AI | Apache-2.0 | results |
| ModernBERT large · [2412.13663](https://arxiv.org/abs/2412.13663) · general, classifier, long context | `answerdotai/ModernBERT-large` | Answer.AI | Apache-2.0 | results |
| Longformer · [2004.05150](https://arxiv.org/abs/2004.05150) · general, long context; also the base of the PHI tagger | `allenai/longformer-base-4096` | Allen Institute for AI | Apache-2.0 | results as a classifier; also the base of the PHI tagger (section 3) |
| SciBERT · [1903.10676](https://arxiv.org/abs/1903.10676) · scientific, classifier | `allenai/scibert_scivocab_uncased` | Allen Institute for AI | **none on the card** (the `allenai/scibert` GitHub repository is Apache-2.0): confirm before approval | results |
| Bio_ClinicalBERT · [1904.03323](https://arxiv.org/abs/1904.03323) · clinical, classifier | `emilyalsentzer/Bio_ClinicalBERT` | Alsentzer et al. (MIT) | MIT | results |
| GatorTron base · [Nature Digital Medicine 2022](https://doi.org/10.1038/s41746-022-00742-2) · clinical, classifier | `UFNLP/gatortron-base` | University of Florida / NVIDIA | Apache-2.0 | not run |
| BiomedBERT · [2007.15779](https://arxiv.org/abs/2007.15779) · biomedical, classifier | `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext` | Microsoft | MIT | results |
| BioClinical ModernBERT base · [2506.10896](https://arxiv.org/abs/2506.10896) · clinical, classifier, long context | `thomas-sounack/BioClinical-ModernBERT-base` | Sounack et al. (Dana-Farber) | MIT | results |
| BioClinical ModernBERT large · [2506.10896](https://arxiv.org/abs/2506.10896) · clinical, classifier, long context | `thomas-sounack/BioClinical-ModernBERT-large` | Sounack et al. (Dana-Farber) | MIT | results |
| Clinical-Longformer · [2201.11838](https://arxiv.org/abs/2201.11838) · clinical, long context | `yikuan8/Clinical-Longformer` | Northwestern University (Luo lab) | **none on the card**: confirm before approval | results |

Clinical models were pretrained on clinical notes by their authors (for example MIMIC-III for
Bio_ClinicalBERT and Clinical-Longformer); only their published weights are used here.

## 2. Concept mapping and retrieval (not classifiers)

| Model · paper · domain, role | Hugging Face id | Organisation | Licence (card) | Status |
|---|---|---|---|---|
| SapBERT · [2010.11784](https://arxiv.org/abs/2010.11784) · biomedical, concept mapping (note terms to UMLS/SNOMED) | `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` | University of Cambridge | Apache-2.0 | not run |
| GTE-ModernColBERT · [model card](https://huggingface.co/lightonai/GTE-ModernColBERT-v1) · general, retrieval (evidence lookup for RAG) | `lightonai/GTE-ModernColBERT-v1` | LightOn | Apache-2.0 | not run |
| EmbeddingGemma 300M · [2509.20354](https://arxiv.org/abs/2509.20354) · general, code-graph node embeddings for the DataOps task set (spec 028 T010; 256 of 768 dimensions; reads this repo's own code, no notes) | `google/embeddinggemma-300m` | Google | [Gemma terms of use](https://ai.google.dev/gemma/terms) (accept on Hugging Face first) | results (115 task graphs, 2026-11-03) |

## 3. Large language models and de-identification models

| Model · paper · domain, role | Source | Organisation | Licence | Status |
|---|---|---|---|---|
| MedGemma 1.5 4B (instruction-tuned) · [2507.05201](https://arxiv.org/abs/2507.05201) · medical, note reader (LLM) | `google/medgemma-1.5-4b-it` | Google (Health AI Developer Foundations) | [HAI-DEF terms of use](https://developers.google.com/health-ai-developer-foundations/terms) (accept on Hugging Face first) | results (240 notes) |
| MedGemma 4B (instruction-tuned) · [2507.05201](https://arxiv.org/abs/2507.05201) · medical, note reader (LLM) | `google/medgemma-4b-it` | Google (HAI-DEF) | HAI-DEF terms | results (240 notes) |
| MedGemma 27B text (instruction-tuned) · [2507.05201](https://arxiv.org/abs/2507.05201) · medical, note reader (LLM) | `google/medgemma-27b-text-it` | Google (HAI-DEF) | HAI-DEF terms | not run (needs a large GPU) |
| PHI tagger: Longformer base fine-tuned on MACCROBAT (CC BY 4.0) · spec 010 · de-identification | `allenai/longformer-base-4096` + own fine-tune (not published) | this repo | Apache-2.0 base; MACCROBAT CC BY 4.0 | results (`data/deid/maccrobat_*`) |
| Stanford de-identifier · Chambon et al., JAMIA 2023 · clinical, de-identification | `StanfordAIMI/stanford-deidentifier-base` | Stanford AIMI | MIT | results (de-id benchmark) |
| OBI de-identifier (RoBERTa on i2b2 2014) · clinical, de-identification | `obi/deid_roberta_i2b2` | Oxford Big Data Institute | MIT; **trained on i2b2 2014, a data-use-agreement set**: only the published weights are used, never the data | results (de-id benchmark) |
| spaCy English large (via Microsoft Presidio) · general, named entities for de-identification | `en_core_web_lg` (spaCy) with `presidio-analyzer` | Explosion; Microsoft | MIT; MIT | results (de-id benchmark) |

## 4. Hosted models and services (receive synthetic or de-identified text only)

| Service · role | Where | Licence / terms | Status |
|---|---|---|---|
| Meta Llama 3.3 70B Instruct · LLM judge (spec 012), LLM de-identification, and a zero-shot note reader (spec 017, `llama-3.3-70b-instruct`; Hugging Face reference `meta-llama/Llama-3.3-70B-Instruct`) | Databricks Foundation Model API, pay-per-token endpoint `databricks-meta-llama-3-3-70b-instruct` | Llama 3.3 Community License; Databricks terms | judge: run in dev (2 runs, 2026-10-27); reader: results (240 notes, 2026-10-28); de-id: not run |
| `ai_mask` · de-identification | Databricks SQL AI Function (Public Preview), Databricks-hosted model | Databricks terms | results (400 synthetic challenge notes, 2026-10-28) |
| Azure Health Data Services de-identification · de-identification | Azure (needs `AZURE_DEID_ENDPOINT`) | Microsoft terms | not run |
| Azure AI Language PII detection · de-identification | Azure (needs `AZURE_LANGUAGE_ENDPOINT`) | Microsoft terms | not run |
| Amazon Comprehend Medical · de-identification | AWS (needs `AWS_REGION`) | AWS terms | not run |

## 5. In-house methods (no external model)

TF-IDF + logistic regression (`tfidf_logreg`), note rules (`note_rules`), the TF-IDF + radiograph fusion
(`fusion_tfidf_rad`), the rule phenotypes and the regex de-identifiers are written and trained in this repo
with scikit-learn; they download no pretrained weights.

## 6. Databricks AI features

Databricks runs these on its own hosted models, inside the workspace. Each one sends text to a model that
Databricks manages, so the same rule applies as for section 4: only synthetic or de-identified text. Two
workspace settings change where the text can go:
- **Cross-Geo processing:** when it's off, text is processed in the workspace's own region (Databricks
  calls this its Geo).
- **Partner-powered AI features:** when they're off, features that rely on partner models stop working
  unless you give them your own model.

| Feature | What it does here | Model behind it | Status |
|---|---|---|---|
| `ai_query` (SQL AI Function, [docs](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query)) | Sends a prompt to a serving endpoint from SQL. Used for the LLM judge at corpus scale (`02_llm_judge.sql`), the benchmark's optional LLM challenger (`01_run_benchmark.py`) and, as an option, MedGemma served on Model Serving | whatever endpoint is named; here the Llama 3.3 70B endpoint | judge: run in dev; challenger: off by default |
| `ai_classify` (SQL AI Function, GA June 2026, [docs](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_classify)) | Gives each review note one of the six statuses, each with a one-line description (spec 017: `dbai-classify`, `scripts/41_databricks_ai_methods.py`) | Databricks-managed; the docs don't name it | not run |
| `ai_extract` (SQL AI Function, GA June 2026) | Could pull measurements (CAL, probing depth, teeth lost) out of a note, for the rules to stage | Databricks-managed; not named | not used (listed for review) |
| `ai_mask` (SQL AI Function, Public Preview) | De-identification: replaces identifiers with `[MASKED]` (spec 007; the *De-id AI methods* job) | Databricks-hosted LLM; not named | results (400 challenge notes, 2026-10-28) |
| Foundation Model API pay-per-token endpoints | The hosted LLMs behind `ai_query`, the judge and the Llama reader (section 4) | Meta Llama 3.3 70B Instruct | see section 4 |
| MLflow `make_judge` (custom judge, `mlflow_judge.py`) | The AAP/EFP judge, written as an MLflow GenAI judge | the model passed in: here the judge endpoint | run in dev with the judge |
| MLflow built-in Guidelines judge (`aap_guidelines`) | Checks answers against five plain-language AAP rules | **a Databricks-hosted judge model by default**, unless a model is passed; this repo passes the judge endpoint ([built-in judges](https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/predefined-judge-scorers)) | defined; runs only in monitoring |
| MLflow production monitoring scorers (`05_judge_monitoring.py`) | Databricks runs the judges above on a sample of live traces, and the PHI scan on all of them | as each judge | uat/prod only; not running |
| AI Gateway (on serving endpoints) | Usage tracking and rate limits for the planned chart review agent's endpoint (spec 015) | n/a (a gateway, not a model) | planned |
| Genie (AI/BI) | Natural-language questions over the gold tables, for people | Databricks-managed | not set up; mentioned in notebook 01 |
| Databricks Assistant | Code and SQL help in notebooks, for people | Databricks-managed | not used by any pipeline. If people use it in this workspace, it sees the notebook code and table schemas they work on |

## For an AI-use review

- **Licence gaps**: SciBERT and Clinical-Longformer state no licence on their cards; MedGemma uses Google's
  HAI-DEF terms (not an open-source licence) and needs the terms accepted per account.
- **Training data**: the OBI de-identifier was trained on i2b2 2014 (data-use agreement); clinical encoders
  were pretrained on MIMIC or institutional notes. Using published weights doesn't bring that data in, but
  reviewers may ask.
- **Data flow**: sections 1–3 run where the data is; section 4 sends text to a hosted service, and only
  synthetic or de-identified text, behind the leak gate.
- **Databricks-managed models**: `ai_classify`, `ai_extract`, `ai_mask` and the default built-in judge run on
  models Databricks doesn't name in their documentation, and can change. Record the workspace's cross-Geo and
  partner-powered AI settings with the approval.
- **Not run yet** (no real results): GatorTron, SapBERT, GTE-ModernColBERT, MedGemma 27B,
  `ai_classify`, and every service in section 4 except the judge.
