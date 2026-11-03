# PR #506 review: the pipeline doctor's system-table grants as a setup script

Closes #504. Branch `chore/504-027-system-table-grants`. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Change

`databricks/setup/grant_system_tables.sh` grants a target's admin group three privileges on `system` and
`system.lakeflow`. `create_service_principal.sh` calls it, the doctor's error names it, and the deployment guide
documents it. Six new tests.

## Checks against the rules

| Rule | Result |
|---|---|
| Issue, branch, `Closes #504` | yes |
| Test first | the six tests failed before the script existed |
| Least privilege | only `USE_CATALOG`, `USE_SCHEMA`, `SELECT` on `system.lakeflow`; a test fails on `ALL_PRIVILEGES`, `MODIFY`, `system.access` or `system.billing` |
| Same names in every environment | the group name comes from the target; no IDs in code (a test fails on a UUID) |
| Idempotent | adding a privilege already held changes nothing |
| Check settings before work | an unknown target fails at once, naming it |
| Settings change by PR, naming environments | this PR changes no environment; running it for dev is a separate, approved step |
| Secrets | none involved |

## Findings

1. **Not run against a workspace.** There's no Databricks CLI in this session. The call form matches the existing
   metastore grant in `create_service_principal.sh`. The script's last line prints effective privileges, so the
   first real run shows whether it worked. Not blocking.
2. **Optional:** the notebook's import block has a ruff `I001` finding. It was already there before this PR and
   is left alone.

Verdict: ready to merge.
