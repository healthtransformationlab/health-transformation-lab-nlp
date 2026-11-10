# PR 665 review: an automated screen of all 93 tasks, compared with the 30 the owner checked (#664)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/664-...`, `Closes #664` | ok |
| Test first: three tests added to `test_task_screen.py` failed without the table (3 errors), pass with it; the first screen's six tests still pass | ok |
| Every published task has one row: 93 rows, the published ids, ratings on the scale, pass means both ratings are 0 or 1 | ok |
| The raters were blind to the first screen: each was given the task files and the written protocol only, told not to look for other ratings, and the first screen's table was not among their files | ok |
| The protocol's two questions and four-point scales are the first screen's, word for word | ok |
| Compared with the 30 the owner checked: the same verdict on 30 of 30 (25 unfair, 5 fair) | ok |
| 25 tasks were rated twice by different raters (stand-ins started when two raters wrote nothing for nine minutes; both then finished): the same verdict on all 25. The table keeps the first eight raters' ratings | ok |
| Labelled everywhere as an AI reviewer's rating, not checked by a person outside the 30 | ok |
| The README's counts are the table's (a test checks the pass count and the agreement) | ok |
| Reasons were checked for the wording rules and for organisation names by the repository's tests | ok |
| No secrets, no real data; merging starts no run and publishes nothing | ok |

## Notes
- The two screens agree on all 30, but they are not independent of each other in kind: both are AI reviewers
  reading the same files against the same two questions. What the agreement shows is that the rating is stable
  across separate passes, not that a person reading the tests would give it.
- 76 of 93 failing is a statement about how the tasks were written: the statements are the repository's own issue
  and pull request text, which was never meant to list the names a test would import. The set keeps every task and
  carries the verdict as a label.
- Against the run table, 4 of 13 passing tasks resolved and 1 of 35 failing. Thirteen and five are small numbers.

## Blocking
None.
