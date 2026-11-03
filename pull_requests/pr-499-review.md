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

## Added after CI: a register fix (main was red)

The `python-databricks-runtime` job failed on `test_hf_publish.py`. PR #496 had written `(set 2026-11-03, #495)` in a
register value. In YAML, a space and then `#` starts a comment, so the rest of the value, including `HF_TOKEN`, was
dropped. #496 only changed the register, so the Python jobs didn't run on it. Three older values had the same cut,
two of them from #465. This PR now writes `issue 495` instead, fixes all four, and adds
`test_no_register_value_is_cut_short_by_a_yaml_comment`. Full suite: 1644 passed, 15 skipped.
