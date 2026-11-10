# PR 661 review: the larger-budget rerun, paired with the tight-limits run (#656)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/656-...`, `Closes #656` | ok |
| Test first: the paired-row and graph-call tests failed before `paired_row` and `graph_tool_calls` existed; `test_gemma_agent.py` passes (38) | ok |
| The table is written whole on each `score` (idempotent); every row carries both runs' timestamps (`tight_run_ts`, `larger_run_ts`) | ok |
| Labelled as this repository's harness, not the competition's evaluator, in the script's output and the README | ok |
| A run still going is said to be: "23 of the 48 scored tasks had finished"; the tasks are the cheapest first, not a random sample, and the README and the paper say so | ok |
| Thinking was really on: Gemma 4's chat template adds its thinking marker to the system turn when `enable_thinking` is set (read from the model's `chat_template.jinja`) | ok |
| No answer leakage: one task's bundle on disk at a time, no reference patch or tests in a bundle (PR 657's checks) | ok |
| Network: Colab has it and Kaggle's kernels did not. No `run_command` in the 23 transcripts names a network tool or address, and commands get an allow-listed environment without the notebook's Kaggle token | ok, stated |
| Graph-tool calls are counted from each transcript's tool calls, not from the model's own summary | ok |
| No secrets, no real data, no organisation names; wording and conventions tests pass | ok |
| Merging starts no run and publishes nothing; the private results dataset is not attached anywhere public | ok |

## Notes
- The comparison is not clean on two counts, both in the README: the context is 20,000 tokens against 24,576, and one
  run (`htlnlp_94`) had turns stopped at that limit (`larger_over_context_turn_count`).
- 2 resolved against 2 on 23 tasks says the tight limits did not decide the baseline's result on its cheapest tasks.
  It says nothing about the dearer ones: one task flipped each way (`htlnlp_187` gained, `htlnlp_226` lost).
- The Colab run goes on after this table was written; a later `score` rewrites the table whole.

## Blocking
None.
