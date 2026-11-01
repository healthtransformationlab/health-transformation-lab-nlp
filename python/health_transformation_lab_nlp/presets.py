"""Named presets of the analysis settings (spec 032 US7, #446).

A preset is a named set of the design choices spec 032 made into settings: the status grouping, which visits count,
how an absent diagnosis code is read, the stage IV rules reported, how each model is validated, the consistency split
and the CAL reliability ICC. `analysis_presets.yaml` holds them: `repo_v1` writes out today's defaults (a test checks
each against the code), `exploratory_1` turns common choices of published record studies on together. Presets name
settings only, never a study, person or organisation.

`run_preset` runs every part on freshly generated synthetic data with fixed seeds (scripts/58_preset.py writes it).
Every number is SYNTHETIC: agreement with a synthetic answer key, not a finding about any practice or patient.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import pandas as pd
import yaml

from . import classify_status as cs
from . import (
    labels,
    open_dental,
    phenotype,
    prevalence,
    reliability_cal,
    study,
    tooth_loss,
    tooth_loss_dq,
)
from . import tooth_loss_model as tlm
from .paths import REPO_ROOT
from .sources import READERS
from .telemetry import traced

PRESETS_FILE = Path(__file__).with_name("analysis_presets.yaml")
BASE_PRESET = "repo_v2"           # the code's defaults (spec 032 US8)
DATA_LABEL = "synthetic"

# Every setting a preset must give, in the order the settings table lists them, with what it means.
PRESET_SETTINGS: dict[str, str] = {
    "grouping": "status grouping for scores and prevalence (labels.GROUPINGS)",
    "also_reported_groupings": "further status groupings reported beside the main one",
    "visit_min_age": "visit-level study set: minimum age at the visit (none: every age)",
    "visit_start_date": "visit-level study set: first visit date that counts (none: every year)",
    "absent_code": "how a treatment plan with no gum-disease code is read (phenotype.ABSENT_CODE_RULES)",
    "stage4_rules": "stage III vs IV rules reported (labels.STAGE4_COUNT_RULES)",
    "tooth_loss_min_age": "tooth-loss model: minimum age at the loss (none: every age)",
    "tooth_loss_start_date": "tooth-loss model: teeth lost (or first charted) before it are left out",
    "tooth_loss_split_unit": "tooth-loss model: hold out whole patients (person) or random teeth (visit)",
    "tooth_loss_test_share": "tooth-loss model: held-out share",
    "tooth_loss_cv_folds": "tooth-loss model: k-fold tuning of XGBoost (none: fixed settings)",
    "classifier_split_unit": "visit-level status classifier: hold out whole people (person) or random visits (visit)",
    "classifier_test_share": "visit-level status classifier: held-out share",
    "classifier_cv_folds": "visit-level status classifier: k-fold tuning of its hyperparameters",
    "consistency_groups": "chart-consistency split by these group types (tooth_loss_dq.ALL_GROUP_TYPES)",
    "cal_icc": "report the reliability (ICC) of attachment loss in repeated charts (reliability_cal)",
}

# The parts run_preset returns, in the order the script writes them (icc only when the preset turns it on).
PARTS = ("settings", "visits_left_out", "visits_agreement", "prevalence", "tooth_loss_left_out", "tooth_loss_scores",
         "tooth_loss_validation", "tooth_loss_stage_recount", "classifier", "consistency", "icc")
AGREEMENT_METHODS = ("notes", *READERS, "probing_chart", "radiograph_ai", "algorithm_v0", "algorithm_design")
PREVALENCE_SOURCES = ("truth_status", "algorithm_design")
CLASSIFIER_OUTCOME = "algorithm_design"
CLASSIFIER_SCHEMES = ("5level", "3level")
CLASSIFIER_SEED = 3                       # scripts/40_classify_status.py's default
HEADLINE_METRICS = ("auc", "brier", "calibration_slope")
ICC_SHAPE = {"n_patients": 100, "n_teeth": 12, "n_visits": 3, "seed": 13}   # scripts/37_cal_reliability.py's defaults
VISIT_SPLIT_WARNING = ("a split by visit puts some people on both sides, which overstates accuracy; "
                       "never read it as the model's accuracy")


def _fail(name: str, setting: str, value, why: str):
    raise ValueError(f"preset {name!r}: setting {setting} = {value!r}: {why}")


def _check_age(name, setting, v):
    if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
        _fail(name, setting, v, "a whole number of years, or null")


def _check_date(name, setting, v):
    if v is None:
        return None
    try:
        return (v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))).isoformat()
    except ValueError:
        _fail(name, setting, v, "an ISO date (YYYY-MM-DD), or null")


def _check_choices(name, setting, values, allowed):
    bad = [x for x in values if x not in allowed]
    if bad or not isinstance(values, list):
        _fail(name, setting, values, f"a list from {tuple(allowed)}")


def _check_share(name, setting, v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v < 1:
        _fail(name, setting, v, "a share between 0 and 1")


def _check_folds(name, setting, v, optional: bool):
    if v is None and optional:
        return
    if isinstance(v, bool) or not isinstance(v, int) or v < 2:
        _fail(name, setting, v, "at least 2" + (", or null for no tuning" if optional else ""))


def _check(name: str, p: dict) -> dict:
    unknown = [k for k in p if k not in PRESET_SETTINGS]
    if unknown:
        raise ValueError(f"preset {name!r}: unknown setting(s) {unknown}; the settings are {list(PRESET_SETTINGS)}")
    missing = [k for k in PRESET_SETTINGS if k not in p]
    if missing:
        raise ValueError(f"preset {name!r}: missing setting(s) {missing}; every preset writes out every setting")
    if p["grouping"] not in labels.GROUPINGS:
        _fail(name, "grouping", p["grouping"], f"one of {tuple(labels.GROUPINGS)}")
    _check_choices(name, "also_reported_groupings", p["also_reported_groupings"], labels.GROUPINGS)
    for s in ("visit_min_age", "tooth_loss_min_age"):
        _check_age(name, s, p[s])
    for s in ("visit_start_date", "tooth_loss_start_date"):
        p[s] = _check_date(name, s, p[s])
    if p["absent_code"] not in phenotype.ABSENT_CODE_RULES:
        _fail(name, "absent_code", p["absent_code"], f"one of {phenotype.ABSENT_CODE_RULES}")
    _check_choices(name, "stage4_rules", p["stage4_rules"], labels.STAGE4_COUNT_RULES)
    if p["tooth_loss_split_unit"] not in tlm.SPLIT_UNITS:
        _fail(name, "tooth_loss_split_unit", p["tooth_loss_split_unit"], f"one of {tlm.SPLIT_UNITS}")
    if p["classifier_split_unit"] not in cs.SPLIT_UNITS:
        _fail(name, "classifier_split_unit", p["classifier_split_unit"], f"one of {cs.SPLIT_UNITS}")
    for s in ("tooth_loss_test_share", "classifier_test_share"):
        _check_share(name, s, p[s])
    _check_folds(name, "tooth_loss_cv_folds", p["tooth_loss_cv_folds"], optional=True)
    _check_folds(name, "classifier_cv_folds", p["classifier_cv_folds"], optional=False)
    _check_choices(name, "consistency_groups", p["consistency_groups"], tooth_loss_dq.ALL_GROUP_TYPES)
    if not isinstance(p["cal_icc"], bool):
        _fail(name, "cal_icc", p["cal_icc"], "true or false")
    return {k: p[k] for k in PRESET_SETTINGS}


def _read(path: Path) -> dict:
    data = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(data, dict):
        raise TypeError(f"{path}: expected a mapping of preset names to settings")
    return data


@traced
def preset_names(path: Path = PRESETS_FILE) -> list[str]:
    """The presets the file names, in its order."""
    return list(_read(path))


@traced
def load_preset(name: str, path: Path = PRESETS_FILE) -> dict:
    """One preset's settings, in PRESET_SETTINGS order. Fails at once on an unknown preset, an unknown or missing
    setting, or a value the code can't use, naming it."""
    data = _read(path)
    if name not in data:
        raise ValueError(f"unknown preset {name!r}; the presets are {list(data)}")
    if not isinstance(data[name], dict):
        raise TypeError(f"preset {name!r}: expected a mapping of settings")
    return _check(name, dict(data[name]))


