"""d3: the OMOP CDM 5.4 tables the benchmark uses, the dental extension (omop/ddl/dental_extension.sql: site,
site_event), the DENTAL_LOCAL concepts and the perio_chart view, declared for the data-dictionary ERD (#607; the
format of every ERD here, #601). Drawn by omop_dental_erd.py.

CDM tables and columns keep their official names. Only the columns used here are listed. Synthetic data only.
"""
from gold_model import Column as C
from gold_model import Relationship as R
from gold_model import Table

TABLES = {
    "person": Table("cdm", "One per patient", "build.py writes person.parquet", [
        C("person_id", "bigint", "patient key", "PK"),
        C("gender_concept_id", "int", "8507 male, 8532 female", "FK"),
        C("year_of_birth", "int", "year only: the CDM keeps no full birth date here"),
        C("person_source_value", "string", "the generator's patient id"),
    ]),
    "visit_occurrence": Table("cdm", "One per patient visit", "build.py writes visit_occurrence.parquet", [
        C("visit_occurrence_id", "bigint", "visit key", "PK"),
        C("person_id", "bigint", "the patient", "FK"),
        C("visit_concept_id", "int", "9202 outpatient visit", "FK"),
        C("visit_start_date", "date", "the exam date"),
    ]),
    "note": Table("cdm", "One per visit: the dental SOAP note", "build.py writes note.parquet", [
        C("note_id", "bigint", "note key (the visit's id)", "PK"),
        C("person_id", "bigint", "the patient", "FK"),
        C("visit_occurrence_id", "bigint", "the visit", "FK"),
        C("note_date", "date", "the visit date"),
        C("note_type_concept_id", "int", "32817 EHR"),
        C("note_title", "string", "Dental SOAP note"),
        C("note_text", "string", "the free-text note; de-identified before silver; never profiled here"),
    ]),
    "note_nlp": Table("cdm", "One per status a reader finds in a note", "(not written yet: results go to gold)", [
        C("note_nlp_id", "bigint", "key", "PK"),
        C("note_id", "bigint", "the note read", "FK"),
        C("lexical_variant", "string", "the verbatim quote the status rests on"),
        C("note_nlp_concept_id", "int", "the status found, a DENTAL_LOCAL PERIO_STATUS_* concept", "FK"),
        C("nlp_system", "string", "the reader: model and version"),
        C("nlp_date", "date", "when it read the note"),
    ]),
    "measurement": Table("cdm", "One per chart summary per visit (design C: per tooth site)",
                         "build.py writes measurement.parquet", [
        C("measurement_id", "bigint", "key", "PK"),
        C("person_id", "bigint", "the patient", "FK"),
        C("visit_occurrence_id", "bigint", "the visit", "FK"),
        C("measurement_concept_id", "int", "a DENTAL_LOCAL concept: PERIO_MAX_PD, PERIO_BOP_PCT ...", "FK"),
        C("measurement_date", "date", "the exam date"),
        C("value_as_number", "double", "mm, percent or a count, by concept"),
        C("measurement_source_value", "string", "the local concept code"),
        C("tooth_number", "int", "design C only: universal tooth number"),
        C("tooth_site", "string", "design C only: MB, B, DB, ML, L, DL"),
    ]),
    "site": Table("dental", "One per person and tooth or tooth surface (OHDSI dental proposal)",
                  "omop/ddl/dental_extension.sql (design A)", [
        C("site_id", "bigint", "key", "PK"),
        C("person_id", "bigint", "the patient", "FK"),
        C("site_concept_id", "int", "SNOMED tooth or surface concept", "FK"),
        C("site_source_value", "string", "'3', '19', '19-MB'"),
        C("parent_site_id", "bigint", "a surface points at its tooth", "FK"),
        C("site_start_date", "date", "eruption, or first seen"),
        C("site_end_date", "date", "extraction"),
    ]),
    "site_event": Table("dental", "One per event tied to a site", "omop/ddl/dental_extension.sql (design A)", [
        C("site_event_id", "bigint", "key", "PK"),
        C("site_id", "bigint", "the tooth or surface", "FK"),
        C("event_id", "bigint", "measurement_id here (or a procedure or condition id)"),
        C("event_field_concept_id", "int", "which table event_id is in: 1147138 measurement"),
        C("site_event_type_concept_id", "int", "how it is known: EHR"),
    ]),
    "concept": Table("vocab", "One per concept: standard vocabularies and the DENTAL_LOCAL rows",
                     "OMOP vocabulary + omop/vocab/local_concepts.csv", [
        C("concept_id", "int", "key; DENTAL_LOCAL from 2000000001", "PK"),
        C("concept_code", "string", "PERIO_MAX_PD · SITE_PD · PERIO_STATUS_* · CDC_AAP_* ..."),
        C("concept_name", "string", "name"),
        C("vocabulary_id", "string", "DENTAL_LOCAL for the local rows"),
        C("domain_id", "string", "Measurement · Observation"),
    ]),
    "perio_chart": Table("view", "One per person and exam: the chart labels.py reads",
                         "view over measurement (omop/ddl/dental_extension.sql)", [
        C("person_id", "bigint", "the patient", "FK"),
        C("visit_occurrence_id", "bigint", "the visit", "FK"),
        C("exam_date", "date", "measurement_date"),
        C("max_probing_depth_mm", "double", "PERIO_MAX_PD"),
        C("bop_pct", "double", "PERIO_BOP_PCT"),
        C("max_cal_mm", "double", "PERIO_MAX_CAL"),
        C("rbl_pct", "double", "PERIO_RBL_PCT"),
        C("teeth_lost_perio", "double", "PERIO_TEETH_LOST"),
    ]),
}

