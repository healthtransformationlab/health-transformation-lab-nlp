---
pr: 795
branch: fix/792-014-telemetry-off-alert
title: "014 BUG1: telemetry asked for Azure but off becomes a SEV3, not only a log warning"
author: claude (implemented by a subagent, reviewed by the coordinator)
reviewed_at: 2026-11-15
reviewer: coordinator verification against .claude/review-rubric.md
verdict: approve
---

# PR Review: telemetry asked for Azure but off becomes a SEV3

## Checks
| Check | Result |
|---|---|
| Issue #792 with its four parts first; names as its Contract | yes |
| Test first: 17 new tests, 16 failed first; full suite 2746 passed, 37 skipped | yes |
| Telemetry stays optional: `setup()` carries on; the warning is kept; one stderr line adds the reason and the fix | yes |
| No secret value: `status()` holds names and reasons only; `dbutils.secrets.list` reads key names only | yes |
| Alerts name a severity (SEV3), an owner and an action (`fix_setting`, with the fix in the evidence); one digest item with a count | yes |
| `register_alerts` would have caught this on day one: the register says the scope holds `appinsights_connection_string`; it doesn't | yes |
| The digest notebook's own status stands for the workspace, and the comment and docs say why (the jobs' statuses aren't recorded) | yes |
| Wording, org references, operations rules | pass |

## Findings
### Blocking
None.
### Should fix (follow-up)
1. Child scripts inherit `DENTAL_TELEMETRY=off` when the notebook found no secret, so their own `status()` reads
   asked=off. The digest uses the notebook's status, which is right; a per-job record (a row per run that doesn't
   depend on spans) would let the doctor see each job. Worth its own issue.
### Minor
2. The register's `if_it_expires` text for the App Insights secret changes to say a SEV3 is raised, which is now true.

## Verdict
Approve. Merge when CI is green.
