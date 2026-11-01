"""Spec 029 US3 (#371): the tooth-level model, P(tooth lost to periodontitis), and the stage recount.

Follows specs/029-tooth-loss/analysis_plan.md: feature sets (section 5), the two label sets (FR-010, section 4), the
70/30 split by patient stratified on the outcome (section 9), the metrics on hand-worked cases (section 10) and the
expected-count stage rule (labels.stage4_rule). Hand-built tooth tables and a small seeded synthetic extract only."""
import math

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import labels
from health_transformation_lab_nlp import open_dental as od
from health_transformation_lab_nlp import tooth_loss as tl
from health_transformation_lab_nlp import tooth_loss_model as tm


def _teeth(rows):
    """rows: (patient_id, tooth_num, tooth_status_code, age); other columns filled with plain values."""
    t = pd.DataFrame(rows, columns=["patient_id", "tooth_num", "tooth_status_code", "age_at_first_exam_num"])
    label = t["tooth_status_code"].map({"extracted_perio": True, "planned_perio": True, "extracted_other": False,
                                        "planned_other": False})
    t["is_perio_loss"] = label.astype("boolean")
    t["loss_date"] = pd.NaT
    for c in tl.COLUMNS:
        if c not in t:
            t[c] = np.nan
    t["tooth_type_code"] = t["tooth_num"].map(tl._tooth_type)
    t["is_smoker"], t["is_diabetic"] = False, False
    return t[tl.COLUMNS]


# ---------- feature sets (analysis plan section 5)

def test_the_shared_design_matrix_has_no_own_measures_and_fixed_columns():
    t = _teeth([(1, 3, "extracted_perio", 50), (1, 8, "missing_at_entry", 50)])
    shared, own = tm.design_matrix(t, "shared"), tm.design_matrix(t, "own")
    assert not any(c.startswith("last_") for c in shared.columns)
    assert any(c.startswith("last_") for c in own.columns) and set(shared.columns) < set(own.columns)
    # one-hot columns for every tooth type, whatever the rows hold, so train and applied sets line up
    assert {f"tooth_type_code={k}" for k in tm.TOOTH_TYPES} <= set(shared.columns)
    assert shared.dtypes.map(lambda d: d.kind == "f").all()


def test_the_answer_key_and_the_label_are_never_features():
    cols = set(tm.design_matrix(_teeth([(1, 3, "extracted_perio", 50)]), "own").columns)
    for banned in ("true_reason_code", "is_perio_loss", "tooth_status_code", "label_source_code", "dx_def_id",
                   "patient_id", "tooth_num", "loss_date"):
        assert not any(c.split("=")[0] == banned for c in cols), banned


# ---------- label sets (FR-010) and who is in them (sections 3, 4)

def test_the_two_label_sets_completed_and_completed_plus_planned():
    t = _teeth([(1, 3, "extracted_perio", 50), (1, 4, "extracted_other", 50), (1, 5, "planned_perio", 50),
                (1, 6, "planned_other", 50), (1, 7, "extracted_no_dx", 50), (1, 8, "missing_at_entry", 50),
                (1, 9, "present", 50)])
    done = tm.label_set(t, "completed")
    both = tm.label_set(t, "completed_planned")
    assert sorted(done["tooth_num"]) == [3, 4]
    assert sorted(both["tooth_num"]) == [3, 4, 5, 6]
    assert both["is_perio_loss"].tolist() == [True, False, True, False]
    with pytest.raises(ValueError, match="label set"):
        tm.label_set(t, "everything")


def test_third_molars_are_left_out_by_default_and_the_minimum_age_is_a_parameter():
    t = _teeth([(1, 1, "extracted_perio", 15), (1, 3, "extracted_perio", 15), (2, 3, "extracted_other", 40),
                (2, 32, "missing_at_entry", 40)])
    every_year = tm.ModelParams(start_date=None)               # these teeth carry no dates
    assert len(tm.eligible(t, tm.ModelParams(min_age=None, include_third_molars=True, start_date=None))) == 4
    assert tm.ModelParams().min_age == 18                      # adults only (analysis plan s. 3)
    assert tm.eligible(t, every_year)["patient_id"].tolist() == [2]       # the 15-year-old is out
    no_cut = tm.ModelParams(min_age=None, start_date=None)
    assert sorted(tm.eligible(t, no_cut)["tooth_num"]) == [3, 3]   # sensitivity: no cut-off



