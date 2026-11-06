# PR 620 review: Gemma 4 E4B on 53 coding-agent tasks, Kaggle GPUs (#569)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/569-...`, `Refs #569` (one part of US2) | ok |
| Only the results file changes against main | ok |
| No answer leakage: one private, offline kernel per task; no reference patch or tests in a bundle | ok |
| Every row carries `run_ts` and its kernel URL; rerun replaces a task's row (merge by `instance_id`) | ok |
| Cost labelled an estimate; allowance hours err high (queue and boot included) | ok |
| Harness note: measured here, not the competition's evaluator | ok |
| Within the owner's 10-hour cap | 10.19 h recorded, plus one unrecorded in-flight task when the job hit its limit |

## Notes
- The cap check uses expected time per task, and actual sessions ran longer, so the 5.5 h dispatch outlasted the
  355-minute job. Lower dispatch caps (5 h) or check measured time too; worth a small follow-up.
- 26 of 50 failures are empty patches: the agent ended without editing. That's the first thing to look at before
  spending more allowance.

## Blocking
None. Results of a limited-compute run: waits for the owner's "merge".
