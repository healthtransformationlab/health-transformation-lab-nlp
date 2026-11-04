# PR 581 review: add _hours to the column suffixes

Closes #580. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- The owner approved adding `_hours` (session, Nov 4, 2026).
- Test first: `test_the_suffixes_here_are_the_ones_agents_md_lists` failed with `_hours` in the test's list and not
  in the table, then passed once the row was added.
- The table exists only in AGENTS.md; other matches for its examples are columns, not copies of the table.
- `_hours` sits between `_seconds` and `_days`, with the same columns as its neighbours.
- Wording and org-name tests pass.

## Findings
- None blocking. `_seconds` stays the default for durations. `_hours` is only for a duration counted in hours where
  that is the unit people read it in, as its row says, so it doesn't become a second way to write the same column.

It changes AGENTS.md, so it waits for the owner's "merge" (AGENTS.md, Branches and issues 6).
