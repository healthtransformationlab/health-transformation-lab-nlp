# The graders on Databricks (spec 019)

Two graders, each an AI/BI dashboard plus a Genie space you can ask questions in plain words. Both are light
versions of designs: the EHR DQ grader follows the React *Perio DQ Monitor*; the lab grader follows the pitch's
uplift and leaderboard slides (`docs/pitch/`). Synthetic data only; the lab grader is simulated until real runs
exist.

| Grader | Dashboard | Genie space | Tables (`health_transformation_lab.gold_perio_bench`) |
|---|---|---|---|
| **EHR DQ grader**: is the dental record fit for periodontal phenotyping? | *EHR DQ grader* | *EHR DQ grader* | `dq_check`, `dq_column_missing`, `dq_prevalence`, `dq_temporal_change`, `dq_stage_transition`, `dq_source_concordance`, `fact_visit_evidence`, `dq_injected_error`, `fact_case_profile_item`, `fact_record_mismatch`, `dq_mismatch_rule` |
| **Lab grader**: do AI answers on medical-dental and access-to-care questions improve with the open agent? | *Lab grader* | *Lab grader* | `dim_grader_question`, `fact_grader_answer` |

## EHR DQ grader

Five domain tiles, then one section per domain:

| Domain | Framework | Measure (the dashboard and Genie use the same definition) |
|---|---|---|
| Completeness | Zozus | Visits with exam form, diagnosis codes and gum measurements all present |
| Accuracy | Zozus | Rules on the whole record, gum measurements first (`algorithm_v0`), agreeing with the truth; each source's agreement where it answers |
| Consistency | Zozus | Spread of periodontitis prevalence across the 8 clinics, in points |
| Temporal plausibility | Kahn | Later visits whose stage improved (design rules); the full stage-to-stage matrix |
| Reliability | de Vet | **Not assessed**: needs real reviewers |

`fact_visit_evidence` holds statuses only (what each evidence source says, and the truth), never note text.

**Case profiles** (spec 026, after KEEPER: Schuemie, Ostropolets et al., npj Digit Med 2025).
`fact_case_profile_item` lays out every synthetic visit's structured evidence the same way, in nine categories:
demographics, presentation (the recorded diagnosis codes and exam form), visit context, measurements, tests and
imaging, risk factors, treatment, other readings (the note reader and the rule phenotypes), and after the visit (the
next visit's recorded code and the plausibility checks it fails). A value the record lacks reads "not recorded".
It is built from `visits_structured.csv` when Load results runs, so it isn't committed twice. Genie can show any
visit's profile ("Show the case profile of visit 1234.").

**Record mismatches** (spec 026 US2). Six rules ask whether a visit's recorded code (the completed diagnosis code)
fits the rest of its record. A failed rule is a record to recheck: usually a coding or charting gap, never a
judgment that a dentist got it wrong. `scripts/45_case_profiles.py` writes them; `r/R/15_spec026.R` is the R twin.

| Rule | Flags a visit when | Threshold source |
|---|---|---|
| `code_vs_chart` | the code is more than one step from the probing-chart reading | the study's chart reader |
| `code_above_chart` | a stage III code, but the chart is within stage I (CAL < 3 mm, bone loss < 15%, no tooth lost, PD < 6 mm) | 2017 AAP/EFP staging |
| `code_below_chart` | a healthy or gingivitis code, but CAL ≥ 3 mm or bone loss ≥ 15% | 2017 AAP/EFP staging |
| `no_periodontal_care` | a periodontitis code, and no periodontal procedure completed or planned | study design |
| `code_vs_radiograph` | a healthy or gingivitis code, and the radiograph AI reads stage II or worse | the study's radiograph AI |
| `stage_drop` | a code lower than a periodontitis stage the patient had before (a stage never goes down) | 2017 AAP/EFP; spec 005 checks |

Scored on **synthetic records, against the generator's truth**, over the visits each rule can check (all
clinics; `dq_mismatch_rule`, clinic `All`). A stage drop counts as true when either visit's code is wrong;
"any rule" uses the visit's own code.

