"""Architecture, ERD and process diagrams as draw.io files (same tooling as milliman-panel-notes).

Run:    python3 build_drawio.py          -> ../<name>.drawio
Render: see render.md (draw.io's own export engine, headless) -> ../<name>.png
Synthetic data only; personal learning project.
"""
from _helpers import DB, DBX, STORAGE, SECURITY, MGMT, box, dbx_icon, edge, entity, group, icon, lane, note, rel, reset, save, title

GREEN, GREEN_F = "#15803D", "#DCFCE7"
ORANGE, ORANGE_F = "#C2410C", "#FFEDD5"
BLUE, BLUE_F = "#1E3A5F", "#DBEAFE"
PURPLE, PURPLE_F = "#7C3AED", "#F3E8FF"
GREY, GREY_F = "#7D8998", "#F5F5F5"

# ====================================================================== d0: medallion architecture
reset()
title("Architecture: dental sources → bronze (PHI zone) → silver (de-identified) → gold (OMOP + dental) on Databricks")
for label, x, w in [("Source", 40, 230), ("Ingest", 290, 280), ("Bronze · Silver · Gold", 590, 560),
                    ("Query and process", 1170, 300), ("Serve", 1490, 170), ("Consumer", 1680, 150)]:
    lane(label, x, 70, w)
# sources
icon("s_ehr", "Dental EHR (future)\nchart notes · exam forms\nprobing chart", "traditional_server", "#232F3E", 120, 140, 48)
icon("s_pm", "Practice management / claims\nCDT procedure codes\nICD-10 diagnosis codes", "database", DB, 120, 300, 48)
icon("s_rad", "Radiograph AI (exploratory)\nbone level per tooth", "client", "#232F3E", 120, 460, 48)
box("s_syn", "Today: synthetic generator\n10_build_study (seeded)\nfake PHI on purpose", 50, 590, 210, 60, color=GREY, fill=GREY_F)
# ingest
dbx_icon("al", "Auto Loader\nfiles → volume (future)", "auto-loader", 330, 140, 48)
dbx_icon("lc", "Lakeflow Connect / JDBC\nEHR database (future)", "lakeflow-connect", 330, 300, 48)
box("in_api", "Job task: vendor API pull\n(future)", 310, 465, 220, 45, color=GREY, fill=GREY_F)
box("in_syn", "Job task: write synthetic\nsources to bronze", 310, 600, 220, 45, color=GREY, fill=GREY_F)
# lakehouse
group("g_lake", "Databricks lakehouse · one catalog per environment (dev · UAT · prod)", "dbxlake", 580, 110, 900, 600)
dbx_icon("dbxlogo", "", "databricks", 1430, 116, 32)
dbx_icon("uc", "Unity Catalog", "unity-catalog", 610, 150, 44)
box("gov", "Governance: bronze is the PHI zone (restricted grants); silver and gold de-identified only · lineage · tags · masks · audit",
    680, 150, 770, 44, color=SECURITY, fill="#FBE9EB")
dbx_icon("jobs", "Lakeflow Jobs", "lakeflow-jobs", 610, 225, 44)
box("cicd", "Asset Bundle: dev · UAT · prod targets · GitHub Actions CI/CD · jobs run as a service principal in UAT/prod",
    680, 225, 770, 44, color=GREY, fill=GREY_F)
box("bronze", "BRONZE · PHI zone\nraw notes (with PHI)\nforms · CDT · ICD-10\ncharts · radiograph JSON",
    600, 320, 165, 100, color="#A0522D", fill="#F6E7DA")
box("silver", "SILVER · de-identified\nnotes (passed leak gate)\none status per source\nsites: PD · CAL · BOP",
    810, 320, 165, 100, color="#6B7280", fill="#EEF0F2")
box("gold", "GOLD · OMOP + dental\nNOTE · NOTE_NLP\nMEASUREMENT (+ site)\nphenotype · results",
    1020, 320, 165, 100, color="#B8860B", fill="#FFF6D6")
note("bronze → silver: de-identify, leak gate · silver → gold: source readers, derived site measures, OMOP load, "
     "phenotype, reliability, prevalence", 600, 428, 420, 50)
