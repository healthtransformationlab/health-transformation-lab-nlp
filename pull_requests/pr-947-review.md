# PR 947 review: AccessBench scores positive actions only, and reports each outcome separately

Closes #943 (spec 045 US1, epic #942). Range: `origin/feat/938-044-access-sections..feat/943-045-positive-scoring`
(stacked on PR 941). Files: `specs/045-access-scoring-v2/` (new), `docs/access_bench_external_reviews.md` (new),
`access_keypoint_judge.py`, `access_batch.py`, `gold_names.py`, `gold_model.py` with rebuilt diagrams and the regenerated
contract, `benchmarks/access_bench/README.md`, and tests.

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none.
- **Real data:** none.
- **Claims:** every number in the new doc comes from the item files or a named live run (30 of 75 negative points,
  0 of 15 time-sensitive, 0 of 60 red flags, 37 of 60 truncated, 14 of 15 at 1,500 tokens). The external reviews are
  labelled AI opinions and suggestions.

## Findings (verified)

1. **No new prompt needed for US1:** the judge already returns a verdict per padded key point; coverage takes the
   positive ones by index, so v2 verdicts score the new way and old runs could be rescored from per-point data if it had
   been stored (it wasn't: US2 stores it).
2. **Legacy kept:** `score_ratio` keeps its padded meaning, relabelled legacy in its column description, so the three
   existing runs stay comparable.
3. **Every item keeps at least two positive points** (tested); none falls below the floor after removing negatives.
4. **Stacked:** retarget to `main` once PR 941 merges.

## Checks

- 17 test files (AccessBench modules, gold model, contracts, diagrams, telemetry, wording): 239 passed. The new tests
  failed before the code.

## Verdict

Approve, merging once CI is green and PR 941 has merged. Nothing runs and nothing is published.
