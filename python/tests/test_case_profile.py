"""Spec 026 US1: a KEEPER-style case profile for every synthetic visit, structured values only."""

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import case_profile as cp
from health_transformation_lab_nlp import plausibility
from health_transformation_lab_nlp.paths import DATASETS_DIR

CATEGORIES = ["Demographics", "Presentation", "Visit context", "Measurements", "Tests and imaging", "Risk factors",
              "Treatment", "Other readings", "After the visit"]


def _visit(**kw):
    base = {"visit_id": 1, "person_id": 10, "clinic_id": 3, "visit_seq": 0, "visit_date": "2021-01-01", "age": 50,
            "charted": True, "treated_before": False, "cigarettes_per_day": 0, "diabetes": False, "hba1c":
            float("nan"), "rec_max_probing_depth_mm": 5.0, "rec_bop_pct": 35.0, "rec_max_cal_mm": 4.0,
            "rec_rbl_pct": 20.0, "rec_teeth_lost_perio": 0.0, "rec_pct_teeth_involved": 40.0, "notes":
            "periodontitis_stage_2", "exam_form": "periodontitis_stage_2", "proc_codes_completed":
            "periodontitis_stage_2", "proc_codes_planned": "unknown", "proc_dx_completed": "periodontitis_stage_2",
            "proc_dx_planned": "unknown", "probing_chart": "periodontitis_stage_2", "radiograph_ai": "unknown",
            "algorithm_v0": "periodontitis_stage_2", "algorithm_design": "periodontitis_stage_2", "in_review":
            False}
    return base | kw


def _value(profile, visit_id, item):
    row = profile[(profile.visit_id == visit_id) & (profile["item"] == item)]
    assert len(row) == 1, (visit_id, item)
    return row["value"].item()


@pytest.fixture
def two_visits():
    first = _visit()
    later = _visit(visit_id=2, visit_seq=1, visit_date="2021-07-01", proc_dx_completed="periodontitis_stage_1",
                   rec_max_cal_mm=1.0)
    return pd.DataFrame([first, later])


def test_every_visit_gets_the_nine_categories_in_order(two_visits):
    p = cp.build_profiles(two_visits)
    for vid in (1, 2):
        cats = p[p.visit_id == vid].sort_values(["category_order", "item_order"]).category.drop_duplicates()
        assert list(cats) == CATEGORIES


def test_values_are_shown_with_their_units(two_visits):
    p = cp.build_profiles(two_visits)
    assert _value(p, 1, "max attachment loss (CAL)") == "4"
    assert p[(p.visit_id == 1) & (p["item"] == "max attachment loss (CAL)")]["unit"].item() == "mm"
    assert _value(p, 1, "recorded diagnosis code, completed") == "periodontitis_stage_2"
    assert _value(p, 1, "diabetes") == "no"


def test_missing_values_and_unknown_statuses_read_not_recorded():
    v = _visit(charted=False, rec_max_probing_depth_mm=float("nan"), rec_bop_pct=float("nan"),
               rec_max_cal_mm=float("nan"), rec_rbl_pct=float("nan"), rec_teeth_lost_perio=float("nan"),
               rec_pct_teeth_involved=float("nan"), probing_chart="unknown", proc_dx_planned="unknown")
    p = cp.build_profiles(pd.DataFrame([v]))
    assert set(p[p.category == "Measurements"]["value"]) == {cp.NOT_RECORDED}
    assert _value(p, 1, "HbA1c") == cp.NOT_RECORDED
    assert _value(p, 1, "recorded diagnosis code, planned") == cp.NOT_RECORDED
    assert _value(p, 1, "probing chart reading") == cp.NOT_TAKEN


def test_the_last_visit_has_no_later_visit_and_the_earlier_one_shows_what_came_next(two_visits):
    p = cp.build_profiles(two_visits)
    assert _value(p, 2, "next visit's recorded code") == cp.NO_LATER_VISIT
    assert _value(p, 1, "next visit's recorded code") == "periodontitis_stage_1"
    # the later visit's code dropped a stage: the plausibility checks say so, at the next visit
    flags = _value(p, 1, "next visit's plausibility flags")
    expected = plausibility.check_history(cp.history_frame(two_visits), "proc_dx_completed")
    assert flags == ", ".join(f for f in plausibility.FLAGS if expected.loc[expected.visit_id == 2, f].item())
    assert "stage_drop" in flags and "cal_drop" in flags
    assert _value(p, 2, "next visit's plausibility flags") == cp.NO_LATER_VISIT


def test_a_visit_with_a_clean_next_visit_says_none(two_visits):
    v = two_visits.assign(proc_dx_completed="periodontitis_stage_2", rec_max_cal_mm=4.0)
    assert _value(cp.build_profiles(v), 1, "next visit's plausibility flags") == "none"


