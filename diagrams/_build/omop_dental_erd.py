"""omop_dental_model.py -> d3, the OMOP dental ERD, in the data-dictionary format (dictionary_erd.py; #607).
Writes   ../d3_erd_omop_dental_full.drawio     every column, profiled from the synthetic OMOP tables build.py writes
         ../d3_erd_omop_dental_entity.drawio   the same layout, each table's header and key columns
Note text is never profiled: free text stays out of diagrams. Tables build.py doesn't write (note_nlp, site,
site_event) say their rows aren't measured yet.
Run: python3 omop_dental_erd.py, then render: node drawio_render.js ../d3_erd_omop_dental_*.drawio (render.md)
"""
import tempfile
from pathlib import Path

import dictionary_erd
import omop_dental_model
import table_profile

OUT = Path(__file__).resolve().parent.parent
PREFIX = "d3_erd_omop_dental"


def stats(n_people: int = 300, seed: int = 42) -> dict:
    """Profile the seeded synthetic OMOP tables (build.build's defaults), the DENTAL_LOCAL concepts and the
    perio_chart view over them. Nothing row-level is kept, only counts."""
    import pandas as pd
    from health_transformation_lab_nlp import build

    with tempfile.TemporaryDirectory() as tmp:
        omop, labels = Path(tmp) / "omop", Path(tmp) / "labels"
        build.build(omop, labels, n_people=n_people, seed=seed)
        frames = {t: pd.read_parquet(omop / f"{t}.parquet")
                  for t in ("person", "visit_occurrence", "note", "measurement")}
    frames["note"] = frames["note"].drop(columns=["note_text"])
    for t, cols in (("visit_occurrence", ["visit_start_date"]), ("note", ["note_date"]),
                    ("measurement", ["measurement_date"])):
        for c in cols:
            frames[t][c] = pd.to_datetime(frames[t][c])
    concepts = pd.read_csv(OUT.parent / "omop" / "vocab" / "local_concepts.csv")
    frames["concept"] = concepts[["concept_id", "concept_code", "concept_name", "vocabulary_id", "domain_id"]]
    m = frames["measurement"]
    chart = m.pivot_table(index=["person_id", "visit_occurrence_id", "measurement_date"],
                          columns="measurement_source_value", values="value_as_number").reset_index()
    frames["perio_chart"] = chart.rename(columns={"measurement_date": "exam_date", **{
        code: field for code, field in build.CHART_FIELDS.items()}})
    return table_profile.profile(frames)


if __name__ == "__main__":
    for path in dictionary_erd.write(PREFIX, omop_dental_model, stats(), OUT):
        print("wrote", path.relative_to(OUT.parent))
