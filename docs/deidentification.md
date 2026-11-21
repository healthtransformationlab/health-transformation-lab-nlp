# De-identification: methods, a labeled test set, and cost-effectiveness

> Personal learning project. Every note, name, date and number here is **synthetic and invented**.
> Nothing describes any organization's de-identification setup. Spec: [007](../specs/007-deid-methods/spec.md).

## Does the synthetic data contain real PHI?

No. The notes carry **fake PHI**: invented names from common-name lists, random record numbers,
phone numbers and dates, reserved example domains for emails and URLs, and SSNs starting with 9
(never issued). It's there so de-identification has something real-shaped to find.

Because the generator inserts every identifier, it **knows where each one is**: every fake
identifier is marked with its character span and category. That makes recall exact. Real notes
never allow this; there you only have a human review sample.

## The test set: three tiers, each adds a check

The **challenge set** is labeled fake PHI in three tiers. Each tier tests something the one before
it can't:

| Tier | What's in it | What it adds |
|---|---|---|
| **easy** | The study notes' header shapes (`Patient:`, `MRN:`, `Dr.`) | Confirms the pipeline removes the PHI the study notes carry |
| **hard** | Prose shapes: first name alone, lowercase names, relatives, "Mrs" without a period, ages over 89, written-out dates, dotted and +1 phones, email, URL, SSN, health plan member IDs, street / city / ZIP, referral practices | Covers the shapes real notes have, beyond headers |
| **unseen** | Written **after** regex v2 and never used to tune it: ALL-CAPS and possessive names, names that are words (Rose, Will), O'/hyphenated names, nicknames, weekday dates, spaced phones, fax, apartment numbers, driver's licence, plate, device serial, IP address, social handle, employer | A fair, held-out comparison: no method was tuned on it (regex v2 was written alongside the hard tier) |

**What "unseen" means, in plain words.** Rules are written by looking at examples. regex v2's
rules were written while looking at the hard tier, so they score 100% there, like a student graded
on the exact questions they studied. The unseen tier is the final exam: identifier shapes added only
after the rules were frozen, which nobody tuned any method against. Real notes will contain shapes
no one thought of, so the unseen score is the best guess at how a method will do on them.

Every tier also has marked **dental decoys**: text that looks like PHI but must survive (Glickman
and Miller classes, Gracey 11/12, tooth numbers, CDT and ICD codes, probing readings like 6-5-6,
drug names, ages under 90). They measure the other side of de-identification: whether the
clinical text the classifiers read comes through intact.

