# PR 579 review: what each agent task costs, and a cap on the GPU allowance

Refs #569. Stacked on PR 578. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: `test_agent_cost.py` and the runner's cost tests were written failing first. Two test mistakes were
  corrected: comparing an exact fraction with a rounded value, and a one-run median.
  Full suite: 2,112 passed, 4 skipped.
- Settings: each declared once in `ops/cost_settings.yaml`, with a source and a date. The file is required, and a
  malformed one stops the runner before any work (AGENTS.md, check settings first).
- Estimates are labelled: every cost row carries `price_basis_text`, which starts "estimate:".
- Failed kernels count towards the cap and the table (FR-007).
- `--plan-only` makes no Kaggle call (the API setup comes after it) and needs no token or sandbox.
- Column names follow AGENTS.md's suffixes: `_seconds`, `_count`, `_hours`, `_ratio`, `_usd`, `_text`.

## Findings
- Not blocking: `allowance_hours` and `gpu_hours` use the suffix `_hours`, which AGENTS.md's table doesn't list.
  It reads plainly, and seconds would hide the unit the allowance is counted in. When the gold table is declared
  (T004), they go in as `_seconds`, or the table gains `_hours`. That is a rules change, so it's the owner's call.
- Not blocking: session time is push to output, queue included, so it errs high. That suits a cap: it never lets a
  run take more than it says.
- Not blocking: ordering by reference-fix size for tasks with no run yet uses the answer only to order the queue.
  The agent never sees it. The bias it brings is stated where the rate is reported.

Nothing blocking. It starts no run, so it can merge when CI is green, after PR 578.
