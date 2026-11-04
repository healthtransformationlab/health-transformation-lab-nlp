# PR review: 020 BUG1, seed variants in the Kaggle encoder notebook (#559)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Issue and branch | `Closes #559`; branch `fix/559-020-encoder-seed-variants` |
| Test first | `tests/test_rungs.py::test_parse_variant_reads_the_class_weight_and_seed_suffixes` failed (ImportError) before `parse_variant` |
| Fix | `rungs.parse_variant` (traced) is the inverse of `output_tag` for +cw and +s<seed>; the notebook passes `--seed` and names the output the same way |
| Tests | Kaggle encoder, rungs and telemetry tests: 49 passed |
| Scope | no run started by this PR; the notebook only runs when the workflow is started |

Nothing blocking.
