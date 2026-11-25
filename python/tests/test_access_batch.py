"""AccessBench LLM batch: simulated scoring into gold-shaped frames (spec 043)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from health_transformation_lab_nlp import access_batch as ab
from health_transformation_lab_nlp import access_phi_items as api
from health_transformation_lab_nlp import gold_names, table_comments


def test_load_batch_defaults_to_five_stable_ids():
    rows = ab.load_batch()
    assert len(rows) == 5
    assert [r["id"] for r in rows] == [r["id"] for r in api.load_items()[:5]]


def test_load_batch_rejects_limit_above_fixture_count():
    with pytest.raises(ValueError, match="limit"):
        ab.load_batch(limit=len(api.load_items()) + 1)


def test_simulated_run_builds_dim_and_fact_for_each_endpoint():
    out = ab.run(
        endpoints=["sim:llama", "sim:gpt"],
        limit=5,
        mode="simulated",
        run_id="r1",
        run_ts=pd.Timestamp("2026-11-23", tz="UTC"),
        git_commit="abc1234",
    )
    dim, fact = out["dim_access_question"], out["fact_access_answer"]
    assert len(dim) == 5
    assert len(fact) == 10
    assert set(fact["endpoint"]) == {"sim:llama", "sim:gpt"}
    assert fact["is_simulated"].all()
    assert fact["score"].between(0, 1).all()
    assert (fact["harm"].isin(["S0", "S1", "S2"])).all()
    assert "is_phi_leak" in fact.columns


def test_leaky_simulated_answer_sets_phi_leak(monkeypatch):
    def leaky_chat(messages, model=None):
        row_prompt = messages[-1]["content"] if messages else ""
        # Echo the first planted name from whatever item we can find
        for r in api.load_items():
            if r["prompt"][:40] in row_prompt or r["id"] in row_prompt:
                name = next(p["text"] for p in r["planted_phi"] if p["type"] == "NAME")
                return {"raw": f"Please call {name} back.", "input_tokens": 1, "output_tokens": 1,
                        "latency_s": 0.01}
        return {"raw": "Call Imani Abernathy.", "input_tokens": 1, "output_tokens": 1, "latency_s": 0.01}

    # Force answer path to use chat even in a custom mode path: monkeypatch answer fn
    monkeypatch.setattr(ab, "_answer", lambda row, endpoint, mode, chat, **kw: (
        f"Call {next(p['text'] for p in row['planted_phi'] if p['type']=='NAME')} today.",
        {"input_tokens": 0, "output_tokens": 0, "latency_s": 0.0, "error": ""},
    ))
    out = ab.run(
        endpoints=["sim:x"], limit=1, mode="simulated", run_id="r2",
        run_ts=pd.Timestamp("2026-11-23", tz="UTC"), git_commit="abc",
    )
    assert bool(out["fact_access_answer"].iloc[0]["is_phi_leak"]) is True


def test_to_gold_accepts_access_batch_frames():
    out = ab.run(
        endpoints=["sim:a"], limit=2, mode="simulated", run_id="r3",
        run_ts=pd.Timestamp("2026-11-23", tz="UTC"), git_commit="deadbeef",
    )
    gdim = gold_names.to_gold(out["dim_access_question"], "dim_access_question")
    gfact = gold_names.to_gold(out["fact_access_answer"], "fact_access_answer")
    assert "question_id" in gdim.columns and "answering_endpoint_name" in gfact.columns
    assert table_comments.declared("gold_access_bench", "fact_access_answer")[0]
    assert table_comments.declared("gold_access_bench", "dim_access_question")[0]


def test_max_usd_stops_further_live_calls():
    calls = {"n": 0}

    def chat(messages, model=None):
        calls["n"] += 1
        return {"raw": "Ask the clinic about sliding fee and FQHC options; fees vary.",
                "input_tokens": 500_000, "output_tokens": 500_000, "latency_s": 0.1}

    out = ab.run(
        endpoints=["databricks-meta-llama-3-3-70b-instruct"],
        limit=5,
        mode="live",
        judge_endpoint="databricks-meta-llama-3-3-70b-instruct",
        max_usd=0.01,
        usd_per_million_in=5.0,
        usd_per_million_out=15.0,
        run_id="r4",
        run_ts=pd.Timestamp("2026-11-23", tz="UTC"),
        git_commit="abc",
        chat=chat,
    )
    # First answer may run; subsequent ones should error out on budget
    errors = out["fact_access_answer"]["error"].fillna("")
    assert calls["n"] >= 1
    assert (errors.str.contains("max_usd") | errors.str.len().eq(0)).any()
    assert errors.str.contains("max_usd").sum() >= 1


# ---------- US5 (#929): the question sets ----------

def test_fixtures_are_the_named_sets():
    assert ab.FIXTURES == ("phi", "perio_screening", "discount_voucher", "all")     # discount_voucher: #939


def test_load_batch_picks_the_screening_set_and_all():
    from health_transformation_lab_nlp import access_hard_items as ahi
    hard = ab.load_batch(limit=10, fixture="perio_screening")
    assert [r["id"] for r in hard] == [r["id"] for r in ahi.load_items()]
    assert all(r["id"].startswith("ACC_PERIO_SCR_") for r in hard)
    both = ab.load_batch(limit=15, fixture="all")
    assert [r["id"] for r in both] == [r["id"] for r in api.load_items()] + [r["id"] for r in hard]
    assert [r["id"] for r in ab.load_batch()] == [r["id"] for r in api.load_items()[:5]]     # default unchanged


def test_load_batch_rejects_an_unknown_fixture_and_a_limit_too_big_for_the_set():
    with pytest.raises(ValueError, match="nonsense"):
        ab.load_batch(fixture="nonsense")
    with pytest.raises(ValueError, match="limit"):
        ab.load_batch(limit=11, fixture="perio_screening")


def test_simulated_run_scores_the_screening_set_with_no_leak():
    out = ab.run(endpoints=["sim:llama"], limit=10, fixture="perio_screening", mode="simulated", run_id="r5",
                 run_ts=pd.Timestamp("2026-11-24", tz="UTC"), git_commit="abc1234")
    dim, fact = out["dim_access_question"], out["fact_access_answer"]
    assert len(dim) == 10 and len(fact) == 10
    assert not fact["is_phi_leak"].any()                      # nothing was planted, so nothing can leak
    assert set(dim["question_id"]) == set(fact["question_id"])


# ---------- US6 (#931): answers are not cut off, and a cut-off answer is marked ----------

def _live(chat=None, **kw):
    return ab.run(endpoints=["databricks-meta-llama-3-3-70b-instruct"], limit=1, mode="live",
                  judge_endpoint="databricks-qwen3-next-80b-a3b-instruct", run_id="r6",
                  run_ts=pd.Timestamp("2026-11-24", tz="UTC"), git_commit="abc", chat=chat, **kw)


def test_the_answer_cap_reaches_the_answering_client(monkeypatch):
    from health_transformation_lab_nlp import llm_reader
    built = {}

    class FakeChat:
        def __init__(self, model=None, max_tokens=300, **kw):
            built[model] = max_tokens

        def __call__(self, messages, visit_id=None):
            return {"raw": "Call the state Medicaid dental line.", "input_tokens": 10, "output_tokens": 10,
                    "latency_s": 0.0}

    monkeypatch.setattr(llm_reader, "OpenAIChat", FakeChat)
    _live(answer_max_tokens=1500)
    assert built["databricks-meta-llama-3-3-70b-instruct"] == 1500       # not the chart reader's 300


def test_an_answer_that_reaches_the_cap_is_marked_truncated():
    def chat_at(n):
        return lambda messages, model=None: {"raw": "Ask which codes were billed.", "input_tokens": 5,
                                             "output_tokens": n, "latency_s": 0.0}
    assert bool(_live(chat_at(1500), answer_max_tokens=1500)["fact_access_answer"].iloc[0]["is_truncated"])
    assert not bool(_live(chat_at(200), answer_max_tokens=1500)["fact_access_answer"].iloc[0]["is_truncated"])
    sim = ab.run(endpoints=["sim:a"], limit=1, mode="simulated", run_id="r7",
                 run_ts=pd.Timestamp("2026-11-24", tz="UTC"), git_commit="abc")
    assert not sim["fact_access_answer"]["is_truncated"].any()


def test_is_truncated_reaches_gold():
    out = ab.run(endpoints=["sim:a"], limit=1, mode="simulated", run_id="r8",
                 run_ts=pd.Timestamp("2026-11-24", tz="UTC"), git_commit="abc")
    assert "is_truncated" in gold_names.to_gold(out["fact_access_answer"], "fact_access_answer").columns


# ---------- spec 044 US1 (#938): the section reaches gold ----------

def test_the_question_table_carries_each_questions_section():
    out = ab.run(endpoints=["sim:a"], limit=15, fixture="all", mode="simulated", run_id="r10",
                 run_ts=pd.Timestamp("2026-11-25", tz="UTC"), git_commit="abc")
    dim = out["dim_access_question"]
    assert set(dim["section"]) == {"oral"}
    assert "section_code" in gold_names.to_gold(dim, "dim_access_question").columns

# ---------- US8 (#935): resource columns ----------

def test_a_live_run_records_resource_level_invented_contact_and_link_counts(monkeypatch):
    from health_transformation_lab_nlp import access_resources
    monkeypatch.setattr(access_resources, "check_links",
                        lambda urls, fetch=None: {u: {"https://ok.example/": True, "https://gone.example/": False}.get(u) for u in urls})
    n_kp = 5

    def chat(messages, model=None):
        if "Return JSON only" in messages[-1]["content"]:      # the judge
            return {"raw": json.dumps({"covered": [True] * n_kp, "red_flag_hit": [False, False, False], "harm": "S1",
                                       "resource_level": 2, "invented_contact": True, "rationale": "x"}),
                    "input_tokens": 1, "output_tokens": 1, "latency_s": 0.0}
        return {"raw": "See https://ok.example/ and https://gone.example/ and https://slow.example/", "input_tokens": 5,
                "output_tokens": 50, "latency_s": 0.0}
    row = _live(chat)["fact_access_answer"].iloc[0]
    assert (row["resource_level"], bool(row["is_invented_contact"])) == (2, True)
    assert (row["link_count"], row["broken_link_count"], row["unchecked_link_count"]) == (3, 1, 1)


def test_resource_columns_reach_gold_and_are_empty_in_simulated_runs():
    out = ab.run(endpoints=["sim:a"], limit=1, mode="simulated", run_id="r9",
                 run_ts=pd.Timestamp("2026-11-25", tz="UTC"), git_commit="abc")
    fact = out["fact_access_answer"]
    assert fact["resource_level"].isna().all() and (fact["link_count"] == 0).all()
    g = gold_names.to_gold(fact, "fact_access_answer")
    assert {"resource_level_num", "is_invented_contact", "link_count", "broken_link_count", "unchecked_link_count"} <= set(g.columns)


# ---------- spec 045 US1 (#943): coverage of positive points ----------

def test_the_batch_writes_positive_coverage_beside_the_legacy_score():
    out = ab.run(endpoints=["sim:a"], limit=5, mode="simulated", run_id="r11",
                 run_ts=pd.Timestamp("2026-11-25", tz="UTC"), git_commit="abc")
    fact = out["fact_access_answer"]
    assert (fact["positive_point_count"] < 5).all() and (fact["coverage_ratio"] == 1.0).all()   # simulated: all met
    g = gold_names.to_gold(fact, "fact_access_answer")
    assert {"positive_point_count", "covered_positive_point_count", "coverage_ratio", "score_ratio"} <= set(g.columns)


# ---------- spec 045 US2 (#944): next step and per-point verdicts reach gold ----------

def test_a_live_v3_verdict_records_next_step_and_verdicts():
    from health_transformation_lab_nlp import access_keypoint_judge as ak
    row = api.load_items()[0]
    n_pos, n_neg = len(ak.positive_points(row)), len(ak.negative_checks(row))

    def chat(messages, model=None):
        if "point_verdicts" in messages[-1]["content"]:       # the judge
            return {"raw": json.dumps({"point_verdicts": [{"verdict": "met", "span": "call the clinic"}]
                                       + [{"verdict": "missing", "span": ""}] * (n_pos - 1),
                                       "red_flag_hit": [False] * n_neg, "harm": "S1", "next_step_pass": False,
                                       "resource_level": 1, "invented_contact": False, "rationale": "x"}),
                    "input_tokens": 1, "output_tokens": 1, "latency_s": 0.0}
        return {"raw": "Call the clinic.", "input_tokens": 5, "output_tokens": 5, "latency_s": 0.0}
    fact = _live(chat)["fact_access_answer"].iloc[0]
    assert fact["is_next_step_pass"] == False and fact["covered_positive_point_count"] == 1      # noqa: E712
    assert json.loads(fact["point_verdict_text"])[0] == {"verdict": "met", "span": "call the clinic"}
    g = gold_names.to_gold(_live(chat)["fact_access_answer"], "fact_access_answer")
    assert {"is_next_step_pass", "point_verdict_text"} <= set(g.columns)


def test_a_town_in_a_simulated_answer_is_not_a_phi_leak(monkeypatch):
    # spec 045 US4 (#946): CITY is recorded, not gated
    def chat(messages, model=None):
        content = messages[-1]["content"]
        if "Return JSON only" in content:
            return {"raw": json.dumps({"covered": [True] * 5, "red_flag_hit": [False] * 3, "harm": "S0",
                                       "rationale": "x"}), "input_tokens": 1, "output_tokens": 1, "latency_s": 0.0}
        return {"raw": "Try the health center in Cottondale; ask about the sliding fee.", "input_tokens": 1,
                "output_tokens": 1, "latency_s": 0.0}
    fact = ab.run(endpoints=["e"], limit=1, fixture="phi", mode="live", judge_endpoint="j", chat=chat,
                            run_id="r", run_ts="2026-11-25T00:00:00Z", git_commit="c")["fact_access_answer"]
    assert not bool(fact.iloc[0]["is_phi_leak"])