def test_only_statuses_and_measures_are_read_never_note_text(two_visits):
    p = cp.build_profiles(two_visits)
    # `notes` in visits_structured is the note reader's status, not the note: the profile shows it as a status
    assert _value(p, 1, "note reader") == "periodontitis_stage_2"
    assert p["value"].str.len().max() <= 60
    assert "text" not in " ".join(p.columns)


def test_profile_items_name_their_source_columns():
    cols = {c for _, _, c, _ in cp.PROFILE_ITEMS if c}
    assert cols <= set(_visit())
    assert [c for c in dict.fromkeys(cat for cat, *_ in cp.PROFILE_ITEMS)] == CATEGORIES


def test_the_built_study_has_one_complete_profile_per_visit():
    v = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
    p = cp.build_profiles(v)
    assert p.visit_id.nunique() == len(v)
    per_visit = p.groupby("visit_id").category.nunique()
    assert (per_visit == len(CATEGORIES)).all()
    assert len(p) == len(v) * len(cp.PROFILE_ITEMS)
    assert p["value"].notna().all()


@pytest.mark.parametrize("value, shown", [
    (np.True_, "yes"), (np.False_, "no"), (True, "yes"), (np.int64(3), "3"), (np.float64(2.5), "2.5"),
    (np.float32("nan"), cp.NOT_RECORDED), (pd.NA, cp.NOT_RECORDED), (pd.NaT, cp.NOT_RECORDED), (None, cp.NOT_RECORDED),
    ("unknown", cp.NOT_RECORDED), ("gingivitis", "gingivitis")])
def test_values_show_the_same_whatever_their_numpy_or_pandas_type(value, shown):
    assert cp._shown(value) == shown


def test_the_first_visit_is_visit_1(two_visits):
    p = cp.build_profiles(two_visits)
    assert _value(p, 1, "visit number for the patient") == "1"
    assert _value(p, 2, "visit number for the patient") == "2"


def test_the_next_visit_is_the_next_by_date_as_the_plausibility_checks_order_them(two_visits):
    # visit_seq says visit 2 comes first, but its date is later: the date decides, as in check_history
    v = two_visits.assign(visit_seq=[1, 0])
    p = cp.build_profiles(v)
    assert _value(p, 1, "next visit's recorded code") == "periodontitis_stage_1"
    assert _value(p, 2, "next visit's recorded code") == cp.NO_LATER_VISIT


def test_nullable_dtypes_build_the_same_profiles(two_visits):
    nullable = two_visits.convert_dtypes()
    assert cp.build_profiles(nullable).equals(cp.build_profiles(two_visits))


def test_treatment_items_say_they_are_statuses_read_from_procedure_codes(two_visits):
    items = set(cp.build_profiles(two_visits).query("category == 'Treatment'")["item"])
    assert items == {"status from periodontal procedure codes, completed",
                     "status from periodontal procedure codes, planned"}


# ---------------------------------------------------------------- spec 026 US2: record-mismatch rules

S = "periodontitis_stage_"
RULE_NAMES = ["code_vs_chart", "code_above_chart", "code_below_chart", "no_periodontal_care", "code_vs_radiograph",
              "stage_drop"]


def _fails(visits):
    c = cp.check_rules(pd.DataFrame(visits))
    return {(r.visit_id, r.rule) for r in c.itertuples() if r.outcome == "fail"}


def _outcome(visits, visit_id, rule):
    c = cp.check_rules(pd.DataFrame(visits))
    return c[(c.visit_id == visit_id) & (c.rule == rule)].outcome.item()


def test_the_rules_are_named_and_a_plain_visit_fails_none():
    assert [r for r, *_ in cp.RULES] == RULE_NAMES
    assert _fails([_visit()]) == set()


@pytest.mark.parametrize("rule, kw", [
    ("code_above_chart", {"proc_dx_completed": S + "3", "probing_chart": S + "2", "rec_max_cal_mm": 2.0,
                          "rec_rbl_pct": 10.0, "rec_teeth_lost_perio": 0.0, "rec_max_probing_depth_mm": 4.0}),
    ("code_below_chart", {"proc_dx_completed": "gingivitis", "probing_chart": S + "1", "rec_max_cal_mm": 4.0,
                          "rec_rbl_pct": 10.0}),
    ("no_periodontal_care", {"proc_codes_completed": "unknown", "proc_codes_planned": "healthy"}),
    ("code_vs_chart", {"proc_dx_completed": "healthy", "probing_chart": S + "2", "rec_max_cal_mm": 1.0,
                       "rec_rbl_pct": 5.0}),
    ("code_vs_radiograph", {"proc_dx_completed": "gingivitis", "probing_chart": "gingivitis",
                            "radiograph_ai": S + "3", "rec_max_cal_mm": 1.0, "rec_rbl_pct": 5.0}),
])
def test_each_rule_fires_alone_on_a_visit_built_for_it(rule, kw):
    assert _fails([_visit(**kw)]) == {(1, rule)}


