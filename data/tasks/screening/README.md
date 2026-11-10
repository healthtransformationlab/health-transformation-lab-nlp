# A screen of 30 published tasks: does each statement say what its tests check?

**Rated by an AI reviewer; checked by the owner from plain-language summaries, not from the code.** Read every
rating here as an AI reviewer's judgment that a person has looked over, not as a person's own reading of the tests
(spec 028, issue #652).

The competition's evaluator shows that a task's reference patch passes and an empty patch fails
(`../official_verifier/`). It does not show that the statement tells an agent what the tests will check. SWE-bench
Verified screened its tasks for that on two questions; this applies the same two to a sample.

## The sample

30 of the 93 published tasks, drawn at random with seed 20261110 within each statement source: 13 of the 39
from issues (tier A), 11 of the 34 from pull requests (tier B), 6 of the 20 from commit messages (tier C).

## The two questions (0 to 3 each; a task passes when both are 0 or 1)

- **Statement** (`statement_rating_num`): reading only the statement and hints, would an engineer know what a correct
  change must do? 0 clear, 1 a sensible reading exists, 2 vague, 3 cannot tell.
- **Tests** (`test_rating_num`): do the tests accept any correct solution to what the statement asks? 0 yes, 1 most,
  2 reasonable solutions would fail (the tests need a name, path, text or number the statement and hints never
  give), 3 they check something else.

## How it was made

A first pass read each task's statement, hints, test patch and reference patch and gave both ratings with a reason,
whether the statement names the fix (`fix_named_code`) and the kind of change (`change_kind_code`). A second pass
read the same files and the first ratings, restated each finding in plain words (`asked_text`, `test_needs_text`,
`told_code`) and said whether it agreed (`is_second_agree`). Test patches were read up to 12,000 characters
(`is_test_patch_cut` marks the longer ones).

## The owner's check

On November 10, 2026 the owner went through all 30 on a sheet. For each task it showed two plain-language sentences
(`asked_text`: what the agent was asked; `test_needs_text`: what the tests insist on), whether the agent was told
(`told_code`), and the AI reviewer's verdict already selected. The owner answered one question, is the test fair,
with fair, unfair or cannot tell, and wrote a note (`owner_fair_code`, `owner_note_text` as written,
`is_owner_agree`).

Fair 5, unfair 25, cannot tell 0: the AI reviewer's verdict on all 30.

The owner did not read the test code, and saw the AI's answer before choosing. It is a check of the AI's
findings, not an independent rating.

## What it found

| | Tasks |
|---|---|
| Screened | 30 |
| Pass (both ratings 0 or 1) | 5 |
| Statement rated 2 or 3 | 10 |
| Tests rated 2 or 3 | 25 |
| Second pass agrees with the first on the tests | 30 |
| Kind of change: fix / feature / maintenance | 4 / 14 / 12 |
| Statement names the fix: no / partly / yes | 3 / 17 / 10 |

By statement source, passing: issues 3 of 13, pull requests 2 of 11, commit messages
0 of 6.

Against the Gemma 4 E4B run (`../agent_runs/gemma-4-e4b-it_kaggle.csv`, each task's latest run): 16 of the 30 were
attempted. Of the 3 that pass the screen the model resolved 1; of the 13 that fail it, 0.

## What it cannot show

- An AI reviewer made both passes. The second saw the first's ratings, and the owner saw the AI's verdict, so
  none of the three agreements is independent.
- 30 tasks: the pass rate for the 93 has a wide interval.
- A task that fails the screen can still be resolved by a solution that happens to use the expected names, and one
  that passes it can still be hard.
- The ratings are of the statement and hints as published; they say nothing about the reference patch's quality.

# An automated screen of all 93 (November 10, 2026)

**Rated by an AI reviewer in one pass; not checked by a person outside the 30 above.** `agent_screen_all.csv` has one
row per published task (spec 028, issue #664).

The first screen leaves 63 tasks unrated. This one rates every task on the same two questions and the same scale,
so the screen can be used as a label, and the 30 the owner checked say how far it can be trusted.

## How it was made

Eight AI raters each took a random share of the 93 tasks. Each read a task's statement, hints, test patch and
reference patch (patches up to 12,000 characters; `is_test_patch_cut` and `is_reference_patch_cut` mark the longer
ones) and gave both ratings with one sentence of reason and what the tests need that the statement and hints never
give (`test_needs_text`). The raters were told not to look for any other rating of these tasks and were given none:
this pass did not see the first screen's ratings or the owner's answers. The table holds each rater's ratings as the
rater left them when it finished; nothing was changed afterwards.

Two raters were slow to write their results, so stand-in raters were started on their tasks; all the first eight
finished, and the table keeps their ratings. That left 26 tasks rated twice by different raters, each without
seeing the other: the same verdict on all 26.

## What it found

| | Tasks |
|---|---|
| Rated | 93 |
| Pass (both ratings 0 or 1) | 17 |
| Statement rated 2 or 3 | 19 |
| Tests rated 2 or 3 | 76 |
| Same verdict as the 30 the owner checked | 30 of 30 |

On the 30 the owner checked: of the 25 judged unfair there, this pass fails 25; of the 5 judged fair, it passes
5. On the 63 nobody had rated, it passes 12.

By statement source, passing: issues 11 of 39, pull requests 6 of 34, commit messages
0 of 20.

Against the Gemma 4 E4B run (`../agent_runs/gemma-4-e4b-it_kaggle.csv`, each task's latest run): 48 of the 93 were
attempted. Of the 13 that pass this screen the model resolved 4; of the 35 that fail it, 1.

## What it cannot show

- One AI pass per task, with no second pass and no person, except on the 30 where the two screens can be compared.
- Eight raters shared the tasks, so a rater's leaning is spread over about a dozen tasks, not averaged out.
- The same limits as the first screen: a failing task can still be resolved by a solution that happens to use the
  expected names, and a passing one can still be hard.