| Rule | Checkable | Flagged | Precision | Recall | Only this rule |
|---|---:|---:|---:|---:|---:|
| `code_vs_chart` | 2,429 | 159 | 0.97 | 0.21 | 6 |
| `code_above_chart` | 2,429 | 3 | 1.00 | 0.00 | 2 |
| `code_below_chart` | 2,429 | 141 | 0.99 | 0.18 | 0 |
| `no_periodontal_care` | 3,061 | 353 | 0.56 | 0.21 | 326 |
| `code_vs_radiograph` | 677 | 141 | 0.99 | 0.48 | 20 |
| `stage_drop` | 1,065 | 478 | 1.00 | 0.70 | 340 |
| any rule | 3,061 | 893 | 0.59 | 0.56 | 694 |

What this says, on synthetic data: the measurement rules are precise but each sees a slice of the wrong codes;
`code_below_chart` adds no flag `code_vs_chart` doesn't already make, though it states a clinical reason; `stage_drop`
and `no_periodontal_care` find the most on their own, the second with many false flags (a periodontitis code is
often right with no procedure billed yet). Of the 45 injected charting errors, 34 have a code; the rules catch 11
of those, where the temporal checks (`dq_injected_error`) catch 15 of all 45. Per-clinic injected-error counts are
too few to compare.

**Records to recheck** (spec 026 US3) is the EHR DQ grader's second page. It shows:

- each rule's scores against the truth, with how many visits it can check;
- the flagged visits, most rules failed first, filtered by clinic and rule;
- the selected visit's case profile beside them.

A banner says the data is synthetic and that a flag is a coding or charting gap, not a clinical error. The page's
datasets read only `dq_mismatch_rule`, `fact_record_mismatch`, `fact_case_profile_item` and `fact_visit_evidence`.

## Lab grader

**A SIMULATED sample until a real run exists: every number is made up.** `python/scripts/43_simulated_grader.py`
(seeded) writes `data/datasets/grader/simulated_grader_*.csv`: 25 questions in each of five categories, three
`sim:` models, each answering on its own and with the agent. A real run commits `grader/grader_questions.csv` and
`grader/grader_answers.csv` with the same columns, and Load results uses those instead. The *Simulated rows* tile
then reads 0.

Practices from GlobalDentBench (`docs/dentbench_methods.md`), as the pitch's uplift and leaderboard slides use them:

| On the dashboard | Measure |
|---|---|
| Uplift by category, access to care first | Score with the agent minus on its own, in points, with a 95% interval; cost per answer beside it |
| Leaderboard | Models ranked within a category, on their own and with the agent separately; never one overall rank |
| Safety | Unsafe (S1 + S2) and irreversible (S2) shares; harm graded by clinicians' rules, not by the judge |
| By reasoning level | L1 recall, L2 routine, L3 individualized, and their macro average |
| Cost against score | One point per model and answer mode |

Score = key points covered / key points (five per question). The judge comes from a family no evaluated model
shares.

## How it's built and deployed

- **Tables:** `health_transformation_lab_nlp/grader_tables.py` builds each table from the committed CSVs. The *Load results* job
  overwrites them on every run, so a rerun leaves the same rows, and every row carries the `sha256` of its files.
- **Dashboards and spaces:** `health_transformation_lab_nlp/dashboards.py` builds `databricks/dashboards/*.lvdash.json` and
  `databricks/genie/*.geniespace.json`. After changing it, run `cd python && python scripts/42_build_dashboards.py`.
  Never edit the JSON by hand: a test checks the committed files match the builder.
- **Tests:** every dashboard query runs in DuckDB on the same tables under the same names, so the SQL is checked
  before deploy.
- **Deploy:** the main bundle deploys the dashboards (`databricks/resources/dashboards.yml`) in every target, under
  the same names. The Genie spaces are their own bundle, `databricks/genie/databricks.yml` (Databricks CLI 1.3.0 or
  later, direct engine), because a space can't be created before the tables it reads. The deploy workflow deploys
  it last, once *Load results* has written every table; until then it skips with a notice, and a later deploy
  creates the spaces (issue #155).
