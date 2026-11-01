# Deploying to dev, UAT and prod (Databricks Asset Bundle)

`databricks.yml` at the repo root defines the bundle; jobs live in
`databricks/resources/jobs.yml`. One set of code, three targets, settings as
variables.

> Synthetic data only in every target until the real-data path is approved.
> Personal learning project; see [DISCLAIMER](../DISCLAIMER.md).

## Targets

| | dev | uat | prod |
|---|---|---|---|
| Purpose | your sandbox (e.g. Free Edition) | shared test | production |
| Bundle mode | default (no name prefixes; schedules paused by preset) | `production` | `production` |
| Deployed by | CI on push to `main` (not from a laptop: a second deploy state would duplicate the jobs) | CI on push to `main`, or on demand | CI on demand, after approval |
| Runs as | the CI service principal | service principal | service principal |
| Workspace path | the service principal's home folder | `/Workspace/Shared/.bundle/health-transformation-lab-nlp/uat` | `.../prod` |
| Workspace | your dev workspace | the UAT workspace | the prod workspace |
| Catalog | `health_transformation_lab` (schemas below) | same | same |
| `n_people` | 300 | 1,500 | 1,500 |
| DistilBERT in the benchmark job (`run_encoder`) | no (baselines only, ~3 min; no torch install) | yes | yes |
| GPU jobs (MedGemma reader, encoders) | yes, serverless GPU | yes, serverless GPU | yes, serverless GPU, all review notes |

Each target is its own workspace (its own `DATABRICKS_HOST`), so catalog and
schema names are the same everywhere. One catalog, one schema per bench and layer (spec 022,
`health_transformation_lab_nlp.schemas`):

| Schema in `health_transformation_lab` | Holds |
|---|---|
| `landing_perio_bench` | the `data` volume: files the pipeline writes (`DENTAL_DATA_ROOT`) |
| `bronze_perio_bench` | raw tables (empty for now) |
| `silver_perio_bench` | cleaned tables (empty for now) |
| `bronze_`/`silver_`/`gold_oral_health_bench` | empty until oral_health_bench has a pipeline |
| `bronze_`/`silver_`/`gold_access_bench` | empty until access_bench has a pipeline |
| `gold_perio_bench` | OMOP tables, study tables `dim_study_note` and `benchmark_metric` (spec 031); results `dim_result_file`, `fact_prediction`, `fact_llm_call` (spec 016); judge scorecard `fact_chart_answer`, `fact_judge_call`, `judge_metric`, `judge_agreement`, `judge_cost`, `deid_score` (spec 012); names: spec 018, [gold_tables.md](gold_tables.md), `perio_note_classifier` |

The bundle creates the catalog, all the schemas and the volume on deploy
(`databricks/resources/unity_catalog.yml`), each with `prevent_destroy` so
`bundle destroy` never drops them. Deploying needs Databricks CLI 0.288 or later
and `CREATE CATALOG` on the metastore. (Older setups used `workspace.dental_dev`,
`dental_uat.dental` and `dental_prod.dental`, made by hand or by an earlier version of
the setup script, then the catalog and secret scope that spec 021 renamed. Nothing uses
them now; drop them once the new catalog is deployed.)

No target uses `mode: development`. That mode prefixes every name (`[dev <user>]`
on jobs, `dev_<user>_` on catalogs, schemas, volumes and registered models, which
is where names like `dev_dental_omop_ci_perio_note_classifier` came from). The
workspace separates environments, so names are identical in dev, uat and prod.
The dev target keeps schedules paused with `presets.trigger_pause_status`.
Resources an earlier development-mode deploy created under `dev_` names are not
removed by this; drop them by hand once nothing uses them.

**Workspaces with Default Storage** (no metastore storage root) can't create a catalog through the
API the bundle uses ("Metastore storage root URL does not exist"). Create it once with SQL, as a
workspace admin, owned by the target's admin group; the deploy workflow then adopts it
(`bundle deployment bind`) and manages its schemas, volume and grants:

