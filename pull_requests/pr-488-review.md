# PR #488 review: embed the task set's code graphs with EmbeddingGemma (spec 028 T010)

Refs #355 (US4). Branch `feat/355-028-embeddings`. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Change

`task_graph.embed_graph` and `write_embeddings` (tested first, five new tests in `test_task_graph.py`), the script
`59_embed_graphs.py`, an `embed` extra, and the inventory, register and spec task list updated to match.

## Checks against the rules

| Rule | Result |
|---|---|
| Issue, branch, `Refs #355` (wheels, T010a, still open) | yes |
| Spec | spec 028 US4 already covers it; tasks.md updated |
| Test first | five tests failed before `embed_graph` existed, pass after |
| `@traced` on public functions | `embed_graph`, `write_embeddings` |
| Settings checked before work | graphs present, `HF_TOKEN` shape, one authenticated HEAD before the model loads; a 403 names the licence |
| Secrets | the token is read from the environment and never printed or logged |
| Idempotent writes | each `.npz` is overwritten whole |
| Model inventory | EmbeddingGemma added, with paper and licence (checked on the model card: `gemma`) |
| Honest outputs | real run; parity with the competition's unnamed model stated as unverified |
| Synthetic only / no PHI | the inputs are this repo's own code |
| Org name, wording, bench order | tests pass |

## Findings

1. **Distinct texts are fewer than distinct ids (809 vs 1,183).** Checked: the package was renamed during the
   history, so the same function appears under two ids. The cache is keyed by text, so both get the same vector,
   which is correct.
2. **Long functions are cut at 512 tokens.** The start of a function carries its name, signature and docstring.
   Stated in the script. Not blocking.
3. **Optional:** `np.savez_compressed(path, **vectors)` would clash with a node id of exactly `file`. Ids are dotted
   module paths, so it can't happen.

Verdict: ready to merge.
