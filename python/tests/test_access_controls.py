"""Seeded control answers test the AccessBench judge (spec 045 US3, #945). No network."""
import json

import pytest

from health_transformation_lab_nlp import access_batch, access_controls as ac, access_keypoint_judge as ak


def test_controls_load_with_every_label_for_each_question():
    controls = ac.load_controls()
    by_q: dict[str, set] = {}
    for c in controls:
        by_q.setdefault(c["question_id"], set()).add(c["label_code"])
    assert len(by_q) >= 2
    assert all(labels == set(ac.LABELS) for labels in by_q.values())


def test_every_control_names_a_real_item_and_its_expected_grades():
    items = {r["id"] for r in access_batch.all_items()}
    for c in ac.load_controls():
        assert c["question_id"] in items
        assert c["expected_harm_code"] in ("S0", "S1", "S2")
        assert isinstance(c["expected_next_step_pass"], bool)
        assert isinstance(c["expected_covered_count"], int)
        assert c["is_simulated"] is True


def test_the_labels_carry_the_expected_harm():
    for c in ac.load_controls():
        want = {"clear_s2": "S2", "clear_s1": "S1", "near_miss": "S0", "empty_but_polished": "S0", "good": "S0"}
        assert c["expected_harm_code"] == want[c["label_code"]], c["control_id"]


def test_validate_rejects_an_unknown_label_and_a_missing_field():
    good = ac.load_controls()[0]
    with pytest.raises(ValueError, match="label_code"):
        ac.validate_control({**good, "label_code": "awful"})
    bad = dict(good)
    del bad["expected_harm_code"]
    with pytest.raises(ValueError, match="expected_harm_code"):
        ac.validate_control(bad)


def test_expected_vs_judged_matches_harm_next_step_and_coverage_within_one():
    c = {"expected_harm_code": "S2", "expected_next_step_pass": False, "expected_covered_count": 0}
    ok = ac.expected_vs_judged(c, {"harm": "S2", "next_step_pass": False, "covered_positive_point_count": 1})
    assert ok == {"is_harm_match": True, "is_next_step_match": True, "is_coverage_match": True, "is_control_match": True}
    miss = ac.expected_vs_judged(c, {"harm": "S0", "next_step_pass": False, "covered_positive_point_count": 0})
    assert miss["is_harm_match"] is False and miss["is_control_match"] is False
    far = ac.expected_vs_judged(c, {"harm": "S2", "next_step_pass": False, "covered_positive_point_count": 3})
    assert far["is_coverage_match"] is False


def test_a_judge_without_next_step_is_not_counted_against_the_control():
    c = {"expected_harm_code": "S0", "expected_next_step_pass": True, "expected_covered_count": 4}
    got = ac.expected_vs_judged(c, {"harm": "S0", "next_step_pass": None, "covered_positive_point_count": 4})
    assert got["is_next_step_match"] is None and got["is_control_match"] is True


def _run(**kw):
    return access_batch.run(endpoints=["sim:llama"], limit=1, fixture="perio_screening", run_id="r1",
                            run_ts="2026-11-25T00:00:00Z", git_commit="abc", **kw)


def test_controls_off_by_default():
    fact = _run()["fact_access_answer"]
    assert not fact["endpoint"].str.startswith("control:").any()
    assert fact["is_control_match"].isna().all()


def test_controls_are_scored_as_pseudo_endpoints_and_their_questions_join_the_dim():
    out = _run(controls=True)
    fact, dim = out["fact_access_answer"], out["dim_access_question"]
    ctl = fact[fact["endpoint"].str.startswith("control:")]
    assert len(ctl) == len(ac.load_controls())
    assert set(ctl["endpoint"]) == {f"control:{lab}" for lab in ac.LABELS}
    assert set(ctl["question_id"]) <= set(dim["question_id"])
    assert dim["question_id"].is_unique
    assert ctl["cost_usd"].eq(0).all()
    # the simulated judge marks every answer good, so only the good controls match
    good = ctl[ctl["endpoint"] == "control:good"]
    assert good["is_control_match"].all()
    assert not ctl[ctl["endpoint"] == "control:clear_s2"]["is_control_match"].any()


def test_a_live_judge_grades_the_control_text_itself():
    seen = []
    items = access_batch.all_items()

    def chat(messages, model=None):
        content = messages[-1]["content"]
        if "point_verdicts" in content:          # the judge
            seen.append(content)
            item = next(r for r in items if r["prompt"] in content)
            n_p, n_n = len(ak.positive_points(item)), len(ak.negative_checks(item))
            return {"raw": json.dumps({"point_verdicts": [{"verdict": "missing", "span": ""}] * n_p,
                                       "red_flag_hit": [True] + [False] * (n_n - 1), "next_step_pass": False,
                                       "harm": "S2", "resource_level": 0, "invented_contact": False,
                                       "rationale": "x"}), "input_tokens": 1, "output_tokens": 1, "latency_s": 0.0}
        return {"raw": "answer", "input_tokens": 1, "output_tokens": 1, "latency_s": 0.0}
    fact = _run(controls=True, mode="live", judge_endpoint="judge", chat=chat)["fact_access_answer"]
    s2 = ac.load_controls()
    s2_text = next(c["answer_text"] for c in s2 if c["label_code"] == "clear_s2")
    assert any(s2_text[:60] in s for s in seen)
    row = fact[fact["endpoint"] == "control:clear_s2"].iloc[0]
    assert row["error"] == "" and bool(row["is_control_match"])
