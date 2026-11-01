"""Periodontal status from the recorded chart with gradient-boosted trees, explained with SHAP (spec 013 G10).

Unit: a charted visit with a known status. Features: the recorded chart plus age, smoking, diabetes, HbA1c
and prior treatment. Two schemes: 5-level (healthy+gingivitis, stage 1-4) and 3-level (healthy+gingivitis,
stage 1-2, stage 3-4). Design after Patel et al. 2022 (Front Artif Intell, doi 10.3389/frai.2022.979525):
XGBoost, 80/20 split (here by person), 5-fold cross-validation for the hyperparameters, one-vs-rest metrics.

Validation settings (spec 032 US5): `split_unit` `person` (the default: no person in both parts, and tuning folds
grouped by person) or `visit` (random visits, folds by visit). A split by visit lets one person's visits fall on
both sides, which flatters the score, so the result's `validation` counts those people; it is never the default.
`test_share` sets the held-out share and `folds` the cross-validation folds.

SHAP: exact TreeSHAP computed by XGBoost itself (pred_contribs), the algorithm of Lundberg et al. 2020 that
the `shap` package uses for trees. For each held-out visit and class, the values plus a bias add up to the
model's margin (log-odds) for that class. Each feature carries its role in the 2017 AAP/EFP classification
(Tonetti, Greenwell & Kornman 2018), so the ranking can be read against it.

Synthetic data: the labels come from the AAP rules applied to the same chart, so stage criteria should
explain most of the model and grade modifiers little. That checks the pipeline; it finds nothing about
real patients. Needs the `ml` extra (xgboost).
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.utils.class_weight import compute_sample_weight

from .labels import LABELS
from .telemetry import traced

FEATURES = ["max_probing_depth_mm", "bop_pct", "max_cal_mm", "rbl_pct", "teeth_lost_perio", "pct_teeth_involved",
            "age", "smoker_1_9", "smoker_10plus", "diabetes", "hba1c", "treated_before"]
_CHART = {"rec_max_probing_depth_mm": "max_probing_depth_mm", "rec_bop_pct": "bop_pct",
          "rec_max_cal_mm": "max_cal_mm", "rec_rbl_pct": "rbl_pct", "rec_teeth_lost_perio": "teeth_lost_perio",
          "rec_pct_teeth_involved": "pct_teeth_involved"}
ROLES = ("stage", "gingivitis", "extent", "grade", "none")
# Role in the 2017 AAP/EFP classification (Tonetti, Greenwell & Kornman 2018; docs/staging_grading.md).
# Age enters grade through % bone loss / age; probing depth is a stage complexity factor.
AAP_ROLE = {"max_cal_mm": "stage", "rbl_pct": "stage", "teeth_lost_perio": "stage", "max_probing_depth_mm": "stage",
            "bop_pct": "gingivitis", "pct_teeth_involved": "extent", "age": "grade", "smoker_1_9": "grade",
            "smoker_10plus": "grade", "diabetes": "grade", "hba1c": "grade", "treated_before": "none"}

SCHEMES = {
    "5level": {"healthy": 0, "gingivitis": 0, "periodontitis_stage_1": 1, "periodontitis_stage_2": 2,
               "periodontitis_stage_3": 3, "periodontitis_stage_4": 4},
    "3level": {"healthy": 0, "gingivitis": 0, "periodontitis_stage_1": 1, "periodontitis_stage_2": 1,
               "periodontitis_stage_3": 2, "periodontitis_stage_4": 2},
    # Spec 023: Patel et al. 2026's 4 classes. The paper has no gingivitis class; here it counts as healthy (not
    # periodontitis), as in 3level (spec 023 FR-004).
    "four": {"healthy": 0, "gingivitis": 0, "periodontitis_stage_1": 1, "periodontitis_stage_2": 2,
             "periodontitis_stage_3": 3, "periodontitis_stage_4": 3},
}
CLASS_NAMES = {"5level": ["healthy_gingivitis", "stage_1", "stage_2", "stage_3", "stage_4"],
               "3level": ["healthy_gingivitis", "stage_1_2", "stage_3_4"],
               "four": ["healthy", "I", "II", "III_IV"]}
# Spec 023 feature sets, after Patel et al. 2026 experiments 1 and 5. Dental: the spec 013 features (chart, age,
# smoking, diabetes, HbA1c, prior treatment) plus ASA class, which the paper counts as a dental-record factor.
# ASA carries medical signal (medical_record.asa_class follows from the conditions), so dental_no_asa shows how
# much. Medical: the synthetic medical record (medical_record.py) plus age; there is no sex column (spec 013 G11).
# The dental sets use the chart the label is computed from: declared, as it is the point of a dental-record model.
MEDICAL_FEATURES = ["is_diabetes", "hba1c", "is_hypertension", "is_ckd", "is_cvd", "is_copd", "systolic_bp_mmhg",
                    "diastolic_bp_mmhg", "age"]
FEATURE_SETS = {
    "dental": [*FEATURES, "asa_class_num"],
    "dental_no_asa": list(FEATURES),
    # is_diabetes is the same fact as the dental set's `diabetes` (both HbA1c >= 6.5), so it isn't added twice
    "dental_medical": [*FEATURES, "asa_class_num",
                       *[c for c in MEDICAL_FEATURES if c not in FEATURES and c != "is_diabetes"]],
    "medical": MEDICAL_FEATURES,
}
ASA_NUM = {"I": 1, "II": 2, "III": 3, "IV": 4}
TEST_SHARE_023 = 0.3   # Patel et al. 2026: 70/30, stratified; the 80/20 split stays the default for 5level/3level
GRID = {"max_depth": [3, 5], "learning_rate": [0.05, 0.2], "reg_lambda": [1.0, 10.0], "min_child_weight": [1, 5],
        "class_weight": [None, "balanced"]}
N_TREES = 200
SPLIT_UNITS = ("person", "visit")       # spec 032 US5; visit: random rows, the people in both parts reported
assert set(SCHEMES["5level"]) == set(LABELS)


@traced
def features(visits: pd.DataFrame, outcome: str, scheme: str) -> pd.DataFrame:
    """Charted visits with a known status: one row each, the features and the class index `y`."""
    v = visits[visits["charted"].astype(bool) & visits[outcome].isin(LABELS)].rename(columns=_CHART).copy()
    v["smoker_1_9"] = ((v["cigarettes_per_day"] > 0) & (v["cigarettes_per_day"] < 10)).astype(int)
    v["smoker_10plus"] = (v["cigarettes_per_day"] >= 10).astype(int)
    for c in ("diabetes", "treated_before"):
        v[c] = v[c].astype(bool).astype(int)
    v["y"] = v[outcome].map(SCHEMES[scheme])
    v[FEATURES] = v[FEATURES].astype(float)                 # hba1c stays NaN when not measured: trees route it
    return v[["visit_id", "person_id", *FEATURES, "y"]].reset_index(drop=True)


@traced
def split_people(f: pd.DataFrame, seed: int = 0, test_share: float = 0.2) -> np.ndarray:
    """True for held-out rows: a random `test_share` of people, so no person is in both."""
    people = np.sort(f["person_id"].unique())
    test = np.random.default_rng(seed).choice(people, size=round(len(people) * test_share), replace=False)
    return f["person_id"].isin(test).to_numpy()


@traced
def split_visits(f: pd.DataFrame, seed: int = 0, test_share: float = 0.2) -> np.ndarray:
    """True for held-out rows: a random `test_share` of visits (`split_unit=visit`). A person's visits can fall on
    both sides (`people_in_both`)."""
    test = np.random.default_rng(seed).choice(len(f), size=round(len(f) * test_share), replace=False)
    return np.isin(np.arange(len(f)), test)


@traced
def people_in_both(f: pd.DataFrame, te: np.ndarray) -> int:
    """How many people have visits in both the training and the test part."""
    te = np.asarray(te, dtype=bool)
    return len(set(f.loc[te, "person_id"]) & set(f.loc[~te, "person_id"]))


def _check_split(split_unit: str, test_share: float) -> None:
    if split_unit not in SPLIT_UNITS:
        raise ValueError(f"split_unit {split_unit!r}: one of {SPLIT_UNITS}")
    if not 0 < test_share < 1:
        raise ValueError(f"test_share {test_share!r}: between 0 and 1")


def _groups(f: pd.DataFrame, split_unit: str) -> np.ndarray:
    """Tuning folds: by person, or by visit when the split is by visit."""
    return f["person_id" if split_unit == "person" else "visit_id"].to_numpy()


def _model(params: dict, n_class: int, seed: int):
    from xgboost import XGBClassifier
    p = {k: v for k, v in params.items() if k != "class_weight"}
    return XGBClassifier(n_estimators=N_TREES, objective="multi:softprob", num_class=n_class, tree_method="hist",
                         random_state=seed, n_jobs=1, **p)


def _fit(params: dict, X, y, n_class: int, seed: int):
    w = compute_sample_weight("balanced", y) if params.get("class_weight") == "balanced" else None
    return _model(params, n_class, seed).fit(X, y, sample_weight=w)


@traced
def tune(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, n_class: int, seed: int = 0,
         grid: dict | None = None, folds: int = 5) -> dict:
    """Grid search by grouped k-fold (people never split across folds), scored by macro F1. A fold whose
    training part lacks a class is skipped (xgboost can't fit it); `cv_folds_used` says how many were left."""
    grid = grid or GRID
    keys = list(grid)
    cv = [(tr, va) for tr, va in GroupKFold(n_splits=folds).split(X, y, groups)
          if len(np.unique(y[tr])) == n_class]
    if not cv:
        raise ValueError(f"every training fold lacks a class: fewer people per class than folds ({folds})")
    best, best_score = None, -1.0
    for values in itertools.product(*(grid[k] for k in keys)):
        params = dict(zip(keys, values))
        scores = [f1_score(y[va], _fit(params, X.iloc[tr], y[tr], n_class, seed).predict(X.iloc[va]),
                           average="macro", labels=list(range(n_class)), zero_division=0) for tr, va in cv]
        if np.mean(scores) > best_score:
            best, best_score = params, float(np.mean(scores))
    return best | {"cv_macro_f1": best_score, "cv_folds_used": len(cv)}


@traced
def shap_values(model, X: pd.DataFrame) -> np.ndarray:
    """Exact TreeSHAP: (visits, classes, features + bias); each row adds up to the class margin."""
    from xgboost import DMatrix
    phi = model.get_booster().predict(DMatrix(X, missing=np.nan), pred_contribs=True)
    return np.asarray(phi).reshape(len(X), -1, X.shape[1] + 1)


@traced
def train_eval(f: pd.DataFrame, scheme: str, seed: int = 0, grid: dict | None = None, folds: int = 5,
               split_unit: str = "person", test_share: float = 0.2) -> dict:
    """Split, tune by `folds`-fold CV, fit and score on the held-out part, with SHAP. `validation` says how: the
    split unit, the held-out share, the folds and how many people are in both parts (0 when split by person)."""
    _check_split(split_unit, test_share)
    names = CLASS_NAMES[scheme]
    n_class = len(names)
    te = (split_people if split_unit == "person" else split_visits)(f, seed, test_share)
    X, y = f[FEATURES], f["y"].to_numpy()
    missing = [names[k] for k in range(n_class) if not (y[~te] == k).any()]
    if missing:
        raise ValueError(f"no {', '.join(missing)} among the training people: the model can't learn it "
                         "(a larger study, or a coarser scheme such as 3level)")
    best = tune(X[~te], y[~te], _groups(f.loc[~te], split_unit), n_class, seed, grid, folds)
    params = {k: v for k, v in best.items() if k not in ("cv_macro_f1", "cv_folds_used")}
    model = _fit(params, X[~te], y[~te], n_class, seed)
    Xt, yt = X[te], y[te]
    proba = model.predict_proba(Xt)
    pred = proba.argmax(axis=1)

    rows = []
    for k, name in enumerate(names):
        pos, hit = yt == k, pred == k
        rows.append({"class": name, "n_test": int(pos.sum()),
                     "auroc": roc_auc_score(pos, proba[:, k]) if 0 < pos.sum() < len(pos) else np.nan,
                     "sensitivity": (hit & pos).sum() / pos.sum() if pos.any() else np.nan,
                     "specificity": (~hit & ~pos).sum() / (~pos).sum() if (~pos).any() else np.nan})
    metrics = pd.DataFrame(rows)

    phi = shap_values(model, Xt)
    imp = pd.DataFrame({"feature": FEATURES, "role": [AAP_ROLE[c] for c in FEATURES],
                        "mean_abs_shap": np.abs(phi[:, :, :-1]).mean(axis=(0, 1))})
    for k, name in enumerate(names):
        imp[f"mean_abs_shap_{name}"] = np.abs(phi[:, k, :-1]).mean(axis=0)
    imp = imp.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    per = pd.concat([pd.DataFrame(phi[:, k, :], columns=[*FEATURES, "bias"])
                     .assign(visit_id=f.loc[te, "visit_id"].to_numpy(), **{"class": name})
                     for k, name in enumerate(names)], ignore_index=True)
    per = per[["visit_id", "class", *FEATURES, "bias"]]

    summary = {"scheme": scheme, "n_train": int((~te).sum()), "n_test": int(te.sum()),
               "people_test": int(f.loc[te, "person_id"].nunique()), "accuracy": float(accuracy_score(yt, pred)),
               "macro_f1": float(f1_score(yt, pred, average="macro", labels=list(range(n_class)), zero_division=0)),
               "cv_macro_f1": best["cv_macro_f1"], "cv_folds_used": best["cv_folds_used"], "params": params}
    validation = {"split_unit": split_unit, "test_share": test_share, "cv_folds": folds,
                  "people_in_both_count": people_in_both(f, te)}
    return {"summary": summary, "validation": validation, "metrics": metrics, "shap_importance": imp,
            "shap_test": per, "model": model,
            "X_test": Xt, "test_predictions": pd.DataFrame({"visit_id": f.loc[te, "visit_id"].to_numpy(),
                                                            "y": yt, "pred": pred})}


# ---- Spec 023: dental-only, dental+medical and medical-only (Patel et al. 2026, experiments 1 and 5)

@traced
def person_features(visits: pd.DataFrame, record: pd.DataFrame, outcome: str, scheme: str = "four") -> pd.DataFrame:
    """One row per person: their latest charted visit with a known status (Patel et al. 2026's unit is the
    patient), its dental features, the person's synthetic medical record, and the class index `y`."""
    f = features(visits, outcome, scheme)
    dates = visits.set_index("visit_id")["visit_date"]
    f = f.assign(_date=f["visit_id"].map(dates)).sort_values(["person_id", "_date"]).groupby("person_id").tail(1)
    f = f.drop(columns="_date").merge(record, on="person_id", how="inner", validate="one_to_one")
    f["asa_class_num"] = f["asa_class_code"].map(ASA_NUM)
    cols = list(dict.fromkeys(c for fs in FEATURE_SETS.values() for c in fs))
    f[cols] = f[cols].astype(float)                 # hba1c stays NaN when not measured: trees route it
    return f[["visit_id", "person_id", *cols, "y"]].sort_values("person_id").reset_index(drop=True)


@traced
def split_stratified(f: pd.DataFrame, seed: int = 0, test_share: float = TEST_SHARE_023,
                     split_unit: str = "person") -> np.ndarray:
    """True for held-out rows. People are stratified by their highest class; within each class a random
    `test_share` of them (rounded) is held out, so no person is in both parts, and with one row per person each
    class's test count is within one visit of proportional. A class with fewer than 2 people fails: it can't be
    in both parts, and running unstratified would hide that (spec 023 edge cases). With `split_unit=visit` the
    rows themselves are stratified by class and held out at random, so a person can be in both parts."""
    _check_split(split_unit, test_share)
    unit = f.groupby("person_id")["y"].max() if split_unit == "person" else f["y"]
    rng = np.random.default_rng(seed)
    test = []
    for k, members in unit.groupby(unit):
        if len(members) < 2:
            raise ValueError(f"class {k} has {len(members)} {split_unit}: too few to stratify into train and test")
        ids = np.sort(members.index.to_numpy())
        n = min(max(round(len(ids) * test_share), 1), len(ids) - 1)
        test.extend(rng.choice(ids, size=n, replace=False))
    if split_unit == "visit":
        return f.index.isin(test)
    return f["person_id"].isin(test).to_numpy()


def _auc_rank(pos: np.ndarray, score: np.ndarray) -> float:
    """AUC by ranks (Mann-Whitney), ties given their average rank; missing when either side is empty."""
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return np.nan
    r = pd.Series(score).rank(method="average").to_numpy()
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


@traced
def class_metrics(y: np.ndarray, proba: np.ndarray, names: list[str]) -> pd.DataFrame:
    """Per class, one-vs-rest, as Table 2 of Patel et al. 2026 reports them (spec 023 US3; R twin
    r/R/13_spec023.R, parity-tested to 1e-9):
      - sensitivity and specificity of the arg-max class (the first class wins a tie, as numpy's argmax);
      - AUC by ranks with ties averaged, missing (not zero) for a class absent from `y` or with no rest;
      - Brier score: the mean over visits of (that class's probability - 1 if the visit is that class else 0)^2.
    Then a `mean` row: each metric averaged over the classes present in `y` (`classes_averaged` says how many);
    its `n_test` is the number of visits."""
    y, proba = np.asarray(y), np.asarray(proba, dtype=float)
    pred = proba.argmax(axis=1)
    rows = []
    for k, name in enumerate(names):
        pos, hit = y == k, pred == k
        rows.append({"class": name, "n_test": int(pos.sum()),
                     "sensitivity": (hit & pos).sum() / pos.sum() if pos.any() else np.nan,
                     "specificity": (~hit & ~pos).sum() / (~pos).sum() if (~pos).any() else np.nan,
                     "auc": _auc_rank(pos, proba[:, k]),
                     "brier": float(np.mean((proba[:, k] - pos) ** 2)),
                     "classes_averaged": np.nan})
    m = pd.DataFrame(rows)
    present = m["n_test"] > 0
    mean = {c: m.loc[present, c].mean() for c in ("sensitivity", "specificity", "auc", "brier")}   # skips NaN
    rows.append({"class": "mean", "n_test": len(y), **mean, "classes_averaged": int(present.sum())})
    return pd.DataFrame(rows)


@traced
def compare_feature_sets(people: pd.DataFrame, seed: int = 0, grid: dict | None = None, folds: int = 5,
                         scheme: str = "four", split_unit: str = "person",
                         test_share: float = TEST_SHARE_023) -> dict:
    """Train and test each of FEATURE_SETS on the same stratified 70/30 split of `people` (person_features).
    Returns, per feature set and class, the metrics (`metrics`); the held-out class probabilities
    (`predictions`); mean |SHAP| per feature (`shap_importance`); and how it was validated (`validation`, as in
    train_eval). SYNTHETIC: nothing about real patients."""
    names = CLASS_NAMES[scheme]
    n_class = len(names)
    te = split_stratified(people, seed, test_share, split_unit)
    y = people["y"].to_numpy()
    groups = _groups(people.loc[~te], split_unit)
    metrics, preds, imps = [], [], []
    for name, cols in FEATURE_SETS.items():
        X = people[cols]
        best = tune(X[~te], y[~te], groups, n_class, seed, grid, folds)
        params = {k: v for k, v in best.items() if k not in ("cv_macro_f1", "cv_folds_used")}
        model = _fit(params, X[~te], y[~te], n_class, seed)
        proba = model.predict_proba(X[te])
        metrics.append(class_metrics(y[te], proba, names).assign(feature_set=name))
        preds.append(pd.DataFrame(proba, columns=[f"p_{c}" for c in names])
                     .assign(feature_set=name, visit_id=people.loc[te, "visit_id"].to_numpy(), y=y[te]))
        phi = shap_values(model, X[te])
        imps.append(pd.DataFrame({"feature_set": name, "feature": cols,
                                  "mean_abs_shap": np.abs(phi[:, :, :-1]).mean(axis=(0, 1))})
                    .sort_values("mean_abs_shap", ascending=False))
    m = pd.concat(metrics, ignore_index=True)
    m["features"] = m["feature_set"].map({k: " ".join(v) for k, v in FEATURE_SETS.items()})
    m = m.assign(n_train=int((~te).sum()), seed=seed, is_synthetic=True)
    m = m[["feature_set", "class", "n_test", "sensitivity", "specificity", "auc", "brier", "classes_averaged",
           "n_train", "features", "seed", "is_synthetic"]]
    p = pd.concat(preds, ignore_index=True)[["feature_set", "visit_id", "y", *[f"p_{c}" for c in names]]]
    validation = {"split_unit": split_unit, "test_share": test_share, "cv_folds": folds,
                  "people_in_both_count": people_in_both(people, te)}
    return {"metrics": m, "predictions": p, "shap_importance": pd.concat(imps, ignore_index=True),
            "validation": validation}
