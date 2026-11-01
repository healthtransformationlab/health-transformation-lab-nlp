"""Spec 023 US3: per-class sensitivity, specificity, AUC and Brier score, one-vs-rest, plus their class means.
Hand-worked cases; no xgboost needed, so these run in CI. R parity: r/R/13_spec023.R, r/tests/test_parity.R."""

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from health_transformation_lab_nlp.classify_status import CLASS_NAMES, class_metrics
from health_transformation_lab_nlp.paths import DATASETS_DIR

NAMES = ["a", "b", "c"]


def test_committed_results_match_class_metrics_on_the_committed_predictions():
    d = DATASETS_DIR / "classify_status"
    preds = pd.read_csv(d / "synthetic_medical_feature_sets_predictions.csv")
    res = pd.read_csv(d / "synthetic_medical_feature_sets.csv")
    names = CLASS_NAMES["four"]
    for k, g in preds.groupby("feature_set"):
        m = class_metrics(g["y"].to_numpy(), g[[f"p_{c}" for c in names]].to_numpy(), names)
        r = res[res["feature_set"] == k].reset_index(drop=True)
        assert list(r["class"]) == list(m["class"])
        for col in ("n_test", "sensitivity", "specificity", "auc", "brier"):
            assert np.allclose(r[col], m[col], atol=1e-6, equal_nan=True), (k, col)
    parity = pd.read_csv(d / "synthetic_class_metrics_parity.csv")      # the R parity test's Python side
    assert set(parity["feature_set"]) == {*preds["feature_set"], "cases"}
    cases_mean = parity[(parity["feature_set"] == "cases") & (parity["class"] == "mean")]
    assert cases_mean["classes_averaged"].item() == 3


def _row(m, name):
    return m.set_index("class").loc[name]


def test_perfect_model():
    y = np.array([0, 1, 2, 0])
    m = class_metrics(y, np.eye(3)[y], NAMES)
    assert list(m["class"]) == [*NAMES, "mean"]
    per = m[m["class"] != "mean"]
    assert (per[["sensitivity", "specificity", "auc"]] == 1).all().all()
    assert (per["brier"] == 0).all()
    mean = _row(m, "mean")
    assert (mean.sensitivity, mean.specificity, mean.auc, mean.brier) == (1, 1, 1, 0)
    assert mean.classes_averaged == 3 and mean.n_test == 4


def test_constant_model():
    y = np.array([0, 1, 2, 2])
    m = class_metrics(y, np.full((4, 3), 1 / 3), NAMES)
    # every row ties; the first class wins the arg-max, as numpy's argmax (and R's max.col, ties "first")
    assert _row(m, "a").sensitivity == 1 and _row(m, "a").specificity == 0
    assert _row(m, "b").sensitivity == 0 and _row(m, "b").specificity == 1
    assert (m.loc[m["class"] != "mean", "auc"] == 0.5).all()
    # Brier for c: two positives at (1/3 - 1)^2, two negatives at (1/3)^2
    assert _row(m, "c").brier == pytest.approx((2 * (2 / 3) ** 2 + 2 * (1 / 3) ** 2) / 4)


def test_a_class_missing_from_test_is_missing_not_zero():
    y = np.array([0, 0, 1, 1])
    p = np.array([[0.7, 0.2, 0.1], [0.4, 0.5, 0.1], [0.2, 0.6, 0.2], [0.3, 0.3, 0.4]])
    m = class_metrics(y, p, NAMES)
    c = _row(m, "c")
    assert c.n_test == 0 and np.isnan(c.auc) and np.isnan(c.sensitivity)
    assert c.specificity == pytest.approx(3 / 4)            # row 4 is called c: a false positive
    assert c.brier == pytest.approx(np.mean(p[:, 2] ** 2))   # still defined: all negatives
    mean = _row(m, "mean")
    assert mean.classes_averaged == 2
    assert mean.auc == pytest.approx((_row(m, "a").auc + _row(m, "b").auc) / 2)
    assert mean.brier == pytest.approx((_row(m, "a").brier + _row(m, "b").brier) / 2)


def test_auc_averages_ties_and_matches_sklearn():
    y = np.array([0, 0, 1, 1])
    p = np.array([[0.8, 0.2], [0.5, 0.5], [0.5, 0.5], [0.2, 0.8]])
    m = class_metrics(y, p, ["x", "y"])
    # class x: positives score 0.8, 0.5; negatives 0.5, 0.2 -> pairs 1, 1, 0.5, 1 -> 3.5 / 4
    assert _row(m, "x").auc == pytest.approx(0.875)
    rng = np.random.default_rng(3)
    y = rng.integers(0, 3, 200)
    p = rng.dirichlet(np.ones(3), 200).round(1)              # rounding makes ties
    m = class_metrics(y, p, NAMES)
    for k, name in enumerate(NAMES):
        assert _row(m, name).auc == pytest.approx(roc_auc_score(y == k, p[:, k]), abs=1e-12)


def test_brier_is_the_one_vs_rest_mean_squared_error():
    y = np.array([0, 1, 1])
    p = np.array([[0.6, 0.4], [0.3, 0.7], [0.5, 0.5]])
    m = class_metrics(y, p, ["x", "y"])
    assert _row(m, "x").brier == pytest.approx(((0.6 - 1) ** 2 + 0.3 ** 2 + 0.5 ** 2) / 3)
    assert _row(m, "y").brier == pytest.approx((0.4 ** 2 + (0.7 - 1) ** 2 + (0.5 - 1) ** 2) / 3)
