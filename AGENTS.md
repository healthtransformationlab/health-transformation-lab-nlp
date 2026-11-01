# AGENTS.md

Rules for every coding agent working in this repo (Claude Code, Codex, Cursor, Copilot and others).
Claude Code reads them through `CLAUDE.md`, which imports this file and adds its own workflow.

Folders with their own rules have their own `AGENTS.md` (read it before working there):

- `databricks/agents/chart_review/AGENTS.md`: the planned Databricks chart review agent.

## Ground rules

Read `DISCLAIMER.md` and `.specify/memory/constitution.md` first. The short version:

- **Personal learning project, not affiliated.** Don't describe anything here as
  an organization's plan, study, finding or partnership. Mention companies only
  as their public sources describe them, with a citation.
- **Synthetic only. No PHI, ever.** Don't add real notes, real names, or
  employer data anywhere, including tests and prompt examples. One exception:
  published, already de-identified datasets licensed for redistribution (MACCROBAT,
  CC BY 4.0) live in `data/external/<name>/` with a README giving source and licence,
  for evaluation and training only, never mixed into the synthetic sets.
  Data-use-agreement sets (i2b2/n2c2) never go in.
- **Python and R stay in parity.** If you change labels, scoring, reliability
  or cost-effectiveness on one side, change the other and run the parity test.
- **Test first.** Write the failing test, then the code.
- **Label simulated output as simulated.** Never present a dry-run number as a result.

## Words: we find gum disease in records, we don't diagnose

We aren't clinicians. "Diagnosis" is only ever something a dentist recorded (`diagnosis code`, "the recorded
diagnosis"), never something our rules, models or agents do. What we do is phenotyping, but most readers don't know
the word: say it plainly first and give the term once in brackets, e.g. "finding gum disease in dental records
(phenotyping)", then "case finding".

| Avoid | Write |
|---|---|
| diagnose, AI diagnoses, diagnostic tool | identify or find gum disease in the record; record-reading or case-finding tool |
| accurate diagnosis, diagnosis accuracy | agreement with gum specialists reviewing the same record |
| inaccurate or wrong diagnosis, misdiagnosis | record mismatch ("the recorded code doesn't fit the chart"); records to recheck |

A mismatch is often a coding or charting gap, not a clinical error: never imply a dentist got it wrong. This covers
docs, decks, dashboards, Genie instructions, table and column names, issues and PRs. Quoting a cited paper's own
words is fine. `python/tests/test_wording.py` fails CI on the phrases to avoid in any other tracked file (past PR
reviews in `pull_requests/` are records and stay as written).

## The benchmarks

Always in this order, wherever two or more are named (prose, lists, tables, decks, cards, schemas, code):
**PerioBench, then OralHealthBench, then AccessBench**; in code, `perio_bench`, `oral_health_bench`, `access_bench`.
`python/tests/test_bench_order.py` fails CI on a list out of order.

- **PerioBench: trustworthy records.** Measure the data quality of electronic dental records.
- **OralHealthBench (planned): accurate AI answers.** Score the AI that millions of people ask on the questions that
  matter at the seam of medical and dental care: medicines, chronic disease, emergencies.
- **AccessBench (exploratory): getting care.** Whether an answer helps someone actually get care.

## Sources of truth (the map)

Mental model: **synthetic dental notes go in; a status (healthy to periodontitis stage 4) with a verbatim
quote comes out; the answer key and a second-model judge score it; the ladder and leaderboards compare
systems.** Read the file that owns a concern before changing anything that touches it.

