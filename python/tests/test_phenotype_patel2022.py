"""Spec 024 US3: the stepwise phenotype of Patel et al. 2022 (diagnosis codes, then notes, then chart), scored like
the other methods. Synthetic data only."""

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import completeness, periodx, phenotype, reliability
from health_transformation_lab_nlp.paths import DATASETS_DIR

U = "unknown"


def row(**kw):
    base = {"exam_form": "periodontitis_stage_4", "proc_dx_completed": U, "proc_dx_planned": U,
            "periodx_note_label": U, "periodx_chart_label": U}
    base.update(kw)
    return pd.Series(base)


def test_the_papers_order_is_its_own_constant_not_a_design_group():
    assert phenotype.PATEL2022_ORDER == ["dx_code", "notes", "probing_chart"]
    assert phenotype.PATEL2022_SECTIONS == {"M1": ["proc_dx_completed", "proc_dx_planned"],
                                            "M2": ["periodx_note_label"], "M3": ["periodx_chart_label"]}
    assert set(phenotype.DESIGN_GROUPS) == {"exam_form", "dx_code", "notes", "probing_chart"}


def test_acceptance_1_a_completed_code_decides_and_notes_and_chart_are_not_read():
    r = row(proc_dx_completed="periodontitis_stage_2", proc_dx_planned="gingivitis",
            periodx_note_label="periodontitis_stage_3", periodx_chart_label="healthy")
    assert phenotype.phenotype_patel2022(r) == ("periodontitis_stage_2", "M1")


def test_planned_codes_count_after_completed_ones():
    assert phenotype.phenotype_patel2022(row(proc_dx_planned="gingivitis",
                                             periodx_note_label="healthy")) == ("gingivitis", "M1")


def test_the_note_decides_when_there_is_no_code():
    r = row(periodx_note_label="periodontitis_stage_1", periodx_chart_label="periodontitis_stage_3")
    assert phenotype.phenotype_patel2022(r) == ("periodontitis_stage_1", "M2")


def test_acceptance_2_no_code_and_no_diagnosis_in_the_note_the_chart_decides():
    r = row(periodx_note_label=U, periodx_chart_label="periodontitis_stage_3")
    assert phenotype.phenotype_patel2022(r) == ("periodontitis_stage_3", "M3")


def test_the_exam_form_is_never_used():
    assert phenotype.phenotype_patel2022(row()) == (U, "none")


def test_visits_table_reads_note_and_chart_for_every_visit():
    v = pd.DataFrame({
        "visit_id": [1, 2, 3], "age": [50, 60, 40], "cigarettes_per_day": [0, 12, 0], "diabetes": [False, False, True],
        "hba1c": [np.nan, np.nan, 7.4], "charted": [True, True, False],
        "rec_max_probing_depth_mm": [4.8, 3.0, np.nan], "rec_bop_pct": [35.0, 20.0, np.nan],
        "rec_max_cal_mm": [3.4, 0.5, np.nan], "rec_rbl_pct": [20.0, 0.0, np.nan],
        "rec_teeth_lost_perio": [0.0, 0.0, np.nan], "rec_pct_teeth_involved": [40.0, 0.0, np.nan],
        "proc_dx_completed": [U, U, "gingivitis"], "proc_dx_planned": [U, U, U], "exam_form": [U, "healthy", U],
        "note_text": ["Dx: findings reviewed.", "d: localized plaque induced gingivitis", "See perio chart."]})
    t = periodx.visits_table(v)
    assert list(t.columns) == periodx.VISIT_COLUMNS
    assert list(t.algorithm_patel2022) == ["periodontitis_stage_2", "gingivitis", "gingivitis"]
    assert list(t.algorithm_patel2022_decided_by) == ["M3", "M2", "M1"]
    assert list(t.periodx_chart_label) == ["periodontitis_stage_2", "gingivitis", U]
    assert list(t.periodx_note_status) == [periodx.NO_DIAGNOSIS, periodx.LOCALIZED_GINGIVITIS, periodx.NO_DIAGNOSIS]
    assert t.loc[0, "periodx_chart_grade"] == "B" and t.loc[2, "periodx_chart_status"] == U


