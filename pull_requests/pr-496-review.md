# PR #496 review: record the new Hugging Face publish token in the secrets register

Closes #495. Branch `chore/495-025-hf-publish-token`. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Change

One entry in `ops/secrets_register.yaml`, "Hugging Face publish token": the new fine-grained token
`kaggle-publish`, its scope, where it is stored, and an expiry of 2027-02-01 with a renew-by date of 2027-01-18.

## Checks against the rules

| Rule | Result |
|---|---|
| Issue, branch `<type>/<issue>-<slug>`, `Closes #495` | yes |
| A new credential updates the register in the same PR | yes, this PR is the register update |
| Scope is the narrowest that works | yes: no user permissions; org repositories only, with read, create and write. The workflow calls only `create_repo` and `upload_folder` |
| Expiry recorded; renew 14 days before | yes: Hugging Face offered no expiry, so the 90-day limit is ours, and the date makes the reminders fire |
| Rotate without a gap | the old "Claude" token stays until a publish has run with the new one, then loses write access |
| Never a secret value in a file, PR or chat | yes: names and dates only |
| Settings change by PR, naming environments | `dev`, secret added by the owner |
| Tests | register, operations, wording and org-name tests pass |

## Findings

None blocking. The token hasn't been used yet. The first Hugging Face publish (#356, waiting on the owner) is its
test, and the workflow checks the token before uploading anything.

Verdict: ready to merge.
