"""Spec 042 US2 (#864): the model ranking, its drivers and the LLM readers' traces and scores load into Databricks,
with comments that explain them. A fake client stands in for the workspace: it records the SQL it is sent and the
runs and traces it would write, and answers which are already there. Synthetic charts only.
"""

import re

import pytest

from health_transformation_lab_nlp import model_drivers as md
from health_transformation_lab_nlp import model_drivers_load as ld
from health_transformation_lab_nlp import readme_results as rr

FAKE = "ghp_" + "Q7w" * 12          # built here so no token-shaped text is committed


class FakeClient:
    def __init__(self):
        self.sql_sent, self.runs, self.traces = [], [], []

    def sql(self, statement):
        self.sql_sent.append(statement)

    def existing_trace_keys(self):
        return {t["tags"]["trace_key"] for t in self.traces}

    def existing_run_methods(self, commit):
        return {r["tags"]["method_code"] for r in self.runs if r["tags"]["git_commit_sha"] == commit}

    def log_run(self, run):
        self.runs.append(run)

    def write_trace(self, trace):
        self.traces.append(trace)

    def flush(self):
        pass


@pytest.fixture(scope="module")
def inp():
    return rr.load_inputs()


@pytest.fixture(scope="module")
def built(inp):
    return md.build(inp, n_boot=20)


BATCH = {"run_id": "load-test", "run_ts": "2026-11-17T00:00:00Z", "git_commit_sha": "abc1234"}


def test_sql_literal():
    assert ld.sql_literal(None) == "NULL" and ld.sql_literal(float("nan")) == "NULL"
    assert ld.sql_literal(True) == "TRUE" and ld.sql_literal(3) == "3"
    assert ld.sql_literal("it's") == "'it\\'s'"


def test_table_sql_declares_types_and_comments(built):
    stmts = ld.table_sql("model_rank", built["model_rank"], BATCH, "cat", "sch")
    create = stmts[0]
    assert create.startswith("CREATE OR REPLACE TABLE cat.sch.model_rank (")
    assert "correct_count BIGINT COMMENT 'Charts whose status group" in create
    assert "is_rules4 BOOLEAN COMMENT" in create and "vs_leader_p_ratio DOUBLE COMMENT" in create
    assert "git_commit_sha STRING COMMENT" in create
    assert re.search(r"\) COMMENT 'PerioBench: every note-reading method ranked", create)
    rows = sum(s.count("),(") + 1 for s in stmts[1:])
    assert all(s.startswith("INSERT INTO cat.sch.model_rank VALUES") for s in stmts[1:]) and rows == 43


def test_every_loaded_column_has_a_comment(built, inp):
    tables = ld.tables(built, inp)
    assert set(tables) == set(md.TABLES) | {"model_chart_result"}
    for name, df in tables.items():
        _, cols = ld.COMMENTS[name]
        missing = [c for c in df.columns if c not in cols]
        assert not missing, (name, missing)


def test_chart_result_one_row_per_method_and_chart(built, inp):
    cr = ld.tables(built, inp)["model_chart_result"]
    assert len(cr) == 43 * 223
    top = cr[cr.method_code == "modernbert-large+rules4"]
    assert top.is_correct.sum() == 203
    assert not (cr.is_correct & cr.is_unsafe_error).any() and not (cr.is_correct & cr.is_wrong_stage).any()


def test_llm_traces_scored_and_scrubbed(inp, monkeypatch):
    traces = ld.llm_traces(inp)
    assert {t["tags"]["method_code"] for t in traces} == {"llama-3.3-70b-instruct", "medgemma-4b-it",
                                                         "medgemma-1.5-4b-it"}
    assert len(traces) == 3 * 223
    assert len({t["tags"]["trace_key"] for t in traces}) == len(traces)
    llama = [t for t in traces if t["tags"]["method_code"] == "llama-3.3-70b-instruct"]
    assert sum(t["assessments"]["is_correct"] for t in llama) == 187       # the leaderboard's 83.9 of 100
    t = llama[0]
    assert {"is_correct", "is_unsafe_error", "is_wrong_stage", "is_gate_ok", "is_fallback"} <= set(t["assessments"])
    assert t["attributes"]["gen_ai.usage.input_tokens"] > 0 and t["end_ns"] > t["start_ns"]
    assert "note_text" in t["inputs"]


def test_secret_in_a_note_never_reaches_a_trace(inp):
    key = inp["key"].copy()
    key.loc[key.index[0], "note_text"] = f"token {FAKE} in a note"
    traces = ld.llm_traces({**inp, "key": key})
    assert not any(FAKE in str(t) for t in traces)


def test_load_twice_writes_traces_and_runs_once(built, inp):
    client = FakeClient()
    first = ld.load(built, inp, client, BATCH, catalog="cat", schema="sch")
    assert first["trace_written_count"] == 3 * 223 and first["run_written_count"] == 43
    assert first["table_count"] == len(md.TABLES) + 1
    second = ld.load(built, inp, client, BATCH, catalog="cat", schema="sch")
    assert second["trace_written_count"] == 0 and second["run_written_count"] == 0
    assert len(client.traces) == 3 * 223 and len(client.runs) == 43
    run = next(r for r in client.runs if r["tags"]["method_code"] == "modernbert-large+rules4")
    assert run["metrics"]["correct_count"] == 203 and run["params"]["size_code"] == "large"
