"""Spec 024 US1: the PerioDx Diagnoser (Patel et al. 2022, Fig. 2), one hand-built chart per branch of the figure.

Every chart here is synthetic. Statuses are the figure's own boxes; `label` maps them to the six labels the
benchmark scores (healthy, gingivitis, periodontitis stage I-IV)."""

import dataclasses

import pytest

from health_transformation_lab_nlp import periodx as px

AGE = 50


def chart(**kw):
    """A chart that answers no to every entry question, with BOP 5%; override what a branch needs."""
    base = {"bop_pct": 5.0, "max_pd_mm": 3.0, "bone_loss_pct": 0.0, "max_cal_mm": 0.0, "interproximal_cal_teeth": 0,
                "recession_teeth": 0, "cal5_adjacent_teeth": 0, "pd5_adjacent_teeth": 0, "furcation_class": 0,
                "vertical_bone_loss_mm": 0.0, "occluding_pairs": 14, "mobility2_teeth": 0, "complex_rehab": False,
                "teeth_lost_perio": 0, "pct_teeth_involved": 10.0}
    base.update(kw)
    return px.PerioDxChart(**base)


def perio(**kw):
    """A periodontitis case: bone loss detectable and a 5 mm pocket; stage I measures unless overridden."""
    base = {"bop_pct": 20.0, "max_pd_mm": 4.0, "bone_loss_pct": 10.0, "max_cal_mm": 2.0, "interproximal_cal_teeth": 0}
    base.update(kw)
    return chart(**base)


def run(c, age=AGE, cigarettes_per_day=0, diabetes=False, hba1c=None):
    return px.chart_status(c, age=age, cigarettes_per_day=cigarettes_per_day, diabetes=diabetes, hba1c=hba1c)


# ---------------------------------------------------------------- entry: health and gingivitis

@pytest.mark.parametrize("bop, status, label", [
    (5.0, px.HEALTH, "healthy"),
    (10.0, px.LOCALIZED_GINGIVITIS, "gingivitis"),
    (25.0, px.LOCALIZED_GINGIVITIS, "gingivitis"),        # acceptance scenario 1
    (30.0, px.LOCALIZED_GINGIVITIS, "gingivitis"),
    (30.5, px.GENERALIZED_GINGIVITIS, "gingivitis"),
])
def test_no_to_all_three_entry_questions_bop_decides(bop, status, label):
    f = run(chart(bop_pct=bop, bone_loss_pct=0.0))
    assert (f.status, f.label, f.stage, f.grade, f.extent) == (status, label, None, "NA", "NA")
    assert f.section == "M3"


@pytest.mark.parametrize("entry", [{"bone_loss_pct": 5.0}, {"interproximal_cal_teeth": 2, "max_cal_mm": 3.0},
                                   {"recession_teeth": 2}])
def test_yes_to_any_entry_question_without_a_4mm_pocket_is_a_reduced_periodontium(entry):
    healthy = run(chart(bop_pct=5.0, max_pd_mm=3.5, **entry))
    inflamed = run(chart(bop_pct=10.0, max_pd_mm=3.5, **entry))
    assert (healthy.status, healthy.label) == (px.REDUCED_HEALTHY, "healthy")
    assert (inflamed.status, inflamed.label) == (px.GINGIVAL_INFLAMMATION, "gingivitis")


def test_one_tooth_with_cal_over_2mm_is_not_enough_to_enter():
    f = run(chart(interproximal_cal_teeth=1, max_cal_mm=3.0, bone_loss_pct=0.0, max_pd_mm=5.0, bop_pct=20.0))
    assert f.status == px.LOCALIZED_GINGIVITIS


def test_yes_to_any_entry_question_and_a_4mm_pocket_is_periodontitis():
    f = run(perio())
    assert (f.status, f.stage, f.label) == (px.PERIODONTITIS, 1, "periodontitis_stage_1")


# ---------------------------------------------------------------- stage

@pytest.mark.parametrize("criterion", [{"bone_loss_pct": 40.0}, {"cal5_adjacent_teeth": 2, "max_cal_mm": 5.0},
                                       {"furcation_class": 2}, {"vertical_bone_loss_mm": 3.0},
                                       {"pd5_adjacent_teeth": 2, "max_pd_mm": 6.0}])
def test_each_stage_iii_iv_criterion_with_no_complexity_and_no_tooth_loss_is_the_dead_end_default(criterion):
    f = run(perio(**criterion))
    assert f.stage == px.III_IV_NO_TOOTH_LOSS == 3


def test_fewer_than_10_occluding_pairs_gives_stage_iv():
    assert run(perio(bone_loss_pct=40.0, occluding_pairs=9)).stage == 4
    assert run(perio(bone_loss_pct=40.0, occluding_pairs=10)).stage == 3


def test_occlusal_trauma_at_5_or_more_teeth_gives_stage_iv():
    assert run(perio(bone_loss_pct=40.0, mobility2_teeth=5)).stage == 4
    assert run(perio(bone_loss_pct=40.0, mobility2_teeth=4)).stage == 3


