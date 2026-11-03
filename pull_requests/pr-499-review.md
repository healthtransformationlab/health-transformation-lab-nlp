# PR #499 review: agents merge their own green PRs without waiting for "merge"

Closes #497. Branch `docs/497-000-agents-merge-green-prs`. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Change

Rule 6 in AGENTS.md "Branches and issues". An agent merges its own PR once three things are true: every check is
green on the latest commit, there is no conflict, and the review finds nothing blocking. Paid runs, publishing
outside the repo, deletions, rule changes and held PRs still wait for the owner. The rule also says to check for
another session's duplicate work first.

## Checks against the rules

| Rule | Result |
|---|---|
| Issue, branch, `Closes #497` | yes |
| A decision goes in an ADR, not only in an issue | the rule itself is the record, in AGENTS.md, where agents read it. The issue holds the owner's request and date |
| Wording, org name, bench order | tests pass |
| Doesn't widen anything costly | paid runs, publishing and deletions keep the owner's approval, as they did before |

## Findings

1. The rule covers only PRs an agent opened. A PR from the owner, Dependabot or the Kaggle results workflow isn't
   included. That's intended.
2. The exception for rule changes covers this PR too, so it waits for the owner's "merge".

Verdict: ready to merge on the owner's "merge".
