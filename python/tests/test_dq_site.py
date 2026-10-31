"""docs/site/data-quality.json (#399): the data-quality results as one JSON file for the website's static page,
generated from the committed results so it can't go stale. Synthetic data only."""
import json

import pandas as pd
import pytest

from health_transformation_lab_nlp import dq_site
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT


@pytest.fixture(scope="module")
def d():
    return dq_site.build()


def test_the_json_is_current(d):
    assert json.loads(dq_site.OUT.read_text()) == d, "run python scripts/50_dq_site.py"
    assert dq_site.OUT == REPO_ROOT / "docs" / "site" / "data-quality.json"


def test_it_says_synthetic_and_carries_every_check(d):
    assert d["is_synthetic"] is True and "synthetic" in d["note"].lower()
    overall = pd.read_csv(DATASETS_DIR / "data_quality" / "dq_overall.csv")
    assert [c["check"] for c in d["checks"]] == list(overall["check"])
    c = next(c for c in d["checks"] if c["check"] == "completeness:exam_form")
    assert c["n_fail"] == 695 and c["fail_pct"] == round(100 * 695 / 4343, 1) and c["label"]


def test_clinics_far_from_the_rest_are_flagged():
    rows = pd.DataFrame({"clinic": ["1", "2", "3", "4", "5", "6"], "pct": [10.0, 11.0, 9.0, 10.0, 10.5, 40.0]})
    assert list(dq_site.flag_outliers(rows["pct"])) == [False, False, False, False, False, True]


def test_the_open_dental_profile_is_the_load_jobs_default_extract(d):
    names = {r["metric"] for r in d["open_dental"]}
    assert {"charted_visit_office_share", "partial_chart_share", "unread_tooth_share"} <= names
    assert all(0 <= r["pct"] <= 100 for r in d["open_dental"] if r["pct"] is not None)