def test_the_teeth_left_out_are_counted_by_reason_including_an_unknown_age():
    # a tooth whose age isn't recorded is left out once a cut-off applies: say how many, so a real run reports it
    t = _teeth([(1, 1, "extracted_perio", 40), (1, 3, "extracted_perio", 15), (2, 3, "extracted_other", 40),
                (3, 4, "missing_at_entry", None)])
    every_year = tm.ModelParams(start_date=None)               # these teeth carry no dates
    out = tm.exclusions(t, every_year)
    assert out == {"third_molar_count": 1, "under_min_age_count": 1, "unknown_age_count": 1,
                   "before_start_date_count": 0, "unknown_date_count": 0, "eligible_count": 1}
    assert tm.exclusions(t, tm.ModelParams(min_age=None, start_date=None))["unknown_age_count"] == 0
    assert out["eligible_count"] == len(tm.eligible(t, every_year))


def test_a_start_date_leaves_out_teeth_lost_or_first_charted_before_it():
    # spec 032 US2 (#441): the date is the loss date, or the first exam date when the loss date isn't recorded
    t = _teeth([(1, 3, "extracted_perio", 40), (1, 4, "extracted_other", 40), (2, 3, "missing_at_entry", 40),
                (3, 3, "missing_at_entry", 40), (4, 3, "missing_at_entry", 40)])
    t["loss_date"] = pd.to_datetime(["2019-06-01", "2021-03-01", None, None, None])
    t["first_exam_date"] = pd.to_datetime(["2018-01-01", "2018-01-01", "2019-12-31", "2020-01-01", None])
    assert tm.ModelParams().start_date == "2018-01-01"         # the default since spec 032 US8 (#448)
    every_year = tm.ModelParams(start_date=None)
    assert len(tm.eligible(t, every_year)) == 5
    params = tm.ModelParams(start_date="2020-01-01")
    kept = tm.eligible(t, params)
    assert list(zip(kept["patient_id"], kept["tooth_num"])) == [(1, 4), (3, 3)]
    out = tm.exclusions(t, params)
    assert out["before_start_date_count"] == 2 and out["unknown_date_count"] == 1
    assert out["eligible_count"] == 2 == len(kept)
    none = tm.exclusions(t, every_year)
    assert none["before_start_date_count"] == 0 and none["unknown_date_count"] == 0
    assert tm.exclusions(t)["unknown_date_count"] == 1          # the default date: the undated tooth is out


def test_the_start_date_applies_after_the_age_cut_and_counts_each_tooth_once():
    t = _teeth([(1, 3, "extracted_perio", 15), (2, 3, "extracted_other", 40)])
    t["loss_date"] = pd.to_datetime(["2010-01-01", "2010-01-01"])
    out = tm.exclusions(t, tm.ModelParams(start_date="2020-01-01"))
    assert out["under_min_age_count"] == 1 and out["before_start_date_count"] == 1 and out["eligible_count"] == 0


def test_a_run_with_a_start_date_reads_the_first_exam_date_from_the_extract():
    tables, _, readings = od.build_with_readings(od.Params(n_patients=150), 3)
    x = {**od.clean(tables), "radiograph_bone_level": readings}
    teeth = tm.with_first_exam_date(tl.tooth_table(x), x)
    exams = x["perioexam"]
    first = pd.to_datetime(exams["examdate"]).groupby(pd.to_numeric(exams["patnum"])).min()
    charted = teeth[teeth["patient_id"].isin(first.index)]
    assert len(charted) > 0
    assert (charted["first_exam_date"].to_numpy() == charted["patient_id"].map(first).to_numpy()).all()

# ---------- the split (section 9)

