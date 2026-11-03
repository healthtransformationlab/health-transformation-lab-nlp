# PR #483 review: record the website push token's expiry in the secrets register

Closes #479. Branch `chore/479-000-site-token-expiry`. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Change

One entry in `ops/secrets_register.yaml` ("Website push token", `SITE_PUSH_TOKEN`):

- `expires: 2027-02-01`, replacing `unknown`. The token was made on 2026-11-03 with a 90-day lifetime.
- `lifetime` now names the creation date and the renew-by date, 2027-01-18 (14 days before expiry).

## Checks against the rules

| Rule | Result |
|---|---|
| Issue, branch `<type>/<issue>-<slug>`, `Closes #479` | yes |
| Credential change updates the register in the same PR | yes, this PR is the register update |
| Never a secret value in a file, PR or chat | yes: only dates; the value was never shown |
| Renew 14 days before expiry | the renew-by date is recorded |
| Spec needed | no: a register fact, not a dataset, metric, label or workflow change |
| Tests | `python -m pytest -q tests`: 1632 passed, 15 skipped |

## Evidence that the credential works

Run 41675973955 of "Copy the decks to the website" used `SITE_PUSH_TOKEN`, passed the push check and pushed site
commit 9510212 (`perio-bench/index.html`).

## Findings

None blocking. The date in `expires` comes from the owner's report ("made it 90 days"), not from GitHub, which didn't
show it; if GitHub's token page later shows another date, correct it here.

Verdict: ready to merge.
