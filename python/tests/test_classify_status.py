"""Status classifier with SHAP explanations (spec 013 G10): gradient-boosted trees on the recorded chart."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("xgboost")

from health_transformation_lab_nlp import classify_status as cs
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR

SMALL = {"max_depth": [3], "learning_rate": [0.3], "reg_lambda": [1.0], "min_child_weight": [1],
         "class_weight": [None, "balanced"]}


@pytest.fixture(scope="module")
def visits():
    return pd.read_csv(DATASETS_DIR / "visits_structured.csv")


@pytest.fixture(scope="module")
def result(visits):
    return cs.train_eval(cs.features(visits, "algorithm_design", "5level"), "5level", seed=1, grid=SMALL, folds=3)


def test_schemes_map_every_status():
    for name, n in (("5level", 5), ("3level", 3)):
        m = cs.SCHEMES[name]
        assert set(m) == set(LABELS) and sorted(set(m.values())) == list(range(n))
        assert m["healthy"] == m["gingivitis"] == 0
    assert cs.SCHEMES["3level"]["periodontitis_stage_2"] == 1 and cs.SCHEMES["3level"]["periodontitis_stage_3"] == 2


def test_features_use_charted_visits_with_a_known_status_only(visits):
    f = cs.features(visits, "algorithm_design", "5level")
    keep = visits[visits["charted"] & visits["algorithm_design"].isin(LABELS)]
    assert len(f) == len(keep) and set(f["visit_id"]) == set(keep["visit_id"])
    assert list(f.columns) == ["visit_id", "person_id", *cs.FEATURES, "y"]
    assert f[[c for c in cs.FEATURES if c != "hba1c"]].notna().all().all()   # hba1c stays missing when not measured
    assert every_feature_has_a_role()


def every_feature_has_a_role():
    return set(cs.AAP_ROLE) == set(cs.FEATURES) and set(cs.AAP_ROLE.values()) <= set(cs.ROLES)


def test_people_are_never_in_both_splits(visits):
    f = cs.features(visits, "algorithm_design", "5level")
    te = cs.split_people(f, seed=1)
    assert not set(f.loc[te, "person_id"]) & set(f.loc[~te, "person_id"])
    assert 0.15 < f.loc[te, "person_id"].nunique() / f["person_id"].nunique() < 0.25   # 80/20 by person


def test_result_has_metrics_and_shap(result):
    m = result["metrics"]
    assert list(m["class"]) == cs.CLASS_NAMES["5level"]
    for c in ("auroc", "sensitivity", "specificity", "n_test"):
        assert m[c].notna().all(), c
    s = result["summary"]
    assert 0 <= s["macro_f1"] <= 1 and 0 <= s["accuracy"] <= 1 and s["n_test"] == m["n_test"].sum()
    assert s["params"]["class_weight"] in (None, "balanced")
    imp = result["shap_importance"]
    assert set(imp["feature"]) == set(cs.FEATURES)
    assert {"mean_abs_shap", "role", *[f"mean_abs_shap_{c}" for c in cs.CLASS_NAMES["5level"]]} <= set(imp.columns)
    per = result["shap_test"]
    assert len(per) == s["n_test"] * 5 and {"visit_id", "class", *cs.FEATURES, "bias"} <= set(per.columns)


def test_shap_rows_add_up_to_the_model_margin(result):
    X = result["X_test"]
    phi = cs.shap_values(result["model"], X)                       # (visits, classes, features + bias)
    margin = result["model"].predict(X, output_margin=True)
    assert phi.shape == (len(X), 5, len(cs.FEATURES) + 1)
    assert np.allclose(phi.sum(axis=2), margin, atol=1e-4)


def test_attachment_loss_explains_more_than_grade_modifiers(result):
    # synthetic charts are labelled by the AAP rules, so SHAP should recover them: a check of the pipeline.
    # % teeth involved is 0 without attachment loss, so it separates healthy/gingivitis from periodontitis.
    imp = result["shap_importance"].set_index("feature")
    assert set(imp.index[:5]) <= {f for f, r in cs.AAP_ROLE.items() if r in ("stage", "extent")}
    top = imp["mean_abs_shap"].max()
    for f in ("smoker_1_9", "smoker_10plus", "diabetes"):     # set the grade, not the stage
        assert imp.loc[f, "mean_abs_shap"] < 0.1 * top, f


def test_same_seed_same_result(visits):
    f = cs.features(visits, "algorithm_design", "3level")
    a = cs.train_eval(f, "3level", seed=4, grid=SMALL, folds=3)
    b = cs.train_eval(f, "3level", seed=4, grid=SMALL, folds=3)
    pd.testing.assert_frame_equal(a["shap_importance"], b["shap_importance"])
    assert a["summary"]["params"] == b["summary"]["params"]


def test_a_class_missing_from_the_training_people_fails_with_a_clear_message(visits):
    # xgboost infers the class count from the labels: without this check a missing stage 4 gives 4 probability
    # columns and an IndexError later, and a missing middle class an "Invalid classes" error
    f = cs.features(visits, "algorithm_design", "5level")
    f = f[f["y"] != 4]                                 # no stage 4 at all, so none among the training people
    with pytest.raises(ValueError, match="stage_4"):
        cs.train_eval(f, "5level", seed=1, grid=SMALL, folds=3)


def test_folds_missing_a_class_are_skipped_in_tuning(visits):
    f = cs.features(visits, "algorithm_design", "5level").reset_index(drop=True)
    tr = f[~cs.split_people(f, seed=1)].reset_index(drop=True)
    stage4_people = tr.loc[tr["y"] == 4, "person_id"].unique()
    # One person with stage 4: the fold that validates on them trains without it, whichever fold GroupKFold picks
    # (scikit-learn 1.6, the Databricks runtime's, assigns groups to folds differently from newer versions; #478).
    keep = tr[(tr["y"] != 4) | tr["person_id"].isin(stage4_people[:1])].reset_index(drop=True)
    best = cs.tune(keep[cs.FEATURES], keep["y"].to_numpy(), keep["person_id"].to_numpy(), 5, seed=1, grid=SMALL, folds=5)
    assert 0 < best["cv_macro_f1"] <= 1 and best["cv_folds_used"] == 4
