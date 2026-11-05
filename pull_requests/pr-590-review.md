# PR 590 review: a Governance page, and spend kept out of the record checks

Refs #570 (T009), #576 (T012). Stacked on PR 589. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: five new tests failed before the change:
  - the record checks leave out cost rows;
  - the Governance page exists;
  - its checks table and tiles agree;
  - cost per task leaves out calibration and says "estimated";
  - Genie handles budget questions.
  Full suite: 2,163 passed, 4 skipped.
- A real bug fixed: since #588, `dq_check` holds cost and performance rows, and the DQ grader's "checks" dataset
  read every row. It now filters to the record categories.
- Every dataset runs in DuckDB on tables built as Load results builds them, and every widget field exists in its
  dataset (existing tests, now over the new datasets too).
- Wording: "estimate" wherever a cost is shown, and the harness is named as this repo's, not the competition's
  evaluator. Wording test passes.
- Generated files: the dashboard and Genie JSON come from `scripts/42_build_dashboards.py`, and the committed-matches
  test passes.

## Findings
- Not blocking: the DQ Genie space now holds a spend table (`fact_agent_task_run`) beside the record tables. Its
  instructions keep the two apart. A separate governance space is an option if questions get mixed.
- Not blocking: one PR touches two issues (T009 is US3, T012 is US4) because they are the same page. Both are
  referenced with "Refs".

Nothing blocking. It starts no run, so it can merge when CI is green, after PR 589.