def _text(v) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else "none"
    return f"{v:g}" if isinstance(v, float) else str(v)


@traced
def settings_table(name: str, path: Path = PRESETS_FILE) -> pd.DataFrame:
    """One row per setting: its default (BASE_PRESET), the preset's value, and whether the preset changes it."""
    base, p = load_preset(BASE_PRESET, path), load_preset(name, path)
    return pd.DataFrame([{"setting_name": s, "default_value_text": _text(base[s]), "preset_value_text": _text(p[s]),
                          "is_changed": base[s] != p[s]} for s in PRESET_SETTINGS])


def _scorer():
    """eval/score.py, the shared scorer (eval/score.R is its R twin)."""
    spec = importlib.util.spec_from_file_location("eval_score", REPO_ROOT / "eval" / "score.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.score


def _visits(p: dict, n_people: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The visit-level study set under the preset, built as study.build_study builds it, and those left out."""
    raw = study.generate_visits(n_people, seed)
    left = study.visit_exclusions(raw, p["visit_min_age"], p["visit_start_date"])
    v = study.visits_in_study(raw, p["visit_min_age"], p["visit_start_date"])
    v = v.rename(columns={c: c + "_raw" for c in READERS})
    v, _ = study.apply_deid(v)
    v = v[v["deid_passed"]].drop(columns=["note_raw", "phi_spans"])   # nothing with PHI past here
    v = study.read_methods(v, p["absent_code"])
    left_out = pd.DataFrame([{"reason_name": k, "visit_count": n} for k, n in left.items()])
    return v.reset_index(drop=True), left_out


def _agreement(v: pd.DataFrame, groupings: list[str]) -> pd.DataFrame:
    score = _scorer()
    parts = []
    for g in groupings:
        for m in AGREEMENT_METHODS:
            s = score(v["truth_status"], v[m], None, model_id=m, run_id="preset", grouping=g)
            parts.append(s.drop(columns=["run_id", "model_id", "language", "timestamp"])
                         .rename(columns={"class": "status_group", "n_test": "visit_count"})
                         .assign(method_name=m, grouping=g))
    out = pd.concat(parts, ignore_index=True)
    return out[["grouping", "method_name", "metric", "status_group", "value", "visit_count"]]


def _prevalence(v: pd.DataFrame, groupings: list[str]) -> pd.DataFrame:
    return pd.concat([prevalence.prevalence_by_group(v, src, g, by="clinic_id").assign(status_source=src)
                      for g in groupings for src in PREVALENCE_SOURCES], ignore_index=True)


def _classifier(v: pd.DataFrame, p: dict) -> pd.DataFrame:
    rows = []
    v = v[[c for c in study.STRUCTURED_COLS if c in v]]       # the columns script 40 reads (visits_structured.csv)
    for scheme in CLASSIFIER_SCHEMES:
        f = cs.features(v, CLASSIFIER_OUTCOME, scheme)
        r = cs.train_eval(f, scheme, seed=CLASSIFIER_SEED, folds=p["classifier_cv_folds"],
                          split_unit=p["classifier_split_unit"], test_share=p["classifier_test_share"])
        s, val = r["summary"], r["validation"]
        rows.append({"scheme": scheme, "outcome": CLASSIFIER_OUTCOME, "split_unit": val["split_unit"],
                     "test_share": val["test_share"], "cv_folds": val["cv_folds"],
                     "train_visit_count": s["n_train"], "test_visit_count": s["n_test"],
                     "test_people_count": s["people_test"], "people_in_both_count": val["people_in_both_count"],
                     "accuracy": s["accuracy"], "macro_f1": s["macro_f1"], "cv_macro_f1": s["cv_macro_f1"],
                     "params_text": str(s["params"])})
    return pd.DataFrame(rows)


def _tooth_loss(p: dict, x: dict, truth: pd.DataFrame, seed: int, n_boot: int) -> dict[str, pd.DataFrame]:
    params = tlm.ModelParams(n_boot=n_boot, min_age=p["tooth_loss_min_age"], start_date=p["tooth_loss_start_date"],
                             split_unit=p["tooth_loss_split_unit"], test_share=p["tooth_loss_test_share"],
                             cv_folds=p["tooth_loss_cv_folds"])
    out = tlm.run(x, truth, params, generator_seed=seed)
    teeth = tlm.with_first_exam_date(tooth_loss.tooth_table(x), x)      # as scripts/51_tooth_loss_model.py counts
    left = pd.DataFrame([{"reason_name": k, "tooth_count": n} for k, n in tlm.exclusions(teeth, params).items()])
    val = out["validation"].drop(columns=["data_label"])
    s = out["scores"]
    s = s[s["model"].isin(tlm.MODELS) & s["metric"].isin(HEADLINE_METRICS)].drop(columns=["data_label"])
    s = s.merge(val[["label_set", "feature_set", "split_unit", "test_share", "cv_folds", "people_in_both_count"]],
                on=["label_set", "feature_set"], how="left").assign(n_boot=n_boot)
    st = out["stage_recount"]
    st = st[st["rule"].isin(p["stage4_rules"])].drop(columns=["data_label"])
    return {"tooth_loss_left_out": left, "tooth_loss_scores": s.reset_index(drop=True), "tooth_loss_validation": val,
            "tooth_loss_stage_recount": st.reset_index(drop=True)}


def _icc() -> pd.DataFrame:
    shape = ICC_SHAPE
    d = reliability_cal.draw_repeated_charts(shape["n_patients"], shape["n_teeth"], shape["n_visits"],
                                             reliability_cal.CalParams(), seed=shape["seed"])
    c = reliability_cal.nested_components(d)
    r = {**{k: c[k] for k in reliability_cal.COMPONENTS}, **reliability_cal.icc_report(c)}
    return pd.DataFrame([{"metric_name": k, "value": float(val), "patient_count": shape["n_patients"],
                          "teeth_per_patient_count": shape["n_teeth"], "visits_per_patient_count": shape["n_visits"]}
                         for k, val in r.items()])


@traced
def run_preset(name: str, n_people: int = 1200, n_patients: int = 6000, seed: int = 42, n_boot: int = 0,
               path: Path = PRESETS_FILE) -> dict[str, pd.DataFrame]:
    """Every part under one preset, on synthetic data with fixed seeds: `n_people` for the visit-level study set
    (study.generate_visits) and `n_patients` for the Open Dental extract (one generator seed, `seed`). Returns one
    frame per PARTS entry (icc only when the preset turns it on), every row labelled synthetic and with the preset's
    name."""
    p = load_preset(name, path)
    groupings = [p["grouping"], *[g for g in p["also_reported_groupings"] if g != p["grouping"]]]
    v, visits_left = _visits(p, n_people, seed)
    out = {"settings": settings_table(name, path), "visits_left_out": visits_left,
           "visits_agreement": _agreement(v, groupings), "prevalence": _prevalence(v, groupings)}
    tables, truth, readings = open_dental.build_with_readings(open_dental.Params(n_patients=n_patients), seed)
    x = {**open_dental.clean(tables), "radiograph_bone_level": readings}   # the reading is SIMULATED (#385)
    out |= _tooth_loss(p, x, truth, seed, n_boot)
    out["classifier"] = _classifier(v, p)
    out["consistency"] = tooth_loss_dq.group_consistency(tables, tuple(p["consistency_groups"]))
    if p["cal_icc"]:
        out["icc"] = _icc()
    return {k: out[k].assign(preset_name=name, data_label=DATA_LABEL).reset_index(drop=True)
            for k in PARTS if k in out}
