"""Spec 028, #652: a screen of 30 published tasks on SWE-bench Verified's two questions (is the statement specified,
do the tests accept any correct solution). An AI reviewer made it, so every place that reports it says so, and the
README's counts are the table's."""
import pandas as pd
import pytest

from health_transformation_lab_nlp.paths import TASKS_DIR

SCREEN = TASKS_DIR / "screening"
QUOTA = {"A": 13, "B": 11, "C": 6}


@pytest.fixture(scope="module")
def screen():
    return pd.read_csv(SCREEN / "agent_screen.csv")


@pytest.fixture(scope="module")
def readme():
    return " ".join((SCREEN / "README.md").read_text(encoding="utf-8").split())


def test_the_sample_is_30_published_tasks_in_the_stated_strata(screen):
    published = set(pd.read_csv(TASKS_DIR / "official_verifier" / "published_verification.csv")["instance_id"])
    manifest = pd.read_csv(TASKS_DIR / "task_manifest.csv").set_index("instance_id")["tier_code"]
    assert len(screen) == 30 and screen["instance_id"].is_unique
    assert set(screen["instance_id"]) <= published
    assert (screen["tier_code"] == screen["instance_id"].map(manifest)).all()
    assert screen["tier_code"].value_counts().to_dict() == QUOTA
    assert screen["sample_seed_num"].nunique() == 1


def test_ratings_are_on_the_scale_and_pass_means_both_are_0_or_1(screen):
    for col in ("statement_rating_num", "test_rating_num"):
        assert screen[col].isin([0, 1, 2, 3]).all(), col
    expected = (screen["statement_rating_num"] <= 1) & (screen["test_rating_num"] <= 1)
    assert (screen["is_pass"] == expected).all()
    assert screen["fix_named_code"].isin(["no", "partly", "yes"]).all()
    assert screen["change_kind_code"].isin(["fix", "feature", "maintenance"]).all()
    assert screen["statement_reason_text"].str.len().gt(0).all() and screen["test_reason_text"].str.len().gt(0).all()


def test_the_second_pass_is_recorded_for_every_task(screen):
    assert screen["second_fair_code"].isin(["fair", "unfair"]).all()
    agrees = (screen["second_fair_code"] == "fair") == (screen["test_rating_num"] <= 1)
    assert (screen["is_second_agree"] == agrees).all()


def test_the_run_columns_are_the_run_tables(screen):
    runs = pd.read_csv(TASKS_DIR / "agent_runs" / "gemma-4-e4b-it_kaggle.csv").set_index("instance_id")["is_resolved"]
    attempted = screen["instance_id"].isin(runs.index)
    assert (screen["is_attempted"] == attempted).all()
    got = screen.loc[attempted].set_index("instance_id")["is_resolved"].astype(str)
    assert (got == runs.loc[got.index].astype(str)).all()
    assert screen.loc[~attempted, "is_resolved"].isna().all()


def test_the_readme_says_who_made_it_and_gives_the_tables_counts(screen, readme):
    assert "Made by an AI reviewer, not by a person." in readme
    n, passed = len(screen), int(screen["is_pass"].sum())
    assert f"| Screened | {n} |" in readme and f"| Pass (both ratings 0 or 1) | {passed} |" in readme
    assert f"| Statement rated 2 or 3 | {int((screen['statement_rating_num'] >= 2).sum())} |" in readme
    assert f"| Tests rated 2 or 3 | {int((screen['test_rating_num'] >= 2).sum())} |" in readme
    kinds = screen["change_kind_code"].value_counts()
    assert f"{kinds.get('fix', 0)} / {kinds.get('feature', 0)} / {kinds.get('maintenance', 0)}" in readme
    att = screen[screen["is_attempted"]]
    resolved = att["is_resolved"].astype(str) == "True"
    ok = att["is_pass"]
    assert (f"Of the {int(ok.sum())} that pass the screen the model resolved {int((ok & resolved).sum())}; "
            f"of the {int((~ok).sum())} that fail it, {int((~ok & resolved).sum())}.") in readme