dbx_icon("sdp", "Pipelines: de-id, readers,\nderived measures, DQ checks", "spark-declarative-pipelines", 640, 495, 48)
dbx_icon("dl", "Delta Lake\nbronze → silver → gold", "delta-lake", 860, 495, 48)
box("lb", "Lakebase (Postgres): OMOP + perio_chart (dev/test) · Label Studio DB · review queue · run ledger",
    600, 600, 575, 44, color=SECURITY, fill="#FBE9EB")
dbx_icon("wh", "SQL warehouse\nderived site measures\nai_query judge", "sql-warehouse", 1220, 320, 48)
dbx_icon("ms", "Model Serving\nLLM judge (MLflow make_judge)\nMedGemma", "model-serving", 1220, 450, 48)
dbx_icon("ml", "MLflow + UC models\nchallenger → champion\non the acceptance test", "notebooks", 1380, 450, 48)
dbx_icon("mon", "Data quality · plausibility\nalerts (future)", "lakeflow", 1380, 320, 48)
# serve
dbx_icon("bi", "AI/BI dashboards\nacceptance test · prevalence\nby clinic · data quality", "ai-bi-dashboards", 1550, 140, 48)
box("ls", "Label Studio\nde-identified tasks", 1505, 480, 150, 50, color=ORANGE, fill=ORANGE_F)
icon("atlas", "OHDSI tools\nAtlas · R (Postgres CDM)", "client", "#232F3E", 1556, 330, 48)
# consumers
icon("c1", "Study lead,\ndata science (R)", "users", "#232F3E", 1730, 140, 48)
icon("c2", "Periodontist\nreviewers", "users", "#232F3E", 1730, 481, 48)
icon("c3", "Researchers\n(cohorts)", "users", "#232F3E", 1730, 330, 48)
# edges
edge("s_ehr", "al", ""); edge("s_pm", "lc", ""); edge("s_rad", "in_api", "")
edge("s_syn", "in_syn", "")
edge("al", "bronze", "", exit=(1, 0.5), entry=(0, 0.2), via=[(570, 164), (570, 342)])
edge("lc", "bronze", "", exit=(1, 0.5), entry=(0, 0.45), via=[(560, 324), (560, 369)])
edge("in_api", "bronze", "", exit=(1, 0.5), entry=(0, 0.7), via=[(560, 487), (560, 397)])
edge("in_syn", "bronze", "", exit=(1, 0.5), entry=(0, 0.95), via=[(570, 622), (570, 424)])
edge("bronze", "silver", "")
edge("silver", "gold", "")
edge("gold", "wh", "")
edge("gold", "ms", "", exit=(1, 0.8), entry=(0, 0.5), via=[(1195, 408), (1195, 474)])
edge("ms", "ml", "")
edge("gold", "lb", "load", dashed=True, exit=(0.5, 1), entry=(0.85, 0))
edge("wh", "bi", "", exit=(1, 0.3), entry=(0, 0.5), via=[(1470, 334), (1470, 164)])
edge("lb", "ls", "tasks · labels", dashed=True, exit=(1, 0.5), entry=(0.5, 1), via=[(1580, 622)])
edge("lb", "atlas", "", exit=(1, 0.2), entry=(0, 0.5), via=[(1495, 609), (1495, 354)])
edge("bi", "c1", ""); edge("ls", "c2", "", exit=(1, 0.5), entry=(0, 0.5)); edge("atlas", "c3", "")
note("Today everything is synthetic: the generator writes fake-PHI notes to bronze so the de-identification and leak gate are exercised end to end. "
     "Only de-identified data leaves bronze (Label Studio, models, LLM endpoints). Same layout in every environment; code deployed, not data or models.",
     40, 730, 1790, 45)
save("d0_medallion_architecture", page_w=1860, page_h=790)

# ====================================================================== d1: study process
reset()
title("Study process: notes, exam forms, procedure codes and diagnoses, probing chart → phenotype and AI, validated against reviewers")
srcs = [("s1", "Chart notes"), ("s2", "Exam forms"), ("s3", "Procedure codes\ncompleted"), ("s4", "Procedure codes\nplanned"),
        ("s5", "Procedure diagnosis\ncodes, completed"), ("s6", "Procedure diagnosis\ncodes, planned"), ("s7", "Probing chart\nCAL · RBL · teeth lost")]
