"""Spec 023 US1 (#198): the synthetic people carry a seeded, synthetic medical record."""

import filecmp
import math
import random
import re

import pandas as pd
import pytest

from health_transformation_lab_nlp import medical_record as mr
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT
from health_transformation_lab_nlp.study import build_study
from health_transformation_lab_nlp.synthetic import draw_history, draw_risk

STATUSES_PERIO = {"periodontitis_stage_1", "periodontitis_stage_2", "periodontitis_stage_3",
                  "periodontitis_stage_4"}


def _people(n: int, seed: int) -> pd.DataFrame:
    """n synthetic people, drawn the way the study draws them (risk factors, then a chart and its status)."""
    rng = random.Random(seed)
    rows = []
    for pid in range(1, n + 1):
        age = rng.randint(18, 84)
        risk = draw_risk(rng)
        status = draw_history(age, 1, risk, rng)[0].status.value
        rows.append({"person_id": pid, "age": age, "truth_status": status,
                     "cigarettes_per_day": risk.cigarettes_per_day, "hba1c": risk.hba1c})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def big():
    people = _people(10_000, seed=7)
    return people, mr.medical_records(people, seed=42)


# ---------------------------------------------------------------- the declared table (FR-002, SC-002)

def test_every_number_in_the_table_names_its_source():
    assert mr.CONDITIONS, "no conditions declared"
    for c in mr.CONDITIONS:
        assert c.rate_source.strip() and c.odds_ratio_source.strip(), c.column
        assert c.odds_ratio > 1 and c.exposed_statuses <= STATUSES_PERIO, c.column
        assert c.base_rates and all(0 < r < 1 for _, _, r in c.base_rates), c.column
        lows = [lo for lo, _, _ in c.base_rates]
        assert lows[0] == 18 and lows == sorted(lows), c.column
    for name, m in mr.MEASURES.items():
        assert m["source"].strip(), name
    assert mr.HYPERTENSION_CONTROL["source"].strip()
    assert mr.ASA_SOURCE.strip()


def test_the_conditions_the_spec_names_are_declared():
    cols = {c.column for c in mr.CONDITIONS}
    assert {"is_hypertension", "is_ckd", "is_cvd"} <= cols
    assert "is_diabetes" not in cols   # reused from the generator's HbA1c, never redrawn


# ---------------------------------------------------------------- the record

def test_seeded_and_reproducible():
    people = _people(300, seed=1)
    a, b = mr.medical_records(people, seed=42), mr.medical_records(people, seed=42)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(mr.medical_records(people, seed=43))


def test_own_random_stream_leaves_the_global_state_alone():
    random.seed(5)
    expected = random.random()
    random.seed(5)
    mr.medical_records(_people(50, seed=2), seed=42)
    assert random.random() == expected


def test_columns_follow_the_naming_rules(big):
    _, rec = big
    assert list(rec.columns) == mr.COLUMNS
    assert rec["person_id"].is_unique
    for col in rec.columns:
        assert re.fullmatch(r"person_id|is_[a-z0-9_]+|[a-z_]+_(mmhg|code)", col), col
    for col in [c for c in rec.columns if c.startswith("is_")]:
        assert rec[col].dtype == bool, col


def test_types_and_ranges(big):
    _, rec = big
    assert rec["is_synthetic"].all()
    assert set(rec["asa_class_code"]) <= {"I", "II", "III", "IV"}
    assert rec["systolic_bp_mmhg"].between(90, 200).all() and rec["diastolic_bp_mmhg"].between(50, 120).all()
    assert (rec["systolic_bp_mmhg"] > rec["diastolic_bp_mmhg"]).all()
    # without hypertension, blood pressure is below the NCHS threshold (140/90)
    normal = rec[~rec["is_hypertension"]]
    assert (normal["systolic_bp_mmhg"] < 140).all() and (normal["diastolic_bp_mmhg"] < 90).all()
    # ASA class I means no condition and no smoking
    people, _ = big
    healthy = rec.merge(people, on="person_id")
    cond = [c.column for c in mr.CONDITIONS] + ["is_diabetes"]
    asa1 = healthy[healthy["asa_class_code"] == "I"]
    assert not asa1[cond].any(axis=None) and (asa1["cigarettes_per_day"] == 0).all()


