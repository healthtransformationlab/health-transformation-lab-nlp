"""An OMOP silver alternative for spec 029's data (#379), declared for its ERD: the same Open Dental silver tables
mapped to OMOP CDM 5.4 plus the repo's dental extension (omop/ddl/dental_extension.sql: site, site_event).

Not built: spec 029 keeps silver in Open Dental's shape (FR-008). This shows what a common model would keep and
lose. CDM tables and columns keep their official names (only the ones this data fills); each description says
which Open Dental column fills it (←) or that nothing in Open Dental does. Synthetic data only.
"""
from gold_model import Column as C
from gold_model import Relationship as R
from gold_model import Table

TABLES = {
    "care_site": Table("cdm", "One per office", "(not built)", [
        C("care_site_id", "bigint", "← clinic.clinicnum", "PK"),
        C("care_site_name", "string", "← clinic.description"),
    ]),
    "person": Table("cdm", "One per patient", "(not built)", [
        C("person_id", "bigint", "← patient.patnum", "PK"),
        C("gender_concept_id", "int", "← patient.gender, mapped to a Gender concept", "FK"),
        C("year_of_birth", "int", "← year of patient.birthdate"),
        C("birth_datetime", "timestamp", "← patient.birthdate"),
        C("care_site_id", "bigint", "← patient.clinicnum", "FK"),
        C("person_source_value", "string", "← patient.patnum"),
    ]),
    "visit_occurrence": Table("cdm", "One per patient and visit date (Open Dental has no visit table)", "(not built)", [
        C("visit_occurrence_id", "bigint", "← built from patnum and the procedure or exam date", "PK"),
        C("person_id", "bigint", "← patient.patnum", "FK"),
        C("visit_concept_id", "int", "not from Open Dental: outpatient visit", "FK"),
        C("visit_start_date", "date", "← procedurelog.procdate or perioexam.examdate"),
        C("care_site_id", "bigint", "← procedurelog.clinicnum", "FK"),
    ]),
    "procedure_occurrence": Table("cdm", "One per completed procedure: planned ones have no place here", "(not built)", [
        C("procedure_occurrence_id", "bigint", "← procedurelog.procnum (procstatus 2 only)", "PK"),
        C("person_id", "bigint", "← procedurelog.patnum", "FK"),
        C("procedure_concept_id", "int", "← procedurecode.proccode, as a CDT concept", "FK"),
        C("procedure_date", "date", "← procedurelog.datecomplete"),
        C("procedure_type_concept_id", "int", "not from Open Dental: EHR record"),
        C("visit_occurrence_id", "bigint", "← patnum and procedure date", "FK"),
        C("procedure_source_value", "string", "← procedurecode.proccode"),
    ]),
    "condition_occurrence": Table("cdm", "One per diagnosis on a procedure, and per medical problem", "(not built)", [
        C("condition_occurrence_id", "bigint", "← built from procnum or diseasenum", "PK"),
        C("person_id", "bigint", "← patnum", "FK"),
        C("condition_concept_id", "int", "← definition.itemname via a local map (0 when an item has no standard concept); disease: diseasedef.icd10code", "FK"),
        C("condition_start_date", "date", "← procedurelog.datecomplete, or disease.datestart (may be empty)"),
        C("condition_type_concept_id", "int", "not from Open Dental: EHR record"),
        C("visit_occurrence_id", "bigint", "← patnum and date", "FK"),
        C("condition_source_value", "string", "← definition.itemname (practice list), or diseasedef.icd10code"),
    ]),
    "measurement": Table("cdm", "One per site measure per exam: probing, gingival margin, mobility, furcation, bleeding", "(not built)", [
        C("measurement_id", "bigint", "← built from periomeasurenum and site", "PK"),
        C("person_id", "bigint", "← perioexam.patnum", "FK"),
        C("measurement_concept_id", "int", "← periomeasure.sequencetype, as a local concept (omop/vocab/local_concepts.csv)", "FK"),
        C("measurement_date", "date", "← perioexam.examdate"),
        C("value_as_number", "double", "← mbvalue … dlvalue, decoded (-1 → null, 100+ → negative)"),
        C("unit_concept_id", "int", "not from Open Dental: millimetre"),
        C("visit_occurrence_id", "bigint", "← patnum and exam date", "FK"),
        C("measurement_source_value", "string", "← sequencetype and site name"),
    ]),
    "observation": Table("cdm", "One per smoking status, and per tooth missing at the chart's start", "(not built)", [
        C("observation_id", "bigint", "← built from patnum, or toothinitialnum", "PK"),
        C("person_id", "bigint", "← patnum", "FK"),
        C("observation_concept_id", "int", "← patient.smokingsnomed (SNOMED), or a local 'tooth missing' concept", "FK"),
        C("observation_date", "date", "← patient.datefirstvisit: toothinitial has no date, so one is assumed"),
        C("observation_source_value", "string", "← smokingsnomed, or toothinitial.toothnum"),
    ]),
    "site": Table("dental", "One per person and tooth (OHDSI dental proposal)", "(not built)", [
        C("site_id", "bigint", "← built from patnum and tooth number", "PK"),
        C("person_id", "bigint", "← patnum", "FK"),
        C("site_concept_id", "int", "← tooth number, as a SNOMED tooth concept", "FK"),
        C("site_source_value", "string", "← procedurelog.toothnum, periomeasure.inttooth, toothinitial.toothnum"),
        C("site_start_date", "date", "not from Open Dental: eruption is never recorded"),
        C("site_end_date", "date", "← the extraction's procedurelog.datecomplete; null when missing at entry"),
        C("site_type_concept_id", "int", "not from Open Dental: EHR record"),
    ]),
    "site_event": Table("dental", "One per event tied to a tooth", "(not built)", [
        C("site_event_id", "bigint", "← built", "PK"),
        C("site_id", "bigint", "← the tooth", "FK"),
        C("event_id", "bigint", "← procedure_occurrence_id, condition_occurrence_id or measurement_id"),
        C("event_field_concept_id", "int", "not from Open Dental: which table event_id is in"),
        C("site_event_type_concept_id", "int", "not from Open Dental: EHR record"),
    ]),
    "concept": Table("vocab", "One per concept: CDT, SNOMED, ICD10CM, and DENTAL_LOCAL for the practice's items", "OMOP vocabulary + omop/vocab/local_concepts.csv", [
        C("concept_id", "int", "concept key", "PK"),
        C("concept_code", "string", "the code in its vocabulary"),
        C("vocabulary_id", "string", "CDT · SNOMED · ICD10CM · DENTAL_LOCAL"),
        C("domain_id", "string", "Procedure · Condition · Measurement · Observation · Spec Anatomic Site"),
        C("concept_name", "string", "name"),
    ]),
    "not_mapped": Table("gap", "What the CDM can't hold from this data (spec 029 keeps it in Open Dental silver)", "(a list, not a table)", [
        C("planned_procedures", "—", "procstatus 1: the CDM records what happened; planned extractions, spec 029's second label set, have no home"),
        C("plan_copies", "—", "proctp and treatplan: alternatives per exam and repeats at later exams"),
        C("edited_plan_text", "—", "proctp code, tooth and diagnosis text that differs from the original"),
        C("diagnosis_list_in_use", "—", "which practice list an item came from, and when the 2017 list replaced the older one"),
        C("missing_tooth_dates", "—", "toothinitial has no date or reason; the observation date above is assumed"),
        C("prognosis", "—", "procedurelog.prognosis has no standard concept"),
    ]),
}