The categories follow HIPAA Safe Harbor and the 2014 i2b2/UTHealth annotation guidelines
([references](references.md#de-identification) 37–38). The names come from lists no engine uses.

**Guidelines and free test material online** ([references](references.md#de-identification) 37–45):

| Resource | What it is | Free? | Fit here |
|---|---|---|---|
| HHS Safe Harbor guidance | The 18 identifiers that must be removed | yes | Category list |
| 2014 i2b2/UTHealth (n2c2) | Standard clinical de-id benchmark and annotation guidelines | guidelines yes; corpus needs a data use agreement | Category scheme used; corpus not used |
| ASQ-PHI (2025) | 1,051 fully synthetic clinical search queries, PHI tagged, with hard negatives | yes, MIT | Second test set, scored below: `26_deid_benchmark.py --external synthetic_clinical_queries.txt` (the file as downloaded) |
| SHIELD (Stanford) | 1,381 real notes with surrogate PHI, adjudicated spans | access by request | Real-note shapes, if access is granted |
| presidio-evaluator | Fake-PII sentence generator from templates, detector evaluation | yes, MIT | Another way to generate labeled fake PHI |
| John Snow Labs | Clinical de-id pipelines in its licensed Healthcare NLP; public speed benchmarks on Databricks | the de-id models are licensed (trial and academic programs exist); no free test set found | Another engine to compare, if licensed |

## Engines and what each adds

| Engine | What it adds | Runs here |
|---|---|---|
| `regex` | Fast, exact and free; removes the header shapes (`Patient:`, `MRN:`, dates, phones) with no dental damage; the dental allowlist keeps BOP, SRP, FMX | yes |
| `regex_v2` | Extends regex to prose shapes: relatives, Mrs/Dr without a period, "Name, DDS", ages > 89, email, URL, SSN, member IDs, more date, phone and address shapes. Catches formatted IDs that NER models miss | yes |
| `presidio` | Microsoft Presidio: spaCy NER finds names and places from context, not from a fixed pattern, so it reaches shapes nobody wrote a rule for | yes (Python 3.12 + spaCy model) |
| `hf_stanford` | Transformer NER trained specifically for clinical de-identification: StanfordAIMI/stanford-deidentifier-base (radiology reports and notes; MIT). Learned clinical context; free; runs on a CPU ([what is BERT?](bert.md)) | yes (CPU here; GPU on Databricks: [`06_deid_benchmark.py`](../databricks/notebooks/06_deid_benchmark.py)) |
| `hf_obi` | A second clinical de-id transformer, obi/deid_roberta_i2b2 (RoBERTa trained on the i2b2 2014 corpus; MIT); a different training set, so a check on the first | yes, same |
| `azure_deid` | Managed Azure Health Data Services de-identification (27 PHI categories): no model to host, vendor-maintained | wired, tested with a fake client; needs `AZURE_DEID_ENDPOINT` |
| `azure_language` | Azure AI Language PII detection, healthcare (PHI) domain: a second managed option | wired, tested with a fake client; needs `AZURE_LANGUAGE_ENDPOINT` and `_KEY` |
| `llm` | An LLM lists every identifier verbatim; reads context like a person and follows written instructions (e.g. "keep Glickman"). Values not found in the note are dropped | wired, tested with a fake reply; needs an endpoint (Databricks serving) |
| `aws_comprehend` | Amazon Comprehend Medical DetectPHI: AWS's managed PHI detection; the engine the ASQ-PHI paper used as its baseline, so running it here checks that paper's result on our notes | wired, tested with a fake client; needs AWS credentials and `AWS_REGION` (`pip install boto3`) |
| `ai_mask` | Databricks' built-in SQL function [`ai_mask`](https://docs.databricks.com/aws/sql/language-manual/functions/ai_mask) (Public Preview): a Databricks-hosted LLM masks the listed entity types. De-identification in the warehouse with one line of SQL and no model or prompt to maintain. Returns masked text, so spans are recovered by aligning it with the original | wired, tested with a fake reply; needs a Databricks SQL warehouse (`DATABRICKS_HOST`, `_TOKEN`, `_WAREHOUSE_ID`) |
| `jsl` | John Snow Labs Healthcare NLP `clinical_deidentification` pipeline: a commercial clinical pipeline with Spark scale-out | wired, tested with a fake pipeline; needs a licence (free academic; trial through their Databricks installer) and Spark |
| `A+B` | Ensemble, the union of the engines' spans: each engine covers the other's gaps | |
| `+guard` | Dental guard: keeps dental terms (eponyms, tooth numbers, probing readings, codes) that general PHI models would remove, at no cost to recall | |

`python scripts/26_deid_benchmark.py --engines azure_deid+regex_v2+guard` runs the Microsoft
service plus regex plus guard, once an Azure resource is set up.

**What published comparisons say.** Transformer models trained for de-identification report
F1 around 0.98–0.99 on the i2b2 corpora (Stanford model card, Chambon et al.). A 2025 comparison by
John Snow Labs ranked its own Healthcare NLP first (recall 0.97), then Azure Health Data Services
(0.92), AWS Comprehend Medical (0.85) and GPT-4o zero-shot (0.77); the authors sell one of the
compared products, so it needs independent checking. None of these were tested on dental notes,
where eponyms and probing readings look like PHI. That's what the challenge set's decoys test.

## Standard test datasets

To compare with published numbers, engines should also be scored on the standard corpora. All are
real (de-identified) clinical text with surrogate PHI, so each needs its own access agreement and
must stay **outside the repo**:

| Dataset | What | Access | Loader |
|---|---|---|---|
| **i2b2/UTHealth 2014 (n2c2)** | 1,304 longitudinal notes, ~28,000 PHI spans; the main benchmark (Stanford and OBI models report on it) | n2c2 data use agreement | `--i2b2-2014 <folder>` (XML) |
| i2b2 2006 | Discharge summaries | n2c2 data use agreement | same XML shape; untested |
| PhysioNet *Deidentified Medical Text* | 2,434 nursing notes, the original deid gold standard | PhysioNet credentialed access (training + DUA) | `--external` after conversion |
| SHIELD (Stanford, 2026) | 1,381 diverse notes, 10,229 adjudicated spans | by request | `--external` |
| ASQ-PHI (2025) | 1,051 synthetic clinical queries with hard negatives | open, MIT | `--external` (scored; see below) |
| Text Anonymization Benchmark | 1,268 court cases (not clinical) | open source | not clinical; skip |

None is dental. The challenge set's dental decoys stay the only test of over-redacting
dental terms.

## Results on the challenge set (400 notes, seed 7)

### How to read the numbers

A de-identification method makes two kinds of mistake, like a spam filter: it can let an identifier
through (spam in the inbox) or remove text that wasn't an identifier (a real email in the spam
folder). Each number below measures one of them.

| Number | Plain meaning | Better is | Example |
|---|---|---|---|
| **Recall** | Share of identifiers removed. One character left counts as a leak | **higher** (1.00 = none leaked) | 0.92 = 8 in 100 identifiers leak |
| **Precision** | Of the characters removed, the share that really were identifiers | **higher** | 0.90 = 10% of what it removed was ordinary text |
| **Decoy damage** | Share of dental terms that look like PHI (Glickman, Gracey 11/12, 6-5-6) that got cut | **lower** (0 = none cut) | 0.17 = 17 in 100 dental terms damaged |
| **Over-redaction** | Share of notes with *no* identifiers that were changed anyway (ASQ-PHI only) | **lower** | 0.89 = 89 in 100 clean notes changed: bad |

Recall protects patients; the other three protect the text the AI reads. A method that removed
everything would have recall 1.00 and be useless, so they're always read together.

| Engine | easy | hard | **unseen** | all | Precision | **Decoy damage** |
|---|---|---|---|---|---|---|
| regex | 1.00 | 0.27 | 0.20 | 0.47 | 0.94 | 0.00 |
| regex_v2 (+guard) | 1.00 | 1.00\* | 0.27 | 0.76 | 0.96 | 0.00 |
| presidio | 0.82 | 0.71 | 0.53 | 0.69 | 0.75 | 0.37 |
| presidio+guard | 0.82 | 0.71 | 0.53 | 0.69 | 0.91 | 0.05 |
| presidio+regex_v2+guard | 1.00 | 1.00\* | 0.57 | 0.86 | 0.89 | 0.05 |
| hf_obi | 0.78 | 0.69 | 0.58 | 0.68 | 0.93 | 0.17 |
| hf_obi+regex_v2+guard | 1.00 | 1.00\* | 0.62 | 0.88 | 0.94 | 0.01 |
| hf_stanford | 1.00 | 0.69 | 0.71 | 0.79 | 0.85 | 0.17 |
| hf_stanford+guard | 1.00 | 0.69 | 0.71 | 0.79 | 0.92 | 0.02 |
| **hf_stanford+regex_v2+guard** | 1.00 | 1.00\* | **0.74** | **0.92** | 0.90 | 0.02 |

\* written alongside this tier; read the unseen column for a fair comparison. The Hugging Face
engines ran on CPU in a 4-CPU container (2026-10-26).

What each method adds:

- **regex_v2** contributes exact coverage of formatted identifiers (phones, IDs, member numbers,
  emails) with no damage to dental text, at about 3,600 notes/s. Every ensemble below relies on it
  for those shapes.
- **Presidio** adds context-based detection: on the unseen tier it doubles regex_v2's recall
  (0.53 vs 0.27) and catches the unseen-tier dates (1.00) that hf_stanford misses.
- **hf_stanford** adds a model trained on clinical text: the highest recall of any single engine
  on the unseen tier (0.71), strongest on names (patients 0.84, clinicians 0.85), employers (1.00),
  other IDs (0.72) and URLs (0.41) (`data/deid/by_category.csv`).
- **hf_obi** adds a second clinical model trained on different notes (i2b2 2014). It catches the
  unseen dates that hf_stanford misses (0.97 vs 0.00), so the two models complement each other.
- **The dental guard** cuts decoy damage from 17% to 2% for hf_stanford and from 37% to 5% for
  Presidio, at no cost to recall.
- **The ensembles** combine those strengths: hf_stanford+regex_v2+guard removes 92% of
  identifiers overall and 74% on the unseen tier, the most of any combination run here.

**What a human review sample still has to cover.** On the unseen tier, about a quarter of
identifiers survive even the best ensemble. No engine finds street addresses, and URLs are mostly
missed. Combining hf_stanford with Presidio or hf_obi (for dates) is the next combination to score.

## Results on ASQ-PHI (1,051 queries, external)

[ASQ-PHI](https://data.mendeley.com/datasets/csz5dzp7nx/1) (Weatherhead et al., MIT) is a second,
independent test set: 1,051 short clinical search queries written by GPT-4o, 2,973 tagged identifiers
in 13 Safe Harbor types, and 219 **hard negatives**, queries that look like they carry PHI but don't.
It adds what the challenge set can't: text nobody here wrote, in a different form (questions, not
chart notes), and a direct measure of over-redaction. It has no dental text, so the dental guard has
nothing to protect there.

Over-redaction = share of the 219 PHI-free queries with anything removed (the paper's
"over-redaction rate").

| Engine | Recall | Precision | **Over-redaction** |
|---|---|---|---|
| regex | 0.31 | 0.96 | 0.10 |
| regex_v2 | 0.53 | 0.97 | 0.10 |
| presidio | 0.54 | 0.72 | 0.90 |
| presidio+regex_v2+guard | 0.76 | 0.76 | 0.91 |
| hf_obi | 0.66 | 0.94 | 0.90 |
| hf_obi+regex_v2+guard | 0.69 | 0.93 | 0.89 |
| hf_stanford | 0.95 | 0.98 | **0.27** |
| **hf_stanford+regex_v2+guard** | **0.96** | 0.97 | 0.35 |
| *Published baseline: Amazon Comprehend Medical, threshold 0.5 (dataset paper)* | *0.95* | | *0.89* |

What it adds to the picture:

- **It confirms the challenge-set ranking on text written by someone else.** hf_stanford+regex_v2+guard
  is again the best (0.96 recall) and again on the cost frontier.
- **It separates the engines on over-redaction.** hf_stanford leaves 73% of PHI-free queries untouched;
  Presidio and hf_obi change about 90% of them, as Comprehend Medical did in the paper. For search
  queries sent to an outside tool, that's the difference between a useful query and a gutted one.
- **regex_v2 adds formatted IDs and emails** (emails 0.97, which hf_stanford misses entirely), at the
  cost of raising over-redaction from 0.27 to 0.35.
- **Still leaking:** about 4% of identifiers, mostly unique identifiers (0.43 recall) and some
  locations (`data/deid/by_category.csv`, tier `external`).

The Comprehend Medical row is the paper's number, not a run here; the `aws_comprehend` engine
reproduces it, and scores the dental challenge set, once an AWS account is attached. Our recall is strict (an identifier
counts as removed only if every character is), so it can be lower than a looser match would give.
One ASQ-PHI tag's value doesn't appear verbatim in its query and can't be scored; two values appear
twice and count twice (2,975 scored spans).

## Results on John Snow Labs' 48-note benchmark (jsl48)

John Snow Labs published the labeled set behind its de-identification comparison
([spark-nlp-workshop](https://github.com/JohnSnowLabs/spark-nlp-workshop/tree/master/tutorials/academic/DeIdentification_Benchmarks_Text2Story2025),
[arXiv 2503.20794](https://arxiv.org/abs/2503.20794)): 48 clinical notes (about 5,200 characters each),
1,479 labeled identifiers in six types. Scoring it puts our free engines next to their published
numbers. **Token F1** is their word-level score: a word is PHI if it starts inside a labeled span;
precision, recall and F1 on the PHI class.

| Engine | Token precision | Token recall | **Token F1** | Our entity recall |
|---|---|---|---|---|
| regex_v2 | 0.66 | 0.65 | 0.65 | 0.53 |
| presidio | 0.60 | 0.73 | 0.66 | 0.68 |
| hf_stanford | 0.81 | 0.93 | **0.87** | 0.89 |
| hf_obi | 0.95 | 0.91 | **0.93** | 0.75 |
| hf_stanford+regex_v2+guard | 0.63 | 0.93 | 0.75 | 0.92 |
| hf_stanford+hf_obi+regex_v2+guard | 0.63 | 0.96 | 0.76 | 0.94 |
| routed+guard | 0.51 | **0.98** | 0.67 | **0.97** |
| *Published (their paper): John Snow Labs / Azure / AWS / GPT-4o* | | | *0.96 / 0.91 / 0.83 / 0.79* | |

What it adds, and how far to trust it:

- **The free clinical models hold up on long medical notes.** hf_obi's token F1 (0.93) sits
  between Azure's and John Snow Labs' published scores; hf_stanford (0.87) beats AWS and GPT-4o.
- **But they may have seen these notes.** The notes look like i2b2 discharge summaries (header
  layout, space-split punctuation). hf_obi was trained on i2b2 2014 and hf_stanford partly on
  i2b2, so their scores here may be inflated. The vendor's own labels and notes, too: an
  independent set would be needed to confirm any ranking.
- **Our dental add-ons cost precision on medical notes.** regex_v2 was written for dental notes and
  over-flags discharge-summary text (precision falls from 0.81 to 0.63 when added to hf_stanford),
  and the dental guard protects shapes like `2-5-94` that look like probing readings, so it drops a
  few real dates (0.99 to 0.95). Both are for dental notes; on general medical text, a transformer
  alone scores better.
- **Ages differ by definition.** The set labels every age; Safe Harbor only requires ages over 89,
  which is what our engines target, so AGE recall is near 0 (47 of 1,479 identifiers).
- **Long notes needed a fix.** These notes are longer than the transformers read at once; they're
  now read in windows (`detect_transformer`). Without that, hf_stanford stopped after about 2,300
  characters.

The file isn't in this repo: real clinical text (even with replacement identifiers) breaks the
synthetic-only rule, and the i2b2 notes are normally under a data use agreement. To reproduce, put
`deidentification_benchmark_ground_truth_48_doc.csv` in `data/raw/` and run
`26_deid_benchmark.py --jsl48 data/raw/<file>`. It isn't priced: throughput was measured on short
dental notes.

## Results on MACCROBAT (200 real case reports, external; spec 009)

[MACCROBAT](https://doi.org/10.6084/m9.figshare.9764942.v2) (Caufield 2019, CC BY 4.0) is 200 clinical
case reports from PubMed Central, edited to the case details and annotated by hand. It is the first
**real** clinical prose these engines have seen, written by people other than the note generator.
The original release (brat files: text plus character offsets) is read by default; the same labels
are also published as BIO tags (B = beginning, I = inside, O = outside an entity; Hugging Face mirror
`ktgiahieu/maccrobat2018_2020`, `--source bio`). BIO can't hold overlapping entities, so the mirror has
about half as many clinical entities, and its spacing is rebuilt from tokens.

It was not built for PHI and has no names or contact details, so it checks two things:

- **PHI recall** on a subset derived by rule from its `Date` and `Age` labels (HIPAA Safe Harbor):
  105 dates with a month or day ("June 2013", "July 29, 2015"). No age is 90 or over.
- **Clinical damage**: share of 22,272 clinical entities (symptoms, diseases, procedures, drugs,
  doses, lab values, anatomy ...) with any character removed. This is over-redaction on real text.

`python python/scripts/32_maccrobat_deid.py` (data committed in `data/external/maccrobat/`, CC BY 4.0;
scores in `data/deid/maccrobat_scores.csv`, `maccrobat_by_type.csv`). Run 2026-10-26 on CPU:

| Engine | PHI date recall | Clinical damage |
|---|---|---|
| regex / regex+guard | 0.22 | 0.004 |
| regex_v2 / regex_v2+guard | 0.27 | 0.004 |
| presidio / presidio+guard | 0.97 | 0.034 |
| presidio+regex_v2+guard | 0.99 | 0.036 |
| hf_stanford / hf_stanford+guard | 0.98 | 0.002 |
| hf_stanford+regex_v2+guard | 0.98 | 0.005 |
| hf_obi | 0.97 | 0.005 |
| hf_obi+regex_v2+guard | 0.98 | 0.008 |
| hf_stanford+presidio+regex_v2+guard | 1.00 | 0.037 |

**What it shows.**
- **Month-year dates leak through the regex engines.** They catch full dates ("July 29, 2015",
  "14/9/2005") but not month-year dates ("January 2014", "in November 2014"), the most common form in
  these reports. The synthetic notes always write full dates, so the challenge set couldn't show this.
  The fix (a month-year shape in `regex_v2`) should be written and then checked on a set it wasn't
  tuned on, not on this one.
- **Presidio finds the dates but costs clinical text** (3.4%, about 9 times the regex engines):
  frequencies read as dates ("daily", "weekly"), units and anatomy codes read as IDs ("m2" in mg/m2,
  vertebrae T1/T2, ECG leads V1–V4), eponyms read as names (Gaucher, Crohn, Bowen, Ehlers), "OCT" and
  visual acuity "6/18" as dates, "p.o." as a location. The dental guard doesn't cover these medical
  terms. It also removes every age and most relative dates and years alone, which aren't PHI but carry the timeline.
- **hf_stanford is the best trade here**: 98% of the dates (2 of 105 leak) with the least clinical
  damage of any engine (0.17%, below the regex engines). It also keeps what isn't PHI: no ages and
  5% of relative dates and years alone removed, against 97% and 89% for Presidio. hf_obi finds as many dates but
  removes 98% of ages. Adding Presidio reaches 100% recall at 20 times the clinical damage.
- **Regex damage is low** (0.4%): Title Case terms read as names ("Glasgow Coma Scale") and slash
  triplets read as dates (pressures such as "72/34/47 mmHg").

**Limits.** The PHI subset is a rule over MACCROBAT's labels, not PHI annotation, and is small (105
dates). Case reports are journal prose, already de-identified by the publisher, not chart notes.
Scoring is Python only, as for spec 007.

## A fine-tuned PHI tagger on MACCROBAT (Age, Sex, Date; spec 010)

Built after a course exercise on de-identification as sequence classification: tag every word
B-/I-/O for MACCROBAT's own `Age`, `Sex` and `Date` labels, fine-tune Longformer, tune it (A), add
regex post-processing of dates (B), and report the final system with its errors (C). Note that this
label set isn't Safe Harbor: MACCROBAT's `Date` includes relative dates ("3 days later"), and sex and
most ages aren't identifiers.

**Set-up.** Original brat files to BIO words (`data/external/maccrobat/bio/`): 200 notes split by
document (seed 42) into 140 train, 20 validation, 40 test. Training settings and post-processing are
chosen on **validation**; the test set is reported for every run but never used to choose. Chunks of
whole sentences up to 250 words; labels on each word's first sub-token; CPU, about 55 minutes per
3-epoch run. Score: exact-span entity F1 per type (seqeval rule) and the support-weighted average
("weighted F1"). `python/scripts/33_maccrobat_phi_tagger.py`, `34_phi_tagger_regex.py`; every run in
`data/deid/maccrobat_tagger_runs.csv`, regex rows in `maccrobat_tagger_regex.csv`, error counts in
`maccrobat_tagger_errors.csv`, each error of the model alone in `data/external/maccrobat/errors/`
(`_val` for analysis, `_test` for the final report).

**Task A: training settings** (2026-10-26; validation 89 entities, test 262):

| Run | Model | lr | Epochs | Other | Val weighted F1 | Val Date F1 | Test weighted F1 |
|---|---|---|---|---|---|---|---|
| baseline | Longformer base | 3e-5 | 3 | | 0.69 | 0.45 | 0.77 |
| **chosen** | Longformer base | 5e-5 | 3 | | **0.74** | **0.55** | **0.80** |
| | Longformer base | 5e-5 | 5 | warm-up 10%, weight decay 0.01 | 0.74 | 0.53 | 0.77 |
| | Clinical-Longformer | 5e-5 | 3 | | 0.68 | 0.43 | 0.79 |

A higher learning rate helps; more epochs with warm-up and weight decay don't; the clinical
pre-training doesn't help on journal case reports. Age (test F1 0.95) and Sex (0.99) are near
ceiling in every run; Date (0.73) decides the average. Not tried (CPU time): batch size, longer
chunks (the long-context point of Longformer), other seeds. With 20 validation notes, gaps under
about 0.05 aren't reliable.

**Task B: regex post-processing** (on the chosen model; `phi_tagger.DATE_PATTERNS` tag words the
model left O; `trim_function_words` cuts leading and trailing function words from predicted dates):

| Post-processing | Val weighted F1 | Test weighted F1 | Test Date F1 |
|---|---|---|---|
| none | 0.74 | 0.80 | 0.73 |
| numeric, month-day-year, day-month-year, month-year (each) | 0.74 | 0.80 | 0.73 |
| year (19xx/20xx alone) | 0.74 | 0.80 | 0.74 |
| relative ("3 days later"), hospital day ("day 4") | 0.74 | 0.80 | 0.73 |
| trim function words (chosen greedily on validation) | **0.81** | 0.77 | 0.69 |
| all | 0.80 | 0.77 | 0.68 |

- **Calendar-date patterns add nothing**: the model already finds every full and month-year date.
- **Year alone** finds a few bare years the model misses ("in 1999"), on test only.
- **Relative and hospital-day patterns** add spurious dates: MACCROBAT labels many of those phrases
  as `Time` or leaves them unlabelled.
- **Trimming function words** looks best on validation but loses on test. 57 of the 734 gold dates
  start with a function word the annotators kept ("within 2 weeks", "at age 12", "a week later"),
  and the rule strips them.

**Task C: final system and its errors.** By the rule set before looking at test (choose on
validation), the final system is Longformer base (lr 5e-5, 3 epochs, batch 4, 250-word chunks, seed
42) with `trim_function_words`: **test weighted F1 0.77** (Age 0.95, Sex 0.99, Date 0.69). The model
alone scores 0.80 on test; switching to it now would be choosing on test, so it is reported as the
finding rather than the result: the 20-note validation set is too small to choose post-processing on.

The kinds of error were read on the **validation** listing (the same groups show on test: on
validation the boundary errors are mostly trailing words, "5th day of", "2 weeks after the", which
is why trimming won there; on test more are leading words the annotators kept). Counts on test:

| Test Date errors (model alone) | n | What they are |
|---|---|---|
| Wrong boundary | 27 | Same date, different edges: "the following morning" vs "following morning", "age of 19 years" vs "At the age of 19 years". Weighted F1 counting any one-to-one overlap is 0.91 on test (0.88 validation), against exact 0.80 |
| Spurious | 29 | Mostly hours ("One hour later", "24 h later", "next morning"), which MACCROBAT labels `Time`, a type this label set drops; some look like unlabelled dates ("after 1 week", "day 4"); three a lone "the" |
| Missed | 18 | Bare years ("1999", "2004"), vague time ("now", "Early on", "preoperative", "past year"), gestational and post-operative days ("37 weeks' gestation", "9th POD") |

Next, if this is taken further: map MACCROBAT's `Time` to Date (or score them together); trim only
trailing function words (seen on validation); use cross-validation over the 160 training notes
instead of one 20-note validation set. The year pattern helped on test only, so it is a
test-informed idea: it needs a fresh split before it is used.

### The same exercise on the course's own files

The course's own `train.txt` / `test.txt` were later in hand (`data/external/maccrobat/course/`,
committed unchanged). They differ from the rebuild above: 160 / 40 notes with a different test set
(only 6 of the 40 test notes are shared), words split on spaces and hyphens but with a sentence-final
period kept on the word ("2005."), and 6 labels (no `I-Sex`; test: 41 Age, 37 Sex, 117 Date).
**Defect in those files:** a word that keeps its period is tagged `O` even inside an entity, so 88
training and 16 of the 117 test dates lose their last word ("September 2005." keeps only "September").
Same protocol: 20 of the 160 training notes held out for validation, choices made there
(`33_maccrobat_phi_tagger.py --conll-dir`, 2026-10-26, CPU):

| Run (course files) | Val weighted F1 | Val Date F1 | Test weighted F1 | Test Age / Sex / Date F1 |
|---|---|---|---|---|
| Longformer base, lr 3e-5, 3 epochs | 0.77 | 0.58 | 0.81 | 0.98 / 0.99 / 0.70 |
| **Longformer base, lr 5e-5, 3 epochs (chosen)** | **0.80** | **0.63** | **0.81** | 0.96 / 0.99 / 0.70 |

| Post-processing (chosen run) | Val weighted F1 | Test weighted F1 |
|---|---|---|
| **none (chosen: nothing raises validation)** | **0.80** | **0.81** |
| month-year | 0.80 | 0.80 |
| year | 0.79 | 0.79 |
| trim function words | 0.79 | 0.77 |
| all | 0.79 | 0.73 |

- **Final system on the course files: the fine-tuned model alone, test weighted F1 0.81.** The higher
  learning rate wins on validation in both data sets.
- **Regex dates lose here for a different reason**: they tag sentence-final years ("2005."), which
  the course labels drop, so a correct tag is scored as an error.
- **Part of the remaining error is the labels.** The model often predicts the full date where the
  file cut it ("age 13 years." against gold "age 13"); 7 of the 26 test Date boundary errors are of
  this kind. Weighted overlap F1 is 0.94. The other errors are the same groups as on the rebuild:
  "At the age of" edges, hours labelled `Time` upstream, and vague time ("previous years").
- **Fix for the data, if the exercise is rerun**: tokenize the period off before assigning labels
  (as the rebuild does), or extend a label onto a word that keeps its period.

## Combining engines: bigger unions and routing

The `+` ensembles above are plain unions: anything any engine flags is removed. Two other ways to
combine were scored on the same run:

- **Bigger unions:** hf_stanford plus hf_obi (which catches the dates hf_stanford misses), or plus
  Presidio.
- **Routing (`routed+guard`):** for each engine and each identifier type it reports, measure how
  often its flags were really PHI on the easy and hard tiers; keep only pairs at least 80% precise,
  then union those. The routes were chosen before scoring and never saw the unseen tier or ASQ-PHI
  (`data/deid/routes.csv`).

| Combination | Unseen recall | ASQ-PHI recall | **ASQ-PHI over-redaction** | Decoy damage (all) | Engine $ per 1M notes |
|---|---|---|---|---|---|
| hf_stanford+regex_v2+guard | 0.74 | 0.96 | **0.35** | 0.02 | ~$23 |
| hf_stanford+presidio+regex_v2+guard | 0.80 | 0.98 | 0.91 | 0.06 | ~$28 |
| hf_stanford+hf_obi+regex_v2+guard | 0.87 | 0.98 | 0.89 | 0.02 | ~$101 |
| routed+guard (all four engines) | **0.88** | **0.98** | 0.92 | 0.06 | ~$106 |

What it shows:

- **Adding a second model buys recall on unseen shapes.** hf_obi lifts unseen recall from 0.74 to
  0.87, mostly by catching the dates hf_stanford misses.
- **It costs over-redaction.** Every combination with hf_obi or Presidio changes about 9 in 10
  PHI-free ASQ-PHI queries, against about 1 in 3 for hf_stanford+regex_v2+guard. Which matters more
  depends on the use: for chart notes kept inside the study, a leak is worse than a removed word;
  for search queries sent to an outside tool, a gutted query is useless.
- **Routing didn't separate the engines.** On the training tiers nearly every engine-type pair was
  over 80% precise, so routing kept almost everything (it dropped only regex_v2's location
  guesses) and behaves like the four-engine union. Those tiers have no PHI-free notes, so they can't
  show which engine over-redacts clean text. Routing needs training notes that include hard
  negatives before it can learn that trade-off.

## Cost-effectiveness

`data/deid/cost_effectiveness.csv`, per 1M notes, for the full mix (`all`) and the held-out tier (`unseen`):

- **Engine cost.** Local engines: node-hours at the throughput **measured** here (regex about
  12,600 notes/s, regex v2 about 3,300, Presidio about 60, hf_stanford about 11 and hf_obi about 3
  on CPU) × the CPU node price (ILLUSTRATIVE $1/hour). Services: the vendor's own billing unit,
  with volume tiers; table below.
- **Review cost.** Human QA of 1 in 1,000 de-identified notes, the same for every engine.
- **Outcome.** Leaked identifiers per 1M notes, then decoy damage as a tie-break.
- **Frontier.** An engine is dominated if one that costs no more leaks no more. ICER = extra USD
  per leaked identifier avoided.

With these inputs every local engine costs under $90 per 1M notes, even the transformers on CPU;
the $3,000 review sample is most of the cost. So the choice comes down to leaks. On both tiers the
frontier ends at hf_stanford+regex_v2+guard: about $21 more per 1M notes than
presidio+regex_v2+guard buys about 375,000 fewer leaked identifiers (all tier).

### What the paid services would cost

Engine cost to de-identify **1 million notes** in one billing month, list prices, US East, checked
2026-10-26. Not run here yet, so this compares **price only**, not quality.

| Engine | Billed per | Price | 1M notes of 410 chars (study notes) | 1M queries of 151 chars (ASQ-PHI) | Price source |
|---|---|---|---|---|---|
| hf_stanford (local, CPU) | node-hour | ~11 notes/s measured | ~$25 | ~$25 | measured; node price ILLUSTRATIVE |
| Azure Health Data Services de-id | MB, 50 MB/month free | $0.05/MB | ~$18 | ~$5 | Azure retail prices API |
| Databricks `ai_mask` | token | $0.50 in / $1.50 out per 1M tokens | ~$295 | ~$166 | Databricks pricing page ($0.07/DBU × Llama 3.3 70B DBU rates) |
| Our LLM prompt (`llm`) on the same endpoint | token | same | ~$281 | ~$249 | same |
| Azure AI Language PII | 1,000-char record | $1.00 per 1,000 to 500K, then $0.75 | ~$875 | ~$875 | Azure retail prices API |
| John Snow Labs Healthcare NLP | licence + node hours | $7,000/month licence (their example); list price by quote | ~$189 if the licence is charged for hours used; **~$7,000** if bought by the month | ~$70 / ~$7,000 | vendor's own example, not a list price |
| **Amazon Comprehend Medical** | 100 chars, 1-unit minimum | $0.0014 to 1M units, $0.0005 to 2M, then $0.00025 | **~$2,650** | ~$1,900 | AWS price list API |

For scale, the human review sample costs about $3,000 per 1M notes with any engine.

What drives the differences:

- **Unit size.** Comprehend bills every 100 characters (a 410-character note is 5 units), Azure
  Language every 1,000 (1 record), Azure de-id per megabyte. Short ASQ-PHI queries still pay
  Comprehend's and Azure Language's one-unit minimum.
- **`ai_mask` pays to get the note back.** It returns the whole masked note, so output tokens
  (the expensive kind) grow with note length; our `llm` engine returns only the identifiers. Its
  own prompt isn't published, so its 150-token overhead is assumed.
- **Pay-per-token is a floor.** Databricks rate-limits pay-per-token endpoints and points large
  workloads to provisioned throughput, billed per hour.

### Microsoft's options compared: price and quality

Microsoft offers several services that find PHI, billed on very different meters; using the wrong
one can cost hundreds of times more. Price per 1M notes, list price, US East (Azure retail prices
API, 2026-10-26). Quality is **measured here** only for Presidio; the Azure services haven't been run
here yet, so their quality comes from published comparisons, marked as such.

| Option | Built for | Library / call | Billing meter | 1M notes × 410 chars | 1M notes × 5,250 chars | Quality |
|---|---|---|---|---|---|---|
| **Health Data Services de-identification service** (`azure_deid`) | PHI in clinical free text: 27 types; tag, redact or surrogate | `azure-health-deidentification`, `DeidentificationClient` | "De-Id": 50 MB free, then $0.05/MB | **~$18** | ~$260 | Token F1 0.91 on John Snow Labs' 48 notes (*vendor-run comparison*, arXiv 2503.20794); not run here |
| **AI Language PII**, PHI domain (`azure_language`) | General PII, with a health filter | `azure-ai-textanalytics`, `recognize_pii_entities(domain_filter="phi")` | "Standard Text Records": $1 per 1,000 records (1,000 chars), tiered | ~$875 | ~$3,050 | No independent figure found; not run here |
| **Text Analytics for Health** | Clinical entity extraction (diagnoses, drugs); *not* a de-identification product | same library, `begin_analyze_healthcare_entities` | "Health Text Records": 5K free, then $20 per 1,000 records, tiered | **~$17,400** | **~$60,900** | Not designed for de-identification |
| Text Analytics for Health commitment tier | Prepaid monthly capacity | — | "Commitment Tier TA4H": $14,000/month and up | fixed | fixed | — |
| FHIR `$de-identify` / Tools for Health Data Anonymization | Structured FHIR and DICOM records, not free text | FHIR service or open source | "Structured De-Identification": $1.14/GB (FHIR); open source free | n/a | n/a | Rule-based on fields; doesn't read notes |
| **Presidio** (open source, Microsoft) | General PII, run on your own compute | `presidio-analyzer` | compute only | ~$5 | not measured | **Measured here:** unseen recall 0.53, ASQ-PHI recall 0.54 with over-redaction 0.90, jsl48 token F1 0.66 |

Takeaways:

- **For clinical notes, the de-identification service is the one to use**, and at $0.05/MB it's also
  the cheapest Azure option. The same text through Text Analytics for Health costs ~1,000× more.
- **If a small Azure run cost thousands of dollars, check the meter name** in Cost Management (group by
  Meter). "De-Id" would need ~200 GB of text to reach $10,000; "Health Text Records" reaches it at
  ~100,000 long notes; a commitment tier bills even when idle.
- **The de-id service's current price dates from 1 May 2025**; a run before then may have been billed
  at an earlier rate.

**Checking John Snow Labs' own comparison.** Their benchmark write-up prices 1M notes of 5,250
characters at $2,418 for Healthcare NLP (node time plus a share of a $7,000-a-month licence), against
$13,125 for Azure de-identification and $14,525 for Comprehend Medical. With the same inputs this
model gives $2,420 for theirs and **$14,525 for Comprehend** (identical: same volume tiers), but
**about $260 for Azure** at today's $0.05/MB. Their Azure figure works out to $2.50/MB; either the price
has dropped since early 2025 or they used a different rate. At today's list prices Azure
de-identification is the cheapest paid option here, not the most expensive.

Every service rate above was read from the vendor's own price source on 2026-10-26 (list price,
US East); `costs.yaml` names each one. Contract discounts, other regions and committed-use tiers
change them. The local engines' node price ($1/hour) is still ILLUSTRATIVE.

Python and R compute the same frontier from `cost_inputs.csv` (parity test).

## Human review in Label Studio (spec 008)

Two projects turn the human review sample into data. **Gold**: annotators mark every identifier in
the original note (pre-filled by an engine; a fifth of notes without, to measure anchoring), and
engines are scored against their consensus, which is how an engine gets scored on real notes. **QA**:
reviewers read the chosen engine's output and say whether anything still identifies, giving the leak
rate with a 95% interval. Set-up: [labelstudio/README.md](../labelstudio/README.md#de-identification-review-projects-spec-008);
protocol: [deid_review_protocol.md](deid_review_protocol.md). Only simulated annotators have run so far.

## Limits

- The challenge set is still written by one person. The unseen tier is held out from regex v2,
  not from that person's idea of a "hard" note. Real notes will differ again.
- Leaks are counted, not weighted: a leaked SSN and a leaked first name count the same.
- The study pipeline still uses `regex` by default (`study.py`). Switching it is action item H2.
