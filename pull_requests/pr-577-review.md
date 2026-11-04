# PR 577 review: spec 036 US4, spend and speed in the data-quality report

Refs #576. A spec change only, reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- One issue for the story (#576), its number in the heading.
- Wording, org-name and bench-order tests pass, run against this branch (`PYTHONPATH=.`, so they scan this checkout).
- Builds on what exists: `dq_check`'s columns (gold_model.py), the doctor's signals and digests (spec 027), and the
  cost data from US1 and US2.
- Severity stays within AGENTS.md's ladder:
  - cost drift is SEV4 there already;
  - a passed budget at SEV3 counts as "a check below threshold";
  - anything more severe is left to the owner.

## Findings
- Not blocking: `dq_check`'s category list in gold_model.py ("conformance · completeness · plausibility") must gain
  `cost` and `performance` in the code PR, with the column comment updated (spec 034).
- Not blocking: the budget register's limits are not in the spec. The owner sets them in `ops/budgets.yaml`, by PR
  (AGENTS.md, settings change by pull request).

Nothing blocking. A spec changes no data, runs nothing and publishes nothing, so it can merge when CI is green.
