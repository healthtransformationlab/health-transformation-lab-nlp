"""Model ladder against the synthetic truth: accuracy with paired bootstrap CIs, stage IV recall,
unsafe errors, calibration, and the rules-decide-stage-IV hybrid (spec 002 T015)."""

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import ladder_eval
from health_transformation_lab_nlp.labels import LABELS

S4 = "periodontitis_stage_4"


def test_rules_override_takes_the_rule_answer_only_for_stage_iv():
    model = pd.Series(["healthy", "periodontitis_stage_3", "gingivitis"])
    rules = pd.Series([S4, "healthy", "gingivitis"])
    assert list(ladder_eval.rules_override(model, rules)) == [S4, "periodontitis_stage_3", "gingivitis"]


def test_expected_calibration_error():
    truth = pd.Series(["healthy", "healthy", "gingivitis", "gingivitis"])
    proba = pd.DataFrame(0.0, index=truth.index, columns=LABELS)
    proba["healthy"] = [0.9, 0.9, 0.9, 0.9]                   # always 90% sure of healthy; right half the time
    proba["gingivitis"] = [0.1, 0.1, 0.1, 0.1]
    assert ladder_eval.expected_calibration_error(truth, proba) == pytest.approx(0.4)


def test_ladder_table_point_estimates_and_paired_difference():
    truth = pd.Series(["healthy"] * 6 + [S4] * 4)
    perfect = truth.copy()
    misses_s4 = pd.Series(["healthy"] * 10)
    t = ladder_eval.ladder_table(truth, {"note_rules": perfect, "m": misses_s4}, n_boot=200, seed=1,
                                 reference="note_rules").set_index("method")
    assert t.loc["m", "accuracy"] == pytest.approx(0.6)
    assert t.loc["m", "stage4_recall"] == 0.0 and t.loc["note_rules", "stage4_recall"] == 1.0
    assert t.loc["m", "s2_rate"] == pytest.approx(0.4)        # stage IV called healthy: irreversible harm
    assert t.loc["m", "diff_vs_ref"] == pytest.approx(-0.4)
    assert t.loc["m", "diff_hi"] < 0                         # clearly worse, even allowing for resampling
    assert t.loc["m", "acc_lo"] <= 0.6 <= t.loc["m", "acc_hi"]
    assert np.isnan(t.loc["m", "ece"])                        # no probabilities given


def test_ladder_table_is_seeded():
    truth = pd.Series(["healthy", "gingivitis"] * 20)
    pred = pd.Series(["healthy"] * 40)
    a = ladder_eval.ladder_table(truth, {"note_rules": truth, "m": pred}, n_boot=100, seed=3)
    b = ladder_eval.ladder_table(truth, {"note_rules": truth, "m": pred}, n_boot=100, seed=3)
    pd.testing.assert_frame_equal(a, b)


def test_by_difficulty_accuracy_per_level():
    truth = pd.Series(["healthy", "healthy", "gingivitis", S4])
    level = pd.Series(["L1", "L1", "L3", "L3"])
    preds = {"a": pd.Series(["healthy", "gingivitis", "gingivitis", "healthy"]), "b": truth.copy()}
    t = ladder_eval.by_difficulty(truth, preds, level).set_index(["method", "difficulty"])
    assert t.loc[("a", "L1"), "accuracy"] == pytest.approx(0.5) and t.loc[("a", "L1"), "n"] == 2
    assert t.loc[("a", "L3"), "accuracy"] == pytest.approx(0.5)
    assert t.loc[("b", "L3"), "accuracy"] == 1.0
    assert list(t.index.get_level_values("difficulty").unique()) == ["L1", "L3"]   # sorted levels


def test_head_to_head_uses_the_encoder_as_reference():
    truth = pd.Series(["healthy"] * 8 + [S4] * 2)
    bert = pd.Series(["healthy"] * 10)                       # misses both stage IV
    llm = truth.copy()
    t = ladder_eval.ladder_table(truth, {"bert-base": bert, "medgemma": llm}, n_boot=200, seed=0,
                                 reference="bert-base").set_index("method")
    assert t.loc["medgemma", "diff_vs_ref"] == pytest.approx(0.2)
    assert t.loc["bert-base", "diff_vs_ref"] == 0.0


def test_missing_charts_counts_unscored_review_charts():
    truth = pd.Series(["healthy"] * 4, index=[1, 2, 3, 4])
    assert ladder_eval.missing_charts(pd.Series(["healthy"] * 4, index=[1, 2, 3, 4]), truth) == 0
    assert ladder_eval.missing_charts(pd.Series(["healthy", None], index=[1, 2]), truth) == 3   # a --limit run


