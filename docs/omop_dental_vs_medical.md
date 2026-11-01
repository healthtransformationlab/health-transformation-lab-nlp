# OMOP for dental vs medical data

> Learning notes from public sources. Synthetic data only in this repo.
> See [DISCLAIMER](../DISCLAIMER.md).

OMOP was built around medical claims and EHRs, and that's where most of its
tooling and vocabulary coverage is. Dental data records different things, in
different ways, and puts the most useful facts for periodontal research where
OMOP has no native place for them. As the OHDSI Dentistry Workgroup put it,
"few, if any, dental datasets have been converted to the OMOP-CDM" (Koski et
al., OHDSI 2025).

## What each source usually tracks

"Usually" matters: content varies by payer, state, system and practice.

| | Medical claims | Medical EHR | Dental claims | Dental EHR |
|---|---|---|---|---|
| **Form / standard** | CMS-1500 / X12 837P (professional), UB-04 / 837I (institutional); pharmacy claims separate | Vendor EHR; HL7 v2, C-CDA, FHIR exchange | ADA Dental Claim Form / X12 837D | Practice-management + charting software; little standard exchange |
| **Diagnoses** | ICD-10-CM, **required** | Problem list, encounter diagnoses (ICD-10-CM, SNOMED) | ICD-10-CM fields exist but are **often not required or filled** | Often **missing or free text**; structured diagnostic terms (e.g. SNODENT, Dental Diagnostic System) not widely used |
| **Procedures** | CPT/HCPCS; ICD-10-PCS inpatient | Orders, procedures, results | **CDT** codes | CDT, as **completed** and **planned** (treatment plan) |
| **Where in the body** | Laterality, sometimes | Anatomical site in notes, some coded | **Tooth number, surface, quadrant / arch** | Tooth, surface and **site** (6 sites per tooth for probing) |
| **Measurements** | Few (some via codes) | Vitals, labs (LOINC), many structured | None | **Perio chart**: probing depth, CAL, recession, bleeding on probing, mobility, furcation; caries charting |
| **Medications** | Pharmacy claims (NDC) | Med list, orders (RxNorm) | Rarely | Medical history form; prescriptions written (e.g. antibiotics, analgesics) |
| **Imaging** | Imaging procedure codes | Radiology reports (text), images in PACS | Radiograph procedure codes (CDT D02xx–D03xx) | Radiograph images, usually **not** structured findings; AI tools now add structured bone-level output |
| **Notes** | None | Large volumes of clinical notes | Narrative only for some claims | Templated progress notes; diagnosis often stated only here |
| **Risk factors** | Via diagnosis codes | Smoking status, diabetes, HbA1c | None | Health history questionnaire (smoking, diabetes), often unstructured or yes/no |
| **Linkage** | Shared member ID within a payer | Within a health system | Separate dental payers / benefits | Separate systems from medical; linkage to the medical record is often missing |

## How that lands in OMOP CDM 5.4

| Need | Medical: usual mapping | Dental: what's different | In this repo |
|---|---|---|---|
| Diagnosis | `CONDITION_OCCURRENCE` (ICD-10-CM → SNOMED standard) | Often has to be **inferred** from charting or notes; that's what this project studies | Model output goes to `NOTE_NLP` as a flag, **never** `CONDITION_OCCURRENCE` |
| Procedure | `PROCEDURE_OCCURRENCE` (CPT/HCPCS standard) | CDT/HCPCS D-codes can appear in Athena as **non-standard or deprecated**, so data may sit in `procedure_source_value` / `source_concept_id` (OHDSI forum) | `PROCEDURE_OCCURRENCE` with CDT source values |
| Planned vs done | Orders, rarely in OMOP | Treatment plans are a key signal (planned scaling and root planing implies perio) | Planned and completed kept as separate evidence types |
| Tooth / surface / site | No native table | Proposed `SITE` / `SITE_EVENT` extension (OHDSI Dentistry Workgroup) | `omop/ddl/dental_extension.sql` |
| Perio chart numbers | `MEASUREMENT` with LOINC | Few standard concepts for per-site perio values | `MEASUREMENT` + local concepts (`DENTAL_LOCAL`, `omop/vocab/local_concepts.csv`) |
| Radiograph findings | `MEASUREMENT` / `OBSERVATION`, report text in `NOTE` | Per-tooth bone level needs site linkage | `MEASUREMENT` linked via `SITE_EVENT` (exploratory, spec 003) |
| Notes | `NOTE`, `NOTE_NLP` | Same tables | Same |

## Why this matters for periodontal phenotyping

- In medical data, the diagnosis code is usually the starting point. In dental
  data, the diagnosis is often **absent from claims**, and in the EHR it's often
  **inconsistent with the charting** (one dissertation found charting-derived
  and recorded diagnoses agreed 47% of the time; see [references](references.md)).
- The strongest evidence (probing depths, CAL, bone loss) is **site-level
  numbers**, which need tooth/site modeling that core OMOP doesn't have.
- Procedures are the most consistently coded dental field, so codes are a
  useful but indirect signal: they say what was done or planned, not the stage.
- Medical-dental linkage (e.g. diabetes, smoking) affects **grade**, but the two
  records often live in different systems and payers.

## Sources

- Koski R, et al. *Identifying Oral Health Concepts from Previously "OMOP-ified" Data.*
  OHDSI 2025 Global Collaborator Showcase, poster 111. [PDF](https://www.ohdsi.org/wp-content/uploads/2025/10/111-koski-robert_Identifying_Oral_Health_Concepts-Robert-Koski.pdf)
- Koski R, Chandrasekharan G, Duncan WD (OHDSI Dentistry Workgroup). *Mapping Dental Use Cases to the OMOP-CDM.* OHDSI 2023.
  [PDF](https://ohdsi.org/wp-content/uploads/2023/10/39-Koski-OHDSIreport-Robert-Koski.pdf)
- OHDSI Forums. *Guidance on mapping deprecated CDT/HCPCS dental procedure codes
  to OMOP standard concepts.* [Thread](https://forums.ohdsi.org/t/guidance-on-mapping-deprecated-cdt-hcpcs-dental-procedure-codes-to-omop-standard-concepts/25709)
- CareSource. *ICD-10 and dental claims* (one payer's example: ICD-10 required
  on CMS-1500 professional claims, not on ADA-form dental claims).
  [Document](https://caresource.com/documents/icd-10-and-dental-claims)
- Patel J.S. *Utilizing Electronic Dental Record Data to Track Periodontal
  Disease Change.* PhD dissertation, IUPUI 2020.
  [IU ScholarWorks](https://scholarworks.indianapolis.iu.edu/items/0768bd4f-e24a-465a-95fe-b8cabca06c68/full)
