# PR 655 review: billing through owner views, not grants on system.billing (#654)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `chore/654-...`, `Closes #654` | ok |
| Test first: schema setting, views script, job parameter, warning names the fix | ok |
| One declaration per setting: `billing_schema` in `databricks.yml` with description and default; same name everywhere | ok |
| Setting checked before work; a malformed value fails naming it | ok |
| SQL: lowercase, three-part names, no `select *` (only the columns the doctor reads) | ok |
| No secret: the application id is a parameter, never in the file | ok |
| Optional data still warns once and leaves costs empty when unreadable | ok |

## Notes
- `ops_billing` sits outside the `<layer>_<bench>` schema pattern: it holds no benchmark data, only access views.
- The views are made by the owner, not the bundle: the deploy's identity can't read `system.billing`.

## Blocking
None.
