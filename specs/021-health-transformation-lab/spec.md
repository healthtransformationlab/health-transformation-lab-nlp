# Feature Specification: rename to Health Transformation Lab (spec 021)

**Feature Branch**: `chore/127-021-rename` | **Issue**: #127

**Created**: 2026-10-28 | **Status**: implemented; the workspace rebuild is owner steps (below)

**Input**: "We need a better title for this repo, maybe health-transformation-lab-nlp, and change all the
catalogs and schemas to health_transformation_lab." The owner then decided (comment on #127, 2026-10-28):
this spec renames the catalog; spec 022 sets the schema names; every open PR merges before this one.

> Personal learning project; synthetic data only. A rename: no dataset, metric or label rule changes.

## What changes

| Thing | Before | After |
|---|---|---|
| GitHub repository | `dental-omop-nlp` | `health-transformation-lab-nlp` (the owner renames it; GitHub redirects the old URLs) |
| Python package | `dental_omop_nlp` (`python/dental_omop_nlp/`) | `health_transformation_lab_nlp` |
| Bundle | `dental-omop-nlp` | `health-transformation-lab-nlp` (a new deployment: new workspace path and state) |
| Catalog | `dental_omop` | `health_transformation_lab` |
| Schemas | `landing_/bronze_/silver_/gold_dental_omop_perio` | unchanged here: spec 022 names them per bench (`<layer>_perio_bench`, `oral_health_bench`, `access_bench`) |
| Secret scope | `dental` | `health_transformation_lab` |
| Telemetry data product id, `service.namespace` | `dental_omop_perio`, `dental-omop-nlp` | `health_transformation_lab`, `health-transformation-lab-nlp` |
| Kaggle notebook | `dental-omop-medgemma-reader` | `health-transformation-lab-medgemma-reader` |
| Azure resource group, App Insights, Log Analytics | `rg-dental-omop-telemetry`, `dental-omop-nlp-appi`, `dental-omop-nlp-logs` | `rg-health-transformation-lab-telemetry`, `health-transformation-lab-nlp-appi`, `health-transformation-lab-nlp-logs` |

**Kept**:
- **Identities.** The CI service principal `dental-omop-ci` and the admin groups `dental_omop_nlp_<target>_admin`
  are real identities with secrets and members. Renaming them would break the deploy's sign-in and grants.
- **History.** Past specs and PR reviews describe what happened under the old names.

## Rebuild, not migrate
The new catalog is built from the repo:
- Load results reloads every committed result.
- The jobs regenerate the study tables, the volumes' files and the registered model.

`dental_omop` and the old bundle's jobs stay until the new catalog checks out, then the owner removes
them. The bundle's `prevent_destroy` keeps a deploy from dropping either catalog.

## Owner steps, in order
1. Rename the repository on GitHub (Settings → General).
2. In each workspace, create the catalog once:
   `CREATE CATALOG IF NOT EXISTS health_transformation_lab`. Free Edition can't create one through the API;
   `deploy.yml` then binds it.
3. Create the secret scope `health_transformation_lab` and put in `hf_token` and
   `appinsights_connection_string`.
4. `terraform -chdir=infra/azure apply`. This creates the renamed Azure resources and a new connection
   string. Destroy the old resources once the new string is in the scope.
5. Merge (after every other open PR); the deploy creates the schemas, the volume and the jobs. Run *Benchmark*, *Judge scorecard* and
   *NHANES perio*; Load results runs on its own.
6. Delete the old bundle's jobs and, when the new catalog checks out, drop `dental_omop` and the scope `dental`.

## Success criteria
- No `dental_omop_nlp` or `dental_omop` catalog reference is left in code, config, tests or current docs
  (schema names are spec 022's). A test checks this, allowing the kept identities and history.
- `pytest` and `bundle validate` pass.