```sql
CREATE CATALOG IF NOT EXISTS health_transformation_lab COMMENT 'Dental OMOP. Synthetic data only.';
ALTER CATALOG health_transformation_lab OWNER TO `dental_omop_nlp_dev_admin`;
```

If a catalog, schema or volume already exists in a workspace (made by hand, or
deployed by someone else's copy of the bundle), deploy fails rather than take it
over. Adopt it once with, e.g.,
`databricks bundle deployment bind health_transformation_lab health_transformation_lab -t dev`
(resource key, then the object's name), and likewise for the schemas and volume.

**A target deployed before with Terraform** (before the catalog resource) must move its state to the
direct engine once, by hand, before CI can deploy it:
`DATABRICKS_BUNDLE_ENGINE=direct databricks bundle deployment migrate -t <target> --noplancheck`.
CI doesn't try this itself: a migrate that failed for a real reason would let the deploy treat the
target as new and duplicate its jobs. dev is already migrated; uat and prod were never deployed.

### Spec 022: from `<layer>_dental_omop_perio` to the bench schemas

Spec 021 deployed `health_transformation_lab.<layer>_dental_omop_perio` to dev; uat and prod were never
deployed. Spec 022 renames them to `<layer>_perio_bench` and adds the empty oral_health_bench and access_bench
schemas. Like spec 021, it **rebuilds rather than copies**: after the deploy, Load results reloads every
committed result into `gold_perio_bench`; run *Benchmark*, *Judge scorecard* and *NHANES perio* to regenerate
the study tables, the volume's files and the registered model.

The old schemas, their `data` volume and the old `perio_note_classifier` stay declared in `databricks.yml` under
the dev target only, with their old bundle keys (`landing`, `bronze`, `silver`, `gold`, `data`,
`perio_note_classifier`), because `prevent_destroy` would fail a deploy that renamed or removed them. uat and
prod never had them, so their first deploy creates only the bench schemas.

**Retiring them** in dev, once the perio_bench tables and model check out:

1. `databricks bundle deployment unbind <key> -t dev` for `landing`, `bronze`, `silver`, `gold`, `data` and
   `perio_note_classifier`, so the bundle stops managing them without deleting them.
2. In a pull request, delete the legacy `schemas`, `volumes` and `registered_models` blocks under dev and
   the `legacy_domain` variable; trim the allow-list in `python/tests/test_no_legacy_schema_names.py`.
3. Drop them in SQL: `DROP SCHEMA health_transformation_lab.<layer>_dental_omop_perio CASCADE;`

Kaggle names changed too (kaggle/README.md lists the old items to delete).

## Variables

| Variable | Default | What it sets |
|---|---|---|
| `catalog`, `legacy_domain` | `health_transformation_lab`, `dental_omop_perio` | the catalog, and the suffix of the old schemas dev keeps until retired (spec 022) |
| `legacy_gold_schemas` | the old catalog's and the spec 021 gold schemas | old gold schemas (`catalog.schema`, comma-separated) whose rows Load results' first task carries into `gold_perio_bench`; missing ones are skipped. Set it to empty once they are dropped (issue #228) |
| `n_people` | `300` | synthetic people in the benchmark job |
| `run_encoder` | `false` (uat/prod `true`) | install CPU-only torch and train the DistilBERT rung in the benchmark job; over 16 minutes on serverless CPU |
| `judge_endpoint` | `none` | Model Serving endpoint for `ai_query` (notebook 02) |
| `warehouse_name` → `warehouse_id` | `Serverless Starter Warehouse` | SQL warehouse for notebook 02 (looked up by name) |
| `reader_rung`, `reader_limit` | `medgemma-1.5-4b-it`, `40` (prod `0` = all) | MedGemma job |
| `reader_shots`, `reader_lora_train` | `0`, `0` | MedGemma reader: few-shot examples per status, and LoRA fine-tune size (0 = off). Change these, or `reader_rung` (e.g. `medgemma-4b-it`), for one run with *Run now with different parameters* |
| `telemetry_exporter` | `azure` | Pipeline telemetry for the GPU and NHANES jobs (spec 014): `azure` sends to Application Insights with the connection string from secret `health_transformation_lab/appinsights_connection_string` (telemetry off if the secret is missing), or `otlp`, `console`, `off`. Setup: [telemetry.md](telemetry.md) |
| `deid_ai_engines`, `deid_llm_endpoint` | `llm`, `ai_mask` and their `+regex_v2+guard` versions; `databricks-meta-llama-3-3-70b-instruct` | De-id AI methods job |
| `hf_secret_scope` | `health_transformation_lab` | secret scope with `hf_token` |
| `gpu_accelerator` | `GPU_1xA10` | serverless GPU for the GPU jobs (Free Edition offers A10) |
| `gpu_environment_version` | `4` | serverless environment for the GPU jobs; Databricks requires one when a task sets `compute` |
| `encoder_gpu_rungs`, `encoder_gpu_lr` | the five GPU encoders; `gatortron-base=2e-5` | what the encoder GPU job fine-tunes, and learning-rate overrides |
| `lakebase_instance`, `lakebase_database`, `lakebase_schema` | `dental-dev` / `-uat` / `-prod`, `databricks_postgres`, `cdm_dev` / `cdm` | where the OMOP CDM goes in Lakebase |
| `service_principal` | placeholder id | who runs uat/prod jobs |
| `users_group` | `users` | group given CAN_VIEW on uat/prod jobs |

Override any variable with `--var name=value`, or the environment variable
`BUNDLE_VAR_<name>` (that's how CI passes them).

## Jobs

| Job | Notebook | Compute |
|---|---|---|
| `study_benchmark` | `01_run_benchmark.py`: build synthetic study, baselines, Delta tables | serverless |
| `llm_judge` | `02_llm_judge.sql`: judge with `ai_query` | SQL warehouse |
| `load_lakebase` | `04_load_lakebase.py`: OMOP CDM 5.4 + dental extension into Lakebase (Postgres) | serverless |
| `medgemma_reader` | `03_medgemma_reader.py`: MedGemma note reader, run log to Delta | serverless GPU; retried twice, 2 minutes apart, if the GPU fails to start or Python fails to restart |
| `encoder_gpu` | `08_encoder_gpu.py`: fine-tunes the encoders that need a GPU (large ModernBERTs, Longformers, GatorTron-base at a lower learning rate; spec 002 T017); predictions to the landing volume and `fact_prediction` (source databricks, replaced per run; spec 031) | serverless GPU; retried like the reader |
| `deid_ai` (De-id AI methods) | `06_deid_benchmark.py` with the de-identification methods that need Databricks services: `llm` (serving endpoint `deid_llm_endpoint`) and `ai_mask` (the SQL warehouse), each alone and with patterns + guard; result CSVs to the landing volume (`deid_ai/`) | serverless |
| `nhanes_perio` (NHANES perio) | `09_nhanes_perio.py`: downloads the public NHANES 2009–2014 periodontal files to the landing volume (`nhanes_raw/`), runs `38_nhanes_perio.py` (CDC/AAP 2012 and ACES, survey-weighted) and writes `nhanes/nhanes_prevalence.csv` next to the published figures; copy that CSV to `data/datasets/nhanes/` | serverless |

## Run in dev from your laptop

CI deploys dev on every merge to `main`, as the service principal; don't `bundle deploy` dev from a
laptop too (its own deploy state would make a second copy of every job). Validate and run instead:

```bash
databricks auth login --host https://<your-workspace>      # once
databricks bundle validate -t dev
databricks bundle run      -t dev study_benchmark
```

To deploy dev before a merge, run the deploy workflow by hand (Actions → *Deploy to Databricks dev* → Run workflow; the target is dev by default).

## Deploy with CI (dev, uat, prod)

- `.github/workflows/ci.yml`: Python tests (including `tests/test_bundle.py`,
  which checks the three targets, variables, notebook paths and parameters),
  R parity, and `bundle validate` for all targets when dev credentials exist.
- `.github/workflows/deploy.yml`: push to `main` deploys **dev** and **uat** (each skips until its environment has the client secret); run it
  manually to choose dev, uat or prod. Prod waits for approval.

One-time setup, per target (the same steps worked on a Free Edition workspace, which
has no account console and no AWS account of your own to configure). Each target is
its own workspace: names are the same in all three, so they can't share one.

1. **Create the service principal and its group.** Logged in as a
   workspace admin:

   ```bash
   databricks auth login --host https://<workspace>
   databricks/setup/create_service_principal.sh uat --print-config   # names it will use, no changes
   databricks/setup/create_service_principal.sh uat [--judge-endpoint <serving endpoint>]
   ```

   A bundle can't create a service principal, so this script does, with the CLI. It
   makes `dental_omop_nlp_uat_sp` and the group `dental_omop_nlp_uat_admin` (you and the
   principal), both at account level through the workspace's SCIM proxy, and assigns
   them to the workspace. It gives the principal `workspace-access` (every API call
   needs it) and `databricks-sql-access` (validate looks up the SQL warehouse), and
   `READ` on the `health_transformation_lab` secret scope (created if missing). It gives the group
   `CREATE CATALOG` on the metastore and, with `--judge-endpoint`, `CAN_QUERY` on that
   endpoint. It does not create the catalog: the first deploy creates `health_transformation_lab`,
   its schemas and the volume, and grants the group `ALL PRIVILEGES` on the catalog.
   Deploy dev from your laptop only after running this for `dev` too, since the
   catalog grant names the target's group. It prints the principal's `id` and `applicationId`.
   Run it once per target; a second run fails at the first step because the
   principal exists.
2. **Create its OAuth secret**, here for 90 days. The output shows it once: put it
   straight into GitHub in step 3, never in a file or a chat.
   ```bash
   databricks service-principal-secrets-proxy create <id> --lifetime 7776000s
   ```
3. **Create the GitHub environment, its variables and the secret.** Host and client
   ID are identifiers, so variables; only the client secret is a secret. `gh secret set`
   prompts for the value, so it stays out of your shell history.
   ```bash
   gh api -X PUT repos/<owner>/health-transformation-lab-nlp/environments/uat
   gh variable set DATABRICKS_HOST      -R <owner>/health-transformation-lab-nlp -e uat -b <workspace url>
   gh variable set DATABRICKS_CLIENT_ID -R <owner>/health-transformation-lab-nlp -e uat -b <applicationId>
   gh variable set SERVICE_PRINCIPAL    -R <owner>/health-transformation-lab-nlp -e uat -b <applicationId>
   gh secret set   DATABRICKS_CLIENT_SECRET -R <owner>/health-transformation-lab-nlp -e uat
   ```
   Optional variables: `JUDGE_ENDPOINT`, `WAREHOUSE_NAME` (default
   `Serverless Starter Warehouse`), `USERS_GROUP` (default `users`).
   Give `prod` required reviewers (Settings → Environments → prod).
4. **Check the sign-in:** Actions → *Test that GitHub can log in to Databricks* → Run workflow, environment `uat`. It
   should print a `userName` equal to `DATABRICKS_CLIENT_ID`. Before the secret
   expires, repeat step 2 and `gh secret set`.
5. **Secrets the jobs read**, in the `health_transformation_lab` scope: `hf_token` (MedGemma job) and
   `lakebase_url` (Lakebase load), e.g. `databricks secrets put-secret health_transformation_lab hf_token`.
   The Lakebase load also needs the principal to be able to connect to the target's
   Lakebase instance; the script doesn't set that up.

Until those secrets exist, the workflows skip the Databricks steps and still run the tests.
Every workflow signs in through `.github/actions/databricks-signin`, which strips spaces and
Windows line endings from the three values first, so a pasted `\r\n` can't break sign-in.

## Checked here, and not

- The YAML was checked against the bundle schema from Databricks CLI v0.270.0,
  before the catalogs resource (CLI >= 0.288) was added; re-run `bundle validate`.
- `bundle validate` and `deploy` against a real workspace haven't been run from
  this repo yet (they need workspace credentials). Run `validate -t dev` first.
- `databricks/setup/create_service_principal.sh` hasn't been run from this repo; its
  calls are the ones that set up a Free Edition workspace for another bundle. The tests
  check its syntax, its names per target, and the workflows' sign-in.
