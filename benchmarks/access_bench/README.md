# AccessBench (exploratory)

Whether an AI answer helps someone **actually get care** (coverage, travel,
safety-net pathways, accommodations) — not only whether the facts are sound.

| Path | Holds |
|------|--------|
| `prompts/` | Authoring prompts that expand access seeds into scored items |
| `seeds/` | Short seed questions about getting care |
| `items/` | Generated scored rows (JSONL preferred) |

## What goes here vs OralHealthBench

| Put the item in… | When it is about… |
|------------------|-------------------|
| **AccessBench** (`access_bench/`) | Getting care: insurance/cost, travel, FQHC/NEMT, VA dental class, EPSDT/CHIP pathways, ADA accommodations, finding affirming or accessible providers, dropped constraints |
| **OralHealthBench** (`oral_health_bench/`) | Accurate answers at the medicine–dental seam (medicines, chronic disease, emergencies) without a binding access pathway |

If a seed has both, prefer AccessBench when the hard part is the pathway or
constraint; prefer OralHealthBench when the hard part is clinical/factual
accuracy.

## Expand seeds into scored items

1. Put seed questions in `seeds/`.
2. Run an LLM with [`prompts/expand_seed_questions.md`](prompts/expand_seed_questions.md).
3. Save each expanded row under `items/` (one JSON object per line).

Ids use an `ACC_` prefix. Rubrics cite published statutes and guidelines only.
Label simulated scores as simulated.

## Dual fixture: access + planted synthetic PHI

[`items/simulated_access_phi_items.jsonl`](items/simulated_access_phi_items.jsonl) plants
invented identifiers (challenge-pool names, example phones, SSNs starting with 9) inside
realistic access prompts. Use it to score:

| Gate | Pass when |
|------|-----------|
| Access pathway | `must_include` met, `red_flags` avoided |
| PHI leak | `deid.leak_check(answer, known_phi)` is empty |

```python
from health_transformation_lab_nlp import access_phi_items, deid
rows = access_phi_items.load_items()
leaks = deid.leak_check(model_answer, access_phi_items.known_phi_for_leak_check(rows[0]))
```

Real PHI is never allowed here.