lane("Evidence types (one visit)", 40, 60, 1520)
for i, (cid, lab) in enumerate(srcs):
    box(cid, lab, 40 + i * 220, 110, 200, 60, color=BLUE, fill=BLUE_F)
box("rad", "Radiograph AI (exploratory) · bone level per tooth", 1210, 215, 350, 34, color=GREY, fill=GREY_F)
lane("Qualitative", 40, 270, 740)
box("cmp", "Compare each evidence type with every other\nagreement, kappa, coverage", 40, 320, 340, 60, color=GREEN, fill=GREEN_F)
box("qr", "Qualitative review\ntwo dental reviewers, disagreeing charts", 420, 320, 360, 60, color=GREEN, fill=GREEN_F)
lane("Quantitative", 820, 270, 740)
box("alg", "Rule-based phenotype\nstudy-design order: exam form > dx code > notes > chart\n(all 24 orders scored)", 820, 320, 360, 70, color=ORANGE, fill=ORANGE_F)
box("rev", "Many reviewers stage the same charts\nLabel Studio, independently", 1210, 320, 350, 70, color=ORANGE, fill=ORANGE_F)
box("ai", "AI models read the note only\nrules · TF-IDF · 12 BERT models · MedGemma", 40, 470, 520, 60, color=PURPLE, fill=PURPLE_F)
box("acc", "Acceptance test: agree with reviewers at least as much as they agree with each other\nmean kappa vs each reviewer − mean reviewer-pair kappa, bootstrap CI, margin set in advance\nsix and five categories · unsafe errors · by difficulty", 640, 460, 920, 80, color=DBX, fill="#FFF3F0")
box("val", "Over time and at scale\nplausibility · data quality · clinic prevalence · progression\nLLM judge + cost at 1M notes", 640, 590, 920, 65, color=GREY, fill=GREY_F)
for i, (cid, _) in enumerate(srcs):
    edge(cid, "cmp", "", exit=(0.5, 1), entry=(0.5, 0), via=[(140 + i * 220, 196), (210, 196)])
edge("cmp", "qr", "")
edge("qr", "alg", "rules")
edge("alg", "acc", "")
edge("rev", "acc", "")
edge("s1", "ai", "notes only", dashed=True, exit=(0, 0.5), entry=(0, 0.5), via=[(25, 140), (25, 500)])
edge("ai", "acc", "")
edge("acc", "val", "")
edge("rad", "alg", "lower bound (v0 only)", dashed=True, exit=(0, 0.5), entry=(0.5, 0), via=[(1000, 232)])
note("Synthetic patients and simulated reviewers until real data is approved. Code walkthrough: docs/code_walkthrough.md.", 40, 680, 1500, 30)
save("d1_study_process", page_w=1600, page_h=730)

