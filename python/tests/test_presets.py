"""Spec 032 US7 (#446): named presets of the analysis settings, and one run of every part under a preset."""

import importlib.util
import inspect

import pytest
import yaml

from health_transformation_lab_nlp import classify_status as cs
from health_transformation_lab_nlp import (
    labels,
    phenotype,
    presets,
    prevalence,
    study,
    tooth_loss_dq,
)
from health_transformation_lab_nlp import tooth_loss_model as tlm
from health_transformation_lab_nlp.paths import REPO_ROOT


def _default(fn, arg):
    return inspect.signature(fn).parameters[arg].default


def _score_fn():
    spec = importlib.util.spec_from_file_location("eval_score_for_presets", REPO_ROOT / "eval" / "score.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.score


# Where each setting's default lives in the code today. repo_v1 must equal every one of them, so a later change of a
# default (spec 032 US8) shows up as a failing test until repo_v1 or the code is put right.
CODE_DEFAULTS = {
    "grouping": lambda: {_default(_score_fn(), "grouping"), _default(prevalence.prevalence_by_group, "grouping"),
                         _default(labels.group_status, "grouping")},
    "also_reported_groupings": lambda: {()},
    "visit_min_age": lambda: {_default(study.visits_in_study, "min_age"), _default(study.build_study, "min_age")},
    "visit_start_date": lambda: {_default(study.visits_in_study, "start_date"),
                                 _default(study.build_study, "start_date")},
    "absent_code": lambda: {_default(study.read_methods, "absent_code"),
                            _default(phenotype.with_absent_code, "absent_code")},
    "stage4_rules": lambda: {tuple(labels.STAGE4_COUNT_RULES)},      # tooth_loss_model.run reports all of them
    "tooth_loss_min_age": lambda: {tlm.DEFAULT.min_age},
    "tooth_loss_start_date": lambda: {tlm.DEFAULT.start_date},
    "tooth_loss_split_unit": lambda: {tlm.DEFAULT.split_unit},
    "tooth_loss_test_share": lambda: {tlm.DEFAULT.test_share},
    "tooth_loss_cv_folds": lambda: {tlm.DEFAULT.cv_folds},
    "classifier_split_unit": lambda: {_default(cs.train_eval, "split_unit")},
    "classifier_test_share": lambda: {_default(cs.train_eval, "test_share")},
    "classifier_cv_folds": lambda: {_default(cs.train_eval, "folds")},
    "consistency_groups": lambda: {tuple(_default(tooth_loss_dq.group_consistency, "group_types")),
                                   tuple(tooth_loss_dq.GROUP_TYPES)},
    "cal_icc": lambda: {False},
}


def test_every_setting_has_a_code_default_checked_here():
    assert set(CODE_DEFAULTS) == set(presets.PRESET_SETTINGS)


@pytest.mark.parametrize("setting", list(CODE_DEFAULTS))
def test_repo_v1_is_every_current_default(setting):
    found = CODE_DEFAULTS[setting]()
    assert len(found) == 1, f"{setting}: the code has more than one default {found}"
    value = presets.load_preset("repo_v1")[setting]
    assert (tuple(value) if isinstance(value, list) else value) == next(iter(found)), setting


def test_both_presets_load_and_name_every_setting():
    assert set(presets.preset_names()) >= {"repo_v1", "exploratory_1"}
    for name in ("repo_v1", "exploratory_1"):
        p = presets.load_preset(name)
        assert list(p) == list(presets.PRESET_SETTINGS)


def test_exploratory_1_turns_on_the_spec_settings():
    p = presets.load_preset("exploratory_1")
    assert p["grouping"] == "five" and p["also_reported_groupings"] == ["three"]
    assert p["visit_min_age"] == 18 and p["tooth_loss_min_age"] == 18
    assert p["visit_start_date"] and p["tooth_loss_start_date"]
    assert p["absent_code"] == "healthy_or_gingivitis"
    assert {"teeth_lt_20", "pairs_lt_10"} <= set(p["stage4_rules"])
    assert p["tooth_loss_split_unit"] == p["classifier_split_unit"] == "visit"
    assert p["tooth_loss_test_share"] == p["classifier_test_share"] == 0.2
    assert p["tooth_loss_cv_folds"] == p["classifier_cv_folds"] == 5
    assert "insurance_type" in p["consistency_groups"]
    assert p["cal_icc"] is True


def test_unknown_preset_fails_naming_it():
    with pytest.raises(ValueError, match="no_such_preset"):
        presets.load_preset("no_such_preset")


def test_unknown_or_missing_setting_fails_naming_it(tmp_path):
    good = yaml.safe_load(presets.PRESETS_FILE.read_text())["repo_v1"]
    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump({"extra": {**good, "colour": "blue"}}))
    with pytest.raises(ValueError, match="colour"):
        presets.load_preset("extra", path)
    path.write_text(yaml.safe_dump({"short": {k: v for k, v in good.items() if k != "absent_code"}}))
    with pytest.raises(ValueError, match="absent_code"):
        presets.load_preset("short", path)


