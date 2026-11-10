"""docs/standards.md (#391): the case definitions, the sources and the reading orders side by side, and where they
disagree, generated from committed files so the numbers can't go stale."""
import pandas as pd
import pytest

from health_transformation_lab_nlp import standards_doc as sd
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT


@pytest.fixture(scope="module")
def md():
    return sd.markdown()


def test_the_page_is_current(md):
    assert (REPO_ROOT / "docs" / "standards.md").read_text() == md, "run python scripts/48_standards_doc.py"


def test_it_names_each_standard_order_and_open_decision(md):
    for text in ("2017 AAP/EFP", "2012 CDC/AAP", "ACES", "Patel et al. 2022", "study design", "algorithm_v0",
                 "algorithm_design", "A2", "A5", "A6", "B6", "Synthetic"):
        assert text in md, text


def test_the_cross_tab_matches_the_committed_file(md):
    xt = pd.read_csv(REPO_ROOT / "data" / "sites" / "aap_vs_cdc.csv", index_col=0)
    stage1_none = int(xt.loc["periodontitis_stage_1", "none"])
    assert f"| Stage I | {stage1_none:,} |" in md
    assert sd.never_cdc_share(xt) == xt.loc["periodontitis_stage_1"].pipe(lambda r: r["none"] / r.sum())


def test_source_pairs_are_listed_least_agreeing_first():
    ag = pd.read_csv(DATASETS_DIR / "method_agreement.csv")
    rows = sd.agreement_rows(ag)
    assert len(rows) == (ag["level"] == "status").sum()
    assert list(rows["kappa"]) == sorted(rows["kappa"])


# ---------- #635: the page went on quoting the 240-chart note set after #467 rebuilt the notes ----------
def _seed_42() -> pd.DataFrame:
    """The committed build's scores in the stability run, scored as the leaderboard scores (#472)."""
    return pd.read_csv(DATASETS_DIR / "ladder" / "seed_stability.csv").query("seed == 42").set_index("method")


def test_the_review_set_size_is_the_scored_charts_not_typed_in(md):
    n = int(_seed_42().loc["algorithm_v0", "n"])
    assert n == len(pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv"))   # today every review chart counts
    assert f"a larger set than the {n} review charts" in md
    assert "240 review charts" not in md


def test_the_charted_visits_are_counted_out_of_every_visit(md):
    visits = pd.read_csv(DATASETS_DIR / "visits_structured.csv", usecols=["charted"])
    charted = int(visits["charted"].sum())
    assert int(pd.read_csv(sd.SITES / "aap_vs_cdc.csv", index_col=0).to_numpy().sum()) == charted
    assert f"{charted:,} synthetic visits with a gum chart, out of {len(visits):,}" in md


def test_the_orders_are_scored_as_the_leaderboard_scores_them(md):
    # the page counted an exact match on six statuses with the codes as built (205 and 169 of 223); every other page
    # gives the leaderboard's score (spec 032 US8: five status groups, the codes re-read): 207 and 176
    stab = _seed_42()
    n = int(stab.loc["algorithm_v0", "n"])
    v0, design = (round(stab.loc[m, "accuracy"] * n) for m in ("algorithm_v0", "algorithm_design"))
    assert (f"On the {n} synthetic review charts, measurements first agrees with the answer key on {v0} and exam "
            f"form first on {design}") in md
    assert "five status groups" in md and "no gum-disease code read as healthy or gingivitis" in md
    results = (REPO_ROOT / "docs" / "results.md").read_text()
    for method, count in (("algorithm_v0", v0), ("algorithm_design", design)):
        rows = [line for line in results.splitlines() if f"| `{method}` |" in line]
        assert len(rows) == 1 and f"**{100 * count / n:.1f}**" in rows[0], method
