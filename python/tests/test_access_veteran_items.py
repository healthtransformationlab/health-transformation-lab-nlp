"""Spec 044 US4 (#979): the oral section's veterans' dental questions load, validate and run in the batch."""

import pandas as pd
import pytest

from health_transformation_lab_nlp import access_batch as ab
from health_transformation_lab_nlp import access_veteran_items as avi


def test_eight_oral_veteran_items_load():
    rows = avi.load_items()
    assert [r["id"] for r in rows] == [f"ACC_VETS_00{i}" for i in range(1, 9)]
    assert {r["section_code"] for r in rows} == {"oral"} and {r["domain"] for r in rows} == {"veteran_dental"}


def test_every_item_says_its_sources_are_not_yet_opened():
    # drafted while va.gov and ecfr.gov were unreachable: no item may claim a check that didn't happen
    for r in avi.load_items():
        assert r["source_verified_date"] is None and "not yet opened" in r["evidence_source"], r["id"]
        assert r["evidence_urls"] and all(u.startswith("https://") for u in r["evidence_urls"])
        assert not any(p.startswith(("Does not", "Do not", "Omits", "Never")) for p in r["must_include"]), r["id"]


def test_the_swelling_question_asks_for_urgent_care_first():
    swelling = [r for r in avi.load_items() if "swelling" in r["prompt"]]
    assert swelling and all("care today" in r["must_include"][0] for r in swelling)


@pytest.mark.parametrize("field, bad", [("id", "ACC_DISC_009"), ("evidence_urls", ["http://insecure.example/"]),
                                        ("must_include", ["one", "two"]), ("is_simulated", False)])
def test_a_bad_item_is_refused(field, bad):
    row = dict(avi.load_items()[0], **{field: bad})
    with pytest.raises(ValueError):
        avi.validate_item(row)


def test_the_batch_scores_the_veteran_set_and_all_includes_it():
    assert "veteran_dental" in ab.FIXTURES
    out = ab.run(endpoints=["sim:a"], limit=8, fixture="veteran_dental", mode="simulated", run_id="r13",
                 run_ts=pd.Timestamp("2026-11-26", tz="UTC"), git_commit="abc")
    assert len(out["dim_access_question"]) == 8
    assert set(out["dim_access_question"]["domain"]) == {"veteran_dental"}
    n = len(ab.all_items())
    assert len(ab.load_batch(limit=n, fixture="all")) == n
    assert {r["id"] for r in avi.load_items()} <= {r["id"] for r in ab.all_items()}