# ---------- spec 030 (#387): what a synthetic score means ----------
def test_a_chart_without_a_probing_chart_or_radiograph_cant_be_staged():
    key = pd.DataFrame({"probing_chart": ["healthy", "unknown", "unknown", "periodontitis_stage_2"],
                        "rad_present": [0.0, 1.0, 0.0, None]}, index=[1, 2, 3, 4])
    assert list(ladder_eval.stageable(key)) == ["stageable", "stageable", "not_stageable", "stageable"]


def test_methods_that_use_the_answer_keys_rules_are_named():
    for m in ("note_rules", "rules_baseline", "modernbert-base+cw+s2+rules4", "algorithm_v0", "algorithm_design",
              "probing_chart", "radiograph_ai"):
        assert ladder_eval.uses_answer_key_rules(m), m
    for m in ("modernbert-base+cw+s2", "tfidf_logreg", "medgemma-1.5-4b-it", "exam_form", "proc_dx_planned"):
        assert not ladder_eval.uses_answer_key_rules(m), m


def test_scores_split_by_stageable_charts():
    truth = pd.Series(["healthy", S4, S4, "gingivitis"], index=[1, 2, 3, 4])
    level = pd.Series(["stageable", "stageable", "not_stageable", "not_stageable"], index=[1, 2, 3, 4])
    got = ladder_eval.by_difficulty(truth, {"m": pd.Series(["healthy", "healthy", S4, "healthy"], index=[1, 2, 3, 4])},
                                    level)
    assert got.set_index("difficulty").loc["stageable", "accuracy"] == 0.5
    assert got.set_index("difficulty").loc["not_stageable", "n"] == 2


def test_the_ladder_script_writes_the_stageable_split():
    from health_transformation_lab_nlp.paths import REPO_ROOT
    src = (REPO_ROOT / "python" / "scripts" / "28_ladder_vs_truth.py").read_text()
    assert "ladder_by_stageable.csv" in src and "ladder_eval.stageable(" in src
    parity = (REPO_ROOT / "r" / "tests" / "test_parity.R").read_text()
    assert "ladder_by_stageable.csv" in parity


# ---------- spec 030 US2 (#397): subgroups and stability ----------
def test_age_bands():
    assert list(ladder_eval.age_band(pd.Series([18, 34, 35, 64, 65, 90]))) == \
        ["under_35", "under_35", "35_64", "35_64", "65_plus", "65_plus"]


def test_seed_spread_summarises_each_method_over_seeds():
    long = pd.DataFrame({"method": ["a", "a", "a", "b"], "seed": [1, 2, 3, 1], "accuracy": [0.8, 0.9, 1.0, 0.5]})
    got = ladder_eval.seed_spread(long).set_index("method")
    assert got.loc["a", "seed_count"] == 3 and got.loc["a", "mean_accuracy"] == pytest.approx(0.9)
    assert got.loc["a", "sd_accuracy"] == pytest.approx(0.1)
    assert (got.loc["a", "min_accuracy"], got.loc["a", "max_accuracy"]) == (0.8, 1.0)
    assert np.isnan(got.loc["b", "sd_accuracy"])           # one seed: no spread


def test_the_scripts_write_the_subgroups_and_the_stability_files():
    from health_transformation_lab_nlp.paths import REPO_ROOT
    ladder = (REPO_ROOT / "python" / "scripts" / "28_ladder_vs_truth.py").read_text()
    assert "ladder_by_age.csv" in ladder and "ladder_by_clinic.csv" in ladder
    stab = (REPO_ROOT / "python" / "scripts" / "49_seed_stability.py").read_text()
    assert "seed_stability.csv" in stab and "seed_stability_summary.csv" in stab
    parity = (REPO_ROOT / "r" / "tests" / "test_parity.R").read_text()
    for f in ("ladder_by_age.csv", "ladder_by_clinic.csv", "seed_stability_summary.csv"):
        assert f in parity, f


def test_the_seed_42_row_matches_the_committed_answer_key():
    from health_transformation_lab_nlp.paths import DATASETS_DIR
    st = pd.read_csv(DATASETS_DIR / "ladder" / "seed_stability.csv")
    key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")
    for m in ("algorithm_v0", "algorithm_design", "exam_form"):
        row = st[(st["method"] == m) & (st["seed"] == 42)].iloc[0]
        assert row["accuracy"] == pytest.approx((key[m] == key["truth_status"]).mean()), m