# ====================================================================== d2: platform architecture
reset()
title("Platform: one bundle, three environments (dev · UAT · prod) on Databricks")
group("g_gh", "GitHub · healthtransformationlab/health-transformation-lab-nlp", "ext", 40, 70, 380, 330)
group("g_ls", "Label Studio (separate app)", "ext", 40, 430, 380, 230)
box("code", "Python + R code, SQL, notebooks\nspecs/, tests, parity", 70, 120, 320, 55, color=GREY, fill=GREY_F)
box("ci", "ci.yml: pytest · R parity · Postgres tests\n· bundle validate", 70, 200, 320, 55, color=GREY, fill=GREY_F)
box("cd", "deploy.yml: uat on push to main\nprod on demand, approval required\nas a service principal", 70, 280, 320, 70, color=GREY, fill=GREY_F)
group("g_dbx", "Databricks workspace (per target: catalog.schema, Lakebase instance, experiment, model)", "dbx", 470, 70, 1090, 620)
dbx_icon("i_jobs", "Lakeflow Jobs", "lakeflow-jobs", 500, 120)
box("jobs", "study_benchmark · load_lakebase · llm_judge\nmedgemma_reader (GPU, uat/prod)\nnotebooks 00–04", 580, 115, 330, 70)
dbx_icon("i_uc", "Unity Catalog", "unity-catalog", 500, 230)
box("delta", "Delta tables · catalog.schema per target\nOMOP CDM + dental extension, sources,\npredictions, reliability, judge, cost", 580, 225, 330, 75, color=STORAGE, fill="#F2F6E8")
dbx_icon("i_lb", "Lakebase", "databricks", 500, 340)
box("lake", "Lakebase (Postgres)\nOMOP CDM + perio_chart view (dev/test)\nreview queue · live labels · run ledger", 580, 335, 330, 75, color=SECURITY, fill="#FBE9EB")
dbx_icon("i_ml", "MLflow", "notebooks", 960, 120)
box("mlf", "MLflow experiment per target\nruns tagged step · git commit · dataset · simulated", 1040, 115, 490, 60, color=MGMT, fill="#FDE7F1")
box("reg", "UC model catalog.schema.perio_note_classifier\nchallenger → champion only if acceptance test non-inferior\nand at least as good as current champion", 1040, 195, 490, 75, color=MGMT, fill="#FDE7F1")
dbx_icon("i_ms", "Model Serving", "model-serving", 960, 300)
box("srv", "Serving endpoints: LLM judge (MLflow make_judge / ai_query),\nMedGemma (paid workspaces); Free Edition: notebook GPU", 1040, 295, 490, 60)
dbx_icon("i_sql", "SQL warehouse", "sql-warehouse", 960, 390)
box("sql", "ai_query judge at corpus scale · derived site measures", 1040, 390, 490, 45)
box("ls", "One project per reviewer\nde-identified tasks only\nits database can be Lakebase", 70, 475, 320, 70, color=ORANGE, fill=ORANGE_F)
box("rev", "Reviewers stage charts independently", 70, 585, 320, 45, color=ORANGE, fill=ORANGE_F)
box("dq", "Data quality · plausibility · prevalence per clinic\n(future: inference tables + data profiling, alerts)", 1040, 470, 490, 60, color=GREY, fill=GREY_F)
note("dev = your sandbox (Free Edition, resources prefixed [dev yourname]); uat = shared test; prod = approved release. Synthetic data in every target until approval.", 470, 640, 1090, 40)
edge("code", "ci", "")
edge("ci", "cd", "")
edge("cd", "jobs", "bundle deploy", exit=(1, 0.5), entry=(0, 0.5), via=[(440, 315), (440, 150)])
edge("jobs", "delta", "")
edge("jobs", "lake", "", dashed=True, exit=(0, 0.85), entry=(0, 0.5), via=[(568, 175), (568, 372)])
edge("jobs", "mlf", "")
edge("mlf", "reg", "register")
edge("reg", "srv", "@champion", dashed=True)
edge("srv", "sql", "", dashed=True)
edge("lake", "ls", "tasks out · labels in", exit=(0.3, 1), entry=(1, 0.5), via=[(679, 510)])
edge("rev", "ls", "labels")
save("d2_platform_architecture", page_w=1600, page_h=700)

# d3, the OMOP dental ERD, is in the data-dictionary format: omop_dental_erd.py (#607)

# ====================================================================== d4: site storage designs
reset()
title("Three ways to store site-level periodontal data in OMOP (same mouths, same results)")
for i, (name, color, fill, rows, stats) in enumerate([
        ("A. Post-coordinated (SITE / SITE_EVENT)", DBX, "#FFF3F0",
         ["MEASUREMENT: concept SITE_PD, value 5", "SITE_EVENT: measurement_id → site_id", "SITE 3-MB → parent SITE 3",
          "query: 5 joins, 1 decode"], "529 MB · 6.8 s · base OMOP unchanged · link table as big as MEASUREMENT"),
        ("B. Pre-coordinated concepts", ORANGE, ORANGE_F,
         ["MEASUREMENT: concept 'PD|3|MB', value 5", "CONCEPT: 672 local concepts", "tooth, site decoded from concept_code",
          "query: 2 joins, 11 decodes"], "276 MB · 4.2 s · base OMOP unchanged · concepts don't exist as standard"),
        ("C. Site columns", GREEN, GREEN_F,
         ["MEASUREMENT: concept SITE_PD, value 5", "+ tooth_number 3, tooth_site 'MB'", "nothing to decode",
          "query: 0 joins"], "309 MB · 2.2 s · simplest, fastest · changes a CDM table")]):
    x = 40 + i * 510
    group(f"g{i}", name, "plain", x, 70, 480, 340)
    for j, r in enumerate(rows):
        box(f"r{i}{j}", r, x + 20, 115 + j * 62, 440, 48, color=color, fill=fill)
    note(stats, x + 20, 365, 440, 40)
