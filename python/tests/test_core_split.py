"""028 AI7 (#674): the core split. The 17 published tasks that pass the screen of all 93 (the statement says what its
tests check) are named in one small file, so a result can be reported on them. The file is the screen's own verdict,
never a second opinion: a task is in it exactly when the screen passes it."""
import pandas as pd

from health_transformation_lab_nlp.paths import TASKS_DIR

SCREEN = TASKS_DIR / "screening"


def test_the_core_split_is_exactly_the_tasks_the_screen_of_all_93_passes():
    core = pd.read_csv(SCREEN / "core_split.csv")
    screen = pd.read_csv(SCREEN / "agent_screen_all.csv")
    assert list(core.columns) == ["instance_id", "tier_code", "is_owner_checked", "owner_check_date"]
    assert sorted(core.instance_id) == sorted(screen.instance_id[screen.is_pass]) and len(core) == 17
    assert core.instance_id.is_unique
    merged = core.merge(screen, on="instance_id", suffixes=("", "_screen"))
    assert (merged.tier_code == merged.tier_code_screen).all()


def test_a_person_has_checked_every_core_verdict_in_summary_on_one_of_two_days():
    """028 AI10 (#688). Five of the 17 were among the first screen's 30, which the owner checked on November 10, 2026.
    The other 12 had an AI reviewer's verdict alone until November 12, when the owner read a summary of each and
    agreed with all 12. Both times the owner read summaries and not the test code, and saw the AI's verdict first:
    the file says who checked a verdict and when, never that the split is validated by people."""
    core = pd.read_csv(SCREEN / "core_split.csv")
    screen = pd.read_csv(SCREEN / "agent_screen_all.csv").set_index("instance_id")
    assert core.is_owner_checked.all()
    first = core[core.owner_check_date == "2026-11-10"]
    second = core[core.owner_check_date == "2026-11-12"]
    assert len(first) == 5 and len(second) == 12 and len(first) + len(second) == len(core)
    assert screen.loc[first.instance_id, "is_owner_checked"].all()          # in the first screen's 30
    assert not screen.loc[second.instance_id, "is_owner_checked"].any()     # outside it: no person had seen them
