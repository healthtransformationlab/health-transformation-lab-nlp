"""docs/site/data-quality.json (#399, #401): the EHR DQ grader's data (spec 019, `dashboards.dq_grader`) as one JSON
file for the website's static page, built from the same tables the grader reads (`grader_tables.dq_tables`), so the
page and the dashboard show the same numbers. Generated from committed results; synthetic data only."""
import json

import pandas as pd
import pytest

from health_transformation_lab_nlp import dashboards, dq_site, grader_tables
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT

GRADER_SECTIONS = {"tiles", "missingness", "checks", "accuracy", "concordance", "prevalence_clinic",
                   "prevalence_scale", "transitions", "temporal", "injected"}


@pytest.fixture(scope="module")
def d():
    return dq_site.build()


@pytest.fixture(scope="module")
def t():
    return grader_tables.dq_tables(DATASETS_DIR)


def test_the_json_is_current(d):
    assert json.loads(dq_site.OUT.read_text()) == d, "run python scripts/50_dq_site.py"
    assert dq_site.OUT == REPO_ROOT / "docs" / "site" / "data-quality.json"


def test_it_has_one_section_per_grader_dataset(d):
    assert GRADER_SECTIONS <= set(dashboards.DQ_SQL)          # the grader still has these datasets
    assert GRADER_SECTIONS <= set(d["sections"])
    assert d["is_synthetic"] is True and "synthetic" in d["note"].lower()


def test_the_tiles_are_the_graders_definitions(d, t):
    v = t["fact_visit_evidence"]
    tiles = d["sections"]["tiles"]
    complete = ((v["exam_form"] != "unknown") & (v["proc_dx_completed"] != "unknown")
                & (v["probing_chart"] != "unknown")).mean()
    assert tiles["completeness_pct"] == round(100 * complete, 1)
    assert tiles["accuracy_pct"] == round(100 * (v["algorithm_v0"] == v["truth_status"]).mean(), 1)
    assert tiles["accuracy_design_pct"] == round(100 * (v["algorithm_design"] == v["truth_status"]).mean(), 1)
    clin = t["dq_prevalence"].query("level == 'clinic' and method == 'algorithm_design'")["periodontitis"]
    assert tiles["consistency_pts"] == round(100 * (clin.max() - clin.min()), 1)
    tc = t["dq_temporal_change"].set_index("method").loc["algorithm_design"]
    assert tiles["implausible_pct"] == round(100 * tc["better"], 1)
    assert tiles["visit_count"] == len(v) and tiles["reliability_text"].startswith("Not assessed")


def test_accuracy_by_source_overall_and_by_clinic(d, t):
    v = t["fact_visit_evidence"]
    acc = pd.DataFrame(d["sections"]["accuracy"])
    row = acc[(acc["clinic"] == "All") & (acc["source"] == "exam_form")].iloc[0]
    ans = v["exam_form"] != "unknown"
    assert row["answered_pct"] == round(100 * ans.mean(), 1)
    assert row["agree_pct"] == round(100 * (v.loc[ans, "exam_form"] == v.loc[ans, "truth_status"]).mean(), 1)
    assert set(acc["clinic"]) == {"All", *v["clinic"].astype(str).unique()}


def test_the_heatmaps_and_tables_carry_the_graders_rows(d, t):
    s = d["sections"]
    assert len(s["transitions"]) == len(t["dq_stage_transition"])
    assert len(s["concordance"]) == (t["dq_source_concordance"]["level"] == "status").sum()
    assert len(s["prevalence_clinic"]) == (t["dq_prevalence"]["level"] == "clinic").sum() // \
        t["dq_prevalence"].query("level == 'clinic'")["method"].nunique()
    assert len(s["checks"]) == len(t["dq_check"])
    assert s["injected"]["injected_count"] == int(t["dq_injected_error"]["injected_errors"].iloc[0])


def test_clinics_far_from_the_rest_are_flagged():
    vals = pd.Series([10.0, 11.0, 9.0, 10.0, 10.5, 40.0])
    assert list(dq_site.flag_outliers(vals)) == [False, False, False, False, False, True]


def test_the_open_dental_profile_stays_as_the_last_section(d):
    names = {r["metric"] for r in d["sections"]["open_dental"]}
    assert {"charted_visit_office_share", "partial_chart_share", "unread_tooth_share"} <= names


