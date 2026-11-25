"""Spec 044 US2 (#939): the oral section's dental discount and voucher questions load, validate and run in the batch."""

import pandas as pd
import pytest

from health_transformation_lab_nlp import access_batch as ab
from health_transformation_lab_nlp import access_discount_items as adi


def test_six_oral_discount_items_load():
    rows = adi.load_items()
    assert [r["id"] for r in rows] == [f"ACC_DISC_00{i}" for i in range(1, 7)]
    assert {r["section_code"] for r in rows} == {"oral"} and {r["domain"] for r in rows} == {"discount_voucher"}


def test_every_item_cites_https_sources_and_has_only_positive_points():
    for r in adi.load_items():
        assert r["evidence_urls"] and all(u.startswith("https://") for u in r["evidence_urls"])
        assert all(x["url"].startswith("https://") for x in r["resources"] if x.get("url"))
        assert not any(p.startswith(("Does not", "Do not", "Omits", "Never")) for p in r["must_include"]), r["id"]
        assert "checked 2026-11-25" in r["evidence_source"]


@pytest.mark.parametrize("field, bad", [("evidence_urls", ["http://insecure.example/"]), ("evidence_urls", []),
                                        ("must_include", ["one", "two"])])
def test_a_bad_item_is_refused(field, bad):
    row = dict(adi.load_items()[0], **{field: bad})
    with pytest.raises(ValueError):
        adi.validate_item(row)


def test_the_batch_scores_the_discount_set_and_all_includes_it():
    assert "discount_voucher" in ab.FIXTURES
    out = ab.run(endpoints=["sim:a"], limit=6, fixture="discount_voucher", mode="simulated", run_id="r12",
                 run_ts=pd.Timestamp("2026-11-25", tz="UTC"), git_commit="abc")
    assert len(out["dim_access_question"]) == 6 and not out["fact_access_answer"]["is_phi_leak"].any()
    assert len(ab.load_batch(limit=21, fixture="all")) == 21
