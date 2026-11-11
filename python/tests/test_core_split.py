"""028 AI7 (#674): the core split. The 17 published tasks that pass the screen of all 93 (the statement says what its
tests check) are named in one small file, so a result can be reported on them. The file is the screen's own verdict,
never a second opinion: a task is in it exactly when the screen passes it."""
import pandas as pd

from health_transformation_lab_nlp.paths import TASKS_DIR

SCREEN = TASKS_DIR / "screening"


def test_the_core_split_is_exactly_the_tasks_the_screen_of_all_93_passes():
    core = pd.read_csv(SCREEN / "core_split.csv")
    screen = pd.read_csv(SCREEN / "agent_screen_all.csv")
    assert list(core.columns) == ["instance_id", "tier_code", "is_owner_checked"]
    assert sorted(core.instance_id) == sorted(screen.instance_id[screen.is_pass]) and len(core) == 17
    assert core.instance_id.is_unique
    merged = core.merge(screen, on="instance_id", suffixes=("", "_screen"))
    assert (merged.tier_code == merged.tier_code_screen).all()
    assert (merged.is_owner_checked == merged.is_owner_checked_screen).all()      # a person checked 5 of the 17
    assert int(core.is_owner_checked.sum()) == 5