| Concern | Lives in |
|---|---|
| Labels, the six statuses, grade and extent rules | `python/health_transformation_lab_nlp/labels.py` |
| Synthetic charts and notes | `synthetic.py`, `notes.py` (seeded; `scripts/10_build_study.py` rebuilds) |
| Reader prompt, parsing, the quote gate | `llm_reader.py` (`PROMPTS`, `parse_answer`) |
| Judge prompts and gates | `judge.py`; scorecard in `judge_scorecard.py` (spec 012) |
| Metrics and the shared Python/R contract | `eval/score.py`, `eval/score.R`, `eval/README.md` |
| Model ladder and rungs | `models.yaml`, `rungs.py`, `ladder_eval.py` |
| Answer key and committed data | `data/datasets/answer_key/review_key.csv`; paths only via `paths.py` |
| Gold table names and column rules | `gold_names.py`, `diagrams/_build/gold_model.py`, "SQL and data names" below |
| Telemetry (`@traced`, levels) | `telemetry.py`, `telemetry_levels.yaml` |
| Kaggle: GPUs, datasets, Kaggle Benchmarks task | `kaggle/README.md`, `kaggle/perio_bench_task.py`, `kbench.py`, `docs/kaggle_benchmarks.md` |
| Settings, secrets, alerts, reruns | `databricks.yml`, `ops/secrets_register.yaml`, `docs/operations.md` |
| Specs, decisions, PR reviews | `specs/NNN-*/`, `docs/adr/`, `pull_requests/` |
| The rules every coding agent follows | this file; Claude Code's own workflow in `CLAUDE.md` |

Generated files are never edited by hand: `docs/edr/README.md` and `docs/results.md` come from
`scripts/35_readme_results.py`, the decks from `docs/build_decks.py`.

## When a change needs a spec

Anything that changes a dataset, a metric, a label rule or the review workflow gets a spec first:
`specs/NNN-name/spec.md` (what and why), then `plan.md` and `tasks.md` in the same folder (how).
Small fixes (a typo, a one-line bug with a regression test) don't need one.
Every pull request gets a review written to `pull_requests/pr-<n>-review.md`, against
`.claude/review-rubric.md` and these rules.

## Decisions and action items

Keep decisions apart from to-dos. A decision (what we chose, why, when to revisit) is a decision record
in `docs/adr/NNNN-slug.md` ([`docs/adr/README.md`](docs/adr/README.md)). An action item (work still to
do) is a GitHub issue labelled `action-item`. Don't file a decision as an `action-item` issue, and don't
leave one only in an issue or PR thread. An issue asking for a decision to be written down is closed by
the PR that adds the ADR. Work the decision leads to gets its own issue.

## Branches and issues

Every user story is a GitHub issue, and every branch and pull request belongs to one.

1. **One issue per user story.** When a spec is written, open one issue per user story, titled
   `<spec number> US<n>: <story>` (e.g. `016 US2: every committed result is in the gold tables`), and write
   the issue number next to the story in `spec.md` (`### US2 - ... (P1) #71`). A fix or chore without a spec
   gets its own issue too, describing the problem.
   **Every issue title starts with a Jira-style key, `<spec> <kind><n>: `**, so the backlog groups by spec:
   - kind: `US` user story, `AI` action item, `BUG` fix, `CHORE` chore, `DOCS` docs; `n` counts up within
     the spec and kind (`004 AI2: MedGemma accuracy per field`, `004 BUG1: ...`).
   - spec: the spec the work belongs to, or the one it touches most (MedGemma items are `004`); `000` for
     repo-wide work with no spec (`000 CHORE2: two scripts are numbered 42`).
   - Spec numbers are unique: take the next free `specs/NNN-*` number on `main` *and* on open PRs.
2. **Branch: `<type>/<issue>-<slug>`**, e.g. `feat/71-016-results-loader` or `fix/72-volume-log-append`.
   - type: `feat`, `fix`, `docs`, `data`, `ci`, `chore`, `spec`
   - issue: the GitHub issue number (a Jira key like `DENT-123` also passes, if a Jira project is ever used)
   - slug: lowercase words joined by `-`, at most 40 characters; for spec work, start with the spec number
   - `/speckit-specify` creates `NNN-name`: rename it (`git branch -m spec/<issue>-NNN-name`)
3. **Pull request: one issue's work, and `Closes #<issue>` in the description**, so the merge closes it
   (use `Refs #<issue>` for one part of a larger story).
