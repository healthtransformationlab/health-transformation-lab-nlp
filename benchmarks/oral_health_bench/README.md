# OralHealthBench (planned)

Score the AI that people ask on questions at the **seam of medical and dental
care**: medicines, chronic disease, emergencies, and related factual accuracy.

| Path | Holds |
|------|--------|
| `prompts/` | Authoring prompts for medicine–dental accuracy items |
| `seeds/` | Short seed questions (clinical / oral–systemic / emergency facts) |
| `items/` | Generated scored rows after expansion |

## Access items do not live here

Anything about **getting care** (coverage, travel, safety-net, accommodations,
finding a provider under constraints) goes in
[`../access_bench/`](../access_bench/), including its seeds, prompts and items.

| Put the item in… | When it is about… |
|------------------|-------------------|
| **OralHealthBench** | Accurate answers where medicine meets dentistry |
| **AccessBench** | Whether the answer helps someone actually get care |

## Expand seeds

Add medicine–dental seeds under `seeds/` and an expand prompt under `prompts/`
when that authoring flow is ready. Until then, access-oriented expansion uses
[`../access_bench/prompts/expand_seed_questions.md`](../access_bench/prompts/expand_seed_questions.md).
