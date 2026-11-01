"""Spec 023 US2: the status classifier on dental-only, dental+medical and medical-only features, 4 classes,
70/30 split stratified by class and kept by person. The xgboost runs are skipped without the `ml` extra."""

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import classify_status as cs
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR

SMALL = {"max_depth": [3], "learning_rate": [0.3], "reg_lambda": [1.0], "min_child_weight": [1],
         "class_weight": [None]}
CHART = {"max_probing_depth_mm", "bop_pct", "max_cal_mm", "rbl_pct", "teeth_lost_perio", "pct_teeth_involved"}


@pytest.fixture(scope="module")
def visits():
    return pd.read_csv(DATASETS_DIR / "visits_structured.csv")


@pytest.fixture(scope="module")
def record():
    return pd.read_csv(DATASETS_DIR / "medical_record.csv")


@pytest.fixture(scope="module")
def people(visits, record):
    return cs.person_features(visits, record, "algorithm_design", "four")


def test_four_scheme_groups_gingivitis_with_healthy_and_stages_three_and_four():
    m = cs.SCHEMES["four"]
    assert set(m) == set(LABELS)
    assert m["healthy"] == m["gingivitis"] == 0
    assert (m["periodontitis_stage_1"], m["periodontitis_stage_2"]) == (1, 2)
    assert m["periodontitis_stage_3"] == m["periodontitis_stage_4"] == 3
    assert cs.CLASS_NAMES["four"] == ["healthy", "I", "II", "III_IV"]


def test_feature_sets_are_declared_exactly():
    fs = cs.FEATURE_SETS
    assert list(fs) == ["dental", "dental_no_asa", "dental_medical", "medical"]
    assert fs["dental_no_asa"] == cs.FEATURES
    assert fs["dental"] == [*cs.FEATURES, "asa_class_num"]
    assert set(fs["dental_medical"]) == set(fs["dental"]) | (set(cs.MEDICAL_FEATURES) - {"is_diabetes"})
    assert fs["medical"] == cs.MEDICAL_FEATURES
    assert "age" in fs["medical"] and not CHART & set(fs["medical"])          # the label's chart stays out
    assert not {"smoker_1_9", "smoker_10plus", "asa_class_num", "treated_before"} & set(fs["medical"])
    for name, cols in fs.items():
        assert len(cols) == len(set(cols)), name


def test_person_features_one_row_per_person_with_every_declared_feature(people, record):
    assert people["person_id"].is_unique
    assert set(people["person_id"]) <= set(record["person_id"])
    cols = set().union(*cs.FEATURE_SETS.values())
    assert cols <= set(people.columns)
    assert set(people["y"]) == {0, 1, 2, 3}
    assert people["asa_class_num"].isin([1, 2, 3, 4]).all()
    assert people["hba1c"].isna().any()                     # not measured stays missing, never imputed
    # diabetes from the visits and from the record never disagree
    assert (people["diabetes"] == people["is_diabetes"]).all()


def test_person_features_take_each_persons_latest_charted_visit(visits, record, people):
    v = visits[visits["charted"].astype(bool) & visits["algorithm_design"].isin(LABELS)]
    latest = v.sort_values(["person_id", "visit_date"]).groupby("person_id").tail(1)
    assert set(people["visit_id"]) == set(latest["visit_id"])


def test_stratified_split_shares_and_people(people):
    te = cs.split_stratified(people, seed=0)
    assert te.dtype == bool and len(te) == len(people)
    assert not set(people.loc[te, "person_id"]) & set(people.loc[~te, "person_id"])
    for k, n in people["y"].value_counts().items():
        n_test = int((people.loc[te, "y"] == k).sum())
        assert abs(n_test - 0.3 * n) <= 1, (k, n, n_test)


def test_stratified_split_is_seeded(people):
    a, b = cs.split_stratified(people, seed=4), cs.split_stratified(people, seed=4)
    assert (a == b).all() and not (a == cs.split_stratified(people, seed=5)).all()


def test_stratified_split_keeps_people_whole_when_they_have_several_rows():
    f = pd.DataFrame({"person_id": np.repeat(np.arange(40), 2), "y": np.tile([0, 1], 40)})
    te = cs.split_stratified(f, seed=1)
    by_person = pd.Series(te).groupby(f["person_id"]).nunique()
    assert (by_person == 1).all()


def test_stratified_split_fails_clearly_on_a_class_too_small_to_split():
    f = pd.DataFrame({"person_id": range(11), "y": [0] * 10 + [1]})
    with pytest.raises(ValueError, match="class 1"):
        cs.split_stratified(f, seed=0)


def test_comparison_rows_one_per_feature_set_and_class(people):
    pytest.importorskip("xgboost")
    small = people.groupby("y").head(60).reset_index(drop=True)
    res = cs.compare_feature_sets(small, seed=2, grid=SMALL, folds=3)
    m = res["metrics"]
    assert len(m) == len(cs.FEATURE_SETS) * 5                     # 4 classes and their mean (US3)
    assert list(m.loc[m["feature_set"] == "medical", "class"]) == [*cs.CLASS_NAMES["four"], "mean"]
    assert set(m["feature_set"]) == set(cs.FEATURE_SETS)
    assert m["is_synthetic"].all() and (m["seed"] == 2).all()
    for name, cols in cs.FEATURE_SETS.items():
        assert set(m.loc[m["feature_set"] == name, "features"]) == {" ".join(cols)}
    for col in ("n_test", "sensitivity", "specificity", "auc", "brier", "classes_averaged"):
        assert col in m.columns
    p = res["predictions"]
    assert set(p["feature_set"]) == set(cs.FEATURE_SETS)
    prob = p[[f"p_{c}" for c in cs.CLASS_NAMES["four"]]].to_numpy()
    assert np.allclose(prob.sum(axis=1), 1, atol=1e-5)
    s = res["shap_importance"]
    for name, cols in cs.FEATURE_SETS.items():
        assert set(s.loc[s["feature_set"] == name, "feature"]) == set(cols)
    again = cs.compare_feature_sets(small, seed=2, grid=SMALL, folds=3)["metrics"]
    pd.testing.assert_frame_equal(m, again)
