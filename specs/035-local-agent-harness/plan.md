# Plan: local agent harness

- `python/health_transformation_lab_nlp/agent_harness.py`:
  - `prepare_workspace`, `Budget`, `Session`, `call_tool` (the nine tools), `CodeGraph`;
  - `build_agent_prompt`, `fill_instruction`;
  - `run_agent`, `extract_patch`, `verify` (reusing `task_gate.strip_protected`, `target_tests`, `run_tests`),
    `run_task`;
  - `OracleModel`, `NullModel`, `load_graph`.
- Models implement `step(messages, tools)` and return `{content, tool_calls: [{id, name, arguments}],
  finish_reason}`. Messages are OpenAI chat format, so US2's client passes them straight through.
- `python/scripts/59_run_agent.py`: a submission folder, the tasks, and the snapshots or this repo's history, in;
  `data/tasks/agent_runs/<model>_<tasks>.csv` out.
- Tests (`python/tests/test_agent_harness.py`): each tool's contract, the budget warning and limits, the prompt
  sections, nudges, patch extraction (new files in, protected files out), the test-file reset, and the oracle and
  null bounds, on a tiny git repo.
