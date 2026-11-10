# Tasks: local agent harness

**Tests**: required (test-first).

## US1 - A local runner for the documented harness #543
- [x] T001 Failing tests: tools, budget, prompt, loop, patch extraction, verification, oracle and null bounds
- [x] T002 `agent_harness.py`
- [x] T003 `scripts/59_run_agent.py`, reading gemma-developer-agent's `agent.yaml`, `prompts/system.md` and `eval_config.yaml`
- [x] T004 Calibration runs (Nov 4, 2026, in the sandbox, gemma-developer-agent's prompt, tools and budgets): `calib:oracle` resolves 111 of 113 published tasks and 3 of 3 samples, `calib:null` 0 of 113 and 0 of 3. The two the oracle can't resolve here skip a required test: `htlnlp_c2e4466e` needs a Postgres server, `htlnlp_cb6ac730` needs R. They are left out of a real model's denominator. Tables in `data/tasks/agent_runs/`

## US2 - The Gemma agent on a Kaggle GPU #544
- [ ] T005 Gemma 4 on a Kaggle GPU, one task per private kernel (spec, "No answers on Kaggle"): `gemma_agent.py`, `kaggle/agent_bundle.py`, `kaggle/agent_kernel.py`, `scripts/60_kaggle_agent.py`; a pilot of three tasks, then the full run on the owner's go-ahead (about 113 GPU runs)
  - Pilot (Nov 4, 2026, 2x T4, 30-minute budget, thinking off): `gemma-4-e4b-it` resolves 2 of 3, `htlnlp_143` and `htlnlp_174`; `htlnlp_170`'s patch fails one required test. 2 to 4 tool calls and 4 to 6 minutes of agent time each, prompts up to 11,067 tokens (`data/tasks/agent_runs/gemma-4-e4b-it_kaggle.csv`). Measured with this repository's harness, not the competition's evaluator. The full run waits for the owner's go-ahead.
  - Full run, first 10 h (Nov 5-6, 2026; PR 620): 56 rows, 5 resolved. Two harness faults found in its transcripts (#621): the 20 tasks run from the published task set came back with empty patches (git refused the snapshot's files, owned by the user that built them), and the 36 run from a local build shipped no code graph or embeddings. Fixed in #621; the 20 rows are dropped and those tasks run again, the 36 are kept and noted.
  - Paired rerun with the code graph (Nov 10, 2026, run 42742256439, with the owner's go-ahead; a cap on GPU hours stopped it at 28 of the 33 tasks given): the tasks first run without their graph, run again on the fixed harness with the same settings. On the 23 that are in the published set the model resolved 2 the first time and 2 the second (one lost, one gained, one both), wrote a patch for 18 and then 20, and called a graph tool in 4 of 23 runs (6 of 145 tool calls). The competition's evaluator agrees with this harness on all 23 rerun patches. `data/tasks/agent_reruns/` keeps both runs side by side, since a rerun replaces its row in the run table
  - Larger-budget rerun (Nov 10, 2026, one L4 on Colab Pro+, started by the owner; #656): the 48 scored tasks, cheapest first, on the same harness with 16,384 output tokens a turn, thinking on, 100 tool calls and 20 minutes. Each is set beside its tight-limits run in `data/tasks/agent_reruns/gemma-4-e4b-it_larger_budget.csv`; the counts, the smaller context (20,000 tokens) and the notebook's network access are in that folder's README. Kept out of `agent_runs/`, which feeds `fact_agent_task_run` and the Kaggle allowance check

## US3 - Resolution rates per tier #545
- [ ] T006 Rates overall and per tier, with and without the skill, in spec 028 T012
