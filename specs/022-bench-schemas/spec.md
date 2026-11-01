# Feature Specification: Databricks schemas and Kaggle names for the three benches

**Feature Branch**: `feat/141-022-bench-schemas`

**Created**: 2026-10-28

**Status**: implemented

**Input**: "our schema names should reflect the new names access_bench perio_bench and oral_health_bench with
bronze silver gold". Owner decision on #127 and #141: spec 021 renames the catalog to
`health_transformation_lab`; this spec names the schemas inside it, and the Kaggle notebooks, datasets, model and
collection, per bench.

> Personal learning project; synthetic data only. No metric, label rule or result changes: the same tables,
> files and model under new names, plus empty schemas for two benches that have no pipeline yet.

The work is framed as three benches: **perio_bench** (periodontal status from charts, everything built so far),
**oral_health_bench** (the umbrella scorecard) and **access_bench** (whether answers help people get care).

## User stories

### US1 - Schemas are named for the benches (P1) #141

| Was (in `health_transformation_lab`) | Now |
|---|---|
| `landing_dental_omop_perio` (the `data` volume) | `landing_perio_bench` (the `data` volume) |
| `bronze_dental_omop_perio` | `bronze_perio_bench` |
| `silver_dental_omop_perio` | `silver_perio_bench` |
| `gold_dental_omop_perio` (tables, `perio_note_classifier`) | `gold_perio_bench` (tables, `perio_note_classifier`) |
| (none) | `bronze_oral_health_bench`, `silver_oral_health_bench`, `gold_oral_health_bench` (empty) |
| (none) | `bronze_access_bench`, `silver_access_bench`, `gold_access_bench` (empty) |

- Names are declared once, in `health_transformation_lab_nlp.schemas`, and are the same in every target.
- Every job, notebook default, dashboard, Genie space, doc and diagram uses them. A test fails if
  `dental_omop_perio` appears anywhere except the legacy bundle entries and history.

Kaggle names follow the bench (owner decision on #141):

| Was | Now |
|---|---|
| notebook `health-transformation-lab-medgemma-reader` | `perio-bench-medgemma-reader` |
| notebook `dental-omop-encoder-gpu` | `perio-bench-encoder-gpu` |
| dataset `synthetic-dental-perio-notes` | `perio-bench-notes` |
| dataset `dental-perio-benchmark-results` | `perio-bench-results` |
| model (planned, #122) | `perio-bench-note-classifier` |
| collection "Dental OMOP NLP" | "Health Transformation Lab: Perio Bench" |

"OMOP" stays wherever it names the data standard.

### US2 - The perio data is rebuilt in the new schemas (P1) #142

Spec 021 rebuilt the catalog rather than copying it; this spec does the same. After the deploy, **Load results**
reloads every committed result into `gold_perio_bench`, and the jobs regenerate the study tables, the volume's
files and the registered model (docs/deployment.md, spec 022 section).

- dev deployed the `<layer>_dental_omop_perio` schemas under spec 021; uat and prod never did. They stay
  declared under the dev target only, with their old bundle keys, so the deploy neither fails on
  `prevent_destroy` nor drops them.
- Retiring them is a documented owner step: unbind, delete from the bundle, drop.

## Out of scope

- Pipelines, tables or questions for oral_health_bench and access_bench.
- Publishing the Kaggle model (#122) and deleting the old Kaggle items (an owner step on kaggle.com).
- Telemetry's data product stays `health_transformation_lab` (spec 021): it names the lab, not a bench.
- Historical specs and PR reviews keep the names they were written with.
