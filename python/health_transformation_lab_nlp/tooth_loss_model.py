"""Was a missing tooth lost to periodontitis? The tooth-level model and the stage recount (spec 029 US3, #371).

Follows the pre-specified analysis plan, specs/029-tooth-loss/analysis_plan.md (TRIPOD+AI order); its section numbers
are given below. Reads the silver tooth table (`tooth_loss.tooth_table`); the answer key (`tooth_loss_truth`) is read
only to score the teeth that have no recorded reason, never as a feature. Synthetic data only.

- Who (s. 3): every tooth, third molars left out by default; adults only: a minimum age (`ModelParams.min_age`,
  default 18; None for no cut-off, a sensitivity analysis). Age is at the tooth's loss, or at the first exam when the
  loss date isn't recorded (teeth missing at entry, planned extractions). Optionally from a start date
  (`ModelParams.start_date`, default None: every year; spec 032 US2): a tooth counts when its loss date, or its
  patient's first exam date when the loss date isn't recorded, is on or after it.
- Label (s. 4, FR-010): 1 = the extraction's diagnosis item is periodontal, 0 = another reason. Two label sets:
  `completed` (completed extractions) and `completed_planned` (plus planned ones; the tooth table already counts a
  tooth planned then completed once, as completed).
- Predictors (s. 5): `shared` (tooth_loss.SHARED_FEATURES, available for every missing tooth: the applied model) and
  `own` (plus the tooth's last measures and chart quality: shown beside it, scored only where own measures exist).
- Models (s. 8): logistic regression (L2, C = 1, standardised; median imputation fitted on training data plus one
  missing indicator per predictor with any missing value) and XGBoost (depth 3, 200 trees, learning rate 0.05,
  subsample 0.8, missing values as they are). No resampling. Baselines: every missing tooth is periodontal, the
  training outcome rate, and only recorded periodontal extractions count (probability 0 for an unlabelled tooth).
- Validation (s. 9): 70/30 split by patient, stratified on the outcome, seed fixed; one split shared by both label
  sets, so both are scored on the same held-out teeth (completed extractions of the held-out patients). Applied sets:
  teeth missing at entry and extractions without a diagnosis, scored against the synthetic answer key.
  Settings (spec 032 US5): `split_unit` `visit` holds out random teeth instead of patients (stratified on the
  outcome); a patient can then be on both sides, which flatters the score, so the `validation` frame counts them
  and it is never the default. `cv_folds` tunes XGBoost by k-fold cross-validated AUC over XGB_GRID (folds grouped
  by patient unless the split is by visit), in place of the fixed XGB_PARAMS.
- Measures (s. 10): AUC, Brier, calibration intercept and slope, a 10-bin calibration table, and sensitivity,
  specificity, PPV and NPV at 0.5 and at Youden's threshold chosen on the training predictions; 95% intervals from
  bootstrap resamples of patients, not teeth. Stage III vs IV per patient under four counting rules, and two rules
  on the teeth left (fewer than 20 teeth, fewer than 10 occluding pairs; spec 032 US4) (labels.STAGE4_COUNT_RULES).

Base-R twins of the metrics and the stage rule: r/R/16_spec029.R, checked by r/tests/test_parity.R.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from . import labels
from . import tooth_loss as tl
from .sites import THIRD_MOLARS
from .telemetry import traced

LABEL_SETS = {"completed": ("extracted_perio", "extracted_other"),
              "completed_planned": ("extracted_perio", "extracted_other", "planned_perio", "planned_other")}
FEATURE_SETS = {"shared": tl.SHARED_FEATURES, "own": tl.OWN_FEATURES}
MODELS = ("logistic", "xgboost")
BASELINES = ("baseline_all_perio", "baseline_outcome_rate", "baseline_recorded_only")
APPLIED_STATUSES = ("missing_at_entry", "extracted_no_dx")
MISSING_STATUSES = ("extracted_perio", "extracted_other", "extracted_no_dx", "missing_at_entry")
EVAL_SETS = ("held_out", "missing_at_entry", "extracted_no_dx")
TOOTH_TYPES = tuple(f"{arch}_{kind}" for arch in ("upper", "lower") for kind in ("incisor", "canine", "premolar",
                                                                                 "molar"))
CHART_QUALITY = ("complete", "partial", "copied", "uniform")
CATEGORICAL = {"tooth_type_code": TOOTH_TYPES, "last_chart_quality_code": CHART_QUALITY}
XGB_PARAMS = {"max_depth": 3, "n_estimators": 200, "learning_rate": 0.05, "subsample": 0.8}
XGB_GRID = {"max_depth": [2, 3, 4], "n_estimators": [100, 200], "learning_rate": [0.05, 0.1],
            "subsample": [0.8, 1.0], "min_child_weight": [1, 5]}       # cv_folds: the tuning grid (spec 032 US5)
SPLIT_UNITS = ("person", "visit")       # visit: random rows, so a patient can be on both sides (reported)
LOGISTIC_C = 1.0
N_BINS = 10
CLIP = 1e-8                     # probabilities are clipped to [CLIP, 1 - CLIP] before the logit
STAGE3_4_CAL_MM = 5.0           # worst CAL at which tooth loss decides III vs IV (AAP worksheet)
DATA_LABEL = "synthetic"


@dataclass(frozen=True)
class ModelParams:
    """The analysis plan's fixed choices, and the open decisions with their defaults."""
    test_share: float = 0.3
    seed: int = 42                         # split, models and bootstrap
    min_age: int | None = 18               # analysis plan s. 3: adults; sensitivity none (None) and 30
    include_third_molars: bool = False     # sensitivity analysis when True
    start_date: str | None = None          # spec 032 US2: ISO date; teeth lost (or first charted) before it are out
    n_boot: int = 1000
    threshold: float = 0.5
    split_unit: str = "person"             # spec 032 US5: SPLIT_UNITS; visit reports the patients in both
    cv_folds: int | None = None            # spec 032 US5: tune XGBoost over XGB_GRID by k-fold CV when set


