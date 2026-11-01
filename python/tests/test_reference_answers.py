"""Reference answers for the MedGemma reader's fields, from the generator's truth (spec 004 US5, #130)."""

import pandas as pd

from health_transformation_lab_nlp import reference_answers as ra
from health_transformation_lab_nlp.paths import DATASETS_DIR

KEY = DATASETS_DIR / "answer_key" / "review_key.csv"
REF = DATASETS_DIR / "answer_key" / "reference_answers.csv"


def _key():
    return pd.DataFrame({
        "visit_id": [3, 1, 2],
        "truth_status": ["periodontitis_stage_2", "healthy", "gingivitis"],
        "truth_grade": ["B", None, None],
        "truth_extent": ["localized", None, None],
        "stated_status": ["periodontitis_stage_3", "healthy", "gingivitis"],
        "note_text": ["x", "y", "z"],
    })


def test_one_row_per_visit_one_column_per_reader_field():
    t = ra.reference_answers(_key())
    assert list(t.columns) == ["visit_id", *ra.FIELDS, "note_stated_status", "source"]
    assert ra.FIELDS == ("status", "grade", "extent")          # what llm_reader.parse_answer returns
    assert t["visit_id"].tolist() == [1, 2, 3]                  # sorted, one row each
    assert t.loc[t.visit_id == 3, ["status", "grade", "extent"]].iloc[0].tolist() == [
        "periodontitis_stage_2", "B", "localized"]


def test_grade_and_extent_are_na_unless_periodontitis():
    t = ra.reference_answers(_key())
    healthy = t[t.visit_id == 1].iloc[0]
    assert healthy["grade"] == "NA" and healthy["extent"] == "NA"   # the reader's own "not applicable" value


def test_the_note_can_disagree_with_the_truth_and_the_reference_follows_the_truth():
    t = ra.reference_answers(_key()).set_index("visit_id")
    assert t.loc[3, "status"] == "periodontitis_stage_2" and t.loc[3, "note_stated_status"] == "periodontitis_stage_3"


def test_the_source_is_recorded_on_every_row():
    t = ra.reference_answers(_key())
    assert t["source"].nunique() == 1 and "generator truth" in t["source"].iloc[0]


def test_committed_table_matches_the_committed_answer_key():
    key = pd.read_csv(KEY)
    committed = pd.read_csv(REF, keep_default_na=False)
    fresh = ra.reference_answers(key)
    pd.testing.assert_frame_equal(committed, fresh.astype(committed.dtypes.to_dict()), check_dtype=False)


def test_committed_table_covers_every_note_medgemma_read():
    ref = pd.read_csv(REF, keep_default_na=False)
    assert ref["visit_id"].is_unique and len(ref) == 240
    for run in ("medgemma-4b-it", "medgemma-1.5-4b-it"):
        d = pd.read_csv(DATASETS_DIR / f"llm_details_{run}.csv")
        assert set(d["visit_id"]) == set(ref["visit_id"]), run
    perio = ref["status"].str.startswith("periodontitis")
    assert set(ref.loc[perio, "grade"]) <= {"A", "B", "C"}
    assert set(ref.loc[perio, "extent"]) <= {"localized", "generalized", "molar_incisor"}
    assert (ref.loc[~perio, ["grade", "extent"]] == "NA").all().all()