def test_drifting_bite_collapse_flaring_or_ridge_defect_gives_stage_iv():
    assert run(perio(bone_loss_pct=40.0, complex_rehab=True)).stage == 4


def test_complexity_factors_count_only_after_a_stage_iii_iv_criterion():
    assert run(perio(occluding_pairs=6, mobility2_teeth=8, complex_rehab=True)).stage == 1


def test_acceptance_2_bone_loss_40_12_pairs_two_teeth_lost_is_stage_iii():
    f = run(perio(bone_loss_pct=40.0, occluding_pairs=12, mobility2_teeth=0, complex_rehab=False,
                  teeth_lost_perio=2))
    assert (f.stage, f.label) == (3, "periodontitis_stage_3")


def test_acceptance_3_tooth_loss_is_checked_before_stage_i_or_ii():
    f = run(perio(bone_loss_pct=10.0, teeth_lost_perio=2))
    assert f.stage == 3


@pytest.mark.parametrize("lost, stage", [(1, 3), (4, 3), (5, 4), (9, 4)])
def test_teeth_lost_to_periodontitis(lost, stage):
    assert run(perio(teeth_lost_perio=lost)).stage == stage
    assert run(perio(bone_loss_pct=40.0, teeth_lost_perio=lost)).stage == stage


@pytest.mark.parametrize("kw, stage", [
    ({"bone_loss_pct": 10.0, "max_pd_mm": 4.0, "max_cal_mm": 2.0}, 1),
    ({"bone_loss_pct": 20.0, "max_pd_mm": 4.0, "max_cal_mm": 2.0}, 2),     # BL 15-33 is a stage II measure
    ({"bone_loss_pct": 10.0, "max_pd_mm": 5.0, "max_cal_mm": 2.0}, 2),     # PD 5 mm
    ({"bone_loss_pct": 10.0, "max_pd_mm": 4.0, "max_cal_mm": 3.0}, 2),     # CAL 3-4 mm
    ({"bone_loss_pct": 10.0, "max_pd_mm": 6.0, "max_cal_mm": 6.0}, 2),     # worse than II, but not at 2+ adjacent teeth
])
def test_bone_loss_box_meeting_stage_i_and_ii_measures_goes_to_the_higher_stage(kw, stage):
    assert run(perio(**kw)).stage == stage


# ---------------------------------------------------------------- extent

@pytest.mark.parametrize("pct, extent", [(29.9, "localized"), (30.0, "generalized"), (80.0, "generalized")])
def test_extent_is_localized_under_30_percent(pct, extent):
    assert run(perio(pct_teeth_involved=pct)).extent == extent


def test_molar_incisor_pattern():
    assert run(perio(molar_incisor=True)).extent == "molar_incisor"


@pytest.mark.parametrize("stage, cal, pd, involved", [
    (3, 5, 4, True), (3, 4, 6, True), (3, 4, 5, False), (3, 6, 3, False),
    (4, 5, 4, True),
    (2, 3, 4, True), (2, 4, 5, True), (2, 2, 5, True), (2, 2, 4, False), (2, 3, 6, False),
    (1, 1, 4, True), (1, 2, 4, True), (1, 2, 5, False), (1, 3, 4, False),
])
def test_a_tooth_is_involved_by_the_pairs_of_its_cases_stage(stage, cal, pd, involved):
    assert px.tooth_involved(stage, cal, pd) is involved


def test_share_of_teeth_involved_counts_teeth_lost_to_periodontitis():
    teeth = [(5, 4), (5, 4), (1, 2), (1, 2), (1, 2), (1, 2)]   # 2 of 6 present teeth involved at stage III
    assert px.pct_teeth_involved(3, teeth, teeth_lost_perio=2) == pytest.approx(100 * 4 / 8)


# ---------------------------------------------------------------- grade

@pytest.mark.parametrize("bl, age, cig, dm, a1c, grade", [
    (10.0, 50, 0, False, None, "A"),        # ratio 0.2, non-smoker, no diabetes
    (10.0, 50, 15, False, None, "C"),       # current smoker >= 10/day
    (10.0, 50, 5, False, None, "B"),        # smoker < 10/day, HbA1c box: no reading -> no
    (10.0, 50, 5, True, 7.5, "C"),          # smoker < 10/day with HbA1c >= 7.0
    (10.0, 50, 0, True, 6.8, "B"),          # non-smoker with diabetes, HbA1c < 7.0
    (10.0, 50, 0, True, 7.0, "C"),
    (25.0, 50, 0, False, None, "B"),        # ratio 0.5 enters at ">= 10 per day": never A
    (25.0, 50, 12, False, None, "C"),
    (25.0, 50, 0, True, 8.0, "C"),
    (40.0, 30, 0, False, None, "C"),        # ratio > 1.0
    (50.0, 50, 0, False, None, "B"),        # ratio exactly 1.0 is in the middle band
    (12.5, 50, 0, False, None, "B"),        # ratio exactly 0.25 is in the middle band
])
def test_grade_follows_bone_loss_over_age_then_smoking_then_hba1c(bl, age, cig, dm, a1c, grade):
    f = run(perio(bone_loss_pct=bl), age=age, cigarettes_per_day=cig, diabetes=dm, hba1c=a1c)
    assert f.grade == grade