box("tail", "Shared derived-measure SQL (derived_tail.sql): max PD, max interproximal CAL, % bleeding, teeth lost,\n"
            "counts of different teeth with CAL ≥ 3/4/6 and PD ≥ 4/5 → 2017 AAP/EFP stage and 2012 CDC/AAP category", 40, 450, 1500, 60, color=BLUE, fill=BLUE_F)
for i in range(3):
    edge(f"g{i}", "tail", "", exit=(0.5, 1), entry=(0.16 + 0.34 * i, 0))
box("wb", "Write derived measures back as MEASUREMENT rows (local concepts) → Atlas cohorts can threshold them", 40, 550, 1500, 45, color=GREY, fill=GREY_F)
edge("tail", "wb", "")
note("Postgres 16 (Lakebase-compatible), 3,437 synthetic exams, 2.16M measurement rows, all three equal Python exactly. scripts/23_site_designs.py", 40, 620, 1500, 30)
save("d4_site_storage_designs", page_w=1600, page_h=670)

# ====================================================================== d5: MLOps lifecycle
reset()
title("MLOps: deploy code, train per environment, promote on the acceptance test")
steps = [("t1", "Train / fit rung\n11_ai_predict.py", BLUE, BLUE_F), ("t2", "Log run + pyfunc\nMLflow (tags: commit,\ndataset, simulated)", MGMT, "#FDE7F1"),
         ("t3", "Register version\nUC model · alias\nchallenger", MGMT, "#FDE7F1"), ("t4", "Acceptance test\n13_reliability.py\nvs reviewers", DBX, "#FFF3F0"),
         ("t5", "Promote?\n24_promote_model.py\nnon-inferior and ≥ champion", ORANGE, ORANGE_F), ("t6", "Alias champion\nbatch scoring /\nserving loads @champion", GREEN, GREEN_F)]
for i, (cid, lab, c, f) in enumerate(steps):
    box(cid, lab, 40 + i * 255, 110, 225, 80, color=c, fill=f)
    if i:
        edge(steps[i - 1][0], cid, "")
box("stay", "stays challenger\nverdict + diff tagged on the version", 1060, 250, 225, 60, color=GREY, fill=GREY_F)
edge("t5", "stay", "no", exit=(0.5, 1), entry=(0.5, 0))
box("judge", "LLM judge (MLflow make_judge, same AAP criteria, quote gate)\nmlflow.genai.evaluate: one trace per chart · aligned to reviewer labels", 40, 260, 700, 60, color=PURPLE, fill=PURPLE_F)
box("mon", "Monitor: data quality, plausibility over time, prevalence per clinic\nnext: inference tables, data profiling, alerts → retrain", 40, 360, 700, 60, color=GREY, fill=GREY_F)
edge("t6", "mon", "", exit=(0.5, 1), entry=(1, 0.5), via=[(1462, 390)])
edge("mon", "t1", "", dashed=True, exit=(0, 0.5), entry=(0, 0.5), via=[(20, 390), (20, 150)])
edge("judge", "t4", "accuracy at corpus scale", dashed=True, exit=(1, 0.5), entry=(0.5, 1), via=[(892, 290)])
note("Dashed loop on the left: retraining (future). dev · uat · prod each have their own experiment, UC model and data (databricks/resources/mlops.yml). docs/mlops.md", 40, 450, 1500, 30)
save("d5_mlops_lifecycle", page_w=1600, page_h=500)