def test_a_bad_value_fails_naming_the_setting(tmp_path):
    good = yaml.safe_load(presets.PRESETS_FILE.read_text())["repo_v1"]
    path = tmp_path / "p.yaml"
    for setting, bad in (("grouping", "seven"), ("absent_code", "maybe"), ("tooth_loss_split_unit", "tooth"),
                         ("stage4_rules", ["coin_flip"]), ("consistency_groups", ["star_sign"]),
                         ("classifier_test_share", 1.5), ("visit_start_date", "not a date")):
        path.write_text(yaml.safe_dump({"bad": {**good, setting: bad}}))
        with pytest.raises(ValueError, match=setting):
            presets.load_preset("bad", path)


def test_no_preset_names_a_study_person_or_organisation():
    text = presets.PRESETS_FILE.read_text().lower()
    for word in ("et al", "university", "institute", "dissertation", "prospectus", " jo "):
        assert word not in text


def test_settings_table_says_what_changed():
    t = presets.settings_table("exploratory_1")
    assert list(t.columns) == ["setting_name", "repo_v1_value_text", "preset_value_text", "is_changed"]
    assert list(t["setting_name"]) == list(presets.PRESET_SETTINGS)
    row = t.set_index("setting_name")
    assert row.loc["grouping", "repo_v1_value_text"] == "six" and row.loc["grouping", "preset_value_text"] == "five"
    assert bool(row.loc["grouping", "is_changed"]) and not bool(row.loc["tooth_loss_min_age", "is_changed"])
    assert not presets.settings_table("repo_v1")["is_changed"].any()


def test_a_small_run_writes_every_part_labelled_synthetic(monkeypatch):
    pytest.importorskip("xgboost")
    monkeypatch.setattr(cs, "GRID", {"max_depth": [2], "learning_rate": [0.2], "reg_lambda": [1.0],
                                     "min_child_weight": [1], "class_weight": [None]})
    monkeypatch.setattr(tlm, "XGB_GRID", {"max_depth": [2], "n_estimators": [20], "learning_rate": [0.1],
                                          "subsample": [1.0], "min_child_weight": [1]})
    out = presets.run_preset("exploratory_1", n_people=150, n_patients=300, seed=42, n_boot=0)
    assert set(out) == set(presets.PARTS)
    for part, df in out.items():
        assert len(df), part
        assert (df["data_label"] == "synthetic").all(), part
        assert (df["preset_name"] == "exploratory_1").all(), part
    left = out["visits_left_out"].set_index("reason_name")["visit_count"]
    assert left["before_start_date_count"] > 0
    agree = out["visits_agreement"]
    assert set(agree["grouping"]) == {"five", "three"}
    prev = out["prevalence"]
    assert set(prev["grouping"]) == {"five", "three"} and "clinic_id" in prev
    assert set(out["tooth_loss_stage_recount"]["rule"]) == set(labels.STAGE4_COUNT_RULES)
    assert (out["tooth_loss_validation"]["split_unit"] == "visit").all()
    assert "people_in_both_count" in out["tooth_loss_scores"] and "people_in_both_count" in out["classifier"]
    assert set(out["classifier"]["scheme"]) == {"5level", "3level"}
    assert "insurance_type" in set(out["consistency"]["group_type_code"])
    assert {"icc_site", "sem_mm"} <= set(out["icc"]["metric_name"])


def test_repo_v1_run_has_no_icc_and_keeps_six_statuses(monkeypatch):
    pytest.importorskip("xgboost")
    monkeypatch.setattr(cs, "GRID", {"max_depth": [2], "learning_rate": [0.2], "reg_lambda": [1.0],
                                     "min_child_weight": [1], "class_weight": [None]})
    out = presets.run_preset("repo_v1", n_people=150, n_patients=300, seed=42, n_boot=0)
    assert "icc" not in out
    assert set(out["visits_agreement"]["grouping"]) == {"six"}
    assert (out["classifier"]["people_in_both_count"] == 0).all()
    assert (out["tooth_loss_validation"]["people_in_both_count"] == 0).all()
