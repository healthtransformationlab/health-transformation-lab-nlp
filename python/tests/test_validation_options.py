"""Spec 032 US5 (#444): how a model is validated, as settings.

`split_unit` (`person`, the default, or `visit`: a random split of rows that reports how many people fall in both
parts), `test_share`, and `cv_folds` (k-fold cross-validated tuning of XGBoost, grouped by person unless the split
is by visit). For the tooth-loss model (tooth_loss_model) and the visit-level status classifier (classify_status).
The defaults change nothing. Synthetic data only."""
import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import open_dental as od
from health_transformation_lab_nlp import tooth_loss as tl
from health_transformation_lab_nlp import tooth_loss_model as tm


def _teeth(n_patients=200, per=3, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_patients):
        perio = p % 4 == 0
        for tooth in rng.choice(range(2, 16), size=per, replace=False):
            rows.append((p, int(tooth), "extracted_perio" if perio else "extracted_other", 50))
    t = pd.DataFrame(rows, columns=["patient_id", "tooth_num", "tooth_status_code", "age_at_first_exam_num"])
    t["is_perio_loss"] = t["tooth_status_code"].eq("extracted_perio").astype("boolean")
    for c in tl.COLUMNS:
        if c not in t:
            t[c] = np.nan
    return t


# ---------- tooth-loss model: the settings and their defaults

def test_the_defaults_are_a_split_by_person_at_30_percent_without_tuning():
    assert tm.SPLIT_UNITS == ("person", "visit")
    d = tm.ModelParams()
    assert (d.split_unit, d.test_share, d.cv_folds) == ("person", 0.3, None)


def test_a_split_by_visit_holds_out_random_rows_stratified_and_seeded():
    t = _teeth()
    test = tm.split_teeth(t, test_share=0.3, seed=7)
    assert test == tm.split_teeth(t, test_share=0.3, seed=7)                # seeded
    assert test != tm.split_teeth(t, test_share=0.3, seed=8)
    assert len(test) == round(len(t) * 0.75 * 0.3) + round(len(t) * 0.25 * 0.3)   # 30% of each outcome
    held = t.index.isin(list(test))
    assert t.loc[held, "is_perio_loss"].mean() == pytest.approx(0.25, abs=0.01)
    assert tm.people_in_both(t["patient_id"], held) > 0                      # the leak a row split allows


def test_people_in_both_counts_people_with_rows_on_each_side():
    assert tm.people_in_both(pd.Series([1, 1, 2, 2, 3]), np.array([True, False, True, True, False])) == 1
    t = _teeth()
    by_person = t["patient_id"].isin(tm.split_patients(t, 0.3, 7)).to_numpy()
    assert tm.people_in_both(t["patient_id"], by_person) == 0


def test_cv_folds_are_grouped_by_person_unless_the_split_is_by_visit_and_seeded():
    t = _teeth()
    y = t["is_perio_loss"].astype(bool).to_numpy(int)
    people = t["patient_id"].to_numpy()
    folds = tm.cv_splits(y, people, folds=5, seed=3)
    assert len(folds) == 5
    for tr, va in folds:
        assert not set(people[tr]) & set(people[va])                        # no person on both sides of a fold
    assert sorted(np.concatenate([va for _, va in folds]).tolist()) == list(range(len(t)))
    again = tm.cv_splits(y, people, folds=5, seed=3)
    assert all((a[1] == b[1]).all() for a, b in zip(folds, again))
    rows = tm.cv_splits(y, None, folds=5, seed=3)                           # by visit: rows, not people
    assert any(set(people[tr]) & set(people[va]) for tr, va in rows)


def test_tuning_picks_one_grid_point_by_cross_validated_auc():
    pytest.importorskip("xgboost")
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=300), "b": rng.normal(size=300)})
    y = (X["a"] + rng.normal(scale=0.5, size=300) > 0).to_numpy(int)
    grid = {"max_depth": [1, 2], "n_estimators": [20], "learning_rate": [0.1], "subsample": [1.0],
            "min_child_weight": [1]}
    best = tm.tune_xgboost(X, y, None, folds=3, seed=1, grid=grid)
    assert best["max_depth"] in (1, 2) and best["n_estimators"] == 20
    assert 0.5 < best["cv_auc"] <= 1 and best["cv_folds_used"] == 3
    assert best == tm.tune_xgboost(X, y, None, folds=3, seed=1, grid=grid)
    assert set(tm.XGB_GRID) == {"max_depth", "n_estimators", "learning_rate", "subsample", "min_child_weight"}


