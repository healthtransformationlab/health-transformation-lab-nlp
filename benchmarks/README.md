# Benchmarks

Personal learning project; not affiliated with any employer or organization.
Synthetic and public sources only — no PHI. See [DISCLAIMER.md](../DISCLAIMER.md).

Always in this order (AGENTS.md):

| Bench | Code name | What it scores |
|-------|-----------|----------------|
| **PerioBench** | `perio_bench` | Trustworthy records: finding gum disease in dental records (phenotyping) and related EDR quality |
| **OralHealthBench** (planned) | `oral_health_bench` | Accurate AI answers where medicine meets dentistry |
| **AccessBench** (exploratory) | `access_bench` | Whether an answer helps someone actually get care: oral health first, then medical and mental (ADR 0014) |

**Routing items:** coverage, travel, safety-net pathways, accommodations and other
getting-care seeds → `access_bench/`. Medicine–dental factual accuracy →
`oral_health_bench/`. See each folder’s README.

Working material for expanding and storing scored items lives under each bench folder.
Committed datasets and gold tables still follow the paths in AGENTS.md (`data/`, Unity Catalog schemas).
