"""Spec 042 US3 (#866): the de-identification tools in the multi-model evaluation format (the one docs/model_drivers.md
uses for phenotyping): a ranked table with paired exact McNemar tests against the best tool on the same identifiers,
contrasts that add one ingredient, and what decides whether an identifier is removed, with an AUC.

The paired tests need one row per tool and identifier, which data/deid/scores.csv (aggregates) does not have: the
local tools were rerun on CPU on the same synthetic challenge set (seed 7, 400 notes) and the rerun must reproduce the
committed aggregates exactly. Fake PHI on synthetic notes only.
"""

import pandas as pd
import pytest

from health_transformation_lab_nlp import deid_drivers as dd

ALLOWED_SUFFIX = ("_id", "_key", "_code", "_name", "_text", "_count", "_ratio", "_pct", "_num", "_seconds", "_ts",
                  "_sha")


@pytest.fixture(scope="module")
def built():
    return dd.build(dd.load_span_result(), n_boot=30)


# ---------- the per-identifier results ----------

def test_span_result_from_raw_spans_unions_engines_then_guards():
    text = "Pt Rose Ng seen; Glickman class II on #3."
    rec = {"note_id": 9, "tier": "unseen", "text": text,
           "phi": [{"start": 3, "end": 10, "text": "Rose Ng", "type": "PATIENT"}],
           "decoys": [{"start": 17, "end": 34, "text": "Glickman class II", "type": "EPONYM"}]}
    raw = {"regex_v2": [[{"start": 3, "end": 7, "type": "NAME"}]],                  # "Rose" only: a leak
           "presidio": [[{"start": 8, "end": 10, "type": "NAME"}, {"start": 17, "end": 25, "type": "NAME"}]]}
    sr = dd.span_result([rec], raw, ["regex_v2", "presidio", "presidio+regex_v2", "presidio+regex_v2+guard"])
    got = sr.set_index(["method_code", "item_kind_code"]).removed_char_count
    assert got[("regex_v2", "phi")] == 4 and got[("presidio+regex_v2", "phi")] == 6   # the space survives: a leak
    assert got[("presidio", "decoy")] == 8 and got[("presidio+regex_v2+guard", "decoy")] == 0
    assert set(sr.columns) == {"method_code", "note_id", "item_kind_code", "item_num", "tier_code", "category_code",
                               "char_count", "removed_char_count"}


def test_span_result_reproduces_the_committed_scores():
    """The rerun's entity recall and decoy damage equal data/deid/scores.csv for every tool rerun, on every tier."""
    rep = dd.reproduce(dd.load_span_result(), dd.load_committed_scores())
    assert set(rep.method_code) == set(dd.PAIRED_METHODS)
    assert set(rep.tier_code) == {"easy", "hard", "unseen", "all"}
    assert rep.is_match.all(), rep[~rep.is_match]


def test_span_result_one_row_per_tool_and_labelled_span():
    sr = dd.load_span_result()
    per = sr.groupby("method_code").size()
    assert (per == 2714 + 2462).all()                     # identifiers + dental decoys of the 400 notes
    assert sr.duplicated(["method_code", "note_id", "item_kind_code", "item_num"]).sum() == 0
    assert (sr.removed_char_count <= sr.char_count).all()


# ---------- tool ingredients ----------

@pytest.mark.parametrize("method, expected", [
    ("regex", {"rules_code": "regex", "is_with_guard": False, "is_with_presidio": False}),
    ("regex_v2+guard", {"rules_code": "regex_v2", "is_with_guard": True}),
    ("hf_stanford", {"rules_code": "none", "is_with_hf_stanford": True, "is_with_hf_obi": False}),
    ("hf_stanford+hf_obi+regex_v2+guard", {"rules_code": "regex_v2", "is_with_hf_stanford": True,
                                           "is_with_hf_obi": True, "is_with_guard": True}),
    ("routed+guard", {"is_routed": True, "is_with_guard": True}),
    ("ai_mask+regex_v2+guard", {"is_with_ai_mask": True, "rules_code": "regex_v2"}),
])
def test_method_feature(method, expected):
    f = dd.method_feature(method)
    assert {k: f[k] for k in expected} == expected


# ---------- 1. the ranking ----------

def test_rank_matches_committed_recall_and_pairs_against_the_leader(built):
    rank = built["deid_tool_rank"]
    scores = dd.load_committed_scores().query("tier == 'all'").set_index("method")
    paired = rank[rank.is_paired]
    assert set(paired.method_code) == set(dd.PAIRED_METHODS)
    for r in paired.itertuples():
        assert r.identifier_count == 2714
        assert r.removed_count / r.identifier_count == pytest.approx(scores.loc[r.method_code, "entity_recall"])
        assert r.damaged_count / r.decoy_count == pytest.approx(scores.loc[r.method_code, "decoy_damage"])
        assert r.removed_lo_pct <= r.removed_pct <= r.removed_hi_pct
    assert paired.removed_count.is_monotonic_decreasing
    lead = paired.iloc[0]
    assert lead.rank_position_count == 1 and lead.leader_only_count == 0 and lead.method_only_count == 0
    assert (paired.leader_only_count >= 0).all() and paired.vs_leader_p_ratio.between(0, 1).all()


def test_ai_mask_is_ranked_from_aggregates_only_and_marked_not_paired(built):
    rank = built["deid_tool_rank"].set_index("method_code")
    for m in dd.UNPAIRED_METHODS:
        r = rank.loc[m]
        assert not r.is_paired and pd.isna(r.vs_leader_p_ratio) and pd.isna(r.leader_only_count)
        assert r.ci_method_code == "wilson"


