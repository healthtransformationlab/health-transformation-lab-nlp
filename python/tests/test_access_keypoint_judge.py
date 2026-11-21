"""Access JSONL → lab grader question rows + key-point judge prompt for Databricks / OpenAI.

must_include becomes the key points (GlobalDentBench-style covered/not); red_flags pad to five
and are also judged as auto-fail hits. Chart judge.py is not used here.
"""

from __future__ import annotations

import json

import pytest

from health_transformation_lab_nlp import access_keypoint_judge as ak
from health_transformation_lab_nlp import access_phi_items as api
from health_transformation_lab_nlp.grader_tables import KEY_POINTS as GRADER_KEY_POINTS


@pytest.fixture(scope="module")
def rows():
    return api.load_items()


def test_key_points_are_must_include_first_then_negated_red_flags_up_to_five(rows):
    row = rows[0]
    pts = ak.key_points(row)
    assert 3 <= len(pts) <= ak.KEY_POINTS
    assert pts[: len(row["must_include"])] == row["must_include"]
    assert len(pts) == min(ak.KEY_POINTS, len(row["must_include"]) + len(row["red_flags"]))
    for p in pts[len(row["must_include"]) :]:
        assert p.startswith("Does not: ")


def test_key_points_constant_matches_grader():
    assert ak.KEY_POINTS == GRADER_KEY_POINTS == 5


def test_infer_level_defaults_l2_and_raises_for_harder_signals():
    base = {
        "id": "ACC_INS_001",
        "knowledge_cutoff_sensitive": False,
        "must_include": ["a", "b", "c"],
        "red_flags": ["r"],
        "evidence_source": "x",
        "is_simulated": True,
        "domain": "insurance_cost",
        "persona": "p",
        "prompt": "hi",
        "planted_phi": [{"text": "hi", "type": "NAME"}, {"text": "x", "type": "OTHER"}],
    }
    assert ak.infer_level(base) == "L2"
    assert ak.infer_level({**base, "knowledge_cutoff_sensitive": True}) == "L3"
    assert ak.infer_level({**base, "id": "ACC_INS_001_H1"}) == "L3"
    assert ak.infer_level({**base, "level": "L1"}) == "L1"


def test_to_grader_question_matches_dim_columns(rows):
    q = ak.to_grader_question(rows[0])
    assert set(q) == {
        "question_id", "category", "category_order", "level", "n_key_points", "source", "simulated",
    }
    assert q["question_id"] == rows[0]["id"]
    assert q["category"] == "Access to care"
    assert q["category_order"] == 1
    assert q["n_key_points"] == len(ak.key_points(rows[0]))
    assert q["source"] == rows[0]["evidence_source"]
    assert q["simulated"] is True
    assert q["level"] in ("L1", "L2", "L3")


def test_to_grader_questions_covers_every_fixture_row(rows):
    frame = ak.to_grader_questions()
    assert list(frame["question_id"]) == [r["id"] for r in rows]
    assert (frame["category"] == "Access to care").all()
    assert (frame["n_key_points"] <= ak.KEY_POINTS).all()


def test_judge_messages_and_ai_query_prompt_include_prompt_answer_and_key_points(rows):
    row, answer = rows[0], "Ask an FQHC about sliding-fee; fees vary; do not invent free care."
    msgs = ak.judge_messages(row, answer)
    assert msgs[0]["role"] == "system" and ak.PROMPT_VERSION in ak.KEYPOINT_SYSTEM
    assert msgs[1]["role"] == "user"
    user = msgs[1]["content"]
    assert row["prompt"] in user
    assert answer in user
    for kp in ak.key_points(row):
        assert kp in user
    for rf in row["red_flags"]:
        assert rf in user
    blob = ak.ai_query_prompt(row, answer)
    assert isinstance(blob, str) and row["prompt"] in blob and answer in blob
    assert "covered" in blob.lower()


def test_parse_and_score_verdict_counts_covered_over_key_points(rows):
    n = len(ak.key_points(rows[0]))
    n_rf = len(rows[0]["red_flags"])
    raw = json.dumps({
        "covered": [True, True, False] + [False] * max(0, n - 3),
        "red_flag_hit": [False] * n_rf,
        "harm": "S0",
        "rationale": "two pathway points met",
    })
    parsed = ak.parse_verdict(raw, n_key_points=n, n_red_flags=n_rf)
    assert parsed["covered"][:3] == [True, True, False]
    assert len(parsed["covered"]) == n
    scored = ak.score_verdict(parsed, n_key_points=n)
    assert scored["key_points_covered"] == 2
    assert scored["score"] == pytest.approx(2 / n)
    assert scored["harm"] == "S0"
    assert scored["red_flag_hit"] == [False] * n_rf


def test_score_verdict_rejects_bad_harm_and_length_mismatch():
    with pytest.raises(ValueError, match="harm"):
        ak.score_verdict({"covered": [True], "red_flag_hit": [], "harm": "S9"}, n_key_points=1)
    with pytest.raises(ValueError, match="covered"):
        ak.parse_verdict('{"covered": [true], "red_flag_hit": [], "harm": "S0"}',
                         n_key_points=3, n_red_flags=0)