def test_the_split_is_by_patient_stratified_and_seeded():
    rng = np.random.default_rng(0)
    rows = []
    for p in range(200):
        perio = p % 4 == 0                                  # a quarter of the patients lose teeth to periodontitis
        for tooth in rng.choice(range(2, 16), size=3, replace=False):
            rows.append((p, int(tooth), "extracted_perio" if perio else "extracted_other", 50))
    t = _teeth(rows)
    test = tm.split_patients(t, test_share=0.3, seed=7)
    assert test == tm.split_patients(t, test_share=0.3, seed=7)          # seeded
    assert test != tm.split_patients(t, test_share=0.3, seed=8)
    assert len(test) == 60                                                  # 30% of the patients
    held = t["patient_id"].isin(test)
    assert not set(t.loc[held, "patient_id"]) & set(t.loc[~held, "patient_id"])   # no patient on both sides
    assert t.loc[held, "is_perio_loss"].mean() == pytest.approx(0.25, abs=0.02)    # stratified on the outcome


# ---------- metrics (section 10), worked by hand

Y = np.array([0, 0, 1, 1, 0, 1])
P = np.array([0.1, 0.4, 0.35, 0.8, 0.6, 0.9])


def test_auc_counts_correctly_ordered_pairs_and_ties_half():
    # positives 0.35, 0.8, 0.9 vs negatives 0.1, 0.4, 0.6: 0.35 beats 1, 0.8 and 0.9 beat 3 each -> 7 / 9
    assert tm.auc(Y, P) == pytest.approx(7 / 9)
    assert tm.auc([0, 1], [0.5, 0.5]) == 0.5
    assert math.isnan(tm.auc([1, 1], [0.2, 0.3]))


def test_brier_is_the_mean_squared_error_of_the_probability():
    assert tm.brier(Y, P) == pytest.approx(np.mean((P - Y) ** 2))
    assert tm.brier([1, 0], [1.0, 0.0]) == 0.0


def test_sensitivity_specificity_and_predictive_values_at_a_threshold():
    m = tm.classification(Y, P, 0.5)       # predicted positive: 0.8, 0.6, 0.9 -> tp 2, fp 1, fn 1, tn 2
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 2)
    assert m["sensitivity"] == pytest.approx(2 / 3) and m["specificity"] == pytest.approx(2 / 3)
    assert m["ppv"] == pytest.approx(2 / 3) and m["npv"] == pytest.approx(2 / 3)
    assert math.isnan(tm.classification([0, 0], [0.1, 0.2], 0.5)["sensitivity"])   # no positives: NaN, never 0


def test_youden_threshold_is_the_smallest_probability_with_the_best_j():
    # at 0.35: tp 3, fp 2 -> J = 1 + 1/3 - 1 = 1/3; at 0.8: tp 2, fp 0 -> J = 2/3 (best); 0.9: J = 1/3
    assert tm.youden_threshold(Y, P) == 0.8
    assert tm.youden_threshold([0, 1, 1], [0.2, 0.7, 0.7]) == 0.7


def test_calibration_slope_and_intercept_are_the_logistic_recalibration_fits():
    rng = np.random.default_rng(3)
    p = rng.uniform(0.05, 0.95, 4000)
    lp = np.log(p / (1 - p))
    y = (rng.uniform(size=p.size) < 1 / (1 + np.exp(-(0.5 + 0.5 * lp)))).astype(int)   # true slope 0.5
    a, b = tm.calibration_slope(y, p)
    assert b == pytest.approx(0.5, abs=0.08) and a == pytest.approx(0.5, abs=0.12)
    # the score equations hold at the fit: sum(y - mu) = 0 and sum((y - mu) * lp) = 0
    mu = 1 / (1 + np.exp(-(a + b * lp)))
    assert abs((y - mu).sum()) < 1e-6 and abs(((y - mu) * lp).sum()) < 1e-6
    # the intercept with the slope fixed at 1 (offset): observed = expected events
    c = tm.calibration_intercept(y, p)
    assert abs((y - 1 / (1 + np.exp(-(c + lp)))).sum()) < 1e-6
    assert math.isnan(tm.calibration_slope([0, 1, 1], [0.4, 0.4, 0.4])[1])         # no spread: no slope


def test_the_calibration_table_has_ten_equal_bins():
    tab = tm.calibration_table(Y, P)
    assert list(tab["bin_num"]) == list(range(10)) and tab["tooth_count"].sum() == len(Y)
    row = tab.set_index("bin_num").loc[3]                  # 0.35 only
    assert row["tooth_count"] == 1 and row["mean_predicted_ratio"] == pytest.approx(0.35)
    assert row["observed_ratio"] == 1.0
    assert tab.set_index("bin_num").loc[9, "tooth_count"] == 1      # 0.9 lands in the last bin, not past it


