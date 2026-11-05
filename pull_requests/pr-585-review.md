# PR 585 review: who can read the billing tables (spec 036 T006)

Refs #568. Docs only (`plan.md`, `tasks.md`), reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- How the finding was reached: Unity Catalog metadata calls with the owner's workspace token (`tables.get`,
  `grants.get`, `grants.get_effective`). No warehouse, no query, no compute.
- Who has what:
  - the `system` catalog grants USE CATALOG to account users;
  - the `system.billing` schema grants USE SCHEMA and SELECT to account admins only;
  - the token's own effective privilege on both tables is SELECT, as an admin.
- What it means for the jobs: they run as `dental-omop-ci` (dev, as the CI deployer) and the uat service
  principal (`run_as` in `databricks.yml`), and neither is an account admin.
- No secret or token value appears in the PR, the files or the commit.
- Wording and org-name tests pass.

## Findings
- None blocking. Reading the service principals' own effective grants was refused: the caller can't see
  another principal's grants. The finding therefore rests on the schema's grant list, which names account admins
  only. A one-line query run as the service principal would confirm it once a grant is made.

It changes docs only and starts nothing, so it can merge when CI is green.
