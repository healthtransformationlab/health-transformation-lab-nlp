"""Data-quality checks between the bronze extract and the silver tooth table (spec 029 FR-009, T006a; #370), after
Kookal et al. 2024 (references item 57), and the consistency split by group. Each check is tested against faults
planted on purpose (`open_dental.plant_faults`), on an extract generated with no other mess. Synthetic data only."""
import importlib.util
import sys

import pandas as pd
import pytest

from health_transformation_lab_nlp import open_dental, tooth_loss_dq
from health_transformation_lab_nlp.paths import REPO_ROOT

CLEAN = open_dental.Params(n_patients=150, edited_copy=0.0, icd_share=0.0, list_adoption_years=0.001,
                           **open_dental.NO_MESS)


@pytest.fixture(scope="module")
def clean():
    tables, _ = open_dental.build(CLEAN, seed=7)
    return tables


@pytest.fixture(scope="module")
def planted(clean):
    return open_dental.plant_faults(clean, seed=3)


def _found(results: pd.DataFrame) -> dict:
    return dict(zip(results["check_name"], results["found_count"]))


def test_every_check_is_declared_once_with_a_domain():
    names = [c.name for c in tooth_loss_dq.CHECKS]
    assert len(names) == len(set(names))
    assert {c.domain for c in tooth_loss_dq.CHECKS} == {"completeness", "accuracy", "plan_copy", "list_in_use",
                                                         "consistency"}
    assert all(c.text for c in tooth_loss_dq.CHECKS)


def test_a_clean_extract_finds_no_faults(clean):
    r = tooth_loss_dq.run_checks(clean, switch_date=CLEAN.list_switch_date)
    counted = r[r["check_name"] != "missing_value_share"]           # a share, reported, never a fault count
    assert (counted["found_count"] == 0).all(), counted[counted["found_count"] > 0][["check_name", "found_count"]]
    assert list(r.columns) == tooth_loss_dq.RESULT_COLUMNS


def test_each_planted_fault_is_found_exactly(planted):
    tables, faults = planted
    found = _found(tooth_loss_dq.run_checks(tables, switch_date=CLEAN.list_switch_date))
    assert set(faults) <= set(found)
    for name, n in faults.items():
        assert found[name] == n, (name, found[name], n)


def test_the_office_with_more_missing_values_is_the_one_flagged(planted):
    tables, faults = planted
    g = tooth_loss_dq.office_missing(tables)
    assert faults["office_missing_share"] == 1
    assert set(g.loc[g["is_flagged"], "group_name"]) == {str(open_dental.FAULT_OFFICE)}


def test_shares_are_found_over_checked(planted):
    tables, _ = planted
    r = tooth_loss_dq.run_checks(tables, switch_date=CLEAN.list_switch_date)
    ok = r["checked_count"] > 0
    assert (r.loc[ok, "found_ratio"] - r.loc[ok, "found_count"] / r.loc[ok, "checked_count"]).abs().max() < 1e-12
    assert r["is_flagged"].dtype == "boolean"


# ---------- consistency by group: is the record kept as well for every group of patients? ----------
def test_groups_cover_office_provider_sex_race_year_and_age(clean):
    g = tooth_loss_dq.group_consistency(clean)
    assert set(g["group_type_code"]) == {"office", "provider", "sex", "race", "exam_year", "age_band"}
    assert set(g["metric_name"]) == {"no_margin_chart", "incomplete_chart"}
    assert list(g.columns) == tooth_loss_dq.GROUP_COLUMNS
    # every chart counted once per group type and metric
    n = len(clean["perioexam"])
    per = g.groupby(["group_type_code", "metric_name"])["chart_count"].sum()
    assert (per == n).all(), per


def test_insurance_type_is_a_group_type_when_asked(clean):
    # spec 032 US6 (#445): the split by insurance (private, public, none) is an option; the default stays as it was
    assert "insurance_type" not in tooth_loss_dq.GROUP_TYPES
    assert tooth_loss_dq.ALL_GROUP_TYPES == (*tooth_loss_dq.GROUP_TYPES, "insurance_type")
    g = tooth_loss_dq.group_consistency(clean, group_types=tooth_loss_dq.ALL_GROUP_TYPES)
    ins = g[g["group_type_code"] == "insurance_type"]
    assert set(ins["group_name"]) <= {"private", "public", "none"} and len(set(ins["group_name"])) >= 2
    per = ins.groupby("metric_name")["chart_count"].sum()
    assert (per == len(clean["perioexam"])).all(), per
    default = tooth_loss_dq.group_consistency(clean)
    pd.testing.assert_frame_equal(default, g[g["group_type_code"] != "insurance_type"].reset_index(drop=True))
    with pytest.raises(ValueError, match="group type"):
        tooth_loss_dq.group_consistency(clean, group_types=("payer",))


