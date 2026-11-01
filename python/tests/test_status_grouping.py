"""Spec 032 US1 (#440): scores and prevalence at a chosen status grouping (six, five or three groups).
R twins: r/R/labels.R (group_status), eval/score.R (score_run), r/R/06_validation.R (prevalence_by_group)."""

import math
import sys

import pandas as pd
import pytest

from health_transformation_lab_nlp.labels import GROUPINGS, LABELS, group_status
from health_transformation_lab_nlp.paths import REPO_ROOT
from health_transformation_lab_nlp.prevalence import prevalence_by_group

sys.path.insert(0, str(REPO_ROOT / "eval"))
from score import score  # noqa: E402

H, G, S1, S2, S3, S4 = LABELS


def test_groupings_name_their_groups_in_order():
    assert list(GROUPINGS) == ["six", "five", "three"]
    assert GROUPINGS["six"] == tuple(LABELS)
    assert GROUPINGS["five"] == ("healthy_or_gingivitis", S1, S2, S3, S4)
    assert GROUPINGS["three"] == ("healthy_or_gingivitis", "mild", "severe")


@pytest.mark.parametrize("grouping,expected", [
    ("six", [H, G, S1, S2, S3, S4]),
    ("five", ["healthy_or_gingivitis", "healthy_or_gingivitis", S1, S2, S3, S4]),
    ("three", ["healthy_or_gingivitis", "healthy_or_gingivitis", "mild", "mild", "severe", "severe"]),
])
def test_group_status_maps_each_status(grouping, expected):
    assert [group_status(s, grouping) for s in LABELS] == expected


def test_no_answer_and_unknown_values_stay_as_they_are():
    for g in GROUPINGS:
        assert group_status(None, g) is None
        assert group_status("", g) == ""
        assert group_status("unknown", g) == "unknown"
        assert math.isnan(group_status(float("nan"), g))


def test_a_source_that_cannot_separate_healthy_from_gingivitis_merges_and_grouping_is_idempotent():
    assert group_status("healthy_gingivitis", "five") == "healthy_or_gingivitis"
    assert group_status("healthy_gingivitis", "three") == "healthy_or_gingivitis"
    assert group_status("healthy_gingivitis", "six") == "healthy_gingivitis"
    for g in GROUPINGS:
        for s in LABELS:
            assert group_status(group_status(s, g), g) == group_status(s, g)


def test_unknown_grouping_fails_naming_the_choices():
    with pytest.raises(ValueError, match="six"):
        group_status(H, "four")


Y_TRUE = [H, G, S1, S2, S3, S4, G, S4]
Y_PRED = [G, H, S2, S1, S4, S3, "none", S4]


def _f1(res):
    return res[res.metric == "f1"].set_index("class")["value"]


def _binary(res):
    return res[res["class"] == ""].set_index("metric")["value"]


def test_the_standalone_scorer_groups_exactly_as_labels_does():
    import score as eval_score
    assert {k: tuple(v) for k, v in eval_score.GROUPINGS.items()} == GROUPINGS
    for g in GROUPINGS:
        for s in [*LABELS, "healthy_gingivitis", "unknown", "none"]:
            assert eval_score._GROUP_OF[g].get(s, s) == group_status(s, g)


def test_score_rejects_an_unknown_grouping():
    with pytest.raises(ValueError, match="three"):
        score(Y_TRUE, Y_PRED, None, "t", grouping="two")


def test_score_default_is_the_six_status_score():
    a = score(Y_TRUE, Y_PRED, None, "t", run_id="r")
    b = score(Y_TRUE, Y_PRED, None, "t", run_id="r", grouping="six")
    pd.testing.assert_frame_equal(a.drop(columns="timestamp"), b.drop(columns="timestamp"))
    assert list(a.loc[a.metric == "f1", "class"]) == list(LABELS)


def test_score_at_five_and_three_groups():
    five = score(Y_TRUE, Y_PRED, None, "t", grouping="five")
    assert list(_f1(five).index) == list(GROUPINGS["five"])
    # healthy <-> gingivitis swaps are right once merged: truth 3 h-or-g, pred 2 (one "none"), both right -> 0.8
    assert _f1(five)["healthy_or_gingivitis"] == pytest.approx(0.8)
    three = score(Y_TRUE, Y_PRED, None, "t", grouping="three")
    assert list(_f1(three).index) == list(GROUPINGS["three"])
    # a stage I <-> II or III <-> IV swap is right at three groups
    assert _f1(three)["mild"] == 1.0 and _f1(three)["severe"] == 1.0
    assert three.loc[three.metric == "macro_f1", "value"].item() == pytest.approx((0.8 + 1 + 1) / 3)
    # periodontitis yes/no is the same at every grouping
    six = score(Y_TRUE, Y_PRED, None, "t")
    for k in ("sensitivity", "specificity", "ppv", "npv"):
        assert _binary(five)[k] == _binary(six)[k] == _binary(three)[k]


def test_prevalence_by_group_at_three_groups():
    v = pd.DataFrame({"person_id": [1, 1, 2, 3, 4, 5], "clinic_id": [1, 1, 1, 2, 2, 2],
                      "visit_date": ["2021-01-01", "2021-07-01", "2021-03-01", "2021-02-01", "2021-02-01",
                                     "2021-02-01"],
                      "status": [G, S3, H, S1, "unknown", "healthy_gingivitis"]})
    t = prevalence_by_group(v, "status", grouping="three").set_index("status_group")
    assert list(t.index) == list(GROUPINGS["three"])
    assert (t["n_people"] == 4).all() and (t["n_unknown"] == 1).all()
    assert t.loc["healthy_or_gingivitis", "share"] == 0.5          # persons 2 and 5
    assert t.loc["mild", "share"] == 0.25 and t.loc["severe", "share"] == 0.25
    assert t["share_ci_low"].le(t["share"]).all() and t["share_ci_high"].ge(t["share"]).all()
    c = prevalence_by_group(v, "status", grouping="five", by="clinic_id")
    assert set(c["clinic_id"]) == {1, 2} and len(c) == 2 * 5
    six = prevalence_by_group(v, "status").set_index("status_group")
    assert list(six.index) == list(LABELS)
    # at six, a source that only says "healthy or gingivitis" counts as known but in neither group
    assert six.loc[H, "share"] == 0.25 and six.loc[G, "share"] == 0