DEFAULT = ModelParams()


@traced
def check_params(params: ModelParams) -> None:
    """Fail at once, naming the setting, on a validation setting that can't work."""
    if params.split_unit not in SPLIT_UNITS:
        raise ValueError(f"split_unit {params.split_unit!r}: one of {SPLIT_UNITS}")
    if not 0 < params.test_share < 1:
        raise ValueError(f"test_share {params.test_share!r}: between 0 and 1")
    if params.cv_folds is not None and params.cv_folds < 2:
        raise ValueError(f"cv_folds {params.cv_folds!r}: at least 2, or None for no tuning")


# ---------- who, the label sets and the predictors

def _age(t: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(t["age_at_loss_num"] if "age_at_loss_num" in t else t["age_at_first_exam_num"],
                         errors="coerce")


def _ref_date(t: pd.DataFrame) -> pd.Series:
    """The date a start date is compared with: the loss date, else the first exam date (when the frame has one)."""
    on = pd.to_datetime(t["loss_date"])
    return on.fillna(pd.to_datetime(t["first_exam_date"])) if "first_exam_date" in t else on


@traced
def eligible(teeth: pd.DataFrame, params: ModelParams = DEFAULT) -> pd.DataFrame:
    """The teeth in the analysis: third molars out unless included; at least `min_age` when one is set (a tooth
    whose age isn't recorded is then left out too: `exclusions` counts them); on or after `start_date` when one is
    set (a tooth with no date is then left out too)."""
    t = teeth if params.include_third_molars else teeth[~teeth["tooth_num"].isin(THIRD_MOLARS)]
    if params.min_age is not None:
        t = t[_age(t) >= params.min_age]
    if params.start_date is not None:
        t = t[_ref_date(t) >= pd.Timestamp(params.start_date)]
    return t


@traced
def exclusions(teeth: pd.DataFrame, params: ModelParams = DEFAULT) -> dict[str, int]:
    """How many teeth `eligible` leaves out, by reason, in the order it applies them (each tooth counted once, under
    the first reason), and how many it keeps."""
    molar = pd.Series(False, index=teeth.index) if params.include_third_molars else \
        teeth["tooth_num"].isin(THIRD_MOLARS)
    age = _age(teeth)
    cut = params.min_age is not None
    unknown = ~molar & age.isna() & cut
    young = ~molar & ~age.isna() & (age < params.min_age if cut else False)
    left = ~molar & ~unknown & ~young
    on = _ref_date(teeth)
    dated = params.start_date is not None
    no_date = left & on.isna() & dated
    early = left & on.notna() & ((on < pd.Timestamp(params.start_date)) if dated else False)
    return {"third_molar_count": int(molar.sum()), "under_min_age_count": int(young.sum()),
            "unknown_age_count": int(unknown.sum()), "before_start_date_count": int(early.sum()),
            "unknown_date_count": int(no_date.sum()), "eligible_count": int((left & ~no_date & ~early).sum())}


@traced
def with_first_exam_date(teeth: pd.DataFrame, x: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The tooth table plus `first_exam_date`: each patient's first perio exam, else their first visit date (the
    same date the age at first exam uses). Added only when a start date is set, so the default run is unchanged."""
    exams = x["perioexam"]
    first = pd.to_datetime(exams["examdate"]).groupby(pd.to_numeric(exams["patnum"], errors="coerce")).min()
    pat = x["patient"]
    visit = pd.Series(pd.to_datetime(pat["datefirstvisit"], errors="coerce").to_numpy(),
                      index=pd.to_numeric(pat["patnum"], errors="coerce"))
    on = teeth["patient_id"].map(first).astype("datetime64[ns]")
    return teeth.assign(first_exam_date=on.fillna(teeth["patient_id"].map(visit).astype("datetime64[ns]")))


@traced
def label_set(teeth: pd.DataFrame, name: str) -> pd.DataFrame:
    """The labelled teeth of one label set (FR-010), with is_perio_loss as the outcome."""
    if name not in LABEL_SETS:
        raise ValueError(f"unknown label set {name!r}; one of {tuple(LABEL_SETS)}")
    return teeth[teeth["tooth_status_code"].isin(LABEL_SETS[name]) & teeth["is_perio_loss"].notna()]


@traced
def design_matrix(teeth: pd.DataFrame, feature_set: str) -> pd.DataFrame:
    """Floats, NaN where not recorded. Categories one-hot over a fixed list (NaN in every column when missing), so
    the training and applied matrices have the same columns. Mobility (0-3) is a number."""
    cols = {}
    for f in FEATURE_SETS[feature_set]:
        v = teeth[f]
        if f in CATEGORICAL:
            for k in CATEGORICAL[f]:
                cols[f"{f}={k}"] = (v == k).astype(float).where(v.notna())
        elif f.startswith("is_"):
            cols[f] = v.map({True: 1.0, False: 0.0}).astype(float)
        else:
            cols[f] = pd.to_numeric(v, errors="coerce").astype("Float64").astype(float)
    return pd.DataFrame(cols, index=teeth.index)


def _predictor(column: str) -> str:
    return column.split("=")[0]


@traced
def split_patients(labelled: pd.DataFrame, test_share: float = 0.3, seed: int = 42) -> frozenset:
    """Held-out patients: `test_share` of each stratum (only periodontal labels, only other, both), seeded."""
    y = labelled["is_perio_loss"].astype(bool)
    by = y.groupby(labelled["patient_id"]).agg(["all", "any"])
    stratum = np.where(by["all"], "perio", np.where(by["any"], "both", "other"))
    rng = np.random.default_rng(seed)
    test = []
    for s in ("both", "other", "perio"):
        pats = np.sort(by.index[stratum == s].to_numpy())
        test.extend(rng.permutation(pats)[:round(len(pats) * test_share)].tolist())
    return frozenset(test)


@traced
def split_teeth(labelled: pd.DataFrame, test_share: float = 0.3, seed: int = 42) -> frozenset:
    """Held-out teeth (index labels) for `split_unit=visit`: `test_share` of each outcome, at random, seeded. A
    patient can have teeth on both sides (`people_in_both`)."""
    y = labelled["is_perio_loss"].astype(bool).to_numpy()
    rng = np.random.default_rng(seed)
    test = []
    for v in (False, True):
        rows = np.sort(labelled.index[y == v].to_numpy())
        test.extend(rng.permutation(rows)[:round(len(rows) * test_share)].tolist())
    return frozenset(test)


@traced
def people_in_both(people, in_test) -> int:
    """How many people have rows in both the training and the test part."""
    people, in_test = np.asarray(people), np.asarray(in_test, dtype=bool)
    return len(set(people[in_test].tolist()) & set(people[~in_test].tolist()))


@traced
def cv_splits(y, groups, folds: int, seed: int = 42) -> list[tuple[np.ndarray, np.ndarray]]:
    """(train, validation) row positions for `folds`-fold CV, stratified on the outcome and seeded; grouped so
    no person is on both sides of a fold, unless `groups` is None (a split by visit)."""
    from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
    y = np.asarray(y, dtype=int)
    if groups is None:
        return list(StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed).split(np.zeros(len(y)), y))
    return list(StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
                .split(np.zeros(len(y)), y, np.asarray(groups)))


@traced
def tune_xgboost(X: pd.DataFrame, y, groups, folds: int, seed: int = 42, grid: dict | None = None) -> dict:
    """The grid point (XGB_GRID by default) with the best mean validation AUC over `folds` folds (cv_splits),
    plus `cv_auc` and `cv_folds_used`. A fold without both outcomes on each side is skipped."""
    grid = grid or XGB_GRID
    y = np.asarray(y, dtype=int)
    cv = [(tr, va) for tr, va in cv_splits(y, groups, folds, seed)
          if len(np.unique(y[tr])) == 2 and len(np.unique(y[va])) == 2]
    if not cv:
        raise ValueError(f"cv_folds {folds}: no fold has both outcomes on each side")
    keys = list(grid)
    best, best_auc = None, -1.0
    for values in itertools.product(*(grid[k] for k in keys)):
        params = dict(zip(keys, values))
        aucs = [_auc(y[va].astype(float), _XGBoost(seed, params).fit(X.iloc[tr], y[tr]).predict(X.iloc[va]))
                for tr, va in cv]
        if np.mean(aucs) > best_auc:
            best, best_auc = params, float(np.mean(aucs))
    return best | {"cv_auc": best_auc, "cv_folds_used": len(cv)}


# ---------- models

class _Logistic:
    """L2 logistic regression, C = 1, standardised inputs; median imputation and missing indicators fitted on the
    training data only (analysis plan s. 7)."""

    def __init__(self, seed: int):
        self.seed = seed

    def _z(self, X: pd.DataFrame) -> np.ndarray:
        Z = X.fillna(self.median)
        for g in self.indicators:
            Z[f"{g}_missing"] = X[[c for c in X.columns if _predictor(c) == g]].isna().any(axis=1).astype(float)
        return Z.to_numpy(float)

    @traced
    def fit(self, X: pd.DataFrame, y: np.ndarray) -> _Logistic:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        self.median = X.median().fillna(0.0)
        self.indicators = sorted({_predictor(c) for c in X.columns if X[c].isna().any()})
        Z = self._z(X)
        self.scaler = StandardScaler().fit(Z)
        self.model = LogisticRegression(C=LOGISTIC_C, max_iter=5000).fit(self.scaler.transform(Z), y)
        return self

    @traced
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(self.scaler.transform(self._z(X)))[:, 1].astype(float)


class _XGBoost:
    def __init__(self, seed: int, params: dict | None = None):
        from xgboost import XGBClassifier
        self.model = XGBClassifier(objective="binary:logistic", tree_method="hist", random_state=seed, n_jobs=1,
                                   eval_metric="logloss", **(params or XGB_PARAMS))

    @traced
    def fit(self, X: pd.DataFrame, y: np.ndarray) -> _XGBoost:
        self.model.fit(X.to_numpy(float), y)
        return self

    @traced
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X.to_numpy(float))[:, 1].astype(float)


@traced
def fit(model: str, X: pd.DataFrame, y, seed: int = 42, xgb_params: dict | None = None):
    """A fitted `logistic` or `xgboost` model with .predict(X) -> P(lost to periodontitis). `xgb_params` replaces
    XGB_PARAMS (a tuned grid point); the logistic model has no such settings."""
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        raise ValueError(f"{model}: the training teeth hold one class only; nothing to fit")
    if model == "xgboost":
        return _XGBoost(seed, xgb_params).fit(X, y)
    return {"logistic": _Logistic}[model](seed).fit(X, y)


# ---------- metrics (twins in r/R/16_spec029.R)

def _arrays(y, p):
    return np.asarray(y, dtype=float), np.asarray(p, dtype=float)


def _auc(y, p) -> float:
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    r = rankdata(np.concatenate([pos, neg]))
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _classification(y, p, threshold) -> dict:
    pred = p >= threshold
    tp, fp = int(np.sum(pred & (y == 1))), int(np.sum(pred & (y == 0)))
    fn, tn = int(np.sum(~pred & (y == 1))), int(np.sum(~pred & (y == 0)))

    def ratio(a, b):
        return a / b if b else float("nan")
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "sensitivity": ratio(tp, tp + fn),
            "specificity": ratio(tn, tn + fp), "ppv": ratio(tp, tp + fp), "npv": ratio(tn, tn + fn)}


def _logit(p):
    q = np.clip(p, CLIP, 1 - CLIP)
    return np.log(q / (1 - q))


def _newton(y, lp, slope: bool, max_iter: int = 100, tol: float = 1e-10) -> tuple[float, float]:
    """Logistic regression of y on logit(p): intercept and slope, or the intercept alone with logit(p) as offset."""
    nan = (float("nan"), float("nan"))
    if np.all(y == y[0]) or (slope and np.ptp(lp) == 0):
        return nan
    a, b = 0.0, 1.0
    with np.errstate(all="ignore"):
        for _ in range(max_iter):
            mu = 1 / (1 + np.exp(-(a + b * lp)))
            w, r = mu * (1 - mu), y - mu
            if slope:
                g0, g1 = np.sum(r), np.sum(r * lp)
                h00, h01, h11 = np.sum(w), np.sum(w * lp), np.sum(w * lp * lp)
                det = h00 * h11 - h01 * h01
                da, db = (h11 * g0 - h01 * g1) / det, (h00 * g1 - h01 * g0) / det
            else:
                da, db = np.sum(r) / np.sum(w), 0.0
            if not (np.isfinite(da) and np.isfinite(db)):
                return nan                                  # separation: the fit runs off to infinity
            a, b = a + da, b + db
            if max(abs(da), abs(db)) < tol:
                return float(a), float(b)
    return nan


def _youden(y, p) -> float:
    ps = np.sort(p)
    ys = y[np.argsort(p, kind="stable")]
    u = np.unique(p)
    pos, neg = ys.sum(), len(ys) - ys.sum()
    if not pos or not neg:
        return float("nan")
    i = np.searchsorted(ps, u, side="left")               # teeth below each threshold
    tp = pos - np.concatenate([[0.0], np.cumsum(ys)])[i]
    fp = (len(ys) - i) - tp
    j = tp / pos + (neg - fp) / neg - 1
    return float(u[np.argmax(j)])


def _calibration_table(y, p) -> pd.DataFrame:
    b = np.minimum(np.floor(p * N_BINS).astype(int), N_BINS - 1)
    rows = []
    for k in range(N_BINS):
        m = b == k
        n = int(m.sum())
        rows.append({"bin_num": k, "bin_low_ratio": k / N_BINS, "bin_high_ratio": (k + 1) / N_BINS, "tooth_count": n,
                     "mean_predicted_ratio": float(p[m].mean()) if n else float("nan"),
                     "observed_ratio": float(y[m].mean()) if n else float("nan")})
    return pd.DataFrame(rows)


@traced
def auc(y, p) -> float:
    """Area under the ROC curve (Mann-Whitney; ties count half). NaN without both classes."""
    return _auc(*_arrays(y, p))


@traced
def brier(y, p) -> float:
    """Mean squared difference between the probability and the outcome."""
    y, p = _arrays(y, p)
    return float(np.mean((p - y) ** 2))


@traced
def classification(y, p, threshold: float) -> dict:
    """Counts, sensitivity, specificity, PPV and NPV with p >= threshold called periodontal (NaN when undefined)."""
    return _classification(*_arrays(y, p), threshold)


@traced
def youden_threshold(y, p) -> float:
    """The smallest predicted probability that maximises sensitivity + specificity - 1 (p >= it is positive)."""
    return _youden(*_arrays(y, p))


@traced
def calibration_slope(y, p) -> tuple[float, float]:
    """(intercept, slope) of the logistic regression of the outcome on logit(p); NaN when it can't be fitted."""
    y, p = _arrays(y, p)
    return _newton(y, _logit(p), slope=True)


@traced
def calibration_intercept(y, p) -> float:
    """Calibration in the large: the intercept with logit(p) as an offset (slope fixed at 1)."""
    y, p = _arrays(y, p)
    return _newton(y, _logit(p), slope=False)[0]


@traced
def calibration_table(y, p) -> pd.DataFrame:
    """Ten equal-width bins of the predicted probability: count, mean predicted, observed share."""
    return _calibration_table(*_arrays(y, p))


def _metrics(y, p, thresholds: dict) -> list[tuple]:
    """(metric, threshold_name, value) rows for one set of teeth."""
    rows = [("auc", None, _auc(y, p)), ("brier", None, float(np.mean((p - y) ** 2))),
            ("calibration_intercept", None, _newton(y, _logit(p), slope=False)[0]),
            ("calibration_slope", None, _newton(y, _logit(p), slope=True)[1]),
            ("outcome_rate", None, float(y.mean())), ("mean_predicted", None, float(p.mean()))]
    for name, t in thresholds.items():
        c = _classification(y, p, t)
        rows += [(m, name, c[m]) for m in ("sensitivity", "specificity", "ppv", "npv")]
    return rows


@traced
def patient_bootstrap(patients, n_boot: int, seed: int = 42):
    """Yields n_boot index arrays, each a resample of whole patients with replacement (analysis plan s. 10)."""
    patients = np.asarray(patients)
    _, inv = np.unique(patients, return_inverse=True)
    order = np.argsort(inv, kind="stable")
    groups = np.split(order, np.flatnonzero(np.diff(inv[order])) + 1)
    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        yield np.concatenate([groups[k] for k in rng.integers(0, len(groups), len(groups))])


def _score(y, p, patients, thresholds: dict, n_boot: int, seed: int) -> list[dict]:
    point = _metrics(y, p, thresholds)
    boot = np.full((n_boot, len(point)), np.nan)
    for b, idx in enumerate(patient_bootstrap(patients, n_boot, seed)):
        boot[b] = [v for _, _, v in _metrics(y[idx], p[idx], thresholds)]
    out = []
    for k, (metric, tname, value) in enumerate(point):
        col = boot[:, k][~np.isnan(boot[:, k])] if n_boot else np.array([])
        lo, hi = (np.percentile(col, [2.5, 97.5]) if len(col) else (np.nan, np.nan))
        out.append({"metric": metric, "threshold_name": tname,
                    "threshold": thresholds.get(tname, np.nan) if tname else np.nan,
                    "value": value, "ci_low": float(lo), "ci_high": float(hi)})
    return out


# ---------- the patient's stage (labels.stage4_rule)

@traced
def patient_worst_cal(x: dict[str, pd.DataFrame]) -> pd.Series:
    """Worst CAL (mm) charted for each patient at any perio exam in the record."""
    teeth = tl._exam_teeth(x).merge(tl._exams(x), on="perioexamnum")
    return teeth.groupby("patient_id")["max_cal"].max()


@traced
def patient_stage(teeth: pd.DataFrame, prob: pd.Series, truth: pd.DataFrame, worst_cal: pd.Series,
                  chart: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per patient: teeth lost to periodontitis counted four ways, and stage IV (>= 5) under each rule; and
    the teeth left, with the occluding pairs between them, for the teeth-left rules (spec 032 US4).
    prob: P(lost to periodontitis) per tooth (teeth's index), read for the unlabelled missing teeth only.
    chart: the whole tooth table the teeth left are read from (default `teeth`): every tooth not missing, planned
    extractions included, whoever the model leaves out; `present_tooth_text` lists them as charted, and the counts
    leave out third molars (labels.stage4_tooth_counts).
    Patients with worst CAL >= 5 mm are the ones tooth loss moves between III and IV (`is_stage3_4`)."""
    chart = teeth if chart is None else chart
    left = chart.loc[~chart["tooth_status_code"].isin(MISSING_STATUSES), ["patient_id", "tooth_num"]]
    left = left.astype("int64").sort_values(["patient_id", "tooth_num"]).groupby("patient_id")["tooth_num"].agg(list)
    t = teeth[["patient_id", "tooth_num", "tooth_status_code"]].assign(p=prob.reindex(teeth.index))
    t = t.merge(truth[["patient_id", "tooth_num", "true_reason_code"]], on=["patient_id", "tooth_num"], how="left")
    t["missing"] = t["tooth_status_code"].isin(MISSING_STATUSES)
    t["unlabelled"] = t["tooth_status_code"].isin(APPLIED_STATUSES)
    rows = []
    for pat, g in t.groupby("patient_id", sort=True):
        recorded = int((g["tooth_status_code"] == "extracted_perio").sum())
        missing = int(g["missing"].sum())
        probs = g.loc[g["unlabelled"], "p"].fillna(0.0).tolist()
        true = int((g["missing"] & (g["true_reason_code"] == "perio")).sum())
        row = {"patient_id": int(pat), "recorded_perio_count": recorded, "missing_count": missing,
               "unlabelled_tooth_count": len(probs), "unlabelled_prob_sum": float(sum(probs)),
               "expected_perio_loss": labels.expected_perio_loss(recorded, probs), "true_perio_count": true,
               "worst_cal_mm": float(worst_cal.get(pat, np.nan))}
        present = left.get(pat, [])
        row["teeth_present_count"], row["occluding_pair_count"] = labels.stage4_tooth_counts(present)
        row["present_tooth_text"] = " ".join(str(n) for n in present)
        for rule in labels.STAGE4_COUNT_RULES:
            row[f"is_stage4_{rule}"] = labels.stage4_rule(rule, recorded, missing, probs, true, teeth_present=present)
        rows.append(row)
    out = pd.DataFrame(rows)
    out["is_stage3_4"] = out["worst_cal_mm"] >= STAGE3_4_CAL_MM
    return out


def _stage_summary(ps: pd.DataFrame, rules) -> list[dict]:
    p = ps[ps["is_stage3_4"]]
    truth, rec = p["is_stage4_truth"], p["is_stage4_recorded_only"]
    out = []
    for rule in rules:
        iv = p[f"is_stage4_{rule}"]
        out.append({"rule": rule, "patient_count": len(p), "stage3_count": int((~iv).sum()),
                    "stage4_count": int(iv.sum()), "agree_truth_count": int((iv == truth).sum()),
                    "false_iv_count": int((iv & ~truth).sum()), "missed_iv_count": int((~iv & truth).sum()),
                    "to_iv_vs_recorded_count": int((iv & ~rec).sum()),
                    "to_iii_vs_recorded_count": int((~iv & rec).sum())})
    return out


# ---------- one run

def _age_at_loss(teeth: pd.DataFrame, x: dict[str, pd.DataFrame]) -> pd.Series:
    born = x["patient"].assign(patient_id=pd.to_numeric(x["patient"]["patnum"], errors="coerce"))
    born = teeth["patient_id"].map(born.set_index("patient_id")["birthdate"].pipe(pd.to_datetime))
    on = pd.to_datetime(teeth["loss_date"])
    before = (on.dt.month < born.dt.month) | ((on.dt.month == born.dt.month) & (on.dt.day < born.dt.day))
    age = on.dt.year - born.dt.year - before.astype(int)
    return age.astype("Float64").fillna(teeth["age_at_first_exam_num"].astype("Float64"))


@traced
def run(x: dict[str, pd.DataFrame], truth: pd.DataFrame, params: ModelParams = DEFAULT,
        generator_seed: int = 42) -> dict[str, pd.DataFrame]:
    """Fit and score every model on both label sets (module docstring). Returns frames: scores, calibration,
    stage_recount, patient_stage, predictions, missing, eval_rows, and validation (how it was validated: the split,
    the patients in both parts, the XGBoost settings). Every row is labelled synthetic."""
    check_params(params)
    teeth = tl.tooth_table(x)
    teeth["age_at_loss_num"] = _age_at_loss(teeth, x)
    if params.start_date is not None:
        teeth = with_first_exam_date(teeth, x)
    el = eligible(teeth, params).reset_index(drop=True)
    true = el.merge(truth, on=["patient_id", "tooth_num"], how="left")["true_reason_code"]
    if params.split_unit == "person":
        test_pats = split_patients(label_set(el, "completed_planned"), params.test_share, params.seed)
        in_test = el["patient_id"].isin(test_pats)
    else:                                       # random teeth: a patient can be on both sides (reported below)
        test_rows = split_teeth(label_set(el, "completed_planned"), params.test_share, params.seed)
        in_test = pd.Series(el.index.isin(list(test_rows)), index=el.index)

    status = el["tooth_status_code"]
    eval_masks = {"held_out": status.isin(LABEL_SETS["completed"]) & el["is_perio_loss"].notna() & in_test,
                  "missing_at_entry": (status == "missing_at_entry") & true.notna(),
                  "extracted_no_dx": (status == "extracted_no_dx") & true.notna()}
    eval_y = {"held_out": el["is_perio_loss"].astype("Float64"), "missing_at_entry": (true == "perio").astype(float),
              "extracted_no_dx": (true == "perio").astype(float)}
    worst_cal = patient_worst_cal(x)
    tag = {"generator_seed": generator_seed}
    scores, cals, preds, eval_rows, stage_parts, missing, validation = [], [], [], [], [], [], []

    def score(ls, fs, model, ev, p, thresholds, boot):
        m = eval_masks[ev]
        y = eval_y[ev][m].to_numpy(float)
        pts = el.loc[m, "patient_id"].to_numpy()
        base = {**tag, "label_set": ls, "feature_set": fs, "model": model, "eval_set": ev,
                "tooth_count": int(m.sum()), "patient_count": len(np.unique(pts))}
        for r in _score(y, p[m.to_numpy()], pts, thresholds, params.n_boot if boot else 0, params.seed):
            scores.append({**base, **r})
        cals.append(_calibration_table(y, p[m.to_numpy()]).assign(**{k: base[k] for k in (
            "generator_seed", "label_set", "feature_set", "model", "eval_set")}))
        eval_rows.append(pd.DataFrame({**{k: base[k] for k in ("generator_seed", "label_set", "feature_set", "model",
                                                               "eval_set")},
                                       "patient_id": pts, "y": y, "p": p[m.to_numpy()]}))

    for ls in LABEL_SETS:
        labelled = el.index.isin(label_set(el, ls).index)
        train = labelled & ~in_test.to_numpy()
        y_train = el.loc[train, "is_perio_loss"].astype(bool).to_numpy(int)
        split = np.where(train, "train", np.where(labelled, "test", "applied"))
        keep = labelled | status.isin(APPLIED_STATUSES).to_numpy()
        # the share missing for each predictor, by label set and split (analysis plan s. 7)
        for sp, rows in (("train", train), ("test", labelled & ~train), *(
                (s, (status == s).to_numpy()) for s in APPLIED_STATUSES)):
            missing += [{**tag, "label_set": ls, "split": sp, "predictor": f, "tooth_count": int(rows.sum()),
                         "missing_ratio": float(el.loc[rows, f].isna().mean()) if rows.any() else np.nan}
                        for f in tl.OWN_FEATURES]
        both = people_in_both(el.loc[labelled, "patient_id"], in_test.to_numpy()[labelled])
        for fs in FEATURE_SETS:
            X = design_matrix(el, fs)
            xgb, cv_auc = XGB_PARAMS, np.nan
            if params.cv_folds:
                groups = None if params.split_unit == "visit" else el.loc[train, "patient_id"].to_numpy()
                best = tune_xgboost(X[train], y_train, groups, params.cv_folds, params.seed)
                cv_auc = best.pop("cv_auc")
                best.pop("cv_folds_used")
                xgb = best
            validation.append({**tag, "label_set": ls, "feature_set": fs, "split_unit": params.split_unit,
                               "test_share": params.test_share, "cv_folds": params.cv_folds,
                               "train_tooth_count": int(train.sum()),
                               "test_tooth_count": int((labelled & ~train).sum()),
                               "people_in_both_count": both, "xgboost_params": str(xgb), "cv_auc": cv_auc})
            for model in MODELS:
                fitted = fit(model, X[train], y_train, params.seed, xgb)
                p = fitted.predict(X)
                cut = _youden(y_train.astype(float), p[train])
                thresholds = {"fixed_0.5": params.threshold, "youden_train": cut}
                eval_rows.append(pd.DataFrame({**tag, "label_set": ls, "feature_set": fs, "model": model,
                                               "eval_set": "train", "patient_id": el.loc[train, "patient_id"].to_numpy(),
                                               "y": y_train.astype(float), "p": p[train]}))
                for ev in EVAL_SETS:
                    if not (fs == "own" and ev == "missing_at_entry"):      # no own measures there
                        score(ls, fs, model, ev, p, thresholds, boot=True)
                rows = keep & ~((fs == "own") & (status == "missing_at_entry").to_numpy())
                preds.append(pd.DataFrame({
                    "patient_id": el.loc[rows, "patient_id"].astype("int64").to_numpy(),
                    "tooth_num": el.loc[rows, "tooth_num"].astype("int64").to_numpy(),
                    "tooth_status_code": status[rows].to_numpy(), "label_set": ls, "feature_set": fs,
                    "model": model, "split": split[rows], "probability": p[rows], "threshold": params.threshold,
                    "predicted_perio": p[rows] >= params.threshold, "generator_seed": generator_seed,
                    "synthetic": True}))
                if fs == "shared":
                    ps = patient_stage(el, pd.Series(p, index=el.index), truth, worst_cal, chart=teeth)
                    stage_parts.append(ps.assign(**tag, label_set=ls, model=model))
        rate = float(y_train.mean())
        for model, value in (("baseline_all_perio", 1.0), ("baseline_outcome_rate", rate),
                             ("baseline_recorded_only", 0.0)):
            p = np.full(len(el), value)
            thresholds = {"fixed_0.5": params.threshold}
            for ev in EVAL_SETS:
                if model != "baseline_recorded_only" or ev != "held_out":   # on held-out teeth it is the label
                    score(ls, "none", model, ev, p, thresholds, boot=False)

    ps_all = pd.concat(stage_parts, ignore_index=True)
    first = ps_all[(ps_all["label_set"] == "completed") & (ps_all["model"] == MODELS[0])]
    recount = [{**tag, "label_set": "all", "model": "none", **r}
               for r in _stage_summary(first, [r for r in labels.STAGE4_COUNT_RULES if r != "expected_perio_loss"])]
    for (ls, model), g in ps_all.groupby(["label_set", "model"], sort=False):
        recount += [{**tag, "label_set": ls, "model": model, **r} for r in _stage_summary(g, ["expected_perio_loss"])]

    def label(df):
        return df.assign(data_label=DATA_LABEL).reset_index(drop=True)
    return {"scores": label(pd.DataFrame(scores)), "calibration": label(pd.concat(cals, ignore_index=True)),
            "stage_recount": label(pd.DataFrame(recount)), "patient_stage": label(ps_all),
            "predictions": pd.concat(preds, ignore_index=True), "missing": label(pd.DataFrame(missing)),
            "eval_rows": label(pd.concat(eval_rows, ignore_index=True)),
            "validation": label(pd.DataFrame(validation))}