RELATIONSHIPS = [
    R("care_site", "person", ("care_site_id",), ("care_site_id",), "care_site_id", "|o--o{"),
    R("care_site", "visit_occurrence", ("care_site_id",), ("care_site_id",), "care_site_id", "|o--o{"),
    R("person", "visit_occurrence", ("person_id",), ("person_id",), "person_id"),
    R("person", "procedure_occurrence", ("person_id",), ("person_id",), "person_id"),
    R("person", "condition_occurrence", ("person_id",), ("person_id",), "person_id"),
    R("person", "measurement", ("person_id",), ("person_id",), "person_id"),
    R("person", "observation", ("person_id",), ("person_id",), "person_id"),
    R("person", "site", ("person_id",), ("person_id",), "person_id"),
    R("visit_occurrence", "procedure_occurrence", ("visit_occurrence_id",), ("visit_occurrence_id",), "visit_occurrence_id", "|o--o{"),
    R("visit_occurrence", "condition_occurrence", ("visit_occurrence_id",), ("visit_occurrence_id",), "visit_occurrence_id", "|o--o{"),
    R("visit_occurrence", "measurement", ("visit_occurrence_id",), ("visit_occurrence_id",), "visit_occurrence_id", "|o--o{"),
    R("site", "site_event", ("site_id",), ("site_id",), "site_id"),
    R("procedure_occurrence", "site_event", ("procedure_occurrence_id",), ("event_id",), "event_id (one of three tables)", "||..o{", derived=True),
    R("condition_occurrence", "site_event", ("condition_occurrence_id",), ("event_id",), "event_id", "||..o{", derived=True),
    R("measurement", "site_event", ("measurement_id",), ("event_id",), "event_id", "||..o{", derived=True),
    R("concept", "procedure_occurrence", ("concept_id",), ("procedure_concept_id",), "procedure_concept_id"),
    R("concept", "condition_occurrence", ("concept_id",), ("condition_concept_id",), "condition_concept_id"),
    R("concept", "measurement", ("concept_id",), ("measurement_concept_id",), "measurement_concept_id"),
    R("concept", "site", ("concept_id",), ("site_concept_id",), "site_concept_id"),
]

AREAS = {   # fill, legend label
    "cdm": ("#E1EEF6", "OMOP CDM 5.4 table (official names)"),
    "dental": ("#FFF4C2", "dental extension: site, site_event (omop/ddl)"),
    "vocab": ("#EFE9FB", "vocabulary"),
    "gap": ("#FDE7F1", "not mapped: what the CDM loses"),
}

# ---------- the data-dictionary view (dictionary_erd.py) ----------
GROUPS = [
    ("Person", 0, ["person", "care_site"]),
    ("Visits", 0, ["visit_occurrence"]),
    ("Clinical events", 1, ["procedure_occurrence", "condition_occurrence", "measurement", "observation"]),
    ("Teeth (dental extension)", 2, ["site", "site_event"]),
    ("Vocabulary", 2, ["concept"]),
    ("Not mapped", 2, ["not_mapped"]),
]
KINDS = {t: "fact" for t in ("visit_occurrence", "procedure_occurrence", "condition_occurrence", "measurement",
                             "observation", "site_event")}
KINDS |= {t: "dimension" for t in ("person", "care_site", "site", "concept", "not_mapped")}
PHI = {("person", "birth_datetime")}
QUESTIONS = {
    ("procedure_occurrence", "procedure_occurrence_id"): "completed only: planned procedures are lost",
    ("observation", "observation_date"): "assumed for missing teeth: the source has no date",
    ("condition_occurrence", "condition_concept_id"): "practice list items need a local map; 0 when unmapped",
}