def test_the_bootstrap_resamples_patients_not_teeth():
    pats = np.array([1, 1, 1, 2, 2, 3])
    for idx in tm.patient_bootstrap(pats, n_boot=20, seed=0):
        drawn = pd.Series(pats[idx]).value_counts()
        size = pd.Series(pats).value_counts()
        assert all(drawn[p] % size[p] == 0 for p in drawn.index)     # whole patients, each 0..k times


# ---------- the stage recount (labels.stage4_rule)

def test_expected_perio_loss_is_recorded_losses_plus_the_probabilities_of_the_unlabelled_teeth():
    assert labels.expected_perio_loss(3, [0.5, 0.75, 0.25]) == pytest.approx(4.5)
    assert labels.expected_perio_loss(0, []) == 0.0


def test_stage4_rule_counts_teeth_by_each_rule_and_calls_iv_at_five():
    kw = {"recorded_perio": 2, "missing": 6, "unlabelled_probs": [0.9, 0.9, 0.9, 0.29], "true_perio": 5}
    assert labels.stage4_rule("recorded_only", **kw) is False
    assert labels.stage4_rule("every_missing", **kw) is True
    assert labels.stage4_rule("expected_perio_loss", **kw) is False                 # 2 + 2.99 = 4.99
    assert labels.stage4_rule("expected_perio_loss", **{**kw, "unlabelled_probs": [1, 1, 0.5, 0.5]}) is True
    assert labels.stage4_rule("truth", **kw) is True
    with pytest.raises(ValueError, match="rule"):
        labels.stage4_rule("guess", **kw)
    assert labels.STAGE4_COUNT_RULES == ("recorded_only", "every_missing", "expected_perio_loss", "truth",
                                         "teeth_lt_20", "pairs_lt_10")


# spec 032 US4 (#443): stage IV also by fewer than 20 teeth, or fewer than 10 occluding pairs, left in the mouth

FULL = [t for t in range(1, 33)]                                    # 28 teeth and 14 pairs once third molars go


def test_stage4_tooth_counts_leave_out_third_molars_and_count_opposing_pairs():
    assert labels.stage4_tooth_counts(FULL) == (28, 14)
    assert labels.stage4_tooth_counts([]) == (0, 0)
    # upper 3 opposes lower 30, upper 14 opposes lower 19; 1, 16, 17 and 32 never count
    assert labels.stage4_tooth_counts([1, 3, 14, 16, 17, 19, 30, 32]) == (4, 2)
    assert labels.stage4_tooth_counts([2, 3, 4, 5]) == (4, 0)                 # one arch: no pairs


def test_stage4_rule_by_teeth_left_calls_iv_below_20_teeth_and_below_10_pairs():
    kw = {"recorded_perio": 0, "missing": 0}
    twenty = [t for t in range(2, 12)] + [33 - t for t in range(2, 12)]    # 20 teeth, 10 opposing pairs
    assert labels.stage4_rule("teeth_lt_20", **kw, teeth_present=twenty) is False
    assert labels.stage4_rule("pairs_lt_10", **kw, teeth_present=twenty) is False
    nineteen = twenty[:-1]                                              # 19 teeth, 9 pairs
    assert labels.stage4_rule("teeth_lt_20", **kw, teeth_present=nineteen) is True
    assert labels.stage4_rule("pairs_lt_10", **kw, teeth_present=nineteen) is True
    one_arch = [t for t in range(2, 16)] + [18, 19, 20, 21, 22, 23]     # 20 teeth, 6 pairs
    assert labels.stage4_rule("teeth_lt_20", **kw, teeth_present=one_arch) is False
    assert labels.stage4_rule("pairs_lt_10", **kw, teeth_present=one_arch) is True
    assert labels.stage4_rule("teeth_lt_20", **kw, teeth_present=twenty + [1, 16]) is False   # molars 3rd aside
    assert labels.stage4_rule("teeth_lt_20", **kw, teeth_present=nineteen + [1]) is True
    for rule in ("teeth_lt_20", "pairs_lt_10"):
        with pytest.raises(ValueError, match="teeth_present"):
            labels.stage4_rule(rule, **kw)
    # the counting rules ignore teeth_present, so existing callers are unchanged
    assert labels.stage4_rule("every_missing", recorded_perio=0, missing=5, teeth_present=[]) is True
    assert labels.stage4_rule("every_missing", 0, 5) is True


