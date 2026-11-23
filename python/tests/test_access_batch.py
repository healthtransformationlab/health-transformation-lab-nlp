"""AccessBench LLM batch: simulated scoring into gold-shaped frames (spec 043)."""

from __future__ import annotations

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
    monkeypatch.setattr(ab, "_answer", lambda row, endpoint, mode, chat: (
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