def test_diabetes_always_agrees_with_hba1c(big):
    people, rec = big
    m = rec.merge(people, on="person_id")
    expected = m["hba1c"].notna() & (m["hba1c"].fillna(0) >= mr.DIABETES_HBA1C)
    assert (m["is_diabetes"] == expected).all()


def _mantel_haenszel(df: pd.DataFrame, col: str, exposed: pd.Series, bands) -> float:
    num = den = 0.0
    for lo, hi, _ in bands:
        s = df[(df["age"] >= lo) & ((df["age"] <= hi) if hi is not None else True)]
        e, y = exposed.loc[s.index], s[col]
        n = len(s)
        a, b = (e & y).sum(), (e & ~y).sum()
        c, d = (~e & y).sum(), (~e & ~y).sum()
        num += a * d / n
        den += b * c / n
    return num / den


def test_age_adjusted_odds_ratios_are_the_cited_ones(big):
    people, rec = big
    m = rec.merge(people, on="person_id")
    for c in mr.CONDITIONS:
        exposed = m["truth_status"].isin(c.exposed_statuses)
        got = _mantel_haenszel(m, c.column, exposed, c.base_rates)
        assert abs(math.log(got) - math.log(c.odds_ratio)) <= mr.OR_TOLERANCE_LOG, (c.column, got, c.odds_ratio)


def test_base_rates_hold_in_the_unexposed(big):
    people, rec = big
    m = rec.merge(people, on="person_id")
    for c in mr.CONDITIONS:
        un = m[~m["truth_status"].isin(c.exposed_statuses)]
        for lo, hi, rate in c.base_rates:
            s = un[(un["age"] >= lo) & ((un["age"] <= hi) if hi is not None else True)]
            se = math.sqrt(rate * (1 - rate) / len(s))
            assert abs(s[c.column].mean() - rate) <= 4 * se, (c.column, lo, s[c.column].mean(), rate)


def test_people_from_visits_takes_each_persons_latest_visit():
    v = pd.DataFrame({"person_id": [1, 1, 2], "visit_date": ["2021-01-01", "2021-07-01", "2021-03-01"],
                      "age": [40, 41, 60], "truth_status": ["healthy", "periodontitis_stage_1", "gingivitis"],
                      "cigarettes_per_day": [0, 0, 5], "hba1c": [None, None, 7.2]})
    p = mr.people_from_visits(v)
    assert list(p["person_id"]) == [1, 2]
    assert list(p["age"]) == [41, 60] and list(p["truth_status"]) == ["periodontitis_stage_1", "gingivitis"]


# ---------------------------------------------------------------- the committed study (FR-001, SC-001)

@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory):
    out = tmp_path_factory.mktemp("study")
    build_study(out, tmp_path_factory.mktemp("raw"))
    return out


def test_rebuild_matches_every_committed_file(rebuilt):
    files = sorted(p.relative_to(rebuilt) for p in rebuilt.rglob("*") if p.is_file())
    assert "medical_record.csv" in {str(f) for f in files}
    for f in files:
        assert filecmp.cmp(rebuilt / f, DATASETS_DIR / f, shallow=False), f"{f} differs from the committed file"


def test_the_data_card_says_the_medical_record_is_synthetic():
    card = (DATASETS_DIR / "README.md").read_text()
    row = next(line for line in card.splitlines() if "`medical_record.csv`" in line)
    assert "synthetic" in row.lower()
    assert "not causes" in card.lower()
    assert (REPO_ROOT / "data" / "datasets" / "medical_record.csv").exists()
