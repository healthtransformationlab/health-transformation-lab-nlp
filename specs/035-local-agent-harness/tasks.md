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

## US3 - Resolution rates per tier #545
- [ ] T006 Rates overall and per tier, with and without the skill, in spec 028 T012
