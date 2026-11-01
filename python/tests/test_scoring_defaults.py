"""Spec 032 US8 (#448): results are scored under the new defaults (five status groups, adults from the start date, a
treatment plan with no gum-disease code read as healthy or gingivitis) without rebuilding the benchmark note set, so
every committed model prediction stays valid. SYNTHETIC data only."""

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import harm, ladder_eval, study
from health_transformation_lab_nlp.labels import DEFAULT_GROUPING, GROUPINGS, HEALTHY_OR_GINGIVITIS, LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR

REREAD = ("proc_dx_completed", "proc_dx_planned", "algorithm_v0", "algorithm_design")


def test_grouped_maps_statuses_and_keeps_no_answer():
    s = pd.Series(["healthy", "gingivitis", "periodontitis_stage_4", np.nan, "healthy_gingivitis"])
    g = ladder_eval.grouped(s)
    assert list(g[:3]) == [HEALTHY_OR_GINGIVITIS, HEALTHY_OR_GINGIVITIS, "periodontitis_stage_4"]
    assert pd.isna(g[3]) and g[4] == HEALTHY_OR_GINGIVITIS
    assert list(ladder_eval.grouped(s, "six")[:3]) == list(s[:3])


def test_grouped_proba_adds_the_merged_statuses():
    p = pd.DataFrame([[0.1, 0.2, 0.3, 0.2, 0.1, 0.1]], columns=LABELS)
    g = ladder_eval.grouped_proba(p)
    assert list(g.columns) == list(GROUPINGS[DEFAULT_GROUPING])
    assert g.iloc[0, 0] == pytest.approx(0.3) and g.sum(axis=1).iloc[0] == pytest.approx(1.0)


def test_the_merged_group_grades_like_healthy():
    assert harm.severity(HEALTHY_OR_GINGIVITIS, HEALTHY_OR_GINGIVITIS) == "S0"
    assert harm.severity("periodontitis_stage_4", HEALTHY_OR_GINGIVITIS) == "S2"
    r = harm.unsafe_rates(pd.Series([HEALTHY_OR_GINGIVITIS, "periodontitis_stage_3"]),
                          pd.Series([HEALTHY_OR_GINGIVITIS, HEALTHY_OR_GINGIVITIS]))
    assert r["n"] == 2 and r["s2_rate"] == 0.5


@pytest.fixture(scope="module")
def key():
    return pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")


def test_rereading_under_no_answer_gives_back_the_answer_key(key):
    # the raw codes are regenerated from the build's seed; read as the build read them, they give the committed key
    again = study.reread_absent_code(key, "no_answer")
    for c in REREAD:
        assert (again[c] == key[c]).all(), c


def test_rereading_turns_only_no_answer_codes_into_healthy(key):
    again = study.reread_absent_code(key)                     # the default: healthy_or_gingivitis
    for c in ("proc_dx_completed", "proc_dx_planned"):
        changed = again[c] != key[c]
        assert changed.any(), c
        assert (key.loc[changed, c] == "unknown").all() and (again.loc[changed, c] == "healthy").all(), c


def test_the_scored_review_charts_are_the_visits_that_count(key):
    visits = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
    view = study.scored_review(key, visits)
    dated = key.merge(visits[["visit_id", "visit_date"]], on="visit_id")
    assert len(view) == len(study.visits_in_study(dated)) < len(key)
    assert (view["age"] >= study.ANALYSIS_MIN_AGE).all()
    assert (pd.to_datetime(view["visit_date"]) >= pd.Timestamp(study.ANALYSIS_START_DATE)).all()


def test_the_committed_ladder_is_scored_under_the_defaults(key):
    lad = pd.read_csv(DATASETS_DIR / "ladder" / "ladder_vs_truth.csv")
    preds = pd.read_csv(DATASETS_DIR / "ladder" / "ladder_preds.csv")
    visits = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
    n = len(study.scored_review(key, visits))
    assert (lad["n"] == n).all() and len(preds) == n
    assert set(preds["truth"]) <= set(GROUPINGS[DEFAULT_GROUPING])
