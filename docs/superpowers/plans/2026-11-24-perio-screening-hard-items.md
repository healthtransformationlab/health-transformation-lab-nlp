# Plan: Perio screening hard AccessBench items

> Design: `docs/superpowers/specs/2026-11-23-perio-screening-access-hard-items-design.md`

## Files

| File | Role |
|------|------|
| `benchmarks/access_bench/seeds/perio_screening_hard_2030.md` | Seed list + forum links |
| `benchmarks/access_bench/items/perio_screening_hard_items.jsonl` | 10 scored rows (no planted PHI) |
| `python/health_transformation_lab_nlp/access_hard_items.py` | Load + validate (no PHI contract) |
| `python/tests/test_access_hard_items.py` | TDD: count 10, ACC_PERIO_SCR_*, rubric shapes, source_thread_url |
| `benchmarks/access_bench/README.md` | One paragraph pointing at the new set |

Do **not** change `simulated_access_phi_items.jsonl` or Access LLM batch default path in this PR (follow-up).

## Tasks

1. Failing test for hard-item loader / 10 ids.  
2. Module + JSONL + seeds until green.  
3. README blurb + wording/org tests clean.
