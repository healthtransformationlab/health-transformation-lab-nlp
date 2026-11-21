---
description: Check the branch, open a PR against main, and review it with the shared rubric
argument-hint: "[title] (default: from the commits)"
---

Open a pull request for the current branch, then review it. Follow `.claude/review-rubric.md`.

## 1. Pre-flight (stop and report if any fails)

- Not on `main`; working tree clean; branch pushed (`git push -u origin <branch>`).
- The branch belongs to an issue (AGENTS.md, "Branches and issues") and is named `<type>/<issue>-<slug>`.
  On an agent session's `claude/*` branch: open (or find) the issue first, then
  `git checkout -b <type>/<issue>-<slug>` and push that (AGENTS.md rule 4); CI fails a PR from `claude/*`.
- `git fetch origin main` and merge it in if the branch is behind (merge, don't rebase a shared branch).
- Run the rubric's three scans (secrets, PHI / real data, organization claims) on
  `origin/main..HEAD`. Any hit stops here: fix it first.
- `cd python && pytest -q tests`; `ruff check` on changed Python files.
- If labels, scoring, reliability or cost-effectiveness changed: say whether the R twin changed too,
  and run `python/scripts/make_parity_inputs.sh && Rscript r/tests/test_parity.R` if R is available
  (otherwise CI `r-parity` is the check; say so in the PR body).
- Dry-run numbers in docs are labelled simulated; new prices name a source.

## 2. Open the PR

Title: `$ARGUMENTS`, or a short imperative summary of the commits. Body:

```markdown
Closes #<issue>

## What changed
<bullets by area: what and why>

## Verification
- <commands run and their results>
- <what was not run and why (e.g. no R here; CI r-parity covers it)>

No PHI, real notes or credentials are committed.
```

End the body with the attribution lines the session asks for. Create it with the GitHub tools.

## 3. Review it

Run the `/pr-review` flow on the new PR number, write `pull_requests/pr-<n>-review.md` and commit it
to the PR's branch.
If the verdict is request-changes, fix the 🔴 findings on the branch, push, and re-review.
Report the PR link and the verdict. **Then merge when ready** under AGENTS.md
rule 6 (#497): checks green on the latest commit, no merge conflict, and this
review finds nothing blocking — without waiting to be told. Still wait for the
owner on limited compute, paid endpoints, external publishes, deletions, or
rule changes (same list in AGENTS.md).
