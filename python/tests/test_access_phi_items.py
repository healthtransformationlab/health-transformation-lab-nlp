"""AccessBench dual fixture: access pathway rubric + planted synthetic PHI for leak checks.

Synthetic identifiers only (from the de-id challenge name pool / reserved example shapes).
Never real PHI.
"""

from __future__ import annotations

import pytest

from health_transformation_lab_nlp import access_phi_items as api
from health_transformation_lab_nlp import deid
from health_transformation_lab_nlp.phi_challenge import CH_FIRST, CH_LAST

REQUIRED = ("id", "domain", "persona", "prompt", "must_include", "red_flags",
            "evidence_source", "knowledge_cutoff_sensitive", "planted_phi", "is_simulated")


def test_simulated_access_phi_items_file_exists_and_loads():
    rows = api.load_items()
    assert len(rows) >= 5
    assert all(r["is_simulated"] is True for r in rows)
    assert all(r["id"].startswith("ACC_") for r in rows)


def test_every_item_has_the_access_and_phi_contract():
    for r in api.load_items():
        missing = [k for k in REQUIRED if k not in r]
        assert not missing, f"{r.get('id')}: missing {missing}"
        assert isinstance(r["must_include"], list) and 3 <= len(r["must_include"]) <= 5
        assert isinstance(r["red_flags"], list) and 1 <= len(r["red_flags"]) <= 3
        assert isinstance(r["planted_phi"], list) and len(r["planted_phi"]) >= 2
        assert isinstance(r["knowledge_cutoff_sensitive"], bool)


def test_every_planted_phi_span_appears_verbatim_in_the_prompt():
    for r in api.load_items():
        for p in r["planted_phi"]:
            assert p["text"] in r["prompt"], f"{r['id']}: planted {p['text']!r} not in prompt"
            assert r["prompt"].count(p["text"]) >= 1


def test_planted_names_come_from_the_synthetic_challenge_pool():
    names = {p["text"] for r in api.load_items() for p in r["planted_phi"] if p["type"] == "NAME"}
    assert names, "expected at least one planted NAME"
    allowed = {f"{a} {b}" for a in CH_FIRST for b in CH_LAST}
    assert names <= allowed, f"non-synthetic names: {names - allowed}"


def test_a_leaky_answer_fails_the_phi_gate_and_a_scrubbed_one_passes():
    row = api.load_items()[0]
    known = api.known_phi_for_leak_check(row)
    leaky = "Call " + known[0]["text"] + " at the FQHC front desk."
    scrubbed = "Call the FQHC that accepts uninsured walk-ins; ask about sliding fee."
    assert deid.leak_check(leaky, known) == [known[0]["text"]]
    assert deid.leak_check(scrubbed, known) == []


def test_validate_items_rejects_phi_missing_from_prompt():
    bad = {
        "id": "ACC_BAD_001", "domain": "insurance_cost", "persona": "x",
        "prompt": "I need a dentist and have no insurance.",
        "must_include": ["a", "b", "c"], "red_flags": ["r"],
        "evidence_source": "CMS", "knowledge_cutoff_sensitive": False,
        "planted_phi": [
            {"text": "Imani Abernathy", "type": "NAME"},
            {"text": "205-555-0147", "type": "PHONE"},
        ],
        "is_simulated": True,
    }
    with pytest.raises(ValueError, match="not in prompt"):
        api.validate_item(bad)
