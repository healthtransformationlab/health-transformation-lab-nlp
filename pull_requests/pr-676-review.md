# PR 676 review: how far the code graph leads to each fix in the competition's development set (#669)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/669-028-devset-graph-reach`, `Closes #669`; spec 028 T025 | ok |
| Competition data: the table holds task ids, counts and ranks. No statement, patch, test, graph or embedding is committed, and the script's cache and checkpoint live outside the repository. The host has said derived labels keyed by task id may be published (Paper Track forum, topics 749803 and 757562) | ok |
| The rules are scripts 63's and 64's, imported, not rewritten: `changed_files`, `changed_runs`, `edited_nodes`, `named_nodes`, `call_distance`, `best_rank`, `chance_top`. What differs is in three tested helpers: `git_headers` (the competition's patches have no `diff --git` line), `resolve_module` (a module under `src/` or a folder that is not a package) and `fetch_source` (a file from GitHub at the base commit, once) | ok |
| Counts recomputed from the committed table for this review: 129 tasks; 5 with no changed module in the graph, 10 with no existing node edited, 114 with one; of the 114, named 29, call edges 23, embedding search first 6, first ten 34, any of the three 66 | ok |
| Chance: 0.148 for the first place and 1.453 for the first ten, summed over the 114 by `chance_top`; the README rounds to 0.1 and 1.5 | ok |
| The competition's own search tool is not credited with a node the statement names itself (rank 0): the summary counts finds beyond a name (6) and beyond a name or call edge (0), and a test checks it. An earlier total of 35 counted the 29 and was never published | ok |
| "The provided embeddings are not EmbeddingGemma document vectors" rests on one measurement (759 nodes of one requests graph: mean cosine 0.05, never above 0.21). The README says it was measured once and is not a column of the table | note |
| The README is written from the tables by a script kept outside the repository (it formats numbers; it computes none that the tables or the two scripts do not give). The script is not committed | note |
| An independent count of the same 129 tasks by another participant agrees closely, and the README sets the two side by side instead of claiming the count as new | ok |
| Test first: nine tests, each failed before its code. The resume option was added after a run was cut short at its time limit, with its two tests first | ok |
| No GPU, no secrets, no real data; merging starts no run and publishes nothing | ok |

Nothing blocking.

## Notes
- The run that made the table took about 70 minutes on four CPU cores. A named node is found by a fixed rule, so
  the name and call-edge counts are lower bounds in both sets, as the README says.
- If the README generator is wanted in the repository, it belongs with script 67 as a `--readme` option; it was
  left out to keep this change to the count itself.