@pytest.mark.parametrize("bl, age", [(None, 50), (10.0, None), (10.0, 0)])
def test_grade_without_age_or_bone_loss_is_not_assessable_not_a_default_b(bl, age):
    c = perio(bone_loss_pct=bl, interproximal_cal_teeth=2, max_cal_mm=3.0)
    assert run(c, age=age).grade == px.NOT_ASSESSABLE


def test_grade_is_na_when_not_periodontitis():
    assert run(chart(bop_pct=20.0)).grade == "NA"


# ---------------------------------------------------------------- bone loss as the form's categories

@pytest.mark.parametrize("band, stage", [("<15", 1), ("15-33", 2), (">33", 3)])
def test_bone_loss_categories_are_accepted(band, stage):
    assert run(perio(bone_loss_pct=band)).stage == stage


def test_a_category_grades_only_when_its_whole_range_falls_in_one_band():
    assert run(perio(bone_loss_pct="<15"), age=70).grade == "A"          # 0-15 / 70 < 0.25
    assert run(perio(bone_loss_pct="<15"), age=40).grade == px.NOT_ASSESSABLE   # 0.0 to 0.375 spans two bands
    assert run(perio(bone_loss_pct=">33"), age=30).grade == "C"          # > 1.1


def test_an_unknown_category_is_refused():
    with pytest.raises(ValueError):
        perio(bone_loss_pct="moderate")


# ---------------------------------------------------------------- missing inputs: fallback, counted as partial

def test_missing_inputs_use_the_documented_fallback_and_mark_the_finding_partial():
    full = run(perio(bone_loss_pct=40.0))
    assert full.partial == ()
    f = run(perio(bone_loss_pct=40.0, occluding_pairs=None, mobility2_teeth=None, complex_rehab=None))
    assert f.stage == 3 and set(f.partial) == {"occluding_pairs", "mobility2_teeth", "complex_rehab"}


def test_a_criterion_that_already_holds_makes_the_missing_ones_irrelevant():
    f = run(perio(bone_loss_pct=40.0, furcation_class=None, vertical_bone_loss_mm=None))
    assert f.partial == ()
    g = run(perio(furcation_class=None))
    assert "furcation_class" in g.partial


def test_every_fig2_constant_cites_the_figure():
    import inspect
    src = inspect.getsource(px)
    for name in px.FIG2_CONSTANTS:
        line = next(ln for ln in src.splitlines() if ln.startswith(f"{name} ="))
        assert "Fig. 2" in line or "Fig. 2" in src.split(f"{name} =")[0].splitlines()[-1], name


# ---------------------------------------------------------------- the repo's summary chart

def test_summary_chart_counts_the_worst_site_at_the_teeth_with_attachment_loss():
    c = px.chart_from_summary(max_pd_mm=6.4, bop_pct=40.0, max_cal_mm=5.5, rbl_pct=38.0, teeth_lost_perio=2,
                              pct_teeth_involved=50.0)
    n = 13                                              # round(50% of the 26 teeth present)
    assert (c.interproximal_cal_teeth, c.cal5_adjacent_teeth, c.pd5_adjacent_teeth) == (n, n, n)
    assert c.recession_teeth is None and c.occluding_pairs is None and c.furcation_class is None
    assert c.pct_teeth_involved == pytest.approx(100 * (n + 2) / 28)
    assert c.bone_loss_pct == 38.0


def test_summary_chart_below_the_thresholds_counts_no_teeth():
    c = px.chart_from_summary(max_pd_mm=3.0, bop_pct=12.0, max_cal_mm=2.0, rbl_pct=8.0, teeth_lost_perio=0,
                              pct_teeth_involved=20.0)
    assert (c.interproximal_cal_teeth, c.cal5_adjacent_teeth, c.pd5_adjacent_teeth) == (0, 0, 0)


def test_summary_chart_from_a_visits_row_returns_none_when_not_charted():
    import pandas as pd
    row = pd.Series({"charted": False, "rec_max_probing_depth_mm": float("nan")})
    assert px.chart_from_row(row) is None
    row = pd.Series({"charted": True, "rec_max_probing_depth_mm": 4.2, "rec_bop_pct": 20.0, "rec_max_cal_mm": 1.5,
                     "rec_rbl_pct": 9.0, "rec_teeth_lost_perio": 0.0, "rec_pct_teeth_involved": 20.0})
    assert px.chart_from_row(row) == px.chart_from_summary(4.2, 20.0, 1.5, 9.0, 0, 20.0)


def test_finding_is_frozen_and_records_its_section():
    f = run(perio())
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.stage = 2
