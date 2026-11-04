# PR 578 review: the Gemma agent on Kaggle GPUs, one task per private kernel

Refs #544. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: the parser, message folding, bundle, kernel metadata, cache-extension and runner tests were each
  written failing first. Full suite: 2,099 passed, 4 skipped.
- No answers reach the agent:
  - the bundle holds only `TASK_FIELDS` (no patch, no tests);
  - the snapshot is refused unless its `.git` holds one commit and no unreachable objects;
  - the shipped files are ones no task changes (`touched_shipped`);
  - the kernel is private, with internet off and exactly one dataset.
- Secrets: the Kaggle token is read from the environment, never written to a bundle, kernel or log.
- Every result is labelled as measured with this repo's harness, not the competition's evaluator.
- `@traced` on every public function in the package (telemetry test passes).
- Merging starts no run: no workflow calls `60_kaggle_agent.py`.

## Findings
- Not blocking: in CI, `test_no_task_changes_the_code_the_bundle_ships` sees only the 3 sample tasks, since
  `data/tasks/tasks.jsonl` is git-ignored. Locally it passes on all 114. A shipped file that a later task changes
  would be caught only where the full set is built. That is also where bundles are built, and `build` refuses such
  a task itself, so the guard holds where it matters.
- Not blocking: `extend_ids` tokenizes each new piece on its own, where a full render tokenizes the whole text.
  Every piece starts at a special token, so the boundaries match; any shape it doesn't cover falls back to a full
  render.
- Not blocking: the cache rerun is one task, with sampling (temperature 0.2), so it shows the cache works, not how
  much it saves. The full run's per-task token totals will show that.

Nothing blocking. It adds scripts and the pilot's results, and starts no run, so it can merge when CI is green.
The full run waits for the owner.