RELATIONSHIPS = [
    R("person", "visit_occurrence", ("person_id",), ("person_id",), "person_id"),
    R("person", "note", ("person_id",), ("person_id",), "person_id"),
    R("person", "measurement", ("person_id",), ("person_id",), "person_id"),
    R("person", "site", ("person_id",), ("person_id",), "person_id"),
    R("visit_occurrence", "note", ("visit_occurrence_id",), ("visit_occurrence_id",), "visit_occurrence_id", "|o--o{"),
    R("visit_occurrence", "measurement", ("visit_occurrence_id",), ("visit_occurrence_id",), "visit_occurrence_id",
      "|o--o{"),
    R("note", "note_nlp", ("note_id",), ("note_id",), "note_id"),
    R("site", "site_event", ("site_id",), ("site_id",), "site_id"),
    R("site", "site", ("site_id",), ("parent_site_id",), "parent_site_id", "|o--o{"),
    R("measurement", "site_event", ("measurement_id",), ("event_id",), "event_id", "||..o{", derived=True),
    R("concept", "measurement", ("concept_id",), ("measurement_concept_id",), "measurement_concept_id"),
    R("concept", "note_nlp", ("concept_id",), ("note_nlp_concept_id",), "note_nlp_concept_id"),
    R("concept", "site", ("concept_id",), ("site_concept_id",), "site_concept_id"),
    R("measurement", "perio_chart", ("person_id",), ("person_id",), "pivots", "||..o{", derived=True),
]

AREAS = {   # fill, legend label (the Mermaid view)
    "cdm": ("#E1EEF6", "OMOP CDM 5.4 table (official names)"),
    "dental": ("#FFF4C2", "dental extension: site, site_event (omop/ddl)"),
    "vocab": ("#EFE9FB", "vocabulary"),
    "view": ("#F1F3F5", "view"),
}

# ---------- the data-dictionary view (dictionary_erd.py) ----------
GROUPS = [
    ("Person and visits", 0, ["person", "visit_occurrence"]),
    ("Notes and what readers find", 0, ["note", "note_nlp"]),
    ("Chart measurements", 1, ["measurement", "perio_chart"]),
    ("Teeth (dental extension)", 1, ["site", "site_event"]),
    ("Vocabulary", 2, ["concept"]),
]
KINDS = {t: "fact" for t in ("visit_occurrence", "note", "note_nlp", "measurement", "site_event")}
KINDS |= {t: "dimension" for t in ("person", "site", "concept")}
KINDS |= {"perio_chart": "summary"}
PHI = {("note", "note_text"), ("person", "person_source_value")}
QUESTIONS = {
    ("measurement", "tooth_number"): "design C only; designs A and B: d4, docs/site_level_omop.md",
    ("note_nlp", "note_nlp_id"): "not written yet: reader results are in gold_perio_bench.fact_prediction",
    ("site", "site_id"): "not loaded yet: design A of three (d4)",
}
