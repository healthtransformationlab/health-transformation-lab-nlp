# PR #523 review: the pipeline doctor's failure email goes to the environment's ALERT_EMAIL

Closes #521. Branch `chore/521-027-alert-email`. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks against the rules

| Rule | Result |
|---|---|
| Issue, branch, `Closes #521` | yes |
| Test first | three new tests in `test_bundle.py` failed before the change |
| One declaration per setting, same names everywhere | `alert_emails` in `databricks.yml`, set from `ALERT_EMAIL` in each GitHub environment |
| Settings change by PR, naming environments | dev changes (failure email on the doctor job); uat unchanged (empty list) |
| Alerts name a severity, owner, action | the doctor's drafted notification carries them; this PR delivers the page |
| No personal data in a public repo | the address is a GitHub variable; a test fails on any address in the bundle or deploy files |
| Real check, not simulated | `databricks bundle validate` with and without the override |

## Findings

1. **The address is quoted into JSON by Python, not by the shell**, so an address with odd characters can't break
   the file. Good.
2. **The doctor still can't read `system.lakeflow` on Free Edition.** The docs say so. The Jobs API change is the
   next PR, so until then a doctor run fails on its settings check, and that failure is now emailed. Not blocking.

Verdict: ready to merge.