def test_a_stage_drop_fails_at_the_later_visit_and_names_the_earlier_one():
    earlier = _visit(proc_dx_completed=S + "3", probing_chart=S + "3", rec_max_cal_mm=5.0, rec_rbl_pct=30.0)
    later = _visit(visit_id=2, visit_seq=1, visit_date="2021-07-01", proc_dx_completed=S + "1",
                   probing_chart=S + "2", rec_max_cal_mm=5.0, rec_rbl_pct=30.0)
    assert _fails([earlier, later]) == {(2, "stage_drop")}
    c = cp.check_rules(pd.DataFrame([earlier, later]))
    row = c[(c.visit_id == 2) & (c.rule == "stage_drop")]
    assert row.related_visit_id.item() == 1 and "visit 1" in row.evidence.item()


def test_stage_drops_match_the_plausibility_checks_on_the_study():
    v = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
    c = cp.check_rules(v)
    ours = set(c[(c.rule == "stage_drop") & (c.outcome == "fail")].visit_id)
    h = plausibility.check_history(cp.history_frame(v), "proc_dx_completed")
    theirs = set(h[h.stage_drop | h.perio_resolved].visit_id)
    assert ours == theirs and ours


def test_missing_evidence_is_not_checkable_and_a_missing_code_is_no_code():
    no_chart = _visit(charted=False, probing_chart="unknown", rec_max_probing_depth_mm=float("nan"),
                      rec_bop_pct=float("nan"), rec_max_cal_mm=float("nan"), rec_rbl_pct=float("nan"),
                      rec_teeth_lost_perio=float("nan"), rec_pct_teeth_involved=float("nan"))
    for rule in ("code_vs_chart", "code_above_chart", "code_below_chart"):
        assert _outcome([no_chart], 1, rule) == "not_checkable"
    assert _outcome([no_chart], 1, "code_vs_radiograph") == "not_checkable"   # radiograph unknown
    assert _outcome([no_chart], 1, "stage_drop") == "not_checkable"           # no earlier periodontitis code
    assert _outcome([no_chart], 1, "no_periodontal_care") == "pass"
    no_code = _visit(proc_dx_completed="unknown")
    assert {_outcome([no_code], 1, r) for r in RULE_NAMES} == {"no_code"}


def _score_case():
    """Four visits at two clinics, hand-worked. Visit 1: stage III code, chart within stage I (above-chart fail),
    truth stage I, an injected error. Visit 2: stage II code, no care (fail), truth stage II. Visit 3: stage III code
    then visit 4 stage I at the same patient: a stage drop where the earlier code is the wrong one."""
    v = pd.DataFrame([
        _visit(visit_id=1, person_id=1, clinic_id=1, proc_dx_completed=S + "3", probing_chart=S + "2",
               rec_max_cal_mm=2.0, rec_rbl_pct=10.0, rec_teeth_lost_perio=0.0, rec_max_probing_depth_mm=4.0),
        _visit(visit_id=2, person_id=2, clinic_id=2, proc_codes_completed="unknown"),
        _visit(visit_id=3, person_id=3, clinic_id=2, proc_dx_completed=S + "3", probing_chart=S + "2"),
        _visit(visit_id=4, person_id=3, clinic_id=2, visit_seq=1, visit_date="2021-07-01",
               proc_dx_completed=S + "1", probing_chart=S + "1", rec_max_cal_mm=5.0, rec_rbl_pct=30.0),
    ])
    truth = pd.DataFrame({"visit_id": [1, 2, 3, 4], "truth_status": [S + "1", S + "2", S + "1", S + "1"],
                          "record_error": ["decimal_slip", None, None, None]})
    return v, truth


