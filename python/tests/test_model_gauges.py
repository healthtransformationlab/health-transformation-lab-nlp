"""#628: the tooth-loss gauges: each measure as a question, XGBoost against logistic regression."""

import math

import pandas as pd
import pytest

from health_transformation_lab_nlp import model_gauges as mg


def _scores(xgb: dict, lr: dict, rate: float = 0.15) -> pd.DataFrame:
    rows = []
    for model, vals in (("xgboost", xgb), ("logistic", lr)):
        base = {"label_set": "completed", "feature_set": "shared", "eval_set": "held_out", "model": model}
        rows.append({**base, "metric": "auc", "threshold_name": None, "value": vals["auc"],
                     "ci_low": vals["auc"] - 0.02, "ci_high": vals["auc"] + 0.02})
        rows.append({**base, "metric": "outcome_rate", "threshold_name": None, "value": rate,
                     "ci_low": float("nan"), "ci_high": float("nan")})
        for m in ("sensitivity", "specificity", "ppv", "npv"):
            rows.append({**base, "metric": m, "threshold_name": "youden_train", "value": vals[m],
                         "ci_low": float("nan"), "ci_high": float("nan")})
    return pd.DataFrame(rows)


XGB = {"auc": 0.85, "sensitivity": 0.40, "specificity": 0.98, "ppv": 0.75, "npv": 0.90}
LR = {"auc": 0.80, "sensitivity": 0.30, "specificity": 0.97, "ppv": 0.65, "npv": 0.88}


def test_each_measure_has_xgboost_the_reference_and_the_difference_in_points():
    t = mg.gauge_table(_scores(XGB, LR)).set_index("measure")
    assert list(t.index) == ["auc", "sensitivity", "ppv", "lr_plus", "lr_minus", "specificity", "npv"]
    assert t.loc["auc", "value"] == 0.85 and t.loc["auc", "reference_value"] == 0.80
    assert t.loc["auc", "difference_pts"] == pytest.approx(5.0)
    assert t.loc["sensitivity", "difference_pts"] == pytest.approx(10.0)
    assert t.loc["auc", "ci_low"] == pytest.approx(0.83)


def test_likelihood_ratios_follow_from_sensitivity_and_specificity():
    t = mg.gauge_table(_scores(XGB, LR)).set_index("measure")
    assert t.loc["lr_plus", "value"] == pytest.approx(0.40 / 0.02)          # 20: a flag is strong evidence
    assert t.loc["lr_minus", "value"] == pytest.approx(0.60 / 0.98)
    assert t.loc["lr_plus", "band"] == "higher" and t.loc["lr_minus", "band"] == "lower"
    assert "strong" in t.loc["lr_plus", "reading"].lower() and "minimal" in t.loc["lr_minus", "reading"].lower()


def test_per_100_readings_and_the_random_selection_baseline():
    t = mg.gauge_table(_scores(XGB, LR)).set_index("measure")
    assert t.loc["sensitivity", "reading"] == "40 caught | 60 missed, per 100 periodontal losses"
    assert t.loc["ppv", "reading"] == "75 correct | 25 false, per 100 flagged teeth"
    assert t.loc["ppv", "baseline"] == pytest.approx(0.15)                 # random selection = the outcome rate
    assert t.loc["auc", "reading"] == "85 of 100 pairs ranked correctly"


def test_bands_only_where_a_published_convention_exists():
    t = mg.gauge_table(_scores(XGB, LR)).set_index("measure")
    assert t.loc["auc", "band"] == "higher"                                # 0.85: excellent (Hosmer & Lemeshow)
    assert mg.auc_band(0.65) == "lower" and mg.auc_band(0.75) == "intermediate"
    for m in ("sensitivity", "ppv", "specificity", "npv"):
        assert t.loc[m, "band"] == "not_set", m                           # no agreed clinical target
    assert all(t["source"].str.len() > 0)


def test_an_undefined_ratio_stays_blank_rather_than_infinite():
    t = mg.gauge_table(_scores({**XGB, "specificity": 1.0}, LR)).set_index("measure")
    assert math.isnan(t.loc["lr_plus", "value"])


def test_the_page_says_synthetic_and_draws_one_gauge_per_measure():
    html = mg.gauges_html(mg.gauge_table(_scores(XGB, LR)), title="Tooth-loss model")
    assert "SYNTHETIC" in html and html.count("<svg") == 7
    assert "XGBoost" in html and "Logistic regression" in html
    assert "target not set" in html


def test_every_needle_lands_in_the_zone_of_its_own_band():
    # the dial's coloured zones match the band the reading names (an LR+ of 6.7 is "higher", in the green zone)
    for v in (1.5, 3.0, 6.7, 15.0):
        band, _ = mg.lr_band(v, plus=True)
        f = mg._position("lr_plus", v)
        assert next(b for a0, a1, b in mg._bands("lr_plus") if a0 <= f <= a1) == band, v
        band, _ = mg.lr_band(1 / v, plus=False)
        f = mg._position("lr_minus", 1 / v)
        assert next(b for a0, a1, b in mg._bands("lr_minus") if a0 <= f <= a1) == band, v
    for v in (0.6, 0.75, 0.85):
        f = mg._position("auc", v)
        assert next(b for a0, a1, b in mg._bands("auc") if a0 <= f <= a1) == mg.auc_band(v), v
