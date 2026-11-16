# PR 837 review: register the Application Insights read key that agent sessions query with (#836)

Reviewed by the author session against `AGENTS.md` ("Configuration and secrets") and `.claude/review-rubric.md`.

| Check | Result |
|---|---|
| Branch `chore/836-014-appinsights-read-key`, `Closes #836`, issue with its four parts before the first commit | ok |
| The register entry has every field (what, made_in, scope, stored_in, used_by, lifetime, expires, owner, if_it_expires) and no value | ok |
| No key value, and no application id, in the repository (the repository is public) | ok |
| The key is read only, on one resource; it was saved through the session's credential form, never in chat | ok |
| `expires: never` is true for these keys; the entry says to delete it when unused and notes Microsoft's move to Entra ID | ok |
| Register and operations tests | 35 passed, 2 skipped |

## Findings

None blocking.

- **Noted.** API-key access to Application Insights is being retired in favour of Microsoft Entra ID. The entry names
  the replacement: a principal with Log Analytics Reader, queried from a workflow, with no key in a session.

## Verdict

Approve. It changes no setting, job or pipeline, and starts nothing. Merge when the checks are green.
