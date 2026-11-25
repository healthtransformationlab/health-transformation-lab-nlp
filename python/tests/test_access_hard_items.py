"""Hard AccessBench items: periodontal screening access pathways (issue #919)."""

from __future__ import annotations

import pytest

from health_transformation_lab_nlp import access_hard_items as ahi

REQUIRED = (
    "id", "domain", "persona", "prompt", "must_include", "red_flags",
    "evidence_source", "knowledge_cutoff_sensitive", "is_simulated",
    "source_thread_url", "screening_goal_tag",
)
EXPECTED_IDS = [f"ACC_PERIO_SCR_{i:03d}" for i in range(1, 12)]   # 011: the contrastive pair of 003 (#957)


def test_hard_items_load_the_perio_screening_rows():
    rows = ahi.load_items()
    assert [r["id"] for r in rows] == EXPECTED_IDS
    assert all(r["is_simulated"] is True for r in rows)
    assert all(r["screening_goal_tag"] == "perio_screening_2030" for r in rows)


def test_every_hard_item_meets_the_access_contract():
    for r in ahi.load_items():
        missing = [k for k in REQUIRED if k not in r]
        assert not missing, f"{r.get('id')}: missing {missing}"
        assert 3 <= len(r["must_include"]) <= 5
        assert 1 <= len(r["red_flags"]) <= 3
        assert isinstance(r["knowledge_cutoff_sensitive"], bool)
        assert r["source_thread_url"].startswith("http")
        assert "planted_phi" not in r


def test_validate_rejects_wrong_goal_tag():
    bad = {
        "id": "ACC_PERIO_SCR_099",
        "section_code": "oral",
        "domain": "insurance_cost",
        "persona": "x",
        "prompt": "How do I get a gum screening on Medicaid?",
        "must_include": ["a", "b", "c"],
        "red_flags": ["r"],
        "evidence_source": "CMS",
        "knowledge_cutoff_sensitive": False,
        "is_simulated": True,
        "source_thread_url": "https://example.com/x",
        "screening_goal_tag": "wrong",
    }
    with pytest.raises(ValueError, match="screening_goal_tag"):
        ahi.validate_item(bad)


def test_validate_requires_the_source_fields():
    # spec 045 US4 (#946)
    row = dict(ahi.load_items()[0])
    del row["recheck_date"]
    with pytest.raises(ValueError, match="recheck_date"):
        ahi.validate_item(row)
    assert ahi.load_items()[0]["jurisdiction_code"] == "US-NY"


def test_no_prompt_gives_the_test_away():
    # 045 US5 (#957): the external reviews found prompts that flagged the test or stated the answer
    from health_transformation_lab_nlp import access_discount_items as adi, access_phi_items as api
    for row in api.load_items() + ahi.load_items() + adi.load_items():
        low = row["prompt"].lower()
        for phrase in ("simulated", "mrn", "under-21 pathway"):
            assert phrase not in low, (row["id"], phrase)
