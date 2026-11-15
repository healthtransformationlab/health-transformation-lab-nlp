# Financial trade-offs

> **Illustrative.** Prices in `costs.yaml` are placeholders, model accuracies
> for the BERT and LLM rows are simulated, and the reviewers are simulated.
> This page shows how to reason about the trade-offs and where the numbers come
> from; it is not a cost estimate for any organization. See [DISCLAIMER](../DISCLAIMER.md).

Methods behind the numbers: [cost_effectiveness.md](cost_effectiveness.md). De-identification costs: [deidentification.md](deidentification.md#cost-effectiveness).

## The question

For a corpus of about a million notes: which method gives enough accuracy, and
passes the [acceptance test](process.md#validation-criterion-as-reliable-as-a-human-reviewer),
at the lowest total cost? And what does it cost to *prove* that?

## Cost components

| Component | Scales with | Where it's modeled |
|---|---|---|
| **Human review for validation** | charts × reviewers × minutes per chart × hourly cost | here (below); not in `costs.yaml` yet |
| **Build**: synthetic data, rules, labeling setup | one-off engineer time | not modeled |
| **Training / fine-tuning** | GPU hours per model | `train_hours` in `costs.yaml` |
| **Inference over the corpus** | notes ÷ throughput × node price, or tokens × token price | `method_cost` (`cost_effectiveness.py`) |
| **LLM judge** (accuracy beyond the reviewed set) | judged notes × tokens × price | `judge_cost` |
| **Storage and tracking**: Delta, MLflow, Lakebase | data size, uptime (scale-to-zero helps) | not modeled; small next to review time |
| **Radiograph AI or other licences** | per image / per site | not priced (`fusion_tfidf_rad` note in `costs.yaml`) |
| **Maintenance**: re-validation when prompts, models or data change | each change | re-run the review set and judge calibration |
| **Cost of errors** | unsafe-error rate × consequences downstream | `unsafe_rate` / `s2_rate` reported; not priced |

## Inference vs accuracy (dry run)

From `data/corpus/simulated_cost_effectiveness.csv` (1,000,000 notes, illustrative prices):

| Method | Judge-corrected accuracy (95% CI) | Cost for 1M notes | On the frontier? |
|---|---|---|---|
| `note_rules` | 0.785 (0.732–0.838) | $0.01 | yes |
| `tfidf_logreg` | 0.922 (0.878–0.964) | $0.06 | yes |
| `fusion_tfidf_rad` | 0.895 (0.852–0.940) | $0.07 + radiograph licence | dominated |
| sim: DistilBERT | 0.885 (0.840–0.930) | $4.78 | dominated |
| sim: BioClinical ModernBERT base | 0.918 (0.873–0.960) | $13.41 | dominated |
| sim: MedGemma 1.5 4B (self-hosted GPU, assumed throughput) | 0.856 (0.809–0.902) | $138.89 | dominated |
| sim: hosted LLM (per-token) | 0.888 (0.842–0.934) | $256.69 | dominated |
| sim: MedGemma 27B (self-hosted, assumed) | 0.904 (0.859–0.951) | $740.74 | dominated |

Two things to take from the shape, not the numbers:

1. **The cost depends on the model, not only on people.** Every row above reads only
   the note; the most expensive is in the hundreds of dollars for a
   million notes at these prices. A frontier commercial model costs far more: at
   list price, about $5,500 for the note alone and about $1.2 million reading the
   whole record with examples and reasoning, three calls a visit (assumed tokens;
   `docs/claims.yaml`, `tiers`). Choose the least costly model that passes the
   acceptance test.
2. **Overlapping intervals.** Most rows' CIs overlap, so on 223 reviewed charts
   the frontier can't separate them. More review charts, or the acceptance test,
   decide, not the point estimates.

Synthetic notes are easier than real ones, which flatters the cheap text
methods. Expect the gap to widen on real notes, especially for L3 (infer) cases.

## Human review is the dominant cost

Arithmetic with the protocol's pace (1–3 minutes per chart; 2 used here):

| Scenario | Charts | Reviewers | Hours |
|---|---|---|---|
| Validation set, as built | 233 | 4 | 31 |
| Larger validation set (tighter CIs) | 600 | 4 | 80 |
| Review every note once (no AI) | 1,000,000 | 1 | 33,333 |

Multiply by a loaded hourly cost of your choosing. At an illustrative $100/hour,
the validation set is about $3,100, a larger one $8,000, and reviewing every
note by hand $3.3M. So the main financial argument for the AI isn't the
inference price. It's replacing review hours, *provided* it passes the acceptance
test with a margin people accept.

## Levers and their trade-offs

| Lever | Saves | Costs / risks |
|---|---|---|
| More review charts | Tighter CIs; clearer winner | Reviewer hours (linear) |
| Fewer reviewers per chart (e.g. 3 not 4) | 25% of review hours | Noisier human bar; Fleiss kappa less stable |
| Stratify review toward hard (L3) and rare stages | Fewer charts for the same information | Weighting needed for overall estimates |
| LLM judge instead of more review | Accuracy estimates at corpus scale for dollars | Judge must be calibrated against people first; adds its own CI |
| Cheap model first, LLM only on low-confidence notes (cascade) | Most notes at TF-IDF/BERT cost | Need a confidence threshold, validated by level |
| Self-host vs hosted LLM | Per-token fees at scale; data stays inside | GPU ops, idle cost (scale-to-zero helps), throughput must be measured |
| Fine-tune (LoRA) vs zero-shot | Higher accuracy per token, shorter prompts | GPU training hours; re-validate after each retrain |
| Retrieval / vocabulary grounding ([rag_and_vocabulary.md](rag_and_vocabulary.md)) | Better L2/L3 accuracy without a bigger model | Longer prompts (token cost), vocabulary upkeep |
| Free Edition for learning | $0 | Quotas, no GPU serving, capacity not guaranteed; not for real data |

## Decision rule (draft)

1. Drop any method that fails the acceptance test (inferior or inconclusive
   after a reasonable review budget).
2. Among the rest, drop dominated methods (more cost, no more accuracy).
3. Choose the cheapest remaining method whose unsafe-error rate is acceptable,
   unless the next one up buys a meaningful drop in unsafe errors for its
   incremental cost (ICER, `16_cost_effectiveness.py`).
4. Price re-validation into the choice: a method that needs re-review after
   every model update costs more than its inference line suggests.

## To make it real

- Replace every price in `costs.yaml` with actual rates; measure throughput on
  the target hardware (`14_benchmark_cost.py`).
- Add reviewer cost per hour and minutes per chart to `costs.yaml`, and the
  review line to the cost table.
- Run the real models (BERT ladder, MedGemma) instead of `sim:` rows.
