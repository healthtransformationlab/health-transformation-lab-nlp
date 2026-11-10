"""docs/scoring.md (#635): the page is written by hand, so each count on it is checked against the committed table it
comes from. It went on quoting the 240-chart note set after #467 rebuilt the notes. SYNTHETIC data only."""
import inspect
import json

import pandas as pd
import pytest

from health_transformation_lab_nlp import ladder_eval, study
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT

LADDER = DATASETS_DIR / "ladder"


@pytest.fixture(scope="module")
def page():
    return (REPO_ROOT / "docs" / "scoring.md").read_text()


@pytest.fixture(scope="module")
def visits():
    return pd.read_csv(DATASETS_DIR / "visits_structured.csv", usecols=["visit_id", "person_id", "charted"])


@pytest.fixture(scope="module")
def key():
    return pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")


def _row(page: str, name: str) -> str:
    """A row of the "Which records each number counts" table, by its first cell."""
    return next(line for line in page.splitlines() if line.startswith(f"| {name} |"))


def test_the_visit_and_patient_counts_are_the_visit_tables(page, visits):
    n, charted = len(visits), int(visits["charted"].sum())
    assert f"{n:,} visits of {visits['person_id'].nunique():,} patients" in page
    assert _row(page, "All synthetic visits").startswith(f"| All synthetic visits | {n:,} |")
    assert _row(page, "Charted visits").startswith(f"| Charted visits | {charted:,} | the visits, of all {n:,},")
    # the count before #467 is the build summary's: the visits kept plus those left out for their date
    left_out = json.loads((DATASETS_DIR / "build_summary.json").read_text())["visits_left_out"]
    earlier = left_out["before_start_date_count"]
    assert left_out["eligible_count"] == n
    assert f"{n + earlier:,} before #467 left out the {earlier} earlier ones" in _row(page, "All synthetic visits")


def test_the_training_and_review_counts_are_the_split(page, visits, key):
    train = pd.read_csv(DATASETS_DIR / "train.csv", usecols=["visit_id", "person_id"])
    assert _row(page, "Training notes").startswith(
        f"| Training notes | {len(train):,} | every visit of {train['person_id'].nunique():,} patients |")
    assert _row(page, "Review charts (test set)").startswith(
        f"| Review charts (test set) | {len(key)} | one visit each of the other {key['person_id'].nunique()} patients")
    assert _row(page, "Scored review charts").startswith(f"| Scored review charts | {len(key)} |")
    # why the set is smaller than the size asked for: the stage IV stratum runs short
    asked_n = inspect.signature(study.build_study).parameters["review_n"].default
    stage4 = "periodontitis_stage_4"
    assert (f"(up to {asked_n}; only {int((key['truth_status'] == stage4).sum())} patients' latest visit is stage IV, "
            f"under the {round(asked_n * study.REVIEW_STRATA[stage4])} asked for)") in _row(page, "Review charts (test set)")
    assert not set(train["person_id"]) & set(key["person_id"])
    others = visits[visits["person_id"].isin(key["person_id"]) & ~visits["visit_id"].isin(key["visit_id"])]
    assert f"The other {len(others)} visits of the {len(key)} held-out patients" in page


def test_the_two_orders_scores_are_the_leaderboards(page, key):
    # seed 42 of the stability run is the committed build, scored as the leaderboard scores (#472)
    stab = pd.read_csv(LADDER / "seed_stability.csv").query("seed == 42").set_index("method")
    assert int(stab.loc["algorithm_v0", "n"]) == len(key)
    v0, design = (round(stab.loc[m, "accuracy"] * len(key)) for m in ("algorithm_v0", "algorithm_design"))
    assert f"{v0} vs {design}" in _row(page, "Scored review charts")
    assert f"The {len(key)} review charts are one draw" in page


def test_the_charts_that_cant_be_staged_are_counted_from_the_tables(page, key):
    split = (pd.read_csv(LADDER / "ladder_by_stageable.csv").query("method == 'note_rules'")
             .set_index("stageable_code"))
    n_not, n_ok = int(split.loc["not_stageable", "n"]), int(split.loc["stageable", "n"])
    apart = key[ladder_eval.stageable(key) == "not_stageable"]
    assert len(apart) == n_not and n_not + n_ok == len(key)
    assert f"{n_not} of the {len(key)} review charts" in page
    # a note states the true status when it writes a diagnosis and that diagnosis is the answer key's
    stated = int(((apart["stated_status"] == apart["truth_status"]) & (apart["dx_pattern"] != "none")).sum())
    assert f"states the true status on {stated} of the {n_not}" in page
    right = {g: round(split.loc[g, "accuracy"] * split.loc[g, "n"]) for g in split.index}
    assert f"the keyword rules get {right['not_stageable']} of the {n_not}" in page
    assert f"({right['stageable']} of {n_ok})" in page


def test_the_seed_ranges_are_the_stability_tables(page):
    n = pd.read_csv(LADDER / "seed_stability.csv")["n"]
    assert f"{n.min()} to {n.max()} charts a seed" in page
    spread = pd.read_csv(LADDER / "seed_stability_summary.csv").set_index("method")
    for method, name in (("algorithm_v0", "rules, gum measurements first"),
                         ("fusion_tfidf_rad", "word counts plus X-ray"), ("note_rules", "keyword rules"),
                         ("algorithm_design", "rules, exam form first")):
        low, high = (round(100 * spread.loc[method, c]) for c in ("min_accuracy", "max_accuracy"))
        assert f"- {name}: {low}–{high}" in page, method


def test_no_count_from_the_240_chart_notes_is_left(page):
    # 240 is still the size the review set aims for, and one seed's set reaches it; nothing else may quote it
    allowed = ("(up to 240;", "to 240 charts a seed")
    left = [line for line in page.splitlines() if "240" in line and not any(a in line for a in allowed)]
    assert not left, left
