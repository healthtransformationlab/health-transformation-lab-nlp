"""Reference answers for the MedGemma reader's fields, from the generator's truth (spec 004 US5, #130)."""

import pandas as pd
import pytest

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


# ---- per-field accuracy (spec 004 US6, #132)

def _ref():
    return pd.DataFrame({"visit_id": [1, 2, 3, 4],
                         "status": ["healthy", "periodontitis_stage_2", "periodontitis_stage_3", "gingivitis"],
                         "grade": ["NA", "B", "C", "NA"], "extent": ["NA", "localized", "generalized", "NA"]})


def _details():
    return pd.DataFrame({"visit_id": [4, 3, 2, 1],                     # order doesn't matter
                         "pred": ["gingivitis", "periodontitis_stage_3", "periodontitis_stage_3", "gingivitis"],
                         "grade": [None, "C", "B", None],
                         "extent": [None, "localized", "localized", None],
                         "gate_ok": [True, True, False, True]})       # visit 2 fell back to note_rules


def test_field_accuracy_one_row_per_field_with_n_and_wilson_ci():
    t = ra.field_accuracy(_details(), _ref()).set_index("field")
    assert t.index.tolist() == list(ra.FIELDS)
    assert list(t.columns) == ["n", "correct", "accuracy", "ci_lo", "ci_hi"]
    assert (t.loc["status", "n"], t.loc["status", "correct"]) == (4, 2)       # visits 3, 4
    assert t.loc["status", "accuracy"] == 0.5
    lo, hi = ra.wilson_ci(2, 4)
    assert (t.loc["status", "ci_lo"], t.loc["status", "ci_hi"]) == (lo, hi)
    assert round(lo, 6) == 0.150039 and round(hi, 6) == 0.849961


def test_grade_and_extent_are_scored_only_where_they_apply_and_a_fallback_answer_is_not_read():
    t = ra.field_accuracy(_details(), _ref()).set_index("field")
    assert t.loc["grade", "n"] == 2 and t.loc["grade", "correct"] == 1     # visit 2's B came from a failed gate
    assert t.loc["extent", "n"] == 2 and t.loc["extent", "correct"] == 0   # visit 3 said localized


def test_wilson_ci_edges():
    assert ra.wilson_ci(0, 0) == (None, None)
    lo, hi = ra.wilson_ci(10, 10)
    assert hi == pytest.approx(1.0) and 0.72 < lo < 0.73


def test_a_partial_run_is_refused():
    with pytest.raises(ValueError, match="1 of 4"):
        ra.field_accuracy(_details()[_details().visit_id != 1], _ref())


def test_committed_per_field_table_matches_the_committed_runs():
    out = pd.read_csv(DATASETS_DIR / "ladder" / "medgemma_field_accuracy.csv")
    ref = pd.read_csv(REF, keep_default_na=False)
    assert set(out["run"]) == {"medgemma-4b-it", "medgemma-1.5-4b-it"}
    for run, got in out.groupby("run"):
        want = ra.field_accuracy(pd.read_csv(DATASETS_DIR / f"llm_details_{run}.csv"), ref)
        pd.testing.assert_frame_equal(got.drop(columns="run").reset_index(drop=True), want, check_dtype=False)
    # the status row is the rung's headline accuracy (pred, after fallback), as in medgemma_vs_bert.csv
    head = pd.read_csv(DATASETS_DIR / "ladder" / "medgemma_vs_bert.csv").set_index("method")["accuracy"]
    st = out[out.field == "status"].set_index("run")["accuracy"]
    for run in st.index:
        assert st[run] == pytest.approx(head[run])


def test_mlflow_metrics_name_each_field():
    m = ra.field_metrics(ra.field_accuracy(_details(), _ref()))
    assert m == {"field_accuracy_status": 0.5, "field_accuracy_grade": 0.5, "field_accuracy_extent": 0.0,
                 "field_n_status": 4, "field_n_grade": 2, "field_n_extent": 2}


def test_the_reader_and_the_per_field_script_log_these_metrics():
    from health_transformation_lab_nlp.paths import REPO_ROOT
    for s in ("11_ai_predict.py", "54_medgemma_field_accuracy.py"):
        assert "field_metrics(" in (REPO_ROOT / "python" / "scripts" / s).read_text(), s