# ---------- 2. contrasts: one ingredient added ----------

def test_every_contrast_adds_exactly_one_ingredient(built):
    con = built["deid_contrast"]
    assert len(con) >= 10
    for r in con.itertuples():
        fa, fb = dd.method_feature(r.method_a_code), dd.method_feature(r.method_b_code)
        diff = [k for k in dd.CONTRAST_FEATURES if fa[k] != fb[k]]
        assert diff == [r.feature_code], (r.method_a_code, r.method_b_code, diff)
        assert r.method_a_code in dd.PAIRED_METHODS and r.method_b_code in dd.PAIRED_METHODS


def test_the_guard_keeps_recall_and_cuts_damage(built):
    con = built["deid_contrast"].set_index(["method_a_code", "method_b_code"])
    g = con.loc[("presidio", "presidio+guard")]
    assert g.feature_code == "is_with_guard"
    assert g.a_removed_count == g.b_removed_count and g.a_only_count == 0 == g.b_only_count
    assert g.b_damaged_count < g.a_damaged_count and g.damage_p_ratio < 0.001
    eff = built["deid_ingredient_effect"].set_index("feature_code")
    assert {"is_with_guard", "is_with_presidio", "is_with_hf_stanford", "is_with_hf_obi", "rules_code"} <= set(eff.index)


# ---------- 3. what decides whether an identifier is removed ----------

def test_category_effect(built):
    eff = built["deid_category_effect"]
    n_methods = len(dd.PAIRED_METHODS)
    assert (eff.run_count == eff.item_count * n_methods).all()
    cat = eff.query("item_kind_code == 'phi' and fact_code == 'category_code'")
    assert cat.item_count.sum() == 2714 and cat.removed_ratio.between(0, 1).all()
    dec = eff.query("item_kind_code == 'decoy' and fact_code == 'category_code'")
    assert dec.item_count.sum() == 2462 and dec.removed_ratio.isna().all() and dec.damaged_ratio.notna().all()


def test_driver_fit_auc(built):
    fit = built["deid_driver_fit"].set_index("feature_set_code")
    assert set(fit.index) == {"identifier", "tool", "identifier_and_tool"}
    for r in fit.itertuples():
        assert 0.5 <= r.auc_ratio <= 1 and r.auc_lo_ratio <= r.auc_ratio <= r.auc_hi_ratio
    assert fit.loc["identifier_and_tool", "run_count"] == 2714 * len(dd.PAIRED_METHODS)
    drop = built["deid_driver_drop"]
    assert {"category_code", "tier_code", "is_with_hf_stanford", "is_with_guard"} <= set(drop.feature_group_code)
    assert set(drop.feature_kind_code) <= {"identifier", "note", "tool"}
    assert drop.auc_drop_ratio.is_monotonic_decreasing


# ---------- data names, comments, pages ----------

def test_every_column_is_typed_and_commented(built):
    for name in dd.TABLES:
        table_comment, cols = dd.COMMENTS[name]
        assert table_comment
        for c in built[name].columns:
            assert c.startswith("is_") or c.endswith(ALLOWED_SUFFIX), (name, c)
            assert cols.get(c), (name, c)


def test_markdown_is_generated_and_names_the_format(built):
    page = dd.details_markdown(built)
    lead = built["deid_tool_rank"].query("is_paired").iloc[0].method_code
    assert lead in page and "McNemar" in page and "AUC" in page and "not paired" in page
    assert "generated by python/scripts/76_deid_drivers.py" in page


def test_committed_outputs_exist():
    for name in dd.TABLES:
        assert (dd.OUT_DIR / f"{name}.csv").exists(), name
    assert dd.DETAILS_DOC.exists() and dd.SPAN_RESULT.exists()


# ---------- loading into Databricks ----------

class FakeClient:
    def __init__(self):
        self.sql_sent = []

    def sql(self, statement):
        self.sql_sent.append(statement)


BATCH = {"run_id": "deid-test", "run_ts": "2026-11-17T00:00:00Z", "git_commit_sha": "abc1234"}


def test_table_sql_declares_types_and_comments(built):
    stmts = dd.table_sql("deid_tool_rank", built["deid_tool_rank"], BATCH, "cat", "sch")
    create = stmts[0]
    assert create.startswith("CREATE OR REPLACE TABLE cat.sch.deid_tool_rank (")
    assert "removed_count BIGINT COMMENT '" in create and "is_paired BOOLEAN COMMENT '" in create
    assert "git_commit_sha STRING COMMENT '" in create and ") COMMENT 'De-identification" in create
    rows = sum(s.count("),(") + 1 for s in stmts[1:])
    assert rows == len(built["deid_tool_rank"])


def test_load_replaces_every_table(built):
    client = FakeClient()
    out = dd.load(built, client, BATCH, "cat", "sch")
    creates = [s for s in client.sql_sent if s.startswith("CREATE OR REPLACE TABLE")]
    assert len(creates) == len(dd.LOAD_TABLES) == out["table_count"]
    assert out["row_count"] == sum(len(dd.load_tables(built)[t]) for t in dd.LOAD_TABLES)
    for name in dd.LOAD_TABLES:
        assert dd.COMMENTS[name][1].keys() >= set(dd.load_tables(built)[name].columns) | set(BATCH)
