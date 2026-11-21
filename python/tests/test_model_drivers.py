"""Spec 042 US1 (#863): each note-reading model ranked, paired against the leader and its neighbours, with the model
and chart features that drive its score. The format is the agent competition's (gemma-developer-agent
docs/findings.md): a ranked table, exact McNemar on paired charts, and what decides outcomes, with an AUC.

Synthetic charts scored against the generator's answer key: agreement, not clinical accuracy.
"""

import importlib.util

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import model_drivers as md
from health_transformation_lab_nlp import readme_results as rr
from health_transformation_lab_nlp.paths import REPO_ROOT


@pytest.fixture(scope="module")
def built():
    return md.build(rr.load_inputs(), n_boot=50)


# ---------- method features ----------

@pytest.mark.parametrize("method, expected", [
    ("modernbert-large+rules4", {"family_code": "modernbert", "size_code": "large", "domain_code": "general",
                                 "is_rules4": True, "is_class_weighted": False, "seed_code": "0"}),
    ("modernbert-base+cw+s1+rules4", {"size_code": "base", "is_class_weighted": True, "seed_code": "1",
                                      "is_rules4": True}),
    ("bioclinical-modernbert-base", {"family_code": "modernbert", "domain_code": "clinical", "size_code": "base"}),
    ("distilbert-base", {"family_code": "bert", "size_code": "small"}),
    ("gatortron-base+lr2e-05", {"learning_rate_text": "2e-05", "domain_code": "clinical"}),
    ("llama-3.3-70b-instruct", {"approach_code": "zero_shot_llm", "size_code": "70b", "domain_code": "general"}),
    ("medgemma-4b-it+rules4", {"approach_code": "zero_shot_llm", "size_code": "4b", "domain_code": "medical"}),
    ("tfidf_logreg", {"approach_code": "tfidf", "input_code": "note"}),
    ("fusion_tfidf_rad+rules4", {"approach_code": "tfidf", "input_code": "note_radiograph", "is_rules4": True}),
    ("note_rules", {"approach_code": "rules"}),
])
def test_method_feature(method, expected):
    f = md.method_feature(method, rr.load_inputs()["registry"])
    assert {k: f[k] for k in expected} == expected


def test_every_feature_name_is_typed():
    """Data names: never a bare name/type/status/value; booleans start is_."""
    for col in md.FEATURES:
        assert col.startswith("is_") or col.endswith(("_code", "_text", "_count")), col


# ---------- the paired test ----------

def test_exact_mcnemar_counts_and_p():
    a = pd.Series([True, True, True, False, True])
    b = pd.Series([False, False, False, False, True])
    a_only, b_only, p = md.exact_mcnemar(a, b)
    assert (a_only, b_only) == (3, 0)
    assert p == pytest.approx(0.25)
    assert md.exact_mcnemar(a, a)[2] == 1.0


# ---------- the rank table reproduces the leaderboard ----------

def test_rank_reproduces_leaderboard(built):
    rank = built["model_rank"].set_index("method_code")
    assert len(rank) == 43                                            # every method that reads the note
    top = rank.loc["modernbert-large+rules4"]
    assert (top.correct_count, top.chart_count) == (203, 223)
    assert top.rank_position_count == 1 and top.leader_only_count == 0
    ladder = rr.load_inputs()["ladder"].set_index("method")
    for m in ladder.index:
        assert rank.loc[m, "correct_count"] / 223 == pytest.approx(ladder.loc[m, "accuracy"])


def test_rank_is_ordered_and_paired_against_the_leader(built):
    rank = built["model_rank"]
    assert rank.correct_count.is_monotonic_decreasing
    llama = rank.set_index("method_code").loc["llama-3.3-70b-instruct"]
    assert (llama.leader_only_count, llama.method_only_count) == (24, 8)      # paired with the leader
    assert llama.vs_leader_p_ratio < 0.05
    assert (rank.leader_only_l3_count <= rank.leader_only_count).all()


# ---------- feature contrasts: pairs differing in one feature ----------

def test_every_contrast_differs_in_exactly_one_feature(built):
    reg = rr.load_inputs()["registry"]
    con = built["model_contrast"]
    assert len(con) > 20
    for r in con.itertuples():
        fa, fb = md.method_feature(r.method_a_code, reg), md.method_feature(r.method_b_code, reg)
        diff = [k for k in md.CONTRAST_FEATURES if fa[k] != fb[k]]
        assert diff == [r.feature_code], (r.method_a_code, r.method_b_code, diff)


def test_known_contrasts(built):
    con = built["model_contrast"].set_index(["method_a_code", "method_b_code"])
    big = con.loc[("modernbert-base", "modernbert-large")]
    assert big.feature_code == "size_code" and (big.a_only_count, big.b_only_count) == (2, 11)
    assert big.p_ratio == pytest.approx(0.0225, abs=1e-4)
    assert con.loc[("modernbert-large", "modernbert-large+rules4")].feature_code == "is_rules4"
    assert con.loc[("modernbert-base+cw", "modernbert-base+cw+s1")].feature_code == "seed_code"


def test_contrast_summary_one_row_per_feature(built):
    s = built["model_feature_effect"].set_index("feature_code")
    assert {"is_rules4", "size_code", "domain_code", "is_class_weighted", "seed_code"} <= set(s.index)
    rules = s.loc["is_rules4"]
    assert rules.pair_count >= 15 and rules.b_better_pair_count >= rules.a_better_pair_count


# ---------- what drives the score: chart facts and model features ----------

def test_chart_feature_effect(built):
    eff = built["chart_feature_effect"]
    l3 = eff.query("chart_feature_code == 'difficulty' and level_text == 'L3'").iloc[0]
    l1 = eff.query("chart_feature_code == 'difficulty' and level_text == 'L1'").iloc[0]
    assert l3.chart_count == 64 and l1.chart_count == 136
    assert l3.correct_ratio < l1.correct_ratio
    assert (eff.run_count == eff.chart_count * 43).all()


def test_driver_fit_auc(built):
    fit = built["driver_fit"].set_index("feature_set_code")
    assert set(fit.index) == {"chart", "model", "chart_and_model"}
    for r in fit.itertuples():
        assert 0.5 <= r.auc_ratio <= 1 and r.auc_lo_ratio <= r.auc_ratio <= r.auc_hi_ratio
    assert fit.loc["chart", "auc_ratio"] > fit.loc["model", "auc_ratio"]
    drop = built["driver_drop"]
    assert set(drop.feature_group_code) >= {"difficulty", "truth_group", "is_rules4", "size_code"}
    assert drop.auc_drop_ratio.is_monotonic_decreasing


# ---------- the drill-down page and the README block are generated ----------

def test_markdown_names_the_leader_and_the_format(built):
    page = md.details_markdown(built)
    assert "modernbert-large+rules4" in page and "McNemar" in page and "AUC" in page
    block = md.readme_block(built)
    assert block.startswith(md.START) and block.endswith(md.END)
    assert "model_drivers.md" in block


def test_committed_outputs_are_current():
    spec = importlib.util.spec_from_file_location("s74", REPO_ROOT / "python/scripts/74_model_drivers.py")
    assert spec is not None
    for name in md.TABLES:
        assert (md.OUT_DIR / f"{name}.csv").exists(), name
    assert md.DETAILS_DOC.exists()
    assert md.START in md.README.read_text()
    assert "](docs/model_drivers.md)" in (REPO_ROOT / "README.md").read_text()     # the landing page links to it