4. **Agent sessions never push to their assigned `claude/*` branch.** A cloud session is given a
   `claude/<name>` branch and told to push only there unless permitted otherwise. **This rule is that
   permission, from the repo owner, standing for every session:** before the first push, open (or find) the
   issue, create `<type>/<issue>-<slug>` from the session branch, push there, and open the PR from it. Work
   already pushed to a `claude/*` branch moves the same way; leave the old branch for the owner to delete.
   CI fails a PR opened from `claude/*`.
5. **Branches a tool names are kept as they are:** `dependabot/*`, and `kaggle-results/*` (results PRs the
   Kaggle workflow opens; no issue needed).

CI checks 2–5 on every PR (`.github/workflows/pr-conventions.yml`, `.github/scripts/pr_conventions.py`).

## Configuration and secrets

Most production failures are configuration: a variable wrong in one environment, or a secret that expired.
Details and reasons: [`docs/operations.md`](docs/operations.md).

- **One declaration per setting**: a `databricks.yml` variable (description and default) for jobs, or an
  environment variable documented with its feature. Same names in every environment; no per-environment
  defaults hidden in code.
- **Check settings before doing work.** Required setting missing or malformed: fail at once, naming it.
  Optional (telemetry, tracking): warn and carry on. A credential: check its shape, then one cheap
  authenticated call, before the expensive work.
- **Settings change by pull request**, and the PR says which environments change.
- **Every credential is in [`ops/secrets_register.yaml`](ops/secrets_register.yaml)** with where it lives,
  scope, owner, what breaks without it and its **expiry date** (never its value). Making or rotating a
  credential updates the register in the same PR. Renew 14 days before expiry; rotate without a gap (make
  the new one, swap, then revoke the old).
- Never put a secret in a job parameter, a file, a log, a span, a PR or chat.

## Alerts and severity

Every alert names a severity, an owner and an action. Without an action it isn't an alert.

| Level | Means | Goes to |
|---|---|---|
| SEV1 | wrong or unsafe output published, data exposed, or production down | the owner directly, now (1 hour) |
| SEV2 | a production pipeline failed and won't recover, or a credential expires within 7 days | the owner by email, same day |
| SEV3 | failed then recovered, a data-quality check below threshold, rescued rows, credential within 30 days | the **daily digest** |
| SEV4 | warnings, deprecations, cost drift, credential within 90 days | the **weekly digest** |

Digests are one email per owner per period: grouped by severity then system, each problem once with a count,
each line with its fix and link, and kept until closed. A chat channel may mirror a digest, never replace it.
A SEV2 that fires every week for the same cause gets its cause fixed or its level lowered.

## Failures, retries and reruns

- **Every write is idempotent**: overwrite, `MERGE` on a key, or delete-then-append by batch key (as Load
  results does). Plain append only for event logs. Databricks repair re-runs a whole task from the start and
  does not make it idempotent for you.
- **Every written row carries its batch key** (`run_id` and `run_ts`, or `file_sha256` and `loaded_ts`; and
  `git_commit_sha`).
- **Retries are set explicitly** per task (count and interval), only for failures that can pass on their own
  (no GPU free, a network blip); a timeout applies to each retry. A bad setting or bad data fails at once.
- A failure says how it ended (exit code, signal, memory) and is logged where it survives the process
  (`runlog`), never into a file opened for append on a volume.

## Ingestion and schema drift

- Auto Loader streams set `cloudFiles.schemaLocation`, a rescued-data column, and a deliberately chosen
  `cloudFiles.schemaEvolutionMode`, with the reason in a comment. Default to `rescue` or `failOnNewColumns`
  for feeds that must not change silently; never `none` without a rescued-data column.
- Rows in the rescued-data column are counted per batch and reported (SEV3).
- `cleanSource` only for single-reader directories, `DELETE` only with bucket versioning on, and keep our
  own file ledger when we must prove what was loaded.

## SQL and data names

New tables and views, in Unity Catalog or Postgres, follow these, and the gold tables do since spec 018
(adapted from jcbowyer/DE_Assessment). OMOP CDM tables and columns keep their official names. Older objects that
don't yet (the Postgres `perio_chart` view, `labeled_notes`, `benchmark_results`, `encoder_gpu_predictions`) change
when they're next touched. `python/tests/test_sql_conventions.py` checks the gold tables declared in
`diagrams/_build/gold_model.py`.