def test_section_completeness_before_and_after_merging():
    v = pd.DataFrame({"m1": ["healthy", U, U, U], "m2": ["gingivitis", "gingivitis", U, U],
                      "m3": ["healthy", U, "periodontitis_stage_2", U],
                      "merged": ["healthy", "gingivitis", "periodontitis_stage_2", U],
                      "by": ["M1", "M2", "M3", "none"]})
    t = completeness.section_completeness(v, {"M1": ["m1"], "M2": ["m2"], "M3": ["m3"]}, "merged", "by")
    assert list(t.section) == ["M1", "M2", "M3", "merged"]
    assert list(t.n_with_value) == [1, 2, 2, 3] and list(t.n_decided) == [1, 1, 1, 3]
    assert list(t.pct_with_value) == [25.0, 50.0, 50.0, 75.0]
    assert list(t.pct_decided) == [25.0, 25.0, 25.0, 75.0]
    assert (t.n_visits == 4).all()


def test_confusion_scores_one_vs_rest_and_pooled_with_no_answer_as_negative():
    truth = pd.Series(["a", "a", "b", "b"])
    pred = pd.Series(["a", "b", "b", "unknown"])
    t = reliability.confusion_scores(truth, pred, ["a", "b"]).set_index("class")
    assert t.loc["a", ["tp", "fp", "fn", "tn"]].tolist() == [1, 0, 1, 2]
    assert t.loc["b", ["tp", "fp", "fn", "tn"]].tolist() == [1, 1, 1, 1]
    assert t.loc["a", "precision"] == 1.0 and t.loc["a", "recall"] == 0.5
    assert t.loc["a", "f1"] == pytest.approx(2 / 3)
    assert t.loc["pooled", ["tp", "fp", "fn", "tn"]].tolist() == [2, 1, 2, 3]
    assert t.loc["pooled", "f1"] == pytest.approx(4 / 7)


def test_confusion_scores_without_predictions_give_nan_precision():
    t = reliability.confusion_scores(pd.Series(["a"]), pd.Series(["unknown"]), ["a", "b"]).set_index("class")
    assert np.isnan(t.loc["a", "precision"]) and t.loc["a", "recall"] == 0.0


def test_score_orders_keeps_24_orders_and_adds_the_papers_as_one_row_never_selected():
    n = 120
    truth = ["periodontitis_stage_2" if i % 2 else "gingivitis" for i in range(n)]
    key = pd.DataFrame({"visit_id": range(n), "exam_form": [U] * n, "proc_dx_completed": [U] * n,
                        "proc_dx_planned": [U] * n, "notes": truth, "probing_chart": truth,
                        "radiograph_ai": [U] * n}).set_index("visit_id")
    wide = pd.DataFrame({f"r{j}": truth for j in range(3)}, index=key.index)
    paper = pd.Series(truth, index=key.index)
    t = phenotype.score_orders(key, wide, n_boot=0, seed=1, extra={"patel2022:dx_code>notes>probing_chart": paper})
    assert len(t) == 25 and t["selected"].sum() == 1
    last = t.iloc[-1]
    assert last["order"] == "patel2022:dx_code>notes>probing_chart" and not last["selected"]
    assert last["holdout_kappa"] == 1.0


# ---------------------------------------------------------------- the committed study

def test_the_periodx_visits_file_covers_every_visit_and_visits_structured_is_unchanged():
    v = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
    p = pd.read_csv(DATASETS_DIR / "periodx_visits.csv")
    assert list(p.columns) == periodx.VISIT_COLUMNS
    assert sorted(p.visit_id) == sorted(v.visit_id)
    assert not [c for c in v.columns if "periodx" in c or "patel" in c]
    assert set(p.algorithm_patel2022_decided_by) <= {"M1", "M2", "M3", "none"}


def test_the_completeness_table_shows_each_section_and_the_merged_share():
    c = pd.read_csv(DATASETS_DIR / "data_quality" / "completeness_patel2022.csv")
    assert set(c.scale) == {"all_visits", "reference_set"}
    for _, g in c.groupby("scale"):
        assert list(g.section) == ["M1", "M2", "M3", "merged"]
        merged = g.set_index("section").loc["merged"]
        assert merged.n_decided == g[g.section != "merged"].n_decided.sum()


def test_confusion_scores_for_the_diagnoser_and_the_extractor_are_committed():
    c = pd.read_csv(DATASETS_DIR / "periodx" / "confusion_scores.csv")
    assert set(c.component) == {"diagnoser", "extractor", "algorithm_patel2022"}
    assert (c.groupby("component").size() == 7).all()          # six labels and pooled
