"""docs/standards.md (#391): the case definitions, the sources and the reading orders side by side, and where they
disagree, generated from committed files so the numbers can't go stale."""
import pandas as pd

from health_transformation_lab_nlp import standards_doc as sd
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT


def test_the_page_is_current():
    assert (REPO_ROOT / "docs" / "standards.md").read_text() == sd.markdown(), \
        "run python scripts/48_standards_doc.py"


def test_it_names_each_standard_order_and_open_decision():
    md = sd.markdown()
    for text in ("2017 AAP/EFP", "2012 CDC/AAP", "ACES", "Patel et al. 2022", "study design", "algorithm_v0",
                 "algorithm_design", "A2", "A5", "A6", "B6", "Synthetic"):
        assert text in md, text


def test_the_cross_tab_matches_the_committed_file():
    xt = pd.read_csv(REPO_ROOT / "data" / "sites" / "aap_vs_cdc.csv", index_col=0)
    md = sd.markdown()
    stage1_none = int(xt.loc["periodontitis_stage_1", "none"])
    assert f"| Stage I | {stage1_none:,} |" in md
    assert sd.never_cdc_share(xt) == xt.loc["periodontitis_stage_1"].pipe(lambda r: r["none"] / r.sum())


def test_source_pairs_are_listed_least_agreeing_first():
    ag = pd.read_csv(DATASETS_DIR / "method_agreement.csv")
    rows = sd.agreement_rows(ag)
    assert len(rows) == (ag["level"] == "status").sum()
    assert list(rows["kappa"]) == sorted(rows["kappa"])
