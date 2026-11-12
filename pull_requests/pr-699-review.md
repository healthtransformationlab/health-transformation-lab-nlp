---
pr: 699
branch: docs/698-000-raise-quota-before-second-path
title: "000 DOCS17: raise a quota before working around it (Kaggle GPU hours and a linked Colab subscription)"
author: jcbowyer
reviewed_at: 2026-11-12
reviewer: coordinator review of the diff against the rubric (no reviewer subagent: one rule, one README section, a three-line change to a refusal and two tests, read line by line)
verdict: approve
---

# PR Review: 000 DOCS17: raise a quota before working around it (#698)

Reviewed against `.claude/review-rubric.md` and AGENTS.md. Range: `c10f807..0c8b9e2`.

## Summary

On November 11, 2026 Kaggle refused a planned rerun for the weekly GPU quota and the run moved to Colab. Nobody had
checked whether Kaggle itself gives more hours; it does, for a linked Colab Pro or Pro+ subscription. The owner
found that a day later and asked for the rules to make sure the check is made. This adds the rule to AGENTS.md, the
how-to to the Kaggle README, the check to the refusal's own message and to the allowance budget's action.

## Scans

| Scan | Result |
|---|---|
| Secrets | none in the diff |
| PHI or real data | none; no data file changes |
| Organisation claims | Kaggle and Colab are described as Kaggle's own pages describe them, each sentence with its link and the date read; `test_no_org_references.py` passes |

## Checks

| Check | Result |
|---|---|
| Branch `docs/698-000-raise-quota-before-second-path`, `Closes #698`; a rule, a how-to and a message, so no spec | ok |
| The owner asked for the rule on November 12, 2026 ("update the agent.md to make sure we do this"). A pull request that changes the rules still waits for the owner's "merge" (AGENTS.md "Branches and issues", 6): asked for, not assumed | note |
| The rule says what to do and in what order: the platform's own way to get more first, the owner asked to use it, then a smaller run, a wait or a second platform, and the issue or PR says what was checked. It sits with the other failure rules and points to the file that owns Kaggle's GPUs in the sources-of-truth map | ok |
| The hours (15 for Colab Pro, 30 for Pro+, each week, on top of the free allowance) and the route (File, then Link to Colab, in Kaggle's notebook editor) are Kaggle's announcement's; "experimental" and one Kaggle account per subscription are its notebook docs'. Both are linked with the date read | ok |
| The README does not say whether a subscription is linked for this account, and the budget's limit is not raised: the number to plan on is the one under Settings on kaggle.com, read at the time | ok |
| The refusal: Kaggle's words stay first and unchanged (the earlier test still passes); the check follows only when the refusal names the GPU quota. A refusal for two running sessions, which more hours would not cure, carries no hint | ok |
| Test first: `test_a_quota_is_raised_before_it_is_worked_around` failed on AGENTS.md as it was, and `test_a_kernel_refused_for_the_gpu_quota_says_where_more_hours_come_from` on the message as it was; both pass now | ok |
| `cd python && pytest -q tests -n auto`: 2,497 passed, 4 skipped | ok |
| `ruff check` on the three changed Python files: 3 findings, the same 3 as on `main` (two `datetime.UTC` aliases, one `re.M`), none on a changed line | ok |
| `ops/budgets.yaml`: only the action's text changes; the limit, unit, period and owner are as they were, so no check's result changes | ok |
| Python and R parity, seeds, paths, prices, deck figures, secrets register, alerts, table writes: not touched | n/a |
| Environments: none. No setting's value changes, no job runs, nothing is published | ok |

Nothing blocking.

## Notes
- Kaggle's pages are drawn in the browser and would not open from the session that wrote this. The hours, the menu
  route and "experimental" are as a web search quoted those pages on November 12, 2026, and they agree with what
  the owner saw on kaggle.com the same day. Whoever links a subscription reads the number under Settings.
- The rule is general (any quota or allowance), and its one worked example is Kaggle's. The shared rules vendored
  into the other repositories (`pipeline-doctor/conventions`) are not changed here.
- The check in the refusal matches Kaggle's wording as it was on November 11 ("Maximum weekly GPU quota"). If
  Kaggle rewords it, the hint goes quiet and the README's row still names the refusal; the test pins today's words.
- Whether a linked subscription would have kept the rerun on Kaggle is not claimed: the pull request says the
  check was not made, not what it would have found.