# ---------- the Perio DQ Monitor layout (#401): every clinic and scale, for the page's filters ----------
def test_the_monitor_has_every_clinic_and_scale(d, t):
    m = d["sections"]["monitor"]
    clinics = {"All", *t["fact_visit_evidence"]["clinic"].astype(str).unique()}
    assert {(c["clinic"], c["scale"]) for c in m} == {(c, s) for c in clinics
                                                       for s in ("all_visits", "complete_cases", "reference_set")}


def test_the_all_visits_slice_matches_the_tiles(d):
    m = next(c for c in d["sections"]["monitor"] if c["clinic"] == "All" and c["scale"] == "all_visits")
    assert m["completeness_pct"] == d["sections"]["tiles"]["completeness_pct"]
    assert m["accuracy_pct"] == d["sections"]["tiles"]["accuracy_pct"]
    assert m["visit_count"] == d["sections"]["tiles"]["visit_count"]


def test_the_funnel_only_narrows(d):
    for c in d["sections"]["monitor"]:
        n = [s["visit_count"] for s in c["funnel"]]
        assert n == sorted(n, reverse=True), (c["clinic"], c["scale"])


def test_the_truth_table_on_a_hand_case():
    v = pd.DataFrame({"exam_form": ["periodontitis_stage_2", "healthy", "periodontitis_stage_3", "unknown"],
                      "truth_status": ["periodontitis_stage_2", "periodontitis_stage_1", "gingivitis", "healthy"]})
    r = dq_site.truth_row(v, "exam_form")
    assert r["answered_count"] == 3 and r["agree_pct"] == round(100 / 3, 1)
    assert r["sensitivity_pct"] == 50.0 and r["specificity_pct"] == 0.0     # perio yes/no among answered
    assert r["ppv_pct"] == 50.0 and r["npv_pct"] == 0.0


def test_reliability_is_credited_to_a_paper_that_defines_it(d):
    # #405: Liaw et al. 2013 reviews data-quality definitions but doesn't define reliability; de Vet et al. 2006 does
    text = json.dumps(d) + json.dumps(dashboards.dq_grader())
    assert "Liaw" not in text
    assert "de Vet" in text


# ---------- spec 029 FR-009 (#370): the extract checks and the chart kept as well for every group ----------
def test_the_extract_checks_and_groups_are_the_modules_own(d):
    from health_transformation_lab_nlp import open_dental, tooth_loss_dq
    tables, _ = open_dental.build(open_dental.Params(), seed=42)    # every table, insurance too (spec 032 US8)
    checks = tooth_loss_dq.run_checks(tables)
    s = d["sections"]
    assert [r["check"] for r in s["extract_checks"]] == list(checks["check_name"])
    assert [r["found_count"] for r in s["extract_checks"]] == list(checks["found_count"])
    groups = tooth_loss_dq.group_consistency(tables)
    assert len(s["chart_by_group"]) == len(groups)
    assert {r["group_type"] for r in s["chart_by_group"]} == set(groups["group_type_code"])
    assert all(0 <= r["pct"] <= 100 for r in s["chart_by_group"])
    assert "insurance_type" in {r["group_type"] for r in s["chart_by_group"]}      # spec 032 US8 (#448)


def test_the_cal_icc_is_reported_and_labelled_simulated(d):
    # spec 032 US8 (#448): the reliability section reports the CAL ICC from scripts/37_cal_reliability.py
    rows = d["sections"]["cal_reliability"]
    committed = pd.read_csv(DATASETS_DIR / "reliability_cal" / "simulated_cal_reliability.csv")
    assert [r["probing_error_sd_mm"] for r in rows] == list(committed["sd_error_true"])
    assert [r["icc_site"] for r in rows] == [round(x, 3) for x in committed["icc_site"]]
    assert all(r["is_simulated"] for r in rows) and all(0 <= r["icc_site"] <= 1 for r in rows)


def test_every_clinic_and_office_has_a_name(d):
    # people read names, not numbers; the study's clinics are synthetic, so the names are invented and say so
    s = d["sections"]
    names = {c["clinic"]: c["name"] for c in s["clinics"]}
    assert set(names) == {r["clinic"] for r in s["prevalence_clinic"]}
    assert len(set(names.values())) == len(names) and all(n.strip() for n in names.values())
    assert all(r["name"] == names[r["clinic"]] for r in s["prevalence_clinic"])
    offices = [r for r in s["chart_by_group"] if r["group_type"] == "office"]
    assert offices and all(r["label"].startswith("Synthetic Dental Clinic") for r in offices)
    providers = [r for r in s["chart_by_group"] if r["group_type"] == "provider"]
    assert all(r["label"] != r["group"] for r in providers)