def test_charts_kept_worse_for_one_insurance_type_are_flagged():
    tables, _ = open_dental.build(open_dental.Params(n_patients=600, **open_dental.NO_MESS), seed=11)
    kind = open_dental.insurance_type(tables)
    public = set(kind[kind == "public"].index)
    ex = tables["perioexam"]
    skip = set(ex.loc[ex["patnum"].isin(public), "perioexamnum"])
    pm = tables["periomeasure"]
    tables = {**tables, "periomeasure": pm[~(pm["perioexamnum"].isin(skip)
                                             & (pm["sequencetype"] == open_dental.SEQ_MARGIN))]}
    g = tooth_loss_dq.group_consistency(tables, group_types=("insurance_type",))
    m = g[g["metric_name"] == "no_margin_chart"].set_index("group_name")
    assert m.loc["public", "value_ratio"] == 1.0 and m.loc["public", "is_flagged"]


def test_a_provider_who_skips_margins_is_flagged():
    tables, _ = open_dental.build(open_dental.Params(n_patients=300, **open_dental.NO_MESS), seed=11)
    ex = tables["perioexam"]
    prov = ex["provnum"].value_counts().index[0]
    skip = set(ex.loc[ex["provnum"] == prov, "perioexamnum"])
    pm = tables["periomeasure"]
    tables = {**tables, "periomeasure": pm[~(pm["perioexamnum"].isin(skip)
                                             & (pm["sequencetype"] == open_dental.SEQ_MARGIN))]}
    g = tooth_loss_dq.group_consistency(tables)
    m = g[(g["group_type_code"] == "provider") & (g["metric_name"] == "no_margin_chart")]
    assert set(m.loc[m["is_flagged"], "group_name"]) == {str(prov)}
    assert m.set_index("group_name").loc[str(prov), "value_ratio"] == 1.0


def test_flags_compare_each_group_with_the_rest():
    # with 4 offices one outlier can never sit 2 SD from a mean that includes it, so each group is compared with the
    # others: mean and SD of the rest, flagged beyond 2 SD (and any difference when the rest don't vary)
    v = pd.Series([0.10, 0.11, 0.09, 0.40], index=list("abcd"))
    f = tooth_loss_dq.flag_against_rest(v)
    assert list(f["is_flagged"]) == [False, False, False, True]
    assert f.loc["d", "rest_mean_ratio"] == pytest.approx(0.10)
    two = tooth_loss_dq.flag_against_rest(pd.Series([0.2, 0.3], index=["0", "1"]))
    assert not two["is_flagged"].any()                                  # one other value: no SD, no flag


def test_small_groups_are_reported_but_never_flagged():
    tables, _ = open_dental.build(open_dental.Params(n_patients=300, **open_dental.NO_MESS), seed=11)
    g = tooth_loss_dq.group_consistency(tables)
    small = g[g["chart_count"] < tooth_loss_dq.MIN_CHARTS]
    assert len(small) and not small["is_flagged"].any()
    assert small["rest_mean_ratio"].isna().all()


# ---------- where the results land: silver tables in the data model, written by the load job ----------
def _model():
    sys.path.insert(0, str(REPO_ROOT / "diagrams" / "_build"))
    spec = importlib.util.spec_from_file_location(
        "od_model", REPO_ROOT / "diagrams" / "_build" / "opendental_silver_model.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


BATCH = ["run_id", "run_ts", "git_commit_sha"]


@pytest.mark.parametrize("table,cols", [("tooth_loss_dq_check", tooth_loss_dq.RESULT_COLUMNS),
                                        ("tooth_loss_dq_group", tooth_loss_dq.GROUP_COLUMNS)])
def test_the_silver_tables_declare_every_column(table, cols):
    m = _model()
    declared = [c.name for c in m.TABLES[table].columns]
    assert sorted(declared) == sorted(cols + BATCH), (table, set(declared) ^ set(cols + BATCH))
    assert m.TABLES[table].area == "dq"


def test_the_load_job_writes_both_tables_idempotently():
    nb = (REPO_ROOT / "databricks" / "notebooks" / "12_load_open_dental.py").read_text()
    for call in ("tooth_loss_dq.run_checks(", "tooth_loss_dq.group_consistency(", '"tooth_loss_dq_check"',
                 '"tooth_loss_dq_group"', "DELETE FROM"):
        assert call in nb, call