def test_the_patient_stage_table_counts_each_rule_from_the_tooth_predictions():
    t = _teeth([(1, 3, "extracted_perio", 50), (1, 4, "extracted_perio", 50), (1, 5, "missing_at_entry", 50),
                (1, 6, "missing_at_entry", 50), (1, 7, "extracted_no_dx", 50), (1, 8, "extracted_other", 50),
                (1, 9, "planned_perio", 50), (2, 3, "missing_at_entry", 50)])
    prob = pd.Series([np.nan, np.nan, 0.9, 0.8, 0.7, np.nan, np.nan, 0.2], index=t.index)
    truth = pd.DataFrame({"patient_id": [1, 1, 1, 1, 1, 1, 1, 2], "tooth_num": [3, 4, 5, 6, 7, 8, 9, 3],
                          "true_reason_code": ["perio"] * 5 + ["other", "perio", "other"]})
    s = tm.patient_stage(t, prob, truth, worst_cal=pd.Series({1: 6.0, 2: 3.0})).set_index("patient_id")
    one = s.loc[1]
    assert one["recorded_perio_count"] == 2 and one["missing_count"] == 6       # planned tooth is still there
    assert one["unlabelled_prob_sum"] == pytest.approx(2.4)
    assert one["expected_perio_loss"] == pytest.approx(4.4)
    assert one["true_perio_count"] == 5                                         # the planned tooth isn't lost yet
    assert (one["is_stage4_recorded_only"], one["is_stage4_every_missing"], one["is_stage4_expected_perio_loss"],
            one["is_stage4_truth"]) == (False, True, False, True)
    assert bool(one["is_stage3_4"]) and not bool(s.loc[2, "is_stage3_4"])        # worst CAL >= 5 mm
    # spec 032 US4: teeth left (present and planned teeth, third molars aside) and the pairs between them
    assert one["teeth_present_count"] == 1 and one["occluding_pair_count"] == 0  # only tooth 9 (planned) is left
    assert one["present_tooth_text"] == "9"
    assert bool(one["is_stage4_teeth_lt_20"]) and bool(one["is_stage4_pairs_lt_10"])


def test_the_patient_stage_table_counts_the_teeth_left_in_a_full_mouth():
    rows = [(1, t, "present", 50) for t in range(1, 33)]
    rows[2] = (1, 3, "missing_at_entry", 50)                            # tooth 3 gone: 27 teeth, 13 pairs
    t = _teeth(rows)
    truth = pd.DataFrame({"patient_id": [1], "tooth_num": [3], "true_reason_code": ["perio"]})
    s = tm.patient_stage(t, pd.Series(0.5, index=t.index), truth, worst_cal=pd.Series({1: 6.0})).iloc[0]
    assert (s["teeth_present_count"], s["occluding_pair_count"]) == (27, 13)
    assert s["present_tooth_text"] == " ".join(str(n) for n in range(1, 33) if n != 3)   # as charted, molars too
    assert not s["is_stage4_teeth_lt_20"] and not s["is_stage4_pairs_lt_10"]
    # the model may leave teeth out (third molars, a minimum age); the teeth left are read from the whole chart
    kept = t[~t["tooth_num"].isin(range(2, 12))]
    s = tm.patient_stage(kept, pd.Series(0.5, index=kept.index), truth, worst_cal=pd.Series({1: 6.0})).iloc[0]
    assert (s["teeth_present_count"], s["occluding_pair_count"]) == (18, 4)
    s = tm.patient_stage(kept, pd.Series(0.5, index=kept.index), truth, worst_cal=pd.Series({1: 6.0}),
                         chart=t).iloc[0]
    assert (s["teeth_present_count"], s["occluding_pair_count"]) == (27, 13)


# ---------- end to end on a small seeded synthetic extract