def test_a_bad_setting_fails_at_once():
    with pytest.raises(ValueError, match="split_unit"):
        tm.check_params(tm.ModelParams(split_unit="tooth"))
    with pytest.raises(ValueError, match="test_share"):
        tm.check_params(tm.ModelParams(test_share=1.0))
    with pytest.raises(ValueError, match="cv_folds"):
        tm.check_params(tm.ModelParams(cv_folds=1))
    tm.check_params(tm.ModelParams())


@pytest.fixture(scope="module")
def extract():
    pytest.importorskip("xgboost")
    tables, truth, reads = od.build_with_readings(od.Params(n_patients=300), seed=5)
    return {**od.clean(tables), "radiograph_bone_level": reads}, truth


def test_a_default_run_reports_the_split_by_person_with_no_one_in_both(extract):
    x, truth = extract
    v = tm.run(x, truth, tm.ModelParams(n_boot=0), generator_seed=5)["validation"]
    assert set(v["split_unit"]) == {"person"} and (v["people_in_both_count"] == 0).all()
    assert set(v["label_set"]) == set(tm.LABEL_SETS) and (v["data_label"] == "synthetic").all()
    assert v["cv_folds"].isna().all() and (v["xgboost_params"] == str(tm.XGB_PARAMS)).all()


def test_a_run_split_by_visit_reports_the_people_in_both_and_tunes_when_asked(extract, monkeypatch):
    x, truth = extract
    monkeypatch.setattr(tm, "XGB_GRID", {"max_depth": [2, 3], "n_estimators": [30], "learning_rate": [0.1],
                                         "subsample": [1.0], "min_child_weight": [1]})
    out = tm.run(x, truth, tm.ModelParams(n_boot=0, split_unit="visit", test_share=0.2, cv_folds=3),
                 generator_seed=5)
    v = out["validation"]
    assert set(v["split_unit"]) == {"visit"} and (v["test_share"] == 0.2).all()
    assert (v["people_in_both_count"] > 0).all()
    assert (v["cv_folds"] == 3).all() and v["cv_auc"].between(0, 1).all()
    assert v["xgboost_params"].str.contains("max_depth").all()
    s = out["scores"]
    assert s.loc[(s["model"] == "xgboost") & (s["metric"] == "auc"), "value"].notna().any()


# ---------- the visit-level status classifier

@pytest.fixture(scope="module")
def visit_features():
    pytest.importorskip("xgboost")
    from health_transformation_lab_nlp import classify_status as cs
    from health_transformation_lab_nlp.paths import DATASETS_DIR
    return cs.features(pd.read_csv(DATASETS_DIR / "visits_structured.csv"), "algorithm_design", "3level")


SMALL = {"max_depth": [3], "learning_rate": [0.3], "reg_lambda": [1.0], "min_child_weight": [1],
         "class_weight": [None]}


def test_the_classifier_split_by_visit_is_random_rows_and_seeded(visit_features):
    from health_transformation_lab_nlp import classify_status as cs
    f = visit_features
    te = cs.split_visits(f, seed=2, test_share=0.25)
    assert (te == cs.split_visits(f, seed=2, test_share=0.25)).all()
    assert te.sum() == round(len(f) * 0.25)
    assert cs.people_in_both(f, te) > 0
    assert cs.people_in_both(f, cs.split_people(f, seed=2)) == 0


def test_the_classifier_reports_how_it_was_validated(visit_features):
    from health_transformation_lab_nlp import classify_status as cs
    f = visit_features
    default = cs.train_eval(f, "3level", seed=1, grid=SMALL, folds=3)
    assert default["validation"] == {"split_unit": "person", "test_share": 0.2, "cv_folds": 3,
                                     "people_in_both_count": 0}
    assert "split_unit" not in default["summary"]                   # the committed summary keeps its columns
    by_visit = cs.train_eval(f, "3level", seed=1, grid=SMALL, folds=3, split_unit="visit", test_share=0.3)
    assert by_visit["validation"]["split_unit"] == "visit"
    assert by_visit["validation"]["people_in_both_count"] > 0
    assert by_visit["summary"]["n_test"] == round(len(f) * 0.3)
    with pytest.raises(ValueError, match="split_unit"):
        cs.train_eval(f, "3level", seed=1, grid=SMALL, folds=3, split_unit="tooth")


def test_the_stratified_split_by_visit_stratifies_rows(visit_features):
    from health_transformation_lab_nlp import classify_status as cs
    f = visit_features
    te = cs.split_stratified(f, seed=0, test_share=0.3, split_unit="visit")
    assert cs.people_in_both(f, te) > 0
    for k, g in f.groupby("y"):
        assert te[f["y"].to_numpy() == k].sum() == min(max(round(len(g) * 0.3), 1), len(g) - 1)
    assert (cs.split_stratified(f, seed=0, test_share=0.3) == cs.split_stratified(f, seed=0)).all()
