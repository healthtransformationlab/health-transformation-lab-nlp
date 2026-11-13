---
pr: 701
branch: docs/700-000-issue-says-what-tests-check
title: "000 DOCS18: an issue says what a test will check, before the work starts"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: coordinator review of the diff against the rubric (no reviewer subagent: a rules section, an issue template, one script of about 150 lines and its tests, read line by line)
verdict: approve
---

# PR Review: 000 DOCS18: an issue says what a test will check, before the work starts (#700)

Reviewed against `.claude/review-rubric.md` and AGENTS.md. Range: `d5556f3..HEAD` of the branch.

## Summary

The tasks mined from this repository are hard for a small local model mostly because of what the issues leave out.
This adds a rule to AGENTS.md saying what an issue holds (Problem, Done when, Contract, Read first, written before
the work), an issue template with the same four parts, and a check on the issue a pull request links. On the
owner's word the same evening it also adds an epic issue over a spec's user stories, spec before code (checked),
and a data contract for a table or file.

## Scans

| Scan | Result |
|---|---|
| Secrets | none in the diff. The workflow passes its own read-only token to the script through the environment; the script never prints it |
| PHI or real data | none; no data file changes |
| Organisation claims | none. The reason cites two counts from this repository's own tables; `test_no_org_references.py` passes |

## Checks

| Check | Result |
|---|---|
| Branch `docs/700-000-issue-says-what-tests-check`, `Closes #700`; a rule and its check, no dataset, metric or label change, so no spec. Mining a second phase of tasks is named as its own spec, not done here | ok |
| The owner asked for the rule on November 12, 2026 ("focus on creating better issues and linked documentation in our agent.md") and for the additions the same evening ("planning user stories epic hierarchy and enforcing specs before coding linked to stories ... data level contracts too"). A pull request that changes the rules still waits for the owner's "merge": asked for with the wording shown, not assumed | note |
| The two counts in the rule are the committed ones: 76 of 93 against 14 of 40 (`data/tasks/screening/README.md`, "What it found"), 26 of 85 task-runs against 1 of 380 (`data/tasks/official_agent_runs/README.md`, "The core split"). Both are labelled as what they are: an AI screen, and five runs of one model | ok |
| The rule fits the rule it sits beside: the text as it stood before the first commit is what the task set records, and a later change is a dated line, never a rewrite. That keeps "task text is never written after the fact" true for tasks mined later | ok |
| The check is date-gated (`PARTS_SINCE` 2026-11-14): issues opened earlier pass as they are, so no open pull request or issue is broken by the merge. Tool branches (`dependabot/*`, `kaggle-results/*`) are not held to it | ok |
| Spec before code: only an issue titled as a user story ("016 US2:") is held to it; its spec must be in the branch and name the issue; a `feat` or `fix` branch also needs `plan.md`; the `spec/` branch that writes the spec does not. A fix, chore or action item is not held to it | ok |
| A check that cannot read the issue fails and says so (one retry for a network error first). Without a token (a laptop, a fork) it checks the branch and the link only, and says the issue was not read | ok |
| Dogfood: issue #700 has the four parts, and when its contract grew it got a dated line and was not rewritten | ok |
| Test first: `test_pr_conventions.py` (the linked number; the four parts as headings or bold labels; each missing part named; the date; the workflow's permission; a story without its spec, without its issue named, without its plan) and `test_agent_docs.py` (AGENTS.md, the template and the check use the same names; the epic, spec-before-code and data-contract text) failed before the change and pass now | ok |
| `cd python && pytest -q tests -n auto` on the first commit: 2,513 passed, 4 skipped. After the second commit the six test files it touches: 101 passed. `ruff check` on the three changed Python files: clean | ok |
| `pr-conventions.yml`: `issues: read` added; the token reaches the script by environment, and the test that no `${{` is pasted into a shell line still passes | ok |
| Python and R parity, seeds, paths, prices, deck figures, secrets register, alerts, table writes: not touched | n/a |
| Environments: none. From the merge, the pull-request check on this repository also reads the linked issue | ok |

Nothing blocking.

## Notes
- The check sees that the four parts are there. It cannot see that they were written before the first commit, or
  that the contract is complete: a part counts when a line starts with its name. The timing rests on the rule and
  on the dated-line habit; a later check could compare the issue's edit history with the first commit's date.
- The epic issue and the sub-issue link are a written rule only; nothing checks them yet.
- Whether issues written this way make the mined tasks easier for a small model is a hypothesis, not a result.
  The counts in the rule are observational, from an AI screen that a person checked in part, and the 17 tasks the
  model did better on are also the smaller ones (the paper says so). The test is the next phase: tasks mined from
  work done under this rule, set beside the 93.
- Counts made on the evening of November 12 and not cited in the rule, because they are not tables in this
  repository yet: 8 of the 9 tasks ever fixed came from issues; issues with a "Done when" list were fixed 6 of 21
  times against 3 of 72; about two thirds of the names the tests insist on were written nowhere before the fix.
- Published work read for this rule, for the record: Khatib et al., "What Makes a Good Bug Report for an AI
  Agent?" (arXiv 2607.07593): expected behaviour and localization help agents, longer reports and lost structure
  hurt. Gloaguen et al., "Evaluating AGENTS.md" (arXiv 2602.11988): standing context files did not raise task
  success and raised cost by over 20%. That second result is why this rule puts the contract in the issue and
  does not add project-wide documentation.