def test_scores_are_counted_over_the_visits_each_rule_can_check():
    v, truth = _score_case()
    s = cp.score_rules(cp.check_rules(v), v, truth).set_index(["rule", "clinic"])
    above = s.loc[("code_above_chart", "All")]
    assert (above.checkable_count, above.flagged_count, above.true_flag_count) == (4, 1, 1)
    assert above.code_truth_mismatch_count == 2          # visits 1 and 3 have codes the truth doesn't share
    assert above.precision == 1.0 and above.recall == 0.5
    assert (above.injected_checkable_count, above.injected_caught_count) == (1, 1)
    care = s.loc[("no_periodontal_care", "All")]
    assert care.flagged_count == 1 and care.true_flag_count == 0 and care.precision == 0.0
    drop = s.loc[("stage_drop", "All")]
    # only visit 4 has an earlier periodontitis code; its drop counts as true because visit 3's code is wrong
    assert (drop.checkable_count, drop.not_checkable_count, drop.flagged_count, drop.true_flag_count) == (1, 3, 1, 1)
    assert s.loc[("code_above_chart", "2")].flagged_count == 0 and s.loc[("code_above_chart", "1")].flagged_count == 1


def test_any_rule_covers_every_coded_visit_and_counts_flags_only_one_rule_made():
    v, truth = _score_case()
    s = cp.score_rules(cp.check_rules(v), v, truth).set_index(["rule", "clinic"])
    a = s.loc[("any_rule", "All")]
    assert (a.checkable_count, a.flagged_count) == (4, 3)
    assert a.true_flag_count == 1                       # visit 1; visit 4's own code is right, visit 2's too
    assert a.only_rule_count == 3                       # each flagged visit fails exactly one rule
    assert s.loc[("code_above_chart", "All")].only_rule_count == 1


def test_every_rule_is_scored_on_the_study_with_its_checkable_count():
    v = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
    truth = pd.read_csv(DATASETS_DIR / "answer_key" / "visits_truth.csv")
    s = cp.score_rules(cp.check_rules(v), v, truth)
    overall = s[s.clinic == "All"].set_index("rule")
    assert list(overall.index) == RULE_NAMES + ["any_rule"]
    assert (overall.checkable_count > 0).all() and (overall.flagged_count > 0).all()
    assert overall.loc["any_rule", "checkable_count"] == (v.proc_dx_completed != "unknown").sum()
    assert overall.loc["any_rule", "injected_checkable_count"] == 34


@pytest.mark.parametrize("kw, fails", [
    # code_above_chart: CAL < 3, bone loss < 15, PD < 6, no tooth lost; each edge sits outside
    ({"rec_max_cal_mm": 2.9}, True), ({"rec_max_cal_mm": 3.0}, False),
    ({"rec_rbl_pct": 14.9}, True), ({"rec_rbl_pct": 15.0}, False),
    ({"rec_max_probing_depth_mm": 5.9}, True), ({"rec_max_probing_depth_mm": 6.0}, False),
    ({"rec_teeth_lost_perio": 1.0}, False),
])
def test_code_above_chart_at_its_thresholds(kw, fails):
    base = {"proc_dx_completed": S + "3", "probing_chart": S + "2", "rec_max_cal_mm": 2.0, "rec_rbl_pct": 10.0,
            "rec_teeth_lost_perio": 0.0, "rec_max_probing_depth_mm": 4.0}
    assert _outcome([_visit(**(base | kw))], 1, "code_above_chart") == ("fail" if fails else "pass")


@pytest.mark.parametrize("kw, fails", [
    # code_below_chart: CAL >= 3 or bone loss >= 15; each edge sits inside
    ({"rec_max_cal_mm": 2.9}, False), ({"rec_max_cal_mm": 3.0}, True),
    ({"rec_rbl_pct": 14.9}, False), ({"rec_rbl_pct": 15.0}, True),
])
def test_code_below_chart_at_its_thresholds(kw, fails):
    base = {"proc_dx_completed": "gingivitis", "probing_chart": S + "1", "rec_max_cal_mm": 1.0, "rec_rbl_pct": 5.0}
    assert _outcome([_visit(**(base | kw))], 1, "code_below_chart") == ("fail" if fails else "pass")


@pytest.mark.parametrize("chart, fails", [(S + "1", False), ("gingivitis", True)])
def test_code_vs_chart_allows_one_step(chart, fails):
    assert _outcome([_visit(probing_chart=chart)], 1, "code_vs_chart") == ("fail" if fails else "pass")


def test_each_mismatch_row_carries_how_many_rules_its_visit_fails(two_visits):
    v = pd.DataFrame([_visit(proc_dx_completed="healthy", probing_chart=S + "2", rec_max_cal_mm=4.0,
                             radiograph_ai=S + "3")])
    m = cp.record_mismatches(cp.check_rules(v), v, pd.DataFrame({"visit_id": [1], "record_error": [None]}))
    assert set(m.rule) == {"code_vs_chart", "code_below_chart", "code_vs_radiograph"}
    assert set(m.failed_rule_count) == {3}
    assert list(m.columns) == ["visit_id", "rule", "rule_label", "evidence", "related_visit_id", "failed_rule_count",
                               "clinic", "injected_error"]