- **Style:** lowercase snake_case names, no quoted or mixed-case identifiers. Keywords lowercase in new SQL; older
  files and the dashboard queries are uppercase, so keep one case per file. Three-part names
  (`health_transformation_lab.gold_perio_bench.fact_prediction`) outside a pipeline. CTEs, not nested subqueries;
  explicit `inner join` / `left join`; no `select *` outside bronze. Each table's comment states its grain.
- **Tables are singular**, one row per noun (`fact_prediction`, not `ai_predictions`).
- **Gold prefixes:** `fact_<event>` one row per event or answer, with a key to each dimension it uses;
  `dim_<noun>` one row per thing described; a summary table is named `<subject>_<noun>` (`judge_metric`,
  `deid_score`); `kpi_<subject>` a metric view. Silver and bronze tables are named for what they hold.
- **pandas frames and CSV files keep their analysis names.** `health_transformation_lab_nlp.gold_names.to_gold` renames them
  when a job writes gold, and fails on a column it doesn't know: declare a new column there, with its gold name.
- **Columns:** `<what it describes>_<kind>`, never a bare generic name (`code`, `name`, `status`, `type`,
  `value`): say whose (`predicted_status_code`, `engine_name`).

| Suffix or prefix | Holds | Type | Example |
|---|---|---|---|
| `_id` | an identifier from a source, OMOP or Databricks | `bigint` or `string` | `visit_id`, `run_id` |
| `_key` | a key built here (hash of a natural key) | `string` | |
| `_code` | a coded value from a fixed set | `string` | `predicted_status_code`, `tier_code` |
| `_name` | a short label | `string` | `method_name`, `engine_name` |
| `_text` | free text: a note, a quote, an error | `string` | `quote_text`, `error_text` |
| `_date` | a calendar date | `date` | `exam_date` |
| `_ts` | a moment: from the source, or when a job acted | `timestamp` (UTC) | `run_ts`, `loaded_ts` |
| `_count` | a count | `bigint` | `row_count`, `judged_count` |
| `_ratio` | a proportion 0 to 1 (or a difference of two) | `double` | `agreement_ratio` |
| `_pct` | a percent 0 to 100; never `percent` | `double` | `bop_pct` |
| `_rate` | a count per unit, the unit named before it | `double` | `leaked_phi_per_1k_note_rate` |
| `_coef` | a coefficient such as Cohen's kappa, −1 to 1 | `double` | `kappa_coef` |
| `_seconds` | a duration | `double` | `latency_seconds` |
| `_usd` | money, US dollars (`double`: per-call costs are fractions of a cent) | `double` | `cost_usd` |
| `_num` | a number that isn't a count or a measure: a position, a year | `bigint` | |
| `_url` | a link | `string` | `run_url` |
| `_sha256`, `_sha` | a file's SHA-256, a git commit's SHA, hex | `string` | `file_sha256`, `git_commit_sha` |
| `is_` prefix | a boolean: true or false, null when unknown; never Y/N or 0/1 | `boolean` | `is_gate_ok`, `is_simulated` |
| `avg_`, `p50_`, `p95_` prefix | an average or percentile of what follows, which keeps its suffix | as that suffix, `double` | `avg_latency_seconds` |

## Commands

```bash
cd python && pip install -e ".[dev]"
pytest -q tests                                   # Python tests
cd .. && python/scripts/make_parity_inputs.sh && Rscript r/tests/test_parity.R   # R vs Python parity
cd python && python scripts/10_build_study.py     # rebuild study datasets (seeded)
cd python && python scripts/35_readme_results.py  # refresh the results leaderboards (docs/edr/README.md, docs/results.md)
cd python && python scripts/42_build_dashboards.py  # rebuild the grader dashboards and Genie spaces (spec 019)
cd python && python scripts/43_simulated_grader.py  # the lab grader's SIMULATED sample (seeded), until real runs exist
python docs/build_decks.py                        # rebuild the slide decks after editing docs/<deck>/slides/
cd python && pytest -q tests/test_kbench.py && python ../kaggle/perio_bench_task.py   # PerioBench as a Kaggle Benchmarks task (docs/kaggle_benchmarks.md)
```

