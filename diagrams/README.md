# Diagrams

draw.io sources with rendered PNGs, and Mermaid process flows. Gold tables: [`gold/data_model.md`](gold/data_model.md) and [`docs/gold_tables.md`](../docs/gold_tables.md). How they're built: [`_build/render.md`](_build/render.md).

| Diagram | What it shows |
|---|---|
| [**d0 medallion architecture**](d0_medallion_architecture.png) ([.drawio](d0_medallion_architecture.drawio)) | Source → ingest → bronze (PHI zone) → silver (de-identified) → gold (OMOP + dental) → query and process → serve → consumers, on Databricks; same style as the Milliman diagrams |
| [d1 study process](d1_study_process.png) ([.drawio](d1_study_process.drawio)) | Chart notes, exam forms, procedure codes and diagnoses (completed and planned) and the probing chart → comparison, qualitative review, rule-based phenotype, AI, reviewers, acceptance test |
| [d2 platform architecture](d2_platform_architecture.png) ([.drawio](d2_platform_architecture.drawio)) | GitHub CI/CD → one bundle, three environments: jobs, Delta, Lakebase, MLflow, UC model, serving, Label Studio |
| [d3 ERD](d3_erd_omop_dental.png) ([.drawio](d3_erd_omop_dental.drawio)) | OMOP CDM 5.4 tables used, dental extension (SITE, SITE_EVENT), local concepts, perio_chart view |
| [d4 site storage designs](d4_site_storage_designs.png) ([.drawio](d4_site_storage_designs.drawio)) | Post-coordinated vs pre-coordinated vs site columns, with measured joins, time and storage |
| [d5 MLOps lifecycle](d5_mlops_lifecycle.png) ([.drawio](d5_mlops_lifecycle.drawio)) | Train → log → register (challenger) → acceptance test → champion; judge; monitoring |
| [**gold logical architecture**](gold/gold_logical_architecture.png) ([.drawio](gold/source/gold_logical_architecture.drawio)) | How results reach `gold_perio_bench`, on the Databricks reference architecture (frame from jcbowyer/DE_Assessment) with Databricks icons |
| [gold physical architecture](gold/gold_physical_architecture.png) ([.drawio](gold/source/gold_physical_architecture.drawio)) | The same with the deployed jobs, notebooks, schemas and tables |
| [gold data model, entity](gold/gold_data_model_entity.png) ([.drawio](gold/source/gold_data_model_entity.drawio), [.mmd](gold/source/gold_data_model_entity.mmd)) | The gold tables (spec 018 names) and their relationships |
| [gold data model, full](gold/gold_data_model_full.png) ([.drawio](gold/source/gold_data_model_full.drawio), [.mmd](gold/source/gold_data_model_full.mmd)) | Every column, type, logical key and description; also as Mermaid in [gold/data_model.md](gold/data_model.md) |
| [**Open Dental silver**](silver/opendental_silver_entity.png) ([full](silver/opendental_silver_full.png); [.drawio](silver/source/opendental_silver_entity.drawio), [full .drawio](silver/source/opendental_silver_full.drawio)) | Spec 029's `silver_opendental_perio`: the cleaned Open Dental tables with their own names, the per-tooth and planned-extraction tables, the data-quality checks and the answer key; every column in [silver/data_model.md](silver/data_model.md) |
| [Open Dental silver, data dictionary](silver/opendental_silver_dictionary.png) ([.drawio](silver/source/opendental_silver_dictionary.drawio)); [OMOP](silver/omop_silver_dictionary.png) | The same tables as a data dictionary: subject areas, fact and dimension headers, each table's row count and grain, each column's meaning, open questions in red, and its profile (nulls, distinct and top values) once spec 029's synthetic extract exists |
| [OMOP silver, an alternative](silver/omop_silver_entity.png) ([full](silver/omop_silver_full.png); [.drawio](silver/source/omop_silver_entity.drawio), [full .drawio](silver/source/omop_silver_full.drawio)) | The same data mapped to OMOP CDM 5.4 and the dental extension, each column naming its Open Dental source, and what the CDM can't hold (not built) |
| [flow 01: run order](flows/01_run_order.png) | Scripts 10–24 and what feeds what |
| [flow 02: review and acceptance](flows/02_review_and_acceptance.png) | Reviewers → human bar vs each method → verdict |
| [flow 03: judge and cost](flows/03_judge_and_cost.png) | Judge bake-off, calibration, corrected accuracy, cost frontier |
