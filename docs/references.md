# References

Everything this repo relies on, and what it's used for.

## Dental NLP and phenotyping

1. **Chuang Y-S, et al.**
   *Extracting periodontitis diagnosis in clinical notes with RoBERTa and regular expression.*
   [arXiv 2311.10809](https://arxiv.org/abs/2311.10809). UTHealth Houston, 8,125 notes.
   → Published diagnosis-line forms and the 98.7% diagnosis-section rate
   ([note_realism.md](note_realism.md)); regex baseline design.
2. **Chuang Y-S, Lee C-T, Tokede O, Lin G-H, Brandon R, Tran TD, Jiang X, Walji MF.**
   *Artificial Intelligence in Extracting Diagnostic Data from Dental Records.*
   [arXiv 2407.21050v2](https://arxiv.org/abs/2407.21050v2). UTHealth + UCSF. (v3 is retitled *Cross-Institutional
   Dental EHR Entity Extraction via Generative AI and Synthetic Notes* and uses 360 notes per site; the 240 below is
   v2's.)
   → Label schema (status, stage, grade, extent); 240 dentist-labeled notes per
   site as the test-set size; synthetic-train / real-test design; the extent trap.
3. **Patel JS.** *Utilizing Electronic Dental Record Data to Track Periodontal
   Disease Change.* PhD dissertation, IUPUI, 2020.
   [IU ScholarWorks](https://scholarworks.indianapolis.iu.edu/items/0768bd4f-e24a-465a-95fe-b8cabca06c68/full).
   → 47% agreement between charting-derived and clinician-recorded diagnoses;
   charting present for ~80% of patients (both modeled in the generator).
4. **Patel JS, Brandon R, Tellez M, Albandar JM, Rao R, Krois J, Wu H.**
   *Developing Automated Computer Algorithms to Phenotype Periodontal Disease
   Diagnoses in Electronic Dental Records.* Methods of Information in Medicine, 2022.
   [PMC9788909](https://pmc.ncbi.nlm.nih.gov/articles/PMC9788909), doi:10.1055/s-0042-1757880 (open access).
   → Rule-based case finding from EDR data at one dental school (27,138 patients with at least one
   comprehensive oral exam, 2017–2021). Three sources fill gaps in a fixed order: (M1) the clinician's
   diagnosis in the structured diagnosis section, then (M2) diagnoses found in clinical notes by the PerioDx
   Extractor (NLP), then (M3) diagnoses computed from periodontal charting by the PerioDx Diagnoser (most
   recent visit, charts whose exam code is "complete" only). A later source is used only when the earlier ones
   are missing; there is no rule for when they disagree. There is no exam-form or PSR step: the periodontal
   evaluation form is read only as note text (M2) and for bone loss in the charting rules (M3). The order
   itself was not validated against expert review; only the Diagnoser (two experts, 200 charts) and the
   Extractor (400 notes) were.
   **What uses it here.** `algorithm_patel2022` (spec 024, not built yet) will run the paper's order. `algorithm_design`
   (`phenotype.py`, exam form → diagnosis codes → note → gum measurements) is this repo's own: putting the
   exam form first, and diagnosis codes attached to done or planned procedures standing in for the
   diagnosis section, are not from the paper (action item A2; checked against the full text, #389, #204).
   `algorithm_v0` (gum measurements first) is this repo's own too.
   **The paper's own inconsistencies** (recorded, not resolved by guessing): the share of the final cohort
   decided by charting is given as both 46% and 51%; spec 024 also notes that Fig. 1 attaches the 36%
   (diagnosis codes) and 18% (notes) figures to the other section. The Extractor is reported at 91% precision
   and 87% recall, which makes F1 0.89, not the 95% stated. Table 1 gives recall 1.0 (0 false negatives),
   224 true positives against 112 actual positives, and a prevalence of 0.59 where 224/400 = 0.56. The HbA1c
   annotation bands ("normal < 5", "pre-diabetes 5.7–6.4") leave 5.0–5.7 unassigned.
5. **Patel JS, Rao R, Brandon R, Iyer V, Albandar JM, Tellez M, Krois J, Wu H.** *Develop a Natural Language
   Processing Pipeline to Automate Extraction of Periodontal Disease Information from Electronic Dental Clinical
   Notes.* ICMHI 2022 (ACM), pp. 61–68. doi:10.1145/3545729.3545744.

## Evaluation methods

6. **Zhao J, Liang J, Cai Z, et al.** *GlobalDentBench: A Multinational Benchmark for
   Evaluating LLM Clinical Reasoning in Dentistry with Expert Calibration.*
   [arXiv 2605.24636](https://arxiv.org/abs/2605.24636), May 2026.
   Code: github.com/FreedomIntelligence/GlobalDentBench.
   → Safety severity S0/S1/S2, reasoning levels, judge selection, key-point
   scoring ([dentbench_methods.md](dentbench_methods.md)).
54. **Hager P, Jungmann F, Holland R, et al.** *Evaluation and mitigation of the limitations of large language
    models in clinical decision-making.* Nat Med 2024;30(9):2613-2622.
    [doi:10.1038/s41591-024-03097-1](https://doi.org/10.1038/s41591-024-03097-1).
    → 2,400 real hospital cases (MIMIC-IV): models did significantly worse than physicians, followed neither
    diagnostic nor treatment guidelines, and could not interpret lab results. Cited in the README and pitch.
55. **Bean AM, Payne RE, Parsons G, et al.** *Reliability of LLMs as medical assistants for the general public: a
    randomized preregistered study.* Nat Med 2026;32(2):609-615.
    [doi:10.1038/s41591-025-04074-y](https://doi.org/10.1038/s41591-025-04074-y).
    → 1,298 members of the public: the models alone named the condition in 94.9% of cases, people using them in
    under 34.5%, no better than a control group; knowledge benchmarks did not predict this.
56. **Al-Ashwal FY, Zawiah M, Gharaibeh L, Abu-Farha R, Bitar AN.** *Evaluating the sensitivity, specificity, and
    accuracy of ChatGPT-3.5, ChatGPT-4, Bing AI, and Bard against conventional drug-drug interactions clinical
    tools.* Drug Healthc Patient Saf 2023;15:137-147.
    [doi:10.2147/DHPS.S425858](https://doi.org/10.2147/DHPS.S425858).
    → 255 drug pairs against Micromedex: accuracy from 0.469 (ChatGPT-3.5) to 0.788 (Bing AI). 2023-era chatbots.

## Data models and classification

7. **Tonetti MS, Greenwell H, Kornman KS.** *Staging and grading of periodontitis:
   Framework and proposal of a new classification and case definition.*
   J Periodontol 2018;89(Suppl 1):S159–S172. → Stage, grade, extent rules (`labels.py`).
8. **Armitage GC.** *Development of a classification system for periodontal
   diseases and conditions.* Ann Periodontol 1999;4(1):1–6. → Pre-2017 terms
   (slight / moderate / severe chronic periodontitis).
9. **Koski R, Chandrasekharan G, Duncan WD (OHDSI Dentistry Workgroup).** *Mapping Dental Use Cases to the
   OMOP-CDM: Vocabulary and Common Data Model Evaluation.* OHDSI Symposium 2023.
   [PDF](https://ohdsi.org/wp-content/uploads/2023/10/39-Koski-OHDSIreport-Robert-Koski.pdf).
   → `SITE` / `SITE_EVENT` tooth-level extension.
10. **OHDSI.** OMOP Common Data Model v5.4. [ohdsi.github.io/CommonDataModel](https://ohdsi.github.io/CommonDataModel/).

## Radiographs (exploratory)

19. **Overjet.** *How to detect periodontal disease with AI* (bone level measurement, FDA 510(k) K210187).
    [overjet.com](https://www.overjet.com/blog/how-to-detect-periodontal-disease-with-ai)
21. **Yavuz MB, et al.** AI detection of periodontal status in bitewing radiographs. EuroPerio10, 2022.
    [Dental Tribune summary](https://www.dental-tribune.com/news/artificial-intelligence-shows-promise-for-detecting-periodontal-status-in-bitewing-radiographs/)

## Case validation (the acceptance test)

27. **OHDSI.** *OHDSI2023 Plenary: Improving the reliability and scale of case validation*
    (Ryan, Ostropolets, Schuemie). [YouTube](https://www.youtube.com/watch?v=scUssf863TI), from about 49 min.
28. **Schuemie MJ, Ostropolets A, Zhuk A, Korsik U, Seo SI, Suchard MA, Hripcsak G, Ryan PB.**
    *Standardized patient profile review using large language models for case adjudication in
    observational research.* npj Digital Medicine 2025;8.
    [doi:10.1038/s41746-025-01433-4](https://doi.org/10.1038/s41746-025-01433-4)

## Knowledge graphs, retrieval and OMOP vocabulary

29. **Lee J, Liu C, Kim JH, et al. (Columbia).** *Comparative effectiveness of medical concept embedding for
    feature engineering in phenotyping.* JAMIA Open 2021;4(2):ooab028.
    [doi:10.1093/jamiaopen/ooab028](https://doi.org/10.1093/jamiaopen/ooab028); preprint
    [medRxiv 2020.07.14.20151274](https://www.medrxiv.org/content/10.1101/2020.07.14.20151274v2). Compares
    knowledge-graph and EHR-data concept embeddings.
30. **Ahmed A, Soby S, Aasman B, Mirhaji P.** *Automated OMOP concept mapping using multi-agent LLMs and
    graph-enhanced semantic retrieval.* OHDSI Symposium 2025.
    [PDF](https://www.ohdsi.org/wp-content/uploads/2025/10/508-Ahmed-Automated-OMOP-Concept-Mapping-Using-Multi-Agent-Large-Language-Models-and-Graph-Enhanced-Semantic-Retrieval-Report-Adil-Ahmed.pdf)
31. **Thio S, Lewis M, Denaxas S, Dobson RJB.** *Unlocking electronic health records: a hybrid graph RAG
    approach to safe clinical AI for patient QA.* arXiv 2602.00009. [link](https://www.arxiv.org/abs/2602.00009)
32. **Zhao X, Liu S, Yang S-Y, Miao C.** *MedRAG.* arXiv 2502.04413. [link](https://arxiv.org/abs/2502.04413v2)

## Platform

33. **Databricks.** *Lakebase release notes.* [docs](https://docs.databricks.com/aws/en/release-notes/lakebase/)
34. **Databricks.** *Free Edition limitations.* [docs](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)

## Epidemiology and data quality

35. **Eke PI, Thornton-Evans GO, Wei L, Borgnakke WS, Dye BA, Genco RJ.** *Periodontitis in US adults:
    National Health and Nutrition Examination Survey 2009-2014.* J Am Dent Assoc 2018;149(7):576-588.
    [doi:10.1016/j.adaj.2018.04.023](https://doi.org/10.1016/j.adaj.2018.04.023); figures via
    [NIDCR](https://nidcr.nih.gov/research/data-statistics/periodontal-disease/adults)
36. **Kahn MG, Callahan TJ, Barnard J, et al.** *A harmonized data quality assessment terminology and framework
    for the secondary use of electronic health record data.* eGEMs 2016;4(1):1244.
    [doi:10.13063/2327-9214.1244](https://doi.org/10.13063/2327-9214.1244)
57. **Kookal KK, Walji MF, Brandon R, Kivanc F, Mertz E, Kottek A, Mullins J, Liang S, Jenson LE, White JM.**
    *Systematically assessing the quality of dental electronic health record data for an investigation into oral
    health care disparities.* J Public Health Dent 2024;84(3):242–250.
    [doi:10.1111/jphd.12618](https://doi.org/10.1111/jphd.12618), PMID 38659337, PMC11499288.
    Data-quality checks on a dental EHR extract (children 0–18, a 30-office dental group in Oregon, records
    2014–2022: 91,487 people, 11 tables, 75 columns). The checks follow the NIH Pragmatic Trials Collaboratory
    framework (Zozus et al. 2014), across three domains and 12 checks (Table 1):
    - completeness: agreed columns present, each checked against the data dictionary, data types, one value per
      field, the share of null/unknown/missing values (NUMs) per column, duplicate rows, cohort inclusion,
      duplicate key combinations, and rows with any missing value;
    - accuracy: values outside known ranges, and values not in standard code sets (CDT, ZIP);
    - consistency: NUMs per office, against the mean of all offices.
    Its published results: 97.2% completeness, 100% extract accuracy, and 29 of 30 offices within 2 SD of the
    mean NUM share. Its Table 2 lists anomalies and how each was resolved (corrected, or accepted as plausible),
    e.g. invalid diagnostic codes corrected and impossible plaque scores corrected. → spec 029: the checks run
    between the bronze extract and the silver tooth table (FR-009). Checked on PubMed and the PMC full text. The
    abstract says benefits "between 2014–2108", a typo for 2014–2018 as the Methods give it. Published figures
    only: the paper's data is not public and never comes in.
62. **de Vet HCW, Terwee CB, Knol DL, Bouter LM.** *When to use agreement versus reliability measures.*
    J Clin Epidemiol 2006;59(10):1033–1039. [doi:10.1016/j.jclinepi.2005.10.015](https://doi.org/10.1016/j.jclinepi.2005.10.015).
    Agreement is how close repeated measurements are; reliability is whether, despite that error, people (or
    teeth, or sites) can still be told apart. → the grader's reliability domain (`dashboards.dq_grader`,
    `docs/graders.md`) and `reliability_cal.py`. The grader once credited this domain to Liaw et al. 2013
    (Int J Med Inform 82(1):10–24), a review whose most common data-quality dimensions are completeness,
    accuracy, correctness, consistency and timeliness, not reliability (#405).

58. **Open Dental Software.** *Open Dental* source code, `OpenDentBusiness/TableTypes` (one class per database
    table). [github.com/OpenDental/OpenDental](https://github.com/OpenDental/OpenDental), branch `24_3`, commit
    `d804c19` (2025-04-01); GPL. → The table and column names, types and meanings of spec 029's synthetic extract
    (`specs/029-tooth-loss/research.md`), read 2026-10-30. Names and meanings only; no code is copied. The same
    schema is published as documentation on opendental.com.

## Classification rules

26. **American Academy of Periodontology.** *Staging and Grading Periodontitis* (worksheet).
    [perio.org PDF](https://www.perio.org/wp-content/uploads/2019/08/Staging-and-Grading-Periodontitis.pdf).
    The rule source for this repo; see [staging_grading.md](staging_grading.md).

## Medical LLMs (exploratory)

22. **Sellergren A, et al.** *MedGemma Technical Report.* [arXiv 2507.05201](https://arxiv.org/abs/2507.05201), 2025.
23. **Google Health AI Developer Foundations.** *MedGemma model card.*
    [developers.google.com](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card-v1)
24. **BioPharmaTrend.** *Google updates open medical AI suite with new imaging and speech models* (MedGemma 1.5, MedASR), January 2026.
    [biopharmatrend.com](https://www.biopharmatrend.com/news/google-updates-open-medical-ai-suite-with-new-imaging-and-speech-models-launches-100k-developer-hackathon-1464/)

25. **Koski R, Boyce D, Martin B, Cha J, Sanchez M.** *Identifying Oral Health Concepts from Previously
    "OMOP-ified" Data.* OHDSI 2025 Global Collaborator Showcase, poster 111.
    [PDF](https://www.ohdsi.org/wp-content/uploads/2025/10/111-koski-robert_Identifying_Oral_Health_Concepts-Robert-Koski.pdf)

## Synthetic data

11. **Tamizh Selvam T.** *Synthetic Dental Clinical Notes Dataset for Dental NLP
    Benchmarking.* IEEE DataPort, 2026. DOI 10.21227/tt32-vp70.
    → Candidate external test set ([data_sources.md](data_sources.md)).
12. **Walonoski J, et al.** *Synthea: An approach, method, and software mechanism
    for generating synthetic patients and the synthetic electronic health care
    record.* JAMIA 2018;25(3):230–238.

## Statistics

13. **Rogan WJ, Gladen B.** *Estimating prevalence from the results of a screening
    test.* Am J Epidemiol 1978;107(1):71–76. → Correcting judge-estimated accuracy.
14. **Fleiss JL.** *Measuring nominal scale agreement among many raters.*
    Psychol Bull 1971;76(5):378–382. → Reviewer reliability.
15. **Cohen J.** *Weighted kappa.* Psychol Bull 1968;70(4):213–220. → Ordinal agreement.
51. **Patel JS, et al.** *Developing and testing a prediction model for periodontal disease using machine
    learning and big electronic dental record data.* Front Artif Intell 2022;5:979525.
    doi:10.3389/frai.2022.979525, PMID 36311550, PMC9608121. → Design of the status classifier (`classify_status.py`, spec 013 G10):
    XGBoost, 80/20 split, 5-fold cross-validated hyperparameters, one-vs-all metrics. It also used SHAP to
    explain predictions (Methods, "Predictor contribution interpretation"; Figure 4), as this repo does.
52. **Lundberg SM, Erion G, Chen H, et al.** *From local explanations to global understanding with
    explainable AI for trees.* Nature Machine Intelligence 2020;2:56–67. → TreeSHAP, the exact SHAP values
    XGBoost computes (`pred_contribs`) for the status classifier.
53. **Patel JS, Tellez M, Katiyar R, Al-Hebshi NN, Santana R, Yucel RM, Ismail A.** *Periodontitis prediction
    model using linked electronic health and dental records.* JDR Clin Trans Res 2026;11(4):555–570 (epub
    2026-02-11). doi:10.1177/23800844251408849, PMID 41673528, PMC13292087. Follows item 51: adds medical-record
    (EHR) features to dental-record (EDR) features for 20,946 adults; XGBoost best of four models; 4 classes
    (healthy, stage I, stage II, stages III+IV); 70/30 stratified train/test split; sensitivity, specificity,
    AUC and Brier score per class; PROBAST and TRIPOD-AI checklists. Experiment 1 (chi-square-selected
    features), averages over the 4 classes in Table 2, sensitivity/specificity/AUC: 66/86/84 with dental records
    only, 66/86/86 with medical records added; experiment 5 (medical records only) 43/70/57.
    → Spec 013 G10 (what the status classifier could adopt) and spec 023 (synthetic medical-record features).
    Checked on PubMed and the PMC full text: authors, volume, issue, pages and the figures above. The text is
    inconsistent in two places: the abstract says 106 features were kept, the Methods say 109; and the
    abstract's best result, 67/85/84, matches neither experiment 1 row of Table 2 (66/86/84, 66/86/86).
    Published figures only: the paper's data is real patient data and never comes into this repo.

59. **Collins GS, Moons KGM, Dhiman P, et al.** *TRIPOD+AI statement: updated guidance for reporting clinical
    prediction models that use regression or machine learning methods.* BMJ 2024;385:e078378.
    doi:10.1136/bmj-2023-078378. → The reporting checklist the tooth-loss analysis plan follows
    ([analysis_plan.md](../specs/029-tooth-loss/analysis_plan.md)) and [evaluation_checklist.md](evaluation_checklist.md).
60. **Benchimol EI, Smeeth L, Guttmann A, et al.** *The REporting of studies Conducted using Observational
    Routinely-collected health Data (RECORD) statement.* PLoS Med 2015;12(10):e1001885.
    doi:10.1371/journal.pmed.1001885. → Reporting for studies on routinely collected records, alongside TRIPOD+AI.
61. **Riley RD, Ensor J, Snell KIE, et al.** *Calculating the sample size required for developing a clinical
    prediction model.* BMJ 2020;368:m441. doi:10.1136/bmj.m441. → The minimum sample size check in the analysis
    plan (section 6).

## De-identification

37. **U.S. Department of Health and Human Services.** *Guidance regarding methods for de-identification of
    protected health information in accordance with the HIPAA Privacy Rule* (Safe Harbor's 18 identifiers;
    Expert Determination). [hhs.gov](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html)
    → The PHI categories in the challenge set.
38. **Stubbs A, Uzuner Ö.** *Annotating longitudinal clinical narratives for de-identification: the 2014
    i2b2/UTHealth corpus.* J Biomed Inform 2015;58(Suppl):S20–S29.
    [doi:10.1016/j.jbi.2015.07.020](https://doi.org/10.1016/j.jbi.2015.07.020). Challenge page:
    [n2c2](https://n2c2.dbmi.hms.harvard.edu/challenge/2014-deidentification-heart-disease)
    → Annotation categories: NAME (patient, doctor, username), PROFESSION, LOCATION (room, department,
    hospital, organization, street, city, state, country, zip, other), AGE, DATE, CONTACT, ID. The corpus itself
    needs a data use agreement and isn't used here.
39. **Microsoft.** *De-identification service in Azure Health Data Services* (TAG, REDACT, SURROGATE; 27 PHI
    categories). [learn.microsoft.com](https://learn.microsoft.com/en-us/azure/healthcare-apis/deidentification/overview);
    pricing: [azure.microsoft.com](https://azure.microsoft.com/pricing/details/health-data-services/)
40. **Microsoft.** *Azure Language in Foundry Tools* (formerly Azure AI Language): PII detection, PHI domain
    (`domain=phi`). Pricing:
    [azure.microsoft.com](https://azure.microsoft.com/pricing/details/cognitive-services/text-analytics/)
41. **Microsoft Presidio** — open-source PII detection (spaCy NER and pattern recognizers).
    [github.com/microsoft/presidio](https://github.com/microsoft/presidio)

42. **Weatherhead J.** *ASQ-PHI: an adversarial synthetic benchmark for clinical de-identification and search
    utility.* Mendeley Data, 2025, [doi:10.17632/csz5dzp7nx.1](https://data.mendeley.com/datasets/csz5dzp7nx/1)
    (MIT). 1,051 fully synthetic clinical search queries, 2,973 tagged PHI elements, 219 hard negatives.
43. **Posada JD, Love D, Datta S, Desai P.** *SHIELD: a diverse clinical note dataset and distilled small
    language models for enterprise-scale de-identification.* [arXiv:2605.03301](https://arxiv.org/abs/2605.03301);
    access: [github.com/susom/shield_dataset](https://github.com/susom/shield_dataset) (data on Stanford Medicine
    Redivis). 1,381 notes with identifiers replaced, 10,229 adjudicated PHI spans in 9 categories.
44. **presidio-evaluator** (presidio-research, MIT) — fake-PII sentence generator from templates, and
    evaluation of PII detectors. [pypi.org/project/presidio-evaluator](https://pypi.org/project/presidio-evaluator/)
45. **John Snow Labs.** *Clinical de-identification at scale: pipeline design and speed–accuracy trade-offs
    across infrastructures* (benchmarks on Databricks).
    [johnsnowlabs.com](https://www.johnsnowlabs.com/clinical-de-identification-at-scale-pipeline-design-and-speed-accuracy-trade-offs-across-infrastructures/)

46. **Chambon PJ, Wu C, Steinkamp JM, Adleberg J, Cook TS, Langlotz CP.** *Automated deidentification of
    radiology reports combining transformer and "hide in plain sight" rule-based methods.* J Am Med Inform
    Assoc 2023;30(2):318–328, [doi:10.1093/jamia/ocac219](https://doi.org/10.1093/jamia/ocac219). Model:
    [StanfordAIMI/stanford-deidentifier-base](https://huggingface.co/StanfordAIMI/stanford-deidentifier-base) (MIT).
47. **Robust DeID** (OBI) — package [robust-deid](https://pypi.org/project/robust-deid/); model [obi/deid_roberta_i2b2](https://huggingface.co/obi/deid_roberta_i2b2)
    (RoBERTa trained on i2b2 2014; MIT).
48. **Kocaman V, Santas M, Gul Y, Butgul M, Talby D.** *Can zero-shot commercial APIs deliver regulatory-grade
    clinical text de-identification?* [arXiv:2503.20794](https://arxiv.org/abs/2503.20794), 2025. Authors are
    from John Snow Labs, one of the compared vendors.

49. **PhysioNet.** *Deidentified Medical Text* (Neamatullah et al. 2008 gold standard), credentialed access.
    [physionet.org](https://www.physionet.org/content/deidentifiedmedicaltext/)
50. **John Snow Labs.** Free academic licences for Spark NLP for Healthcare (incl. de-identification).
    [johnsnowlabs.com](https://johnsnowlabs.com/john-snow-labs-is-providing-free-academic-licenses-to-researchers-and-educators-in-artificial-intelligence);
    Databricks integration and trial: [docs](https://docs.azure.cn/en-us/databricks/partners/ml/john-snow-labs)

## Tools

16. **Spec Kit** (GitHub) — spec-driven development. [github.com/github/spec-kit](https://github.com/github/spec-kit)
17. **Superpowers** (obra) — Claude Code skills for planning, TDD, debugging, review. github.com/obra/superpowers
18. **Label Studio** (HumanSignal) — annotation tool. [labelstud.io](https://labelstud.io)