Full pipeline and dry runs: `README.md`. Study design: `docs/process.md`.

## Conventions

- Commits: imperative subject, body says why. Co-author trailer when an agent wrote it.
- Seeds: every generator and sampler takes one; defaults are fixed.
- Paths: use `health_transformation_lab_nlp.paths`, never hard-code `data/`.
- Telemetry: every public function or method in `python/health_transformation_lab_nlp/` gets `@traced` (from
  `.telemetry`); a test fails without it. Never put note text or row-level data in span attributes or logs.
- Names: simulated files `simulated_*`, simulated methods `sim:<name>`, calibration-only methods `calib:<name>`.
- R: base R only, matching Python to 1e-9 (`r/tests/test_parity.R`).
- Databricks names: identical in every target (catalog `health_transformation_lab`, schemas `<layer>_<bench>`:
  `landing_`/`bronze_`/`silver_`/`gold_perio_bench`, and `bronze_`/`silver_`/`gold_` for `oral_health_bench` and
  `access_bench`; `landing_`/`bronze_`/`silver_`/`gold_opendental_perio` for the Open Dental extract, spec 029;
  `health_transformation_lab_nlp.schemas`, spec 022). Never add `dev_`,
  `[dev <user>]` or per-environment prefixes or suffixes, and never use
  `mode: development` (it adds them): each environment is its own workspace.
  dev is deployed by CI on every merge to `main`; don't `bundle deploy` it from a laptop.
- Secrets and tokens: whenever you tell the user to create one, give the exact scope(s)
  to select, a short lifetime, and where it goes, and add it to `ops/secrets_register.yaml` with its expiry.
  Never ask for it in chat. For this repo:

  | Credential | Where it's made | Scope | Goes to |
  |---|---|---|---|
  | `dental-omop-ci` OAuth secret | Databricks → Settings → Identity and access → Service principals → Secrets | `all-apis` (bundle deploy touches jobs, workspace files, Unity Catalog, MLflow, SQL) | GitHub environment secret `DATABRICKS_CLIENT_SECRET` |
  | Workspace personal access token (admin setup; agent reads job runs) | Databricks → Settings → Developer → Access tokens | `all-apis`, 15 days at most; revoke when not needed | cloud environment variable `DATABRICKS_TOKEN` |
  | `gh` login for `gh secret set` / `gh variable set` | `gh auth login` | `repo` (classic), or fine-grained: this repo, Secrets, Variables and Environments read and write | your laptop only |
  | Hugging Face token for MedGemma | huggingface.co → Settings → Access tokens | Read | Databricks secret scope `health_transformation_lab`, key `hf_token` |
  | Application Insights connection string (telemetry, spec 014) | Azure portal → Application Insights `health-transformation-lab-nlp-appi` → Overview, or `terraform -chdir=infra/azure output -raw connection_string` piped straight into the secret (docs/telemetry.md); also in the git-ignored Terraform state | ingestion only: can send telemetry, can't read; doesn't expire, so rotate by recreating the resource | Databricks secret scope `health_transformation_lab`, key `appinsights_connection_string` |
  | Kaggle API token (MedGemma on Kaggle) | kaggle.com → Settings → API → Generate New Token | the Kaggle account (no narrower scope offered); delete it on Kaggle when not running | GitHub environment `dev` secret `KAGGLE_API_TOKEN` |
  | Hugging Face publish token (spec 025) | huggingface.co → Settings → Access tokens → Fine-grained | write access to the `healthtransformationlab` organisation's repositories only; 90 days at most | GitHub environment `dev` secret `HF_PUBLISH_TOKEN` |
  | Website push token (deck copies, #374) | github.com → Settings → Developer settings → Personal access tokens → Fine-grained tokens, resource owner `healthtransformationlab` | only the repository `healthtransformationlab/healthtransformationlab.github.io`, Contents read and write; 90 days at most | GitHub repository secret `SITE_PUSH_TOKEN` |
