# PR #760 review: a workflow that tags one commit of main

Refs #649. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict
Nothing blocking.

## Checks
- **Least privilege:** `contents: write` only; it runs only by hand (`workflow_dispatch`), with no trigger on push or PR.
- **No injection:** inputs reach the shell only through `env`, never interpolated into the script. The tag name and
  SHA are checked against strict patterns before use.
- **Never moves a tag:** an existing tag at another commit fails the run; at the same commit, the run does nothing.
  So a run can be repeated safely.
- **Only main:** the commit must be an ancestor of `origin/main`.
- **Rules:** it doesn't publish outside the repository (a tag is in the repository), delete anything or change
  AGENTS.md, so it's merged under rule 6.
