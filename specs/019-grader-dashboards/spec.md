# Feature Specification: two graders on Databricks, as AI/BI dashboards and Genie spaces

**Feature Branch**: `feat/102-018-dq-grader` (US1, US2 and the DQ space of US5), then
`feat/104-018-lab-grader` (US3, US4 and the lab space of US5)

**Created**: 2026-10-28

**Status**: implemented; the dashboards and Genie spaces are confirmed on the first dev deploy

**Input**: "We should create Databricks Genie light versions of the React dashboards we designed yesterday;
we should have different dashboards for the healthtransformationlab.org grader and the EHR DQ grader." The EHR
DQ grader's design is the React *Perio Data Quality (DQ) Monitor* (a personal artifact, 2026-10-27). The lab
grader has no design beyond the pitch (`docs/pitch/`, slides 11 uplift, 12 tests and 13 leaderboard) and
GlobalDentBench's practices (`docs/dentbench_methods.md`).

> Personal learning project; synthetic data only. Health Transformation Lab is a personal idea, not any
> organization's plan. The DQ grader reads the synthetic study's structured evidence (statuses and
> measurements, never note text). The lab grader holds only a simulated sample until real runs exist, and says so
> on every page and in every Genie answer.

"Light" means: the React designs' structure and measures, built from Databricks' own AI/BI widgets and Genie, with
no custom front end to host. Same names in every target; deployed by the bundle.

## User stories

### US1 - The data-quality results are in the gold tables (P1) #102
The **Load results** job also writes the data-quality outputs to `dental_omop.gold_dental_omop_perio`. Each
table is overwritten from its deployed CSV on every run (idempotent), and every row carries the file's `sha256`,
`git_commit` and `loaded_at`.

Gold names follow AGENTS.md "SQL and data names" (spec 018): the frames keep analysis names and Load results
renames them with `gold_names.to_gold`; each table is declared in `diagrams/_build/gold_model.py`.

| Table | From | One row per |
|---|---|---|
| `dq_check` | `data_quality/dq_overall.csv`, `dq_by_clinic.csv` | (check, clinic); `clinic` = `All` for the overall rows |
| `dq_column_missing` | `data_quality/completeness_columns.csv` | evidence column: rows, missing, % missing |
| `dq_prevalence` | `prevalence/prevalence_by_clinic.csv`, `data_quality/prevalence_by_scale.csv` | (method, clinic or scale) |
| `dq_temporal_change` | `data_quality/temporal_by_method.csv` joined with `transitions_by_method.csv` | method |
| `dq_stage_transition` | `data_quality/transitions_algorithm_design.csv`, long form | (from stage, to stage), with count, row % and better / same / worse |
| `dq_source_concordance` | `method_agreement.csv` | pair of evidence sources |
| `fact_visit_evidence` | `visits_structured.csv` joined with `answer_key/visits_truth.csv` | visit: clinic, visit date, each evidence source's status, the truth status (no note text) |
| `dq_injected_error` | `data_quality/injected_error_recall.csv` | one row |

### US2 - An EHR DQ grader dashboard (P1) #103
An AI/BI dashboard, **EHR DQ grader**, the light version of the DQ Monitor. A banner says synthetic data, scored
against the generator's truth. One page, filtered by clinic:

- **Five domain tiles**, as in the design: completeness (share of visits with every evidence source present),
  accuracy (the whole-record rule phenotype vs truth), consistency (spread of periodontitis prevalence across
  clinics, in points), temporal plausibility (share of later visits whose stage improves without a reason; Kahn),
  and reliability (de Vet et al. 2006; #405 corrected an earlier credit to Liaw et al. 2013) shown as **not assessed** until real reviewers have labelled charts.
- **Completeness:** missingness by evidence column; checks with their pass rate and status.
- **Accuracy:** each evidence source against the truth (share answered, agreement where answered); concordance
  between sources.
- **Consistency:** prevalence by clinic with its 95% interval, against the overall rate.
- **Temporal plausibility:** the stage transition matrix (rows = earlier visit) with improvements flagged; the
  implausible-change rate by method; the injected-error catch rate (synthetic only).

### US3 - The lab grader's tables, with a seeded simulated sample (P1) #104
Two tables shaped by GlobalDentBench's practices as `docs/dentbench_methods.md` adapts them:

| Table | One row per | Columns |
|---|---|---|
| `grader_questions` | question | `question_id`, `category` (access to care first; clinical cases; medical-dental integration; barriers to care; cost and coverage), `level` (L1 recall, L2 routine reasoning, L3 individualized reasoning), `n_key_points`, `source` (the published evidence behind it) |
| `grader_answers` | (question, model, with or without the agent, run) | `model`, `with_agent`, `key_points_covered`, `score` (covered / key points), `harm` (S0 safe, S1 reversible, S2 irreversible), `cost_usd`, `judge`, `run_id`, `simulated` |

- Until a real run exists, `python/scripts/43_simulated_grader.py --seed 2026` writes `simulated_grader_questions.csv`
  and `simulated_grader_answers.csv`: about 25 questions per category (the pitch's pilot size), three models named
  `sim:model-a/b/c`, and `simulated = true` on every row. Load results loads them; real files (`grader_*.csv`)
  replace them later with no schema change.
- The judge is never of the same family as an evaluated model, and harm is a grade given by clinicians'
  rules, not by the judge, as in `dentbench_methods.md`.

### US4 - A lab grader dashboard (P1) #105
An AI/BI dashboard, **Lab grader**, designed from the pitch's uplift and leaderboard slides. A banner says
SIMULATED while any row is simulated.

- **Uplift by category**, access to care first: score on its own, with the agent, the difference, each with a
  95% interval, and cost per answer (slide 11's table).
- **Leaderboard per category**: models ranked within a category, never one overall rank across categories.
- **Safety**: unsafe rate (S1 + S2) and irreversible-harm rate (S2), on its own and with the agent.
- **By reasoning level**: score per level L1–L3 and the macro average, so easy questions don't flatter a model.
- **Cost vs score**: one point per (model, with agent), since paying more did not reliably buy a better answer in
  GlobalDentBench.

### US5 - A Genie space for each grader (P2) #106
Two Genie spaces declared in the bundle (`genie_spaces` resource; Databricks CLI with the resource, direct
engine), **EHR DQ grader** and **Lab grader**. Each lists only its own tables, defines every measure in its text
instructions exactly as its dashboard computes it, gives sample questions, and tells Genie to say "synthetic" (DQ)
or "simulated" (lab, while it is) in every answer and never to rank models across categories.

## Out of scope
- A hosted React front end, or the React designs themselves.
- Real lab grader runs and the open agent (the pitch's phase 1); reliability (ICC) on real reviewers.
- Any change to a label rule, metric or score already in the study, so no R change.

## Success criteria
- `databricks bundle validate` passes with both dashboards and both spaces.
- Every dashboard dataset's SQL runs in tests against tables built from the committed CSVs.
- Running Load results twice leaves every `dq_*` and `grader_*` table with the same rows.