@pytest.fixture(scope="module")
def small_run():
    pytest.importorskip("xgboost")
    tables, truth, reads = od.build_with_readings(od.Params(n_patients=400), seed=5)
    x = {**od.clean(tables), "radiograph_bone_level": reads}
    return tm.run(x, truth, tm.ModelParams(n_boot=20), generator_seed=5)


def test_a_run_fits_both_models_on_both_label_sets_and_scores_the_same_teeth(small_run):
    s = small_run["scores"]
    assert set(s["label_set"]) == {"completed", "completed_planned"}
    assert {"logistic", "xgboost"} <= set(s["model"])
    assert {"baseline_all_perio", "baseline_outcome_rate", "baseline_recorded_only"} <= set(s["model"])
    assert set(s["eval_set"]) == {"held_out", "missing_at_entry", "extracted_no_dx"}
    n = s[s["metric"] == "auc"].groupby(["eval_set", "feature_set", "label_set", "model"])["tooth_count"].first()
    for ev in ("held_out", "missing_at_entry"):
        assert n.loc[ev].nunique() == 1, ev           # both label sets and models scored on the same teeth
    fitted = s[s["model"].isin(tm.MODELS)]
    assert set(fitted.loc[fitted["eval_set"] == "missing_at_entry", "feature_set"]) == {"shared"}   # no own there
    assert (s["data_label"] == "synthetic").all()
    assert {"auc", "brier", "calibration_intercept", "calibration_slope", "sensitivity", "specificity", "ppv",
            "npv", "outcome_rate"} <= set(s["metric"])
    assert set(s["threshold_name"].dropna()) == {"fixed_0.5", "youden_train"}
    # US7 (#429): teeth missing at entry hold both classes, so AUC and specificity there are numbers
    entry = s[(s["eval_set"] == "missing_at_entry") & s["model"].isin(tm.MODELS)]
    rate = entry.loc[entry["metric"] == "outcome_rate", "value"]
    assert ((rate > 0) & (rate < 1)).all()
    assert entry.loc[entry["metric"].isin(["auc", "specificity"]), "value"].notna().all()
    ok = s[(s["model"] == "xgboost") & (s["metric"] == "auc") & s["value"].notna()]
    assert (ok["ci_low"] <= ok["value"]).all() and (ok["value"] <= ok["ci_high"]).all()


def test_a_run_writes_calibration_stage_recount_predictions_and_missingness(small_run):
    cal = small_run["calibration"]
    assert cal.groupby(["label_set", "feature_set", "model", "eval_set"]).size().eq(10).all()
    st = small_run["stage_recount"]
    assert set(st["rule"]) == set(labels.STAGE4_COUNT_RULES)
    assert (st["stage3_count"] + st["stage4_count"] == st["patient_count"]).all()
    truth_rows = st[st["rule"] == "truth"]
    assert (truth_rows["agree_truth_count"] == truth_rows["patient_count"]).all()
    pr = small_run["predictions"]
    assert pr["probability"].between(0, 1).all() and set(pr["split"]) <= {"train", "test", "applied"}
    assert "present" not in set(pr["tooth_status_code"])
    miss = small_run["missing"]
    assert {"label_set", "split", "predictor", "missing_ratio"} <= set(miss.columns)
    assert miss["missing_ratio"].between(0, 1).all()


def test_a_run_is_seeded(small_run):
    tables, truth, reads = od.build_with_readings(od.Params(n_patients=400), seed=5)
    x = {**od.clean(tables), "radiograph_bone_level": reads}
    again = tm.run(x, truth, tm.ModelParams(n_boot=20), generator_seed=5)
    pd.testing.assert_frame_equal(again["scores"], small_run["scores"])


def test_the_predictions_reach_gold_under_the_declared_names(small_run):
    import importlib.util
    from pathlib import Path

    from health_transformation_lab_nlp import gold_names
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("gold_model", root / "diagrams" / "_build" / "gold_model.py")
    gm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gm)
    rows = small_run["predictions"].assign(run_id="1", run_ts=pd.Timestamp("2026-11-01"), git_commit="abc")
    out = gold_names.to_gold(rows, "fact_tooth_loss_prediction")
    assert list(out.columns) == [c.name for c in gm.TABLES["fact_tooth_loss_prediction"].columns]
