"""The tooth-loss model in the multi-model evaluation format, and whether other models do better (spec 042 US4, #867).

The format is the one spec 042 applied to the note readers (model_drivers.py), here for the tabular tooth-loss model of
spec 029 (tooth_loss_model.py): per missing tooth, P(lost to periodontitis), trained on extractions with a recorded
diagnosis. On the SAME held-out teeth (the plan's patient split), for both label sets and both predictor sets:

1. **A ranked table**: each model's AUC, Brier score and calibration slope, with 95% intervals from bootstrap resamples
   of patients (analysis plan s. 10), on the held-out extractions and on the teeth missing at entry (the applied set,
   scored against the synthetic answer key).
2. **Paired differences** against the best pre-specified model (the plan's logistic regression or XGBoost, whichever
   has the higher AUC there): the AUC and Brier differences on the same bootstrap resamples, and DeLong's test.
3. **Drivers**: mean |SHAP| per predictor for the plan's two models (exact linear and TreeSHAP), permutation importance
   (the held-out AUC lost when one predictor is shuffled) for every model, and the AUC lost when a model is refitted
   without one predictor (shared predictors, the applied model).

The plan's two models are fitted exactly as tooth_loss_model.run fits them (the same split, imputation, 5-fold tuning
of XGBoost over XGB_GRID), so their scores are the pre-specified results. The other models are **post hoc
candidates, outside the analysis plan**: tuned by the same grouped 5-fold cross-validation on the training teeth
(tooth_loss_model.cv_splits) over small fixed grids (GRIDS), scored once on the held-out teeth, and marked
is_prespecified = False everywhere. Adding one to the analysis needs an amendment to the plan's change log first.

Every number is SYNTHETIC: agreement with a synthetic answer key, not a finding about any practice.

    compare(x, truth, params)  {table: DataFrame} for TABLES on one extract
    build(...)                 compare() on the main seed, plus the seed stability table
    details_markdown(built)    docs/tooth_loss_drivers.md
    COMMENTS                   {table: (table comment, {column: comment})}, for Unity Catalog
"""

from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import tooth_loss as tl
from . import tooth_loss_model as tlm
from .paths import REPO_ROOT
from .telemetry import traced

OUT_DIR = REPO_ROOT / "data" / "datasets" / "model_drivers"
DETAILS_DOC = REPO_ROOT / "docs" / "tooth_loss_drivers.md"
TABLES = ("tooth_loss_model_rank", "tooth_loss_model_contrast", "tooth_loss_driver")
STABILITY = "tooth_loss_model_seed"
ALL_TABLES = TABLES + (STABILITY,)
N_PERMUTE = 10                  # shuffles per predictor for permutation importance
DRIVER_FEATURE_SET = "shared"   # the refit-without-one-predictor drop: the applied model only (run time)

MODEL_SPECS = {
    "logistic": {"is_prespecified": True, "family_code": "linear",
                 "model_text": "Logistic regression (L2, C = 1, standardised; median imputation and missing "
                               "indicators): the plan's"},
    "xgboost": {"is_prespecified": True, "family_code": "boosted_trees",
                "model_text": "XGBoost, tuned by 5-fold cross-validation over the plan's grid: the plan's"},
    "elastic_net_logistic": {"is_prespecified": False, "family_code": "linear",
                             "model_text": "Elastic-net logistic regression (L1 and L2 penalties, tuned), imputed "
                                           "and standardised as the plan's"},
    "spline_logistic": {"is_prespecified": False, "family_code": "additive",
                        "model_text": "Logistic regression with cubic splines on each continuous predictor (a "
                                      "GAM-like additive model)"},
    "random_forest": {"is_prespecified": False, "family_code": "bagged_trees",
                      "model_text": "Random forest (500 trees, scikit-learn; missing values handled by the trees)"},
    "hist_gradient_boosting": {"is_prespecified": False, "family_code": "boosted_trees",
                               "model_text": "Histogram gradient boosting (scikit-learn; missing values native)"},
    "ebm": {"is_prespecified": False, "family_code": "additive",
            "model_text": "Explainable Boosting Machine (interpret): a boosted shape function per predictor, no "
                          "interactions (a GAM fitted by boosting)"},
}
PRESPECIFIED = tuple(m for m, s in MODEL_SPECS.items() if s["is_prespecified"])

# the tuning grids of the candidates, by the same grouped 5-fold CV as XGBoost; XGBoost keeps the plan's XGB_GRID
GRIDS = {
    "logistic": {},                                             # the plan fixes C = 1
    "xgboost": tlm.XGB_GRID,
    "elastic_net_logistic": {"C": [0.03, 0.1, 0.3, 1.0], "l1_ratio": [0.25, 0.5, 1.0]},
    "spline_logistic": {"C": [0.1, 0.3, 1.0], "n_knots": [4, 6]},
    "random_forest": {"min_samples_leaf": [1, 5, 20], "max_features": ["sqrt", 0.5]},
    "hist_gradient_boosting": {"learning_rate": [0.05, 0.1], "max_leaf_nodes": [4, 8, 16], "l2_regularization": [0.0,
                                                                                                                1.0]},
    "ebm": {"learning_rate": [0.015, 0.04], "max_leaves": [2, 3]},   # no interactions: 15 times faster (a pure GAM)
}

FEATURE_TEXT = {
    "tooth_type_code": "tooth type (upper or lower; incisor, canine, premolar, molar)",
    "neighbour_max_cal_mm": "the neighbouring teeth's worst attachment loss",
    "mouth_cal5_site_pct": "share of sites with attachment loss of 5 mm or more (first exam)",
    "mouth_max_pd_mm": "deepest pocket in the mouth (first exam)", "mouth_bop_pct": "bleeding on probing (first exam)",
    "mouth_max_rbl_pct": "worst radiographic bone loss (first exam; a SIMULATED reading)",
    "teeth_missing_at_entry_count": "teeth already missing at the first exam", "age_at_first_exam_num": "age",
    "is_smoker": "smoking", "is_diabetic": "diabetes", "last_max_pd_mm": "the tooth's own deepest pocket",
    "last_max_cal_mm": "the tooth's own worst attachment loss", "last_bop_pct": "the tooth's own bleeding",
    "last_mobility_code": "the tooth's own mobility", "last_chart_quality_code": "how good the tooth's last chart was",
    "last_rbl_pct": "the tooth's own radiographic bone loss (SIMULATED reading)"}


@traced
def available_models() -> tuple[str, ...]:
    """The models this environment can fit: every one, less the EBM when `interpret` isn't installed."""
    try:
        import interpret.glassbox  # noqa: F401
        return tuple(MODEL_SPECS)
    except ImportError:
        return tuple(m for m in MODEL_SPECS if m != "ebm")


@traced
def feature_group(column: str) -> str:
    """The predictor a design column belongs to: one-hot columns and missing indicators fold into it."""
    return column.split("=")[0].removesuffix("_missing")


@traced
def default_hyper(name: str) -> dict:
    """The model's settings without tuning: XGB_PARAMS for XGBoost, the first point of the grid otherwise."""
    if name == "xgboost":
        return dict(tlm.XGB_PARAMS)
    return {k: v[0] for k, v in GRIDS[name].items()}


# ---------- the candidates

class _Imputed:
    """Logistic regression on the plan's inputs: median imputation and one missing indicator per predictor with any
    missing value, fitted on the training teeth (analysis plan s. 7), standardised; optionally cubic splines on each
    continuous column (more than two values in training) first."""

    def __init__(self, seed: int, hyper: dict, splines: bool):
        self.seed, self.hyper, self.splines = seed, dict(hyper), splines

    def _frame(self, X: pd.DataFrame) -> np.ndarray:
        Z = X.fillna(self.median)
        for g in self.indicators:
            Z[f"{g}_missing"] = X[[c for c in X.columns if feature_group(c) == g]].isna().any(axis=1).astype(float)
        Z = Z.to_numpy(float)
        if self.splines:
            Z = np.column_stack([Z[:, self.flat], self.spline.transform(Z[:, self.cont])]) if self.cont else Z
        return Z

    @traced
    def fit(self, X: pd.DataFrame, y) -> _Imputed:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import SplineTransformer, StandardScaler
        self.median = X.median().fillna(0.0)
        self.indicators = sorted({feature_group(c) for c in X.columns if X[c].isna().any()})
        if self.splines:
            Z = X.fillna(self.median)
            n_ind = len(self.indicators)
            nuniq = [Z[c].nunique() for c in Z.columns] + [2] * n_ind
            self.cont = [i for i, k in enumerate(nuniq) if k > 2]
            self.flat = [i for i, k in enumerate(nuniq) if k <= 2]
            self.splines = False                                # the plain frame first, to fit the splines on
            raw = self._frame(X)
            self.splines = True
            if self.cont:
                self.spline = SplineTransformer(n_knots=self.hyper["n_knots"], degree=3, knots="uniform",
                                                extrapolation="linear").fit(raw[:, self.cont])
        Z = self._frame(X)
        self.scaler = StandardScaler().fit(Z)
        kw = {"C": self.hyper.get("C", 1.0), "max_iter": 5000}
        if "l1_ratio" in self.hyper:
            kw |= {"l1_ratio": self.hyper["l1_ratio"], "solver": "saga", "random_state": self.seed}
        self.model = LogisticRegression(**kw).fit(self.scaler.transform(Z), np.asarray(y, int))
        return self

    @traced
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(self.scaler.transform(self._frame(X)))[:, 1].astype(float)


class _Sklearn:
    """A scikit-learn or interpret classifier on the raw floats, missing values as they are."""

    def __init__(self, name: str, seed: int, hyper: dict):
        if name == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            self.model = RandomForestClassifier(n_estimators=500, random_state=seed, n_jobs=1, **hyper)
        elif name == "hist_gradient_boosting":
            from sklearn.ensemble import HistGradientBoostingClassifier
            self.model = HistGradientBoostingClassifier(max_iter=200, early_stopping=False, random_state=seed,
                                                        **hyper)
        else:
            from interpret.glassbox import ExplainableBoostingClassifier
            self.model = ExplainableBoostingClassifier(random_state=seed, n_jobs=1, interactions=0, outer_bags=8,
                                                       **hyper)

    @traced
    def fit(self, X: pd.DataFrame, y) -> _Sklearn:
        import warnings
        with warnings.catch_warnings():         # the EBM warns that its plots don't draw missing values
            warnings.simplefilter("ignore", UserWarning)
            self.model.fit(X.to_numpy(float), np.asarray(y, int))
        return self

    @traced
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X.to_numpy(float))[:, 1].astype(float)


@traced
def fit_model(name: str, X: pd.DataFrame, y, seed: int = 42, hyper: dict | None = None):
    """A fitted model with .predict(X) -> P(lost to periodontitis). The plan's two go through tooth_loss_model.fit,
    unchanged; `hyper` is a grid point (default_hyper when None)."""
    hyper = default_hyper(name) if hyper is None else hyper
    if name in PRESPECIFIED:
        return tlm.fit(name, X, y, seed, hyper if name == "xgboost" else None)
    if name in ("elastic_net_logistic", "spline_logistic"):
        return _Imputed(seed, hyper, splines=name == "spline_logistic").fit(X, y)
    if name in ("random_forest", "hist_gradient_boosting", "ebm"):
        return _Sklearn(name, seed, hyper).fit(X, y)
    raise ValueError(f"unknown model {name!r}; one of {tuple(MODEL_SPECS)}")


@traced
def tune(name: str, X: pd.DataFrame, y, groups, folds: int = 5, seed: int = 42) -> tuple[dict, float]:
    """(the grid point with the best mean validation AUC, that AUC), over `folds` grouped folds (cv_splits), as
    tooth_loss_model.tune_xgboost does; XGBoost goes through it unchanged. An empty grid scores its one point."""
    y = np.asarray(y, dtype=int)
    if name == "xgboost":
        best = tlm.tune_xgboost(X, y, groups, folds, seed)
        cv = best.pop("cv_auc")
        best.pop("cv_folds_used")
        return best, cv
    cv = [(tr, va) for tr, va in tlm.cv_splits(y, groups, folds, seed)
          if len(np.unique(y[tr])) == 2 and len(np.unique(y[va])) == 2]
    if not cv:
        raise ValueError(f"cv_folds {folds}: no fold has both outcomes on each side")
    grid = GRIDS[name]
    keys = list(grid)
    best, best_auc = None, -1.0
    for values in itertools.product(*(grid[k] for k in keys)):
        hyper = dict(zip(keys, values))
        aucs = [tlm.auc(y[va], fit_model(name, X.iloc[tr], y[tr], seed, hyper).predict(X.iloc[va])) for tr, va in cv]
        if np.mean(aucs) > best_auc:
            best, best_auc = hyper, float(np.mean(aucs))
    return best, best_auc


# ---------- paired comparison

def _midrank_components(y, p) -> tuple[float, np.ndarray, np.ndarray]:
    from scipy.stats import rankdata
    pos, neg = p[y == 1], p[y == 0]
    m, n = len(pos), len(neg)
    r_all = rankdata(np.concatenate([pos, neg]))
    r_pos, r_neg = rankdata(pos), rankdata(neg)
    v10 = (r_all[:m] - r_pos) / n                               # each positive: share of negatives below it
    v01 = 1 - (r_all[m:] - r_neg) / m                           # each negative: share of positives above it
    return float(v10.mean()), v10, v01


@traced
def delong(y, p_a, p_b) -> tuple[float, float]:
    """(AUC of a minus AUC of b, two-sided p) by DeLong's paired test on the same teeth. It treats teeth as
    independent; the patient bootstrap (paired_difference) is the interval this page reads."""
    y = np.asarray(y, float)
    a, va10, va01 = _midrank_components(y, np.asarray(p_a, float))
    b, vb10, vb01 = _midrank_components(y, np.asarray(p_b, float))
    d = a - b
    if np.allclose(p_a, p_b):
        return 0.0, 1.0
    s10, s01 = np.cov(np.vstack([va10, vb10])), np.cov(np.vstack([va01, vb01]))
    var = (s10[0, 0] + s10[1, 1] - 2 * s10[0, 1]) / len(va10) + (s01[0, 0] + s01[1, 1] - 2 * s01[0, 1]) / len(va01)
    if var <= 0:
        return float(d), 1.0
    return float(d), float(2 * norm.sf(abs(d) / np.sqrt(var)))


def _point(y, p) -> np.ndarray:
    lp = tlm._logit(p)
    return np.array([tlm._auc(y, p), float(np.mean((p - y) ** 2)), tlm._newton(y, lp, slope=True)[1],
                     tlm._newton(y, lp, slope=False)[0]])


def _boot_matrix(y, p, idxs) -> np.ndarray:
    return np.array([_point(y[i], p[i]) for i in idxs]) if idxs else np.empty((0, 4))


def _ci(col) -> tuple[float, float]:
    col = col[~np.isnan(col)]
    return tuple(float(v) for v in np.percentile(col, [2.5, 97.5])) if len(col) else (np.nan, np.nan)


@traced
def paired_difference(y, p_b, p_a, patients, n_boot: int = 1000, seed: int = 42) -> dict:
    """b minus a (AUC and Brier) on the same teeth, with 95% intervals from the same patient bootstrap resamples."""
    y, p_a, p_b = (np.asarray(v, float) for v in (y, p_a, p_b))
    idxs = list(tlm.patient_bootstrap(patients, n_boot, seed))
    diff = _boot_matrix(y, p_b, idxs) - _boot_matrix(y, p_a, idxs)
    point = _point(y, p_b) - _point(y, p_a)
    (alo, ahi), (blo, bhi) = _ci(diff[:, 0]), _ci(diff[:, 1])
    return {"auc_diff_ratio": float(point[0]), "auc_diff_lo_ratio": alo, "auc_diff_hi_ratio": ahi,
            "brier_diff_ratio": float(point[1]), "brier_diff_lo_ratio": blo, "brier_diff_hi_ratio": bhi}


# ---------- one extract

@traced
def prepare(x: dict, truth: pd.DataFrame, params: tlm.ModelParams = tlm.DEFAULT) -> dict:
    """The teeth, the patient split and the evaluation sets exactly as tooth_loss_model.run builds them."""
    tlm.check_params(params)
    teeth = tl.tooth_table(x)
    teeth["age_at_loss_num"] = tlm._age_at_loss(teeth, x)
    if params.start_date is not None:
        teeth = tlm.with_first_exam_date(teeth, x)
    el = tlm.eligible(teeth, params).reset_index(drop=True)
    true = el.merge(truth, on=["patient_id", "tooth_num"], how="left")["true_reason_code"]
    if params.split_unit != "person":
        raise ValueError("tooth_loss_drivers compares models on the plan's patient split only")
    test_pats = tlm.split_patients(tlm.label_set(el, "completed_planned", params.planned_window_days),
                                   params.test_share, params.seed)
    in_test = el["patient_id"].isin(test_pats).to_numpy()
    status = el["tooth_status_code"]
    masks = {"held_out": (status.isin(tlm.LABEL_SETS["completed"]) & el["is_perio_loss"].notna()).to_numpy() & in_test,
             "missing_at_entry": ((status == "missing_at_entry") & true.notna()).to_numpy()}
    ys = {"held_out": el["is_perio_loss"].astype("Float64").fillna(0).to_numpy(float),
          "missing_at_entry": (true == "perio").to_numpy(float)}
    return {"el": el, "in_test": in_test, "masks": masks, "ys": ys, "params": params}


def _fits(prep: dict, models):
    """Yields (label set, feature set, model, hyper, cv AUC, fitted, X, train mask, y_train)."""
    el, params = prep["el"], prep["params"]
    for ls in tlm.LABEL_SETS:
        labelled = el.index.isin(tlm.label_set(el, ls, params.planned_window_days).index)
        train = labelled & ~prep["in_test"]
        y_train = el.loc[train, "is_perio_loss"].astype(bool).to_numpy(int)
        groups = el.loc[train, "patient_id"].to_numpy()
        for fs in tlm.FEATURE_SETS:
            X = tlm.design_matrix(el, fs)
            for model in models:
                if model == "logistic":
                    hyper, cv = {}, np.nan                     # the plan fixes it; run() doesn't cross-validate it
                elif params.cv_folds:
                    hyper, cv = tune(model, X[train], y_train, groups, params.cv_folds, params.seed)
                else:
                    hyper, cv = default_hyper(model), np.nan
                fitted = fit_model(model, X[train], y_train, params.seed, hyper)
                yield ls, fs, model, hyper, cv, fitted, X, train, y_train


def _eval_sets(fs: str):
    return [ev for ev in tlm.EVAL_SETS if not (fs == "own" and ev == "missing_at_entry")]   # no own measures there


def _shap_groups(fitted, X: pd.DataFrame) -> dict[str, float]:
    phi, names = fitted.shap(X)
    phi = pd.DataFrame(phi[:, :len(names)], columns=names)
    return phi.T.groupby(feature_group).sum().T.abs().mean().to_dict()


def _permutation(fitted, X: pd.DataFrame, y, base_auc: float, seed: int) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    out = {}
    for g in dict.fromkeys(feature_group(c) for c in X.columns):
        cols = [c for c in X.columns if feature_group(c) == g]
        drops = []
        for _ in range(N_PERMUTE):
            Xp = X.copy()
            Xp[cols] = X[cols].to_numpy()[rng.permutation(len(X))]
            drops.append(base_auc - tlm.auc(y, fitted.predict(Xp)))
        out[g] = float(np.mean(drops))
    return out


@traced
def compare(x: dict, truth: pd.DataFrame, params: tlm.ModelParams = tlm.DEFAULT, models=None,
            generator_seed: int = 42, drivers: bool = True) -> dict:
    """Fit every model on one extract and score it on the plan's held-out teeth and the teeth missing at entry.
    Returns TABLES (drivers=False leaves the driver table empty, for the stability seeds)."""
    models = tuple(models or available_models())
    prep = prepare(x, truth, params)
    preds, meta, driver_rows = {}, {}, []
    for ls, fs, model, hyper, cv, fitted, X, train, y_train in _fits(prep, models):
        p = fitted.predict(X)
        meta[(ls, fs, model)] = {"hyperparameter_text": json.dumps(hyper, sort_keys=True), "cv_auc_ratio": cv}
        for ev in _eval_sets(fs):
            preds[(ls, fs, ev, model)] = p[prep["masks"][ev]]
        if not drivers:
            continue
        m = prep["masks"]["held_out"]
        y_held = prep["ys"]["held_out"][m]
        base = tlm.auc(y_held, p[m])
        shap = _shap_groups(fitted, X[m]) if model in PRESPECIFIED else {}
        perm = _permutation(fitted, X[m], y_held, base, params.seed)
        for g, drop in perm.items():
            row = {"label_set_code": ls, "feature_set_code": fs, "model_code": model,
                   "is_prespecified": MODEL_SPECS[model]["is_prespecified"], "feature_group_code": g,
                   "feature_text": FEATURE_TEXT.get(g, g), "mean_abs_shap_coef": shap.get(g, np.nan),
                   "permutation_auc_drop_ratio": drop, "refit_auc_without_ratio": np.nan,
                   "refit_auc_drop_ratio": np.nan}
            if fs == DRIVER_FEATURE_SET:
                keep = [c for c in X.columns if feature_group(c) != g]
                refit = fit_model(model, X.loc[train, keep], y_train, params.seed, hyper)
                row["refit_auc_without_ratio"] = tlm.auc(y_held, refit.predict(X.loc[m, keep]))
                row["refit_auc_drop_ratio"] = base - row["refit_auc_without_ratio"]
            driver_rows.append(row)
    rank, contrast = _score_tables(prep, preds, meta, models, params, generator_seed)
    drv = pd.DataFrame(driver_rows)
    if len(drv):
        drv["driver_rank_count"] = drv.groupby(["label_set_code", "feature_set_code", "model_code"])[
            "permutation_auc_drop_ratio"].rank(ascending=False, method="first").astype(int)
    return {"tooth_loss_model_rank": rank, "tooth_loss_model_contrast": contrast, "tooth_loss_driver": drv,
            "n_boot": params.n_boot}


def _score_tables(prep, preds, meta, models, params, generator_seed):
    el = prep["el"]
    rank_rows, con_rows = [], []
    for ls in tlm.LABEL_SETS:
        for fs in tlm.FEATURE_SETS:
            for ev in _eval_sets(fs):
                m = prep["masks"][ev]
                y, pats = prep["ys"][ev][m], el.loc[m, "patient_id"].to_numpy()
                idxs = list(tlm.patient_bootstrap(pats, params.n_boot, params.seed))
                boots = {mod: _boot_matrix(y, preds[(ls, fs, ev, mod)], idxs) for mod in models}
                points = {mod: _point(y, preds[(ls, fs, ev, mod)]) for mod in models}
                order = sorted(models, key=lambda mod: -points[mod][0])
                ref = next(mod for mod in order if mod in PRESPECIFIED)
                for pos, mod in enumerate(order, 1):
                    ci = [_ci(boots[mod][:, k]) for k in range(4)]
                    pt = points[mod]
                    rank_rows.append({
                        "label_set_code": ls, "feature_set_code": fs, "eval_set_code": ev,
                        "rank_position_count": pos, "model_code": mod, "model_text": MODEL_SPECS[mod]["model_text"],
                        "model_family_code": MODEL_SPECS[mod]["family_code"],
                        "is_prespecified": MODEL_SPECS[mod]["is_prespecified"], **meta[(ls, fs, mod)],
                        "tooth_count": int(m.sum()), "patient_count": len(np.unique(pats)),
                        "perio_tooth_count": int(y.sum()),
                        "auc_ratio": pt[0], "auc_lo_ratio": ci[0][0], "auc_hi_ratio": ci[0][1],
                        "brier_ratio": pt[1], "brier_lo_ratio": ci[1][0], "brier_hi_ratio": ci[1][1],
                        "calibration_slope_coef": pt[2], "calibration_slope_lo_coef": ci[2][0],
                        "calibration_slope_hi_coef": ci[2][1], "calibration_intercept_coef": pt[3],
                        "calibration_intercept_lo_coef": ci[3][0], "calibration_intercept_hi_coef": ci[3][1],
                        "generator_seed_num": generator_seed})
                    diff = boots[mod] - boots[ref]
                    (alo, ahi), (blo, bhi) = _ci(diff[:, 0]), _ci(diff[:, 1])
                    if mod == ref:
                        alo = ahi = blo = bhi = 0.0
                    _, p_dl = delong(y, preds[(ls, fs, ev, mod)], preds[(ls, fs, ev, ref)])
                    con_rows.append({
                        "label_set_code": ls, "feature_set_code": fs, "eval_set_code": ev, "model_code": mod,
                        "is_prespecified": MODEL_SPECS[mod]["is_prespecified"], "reference_model_code": ref,
                        "auc_diff_ratio": pt[0] - points[ref][0], "auc_diff_lo_ratio": alo, "auc_diff_hi_ratio": ahi,
                        "delong_p_ratio": p_dl, "brier_diff_ratio": pt[1] - points[ref][1],
                        "brier_diff_lo_ratio": blo, "brier_diff_hi_ratio": bhi,
                        "is_better_beyond_ci": bool(alo > 0), "is_worse_beyond_ci": bool(ahi < 0),
                        "is_brier_better_beyond_ci": bool(bhi < 0)})
    return pd.DataFrame(rank_rows), pd.DataFrame(con_rows)


# ---------- the run: main seed and stability seeds

@traced
def extract(n_patients: int, seed: int) -> tuple[dict, pd.DataFrame]:
    """The synthetic Open Dental extract, cleaned as silver, as scripts/51_tooth_loss_model.py builds it."""
    from . import open_dental
    tables, truth, readings = open_dental.build_with_readings(open_dental.Params(n_patients=n_patients), seed)
    return {**open_dental.clean(tables), "radiograph_bone_level": readings}, truth


@traced
def build(n_patients: int = 6000, seed: int = 42, stability_seeds: int = 5, n_boot: int = 1000,
          models=None) -> dict:
    """compare() on the main generator seed with bootstrap intervals and drivers, then point scores (shared
    predictors, no drivers) on the further stability seeds, seed + 1 onwards, as scripts/51 does."""
    x, truth = extract(n_patients, seed)
    built = compare(x, truth, tlm.ModelParams(n_boot=n_boot), models, generator_seed=seed)
    seeds = [built["tooth_loss_model_rank"]]
    for k in range(1, max(1, stability_seeds)):
        xk, tk = extract(n_patients, seed + k)
        seeds.append(compare(xk, tk, tlm.ModelParams(n_boot=0), models, generator_seed=seed + k,
                             drivers=False)["tooth_loss_model_rank"])
    s = pd.concat(seeds, ignore_index=True)
    s = s[s.feature_set_code.eq("shared")]
    built[STABILITY] = s[["generator_seed_num", "label_set_code", "feature_set_code", "eval_set_code", "model_code",
                          "is_prespecified", "tooth_count", "perio_tooth_count", "auc_ratio", "brier_ratio",
                          "calibration_slope_coef"]].reset_index(drop=True)
    built["n_patients"], built["seed"] = n_patients, seed
    return built


# ---------- the page

_LS = {"completed": "completed extractions", "completed_planned": "completed + planned extractions"}
_FS = {"shared": "shared predictors (the applied model)", "own": "own measures added"}
_EV = {"held_out": "held-out extractions", "missing_at_entry": "teeth missing at entry (synthetic answer key)"}


def _ci_text(r, k: str, fmt: str = ".2f") -> str:
    return f"{getattr(r, k):{fmt}} ({getattr(r, k.replace('_coef', '_lo_coef').replace('_ratio', '_lo_ratio')):{fmt}}" \
           f" to {getattr(r, k.replace('_coef', '_hi_coef').replace('_ratio', '_hi_ratio')):{fmt}})"


def _name(model: str) -> str:
    return f"`{model}`" + ("" if MODEL_SPECS[model]["is_prespecified"] else " *(post hoc)*")


def _verdict(b: dict) -> dict:
    """The facts the plain-words summary and the recommendation are written from."""
    con, rank = b["tooth_loss_model_contrast"], b["tooth_loss_model_rank"]
    cand = con[~con.is_prespecified]
    held = cand[cand.eval_set_code.eq("held_out")]
    entry = cand[cand.eval_set_code.eq("missing_at_entry")]
    main = rank[rank.label_set_code.eq("completed") & rank.feature_set_code.eq("shared")
                & rank.eval_set_code.eq("held_out")].set_index("model_code")
    return {"held_better": held[held.is_better_beyond_ci], "entry_better": entry[entry.is_better_beyond_ci],
            "held_worse": held[held.is_worse_beyond_ci], "brier_better": held[held.is_brier_better_beyond_ci],
            "best_gain": held.auc_diff_ratio.max(), "worst_gain": held.auc_diff_ratio.min(),
            "entry_best_gain": entry.auc_diff_ratio.max() if len(entry) else np.nan,
            "main": main, "cand": cand, "n_cand": cand.model_code.nunique(), "n_cells": len(held)}


def _seed_lines(st: pd.DataFrame) -> list[str]:
    if st is None or not len(st):
        return ["The stability seeds were not run for this page."]
    out = ["Each model refitted (tuning included) on further synthetic extracts made with other generator seeds, shared "
           "predictors, point estimates: the spread is how much the answer moves when the data are drawn again.", "",
           "| Label set | Set of teeth | Model | AUC, lowest to highest | Seeds where it beats the best plan model "
           "| Brier, lowest to highest |", "|---|---|---|---|---:|---|"]
    st = st.copy()
    best = st[st.is_prespecified].groupby(["generator_seed_num", "label_set_code", "eval_set_code"]).auc_ratio.max()
    st["best_pre"] = [best.loc[(r.generator_seed_num, r.label_set_code, r.eval_set_code)] for r in st.itertuples()]
    n_seeds = st.generator_seed_num.nunique()
    for (ls, ev, mod), g in st.groupby(["label_set_code", "eval_set_code", "model_code"], sort=False):
        wins = "" if mod in PRESPECIFIED else f"{int((g.auc_ratio > g.best_pre).sum())} of {n_seeds}"
        out.append(f"| {_LS[ls]} | {_EV[ev]} | {_name(mod)} | {g.auc_ratio.min():.3f} to {g.auc_ratio.max():.3f} | "
                   f"{wins} | {g.brier_ratio.min():.3f} to {g.brier_ratio.max():.3f} |")
    return out


def _seed_wins(st, model: str, ls: str, ev: str) -> tuple[int, int]:
    """(seeds where `model` has a higher AUC than the best plan model, seeds) on one label set and set of teeth."""
    if st is None or not len(st):
        return 0, 0
    g = st[st.label_set_code.eq(ls) & st.eval_set_code.eq(ev)]
    best = g[g.is_prespecified].groupby("generator_seed_num").auc_ratio.max()
    m = g[g.model_code.eq(model)].set_index("generator_seed_num").auc_ratio
    return int((m > best.reindex(m.index)).sum()), len(m)


def _top_drivers(drv: pd.DataFrame, k: int = 3) -> str:
    mean = drv.groupby("feature_group_code").permutation_auc_drop_ratio.mean().sort_values(ascending=False)
    names = [FEATURE_TEXT.get(f, f).split(" (")[0] for f in mean.index[:k]]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _first_everywhere(drv: pd.DataFrame) -> str:
    first = drv[drv.driver_rank_count.eq(1)].feature_group_code.unique()
    return f", and {FEATURE_TEXT.get(first[0], first[0]).split(' (')[0]} is first in every one" if len(first) == 1 else ""


def _entry_bullet(v: dict, st) -> list[str]:
    e = v["entry_better"]
    if not len(e):
        return ["- **On the teeth missing at entry** (the applied set, scored against the synthetic answer key) no "
                "candidate beats the plan's best model beyond the interval either."]
    parts = []
    for mod, g in e.groupby("model_code", sort=False):
        wins = [(ls, *_seed_wins(st, mod, ls, "missing_at_entry")) for ls in g.label_set_code]
        parts.append(f"`{mod}` (AUC {g.auc_diff_ratio.min():+.3f} to {g.auc_diff_ratio.max():+.3f}; higher in "
                     + ", ".join(f"{w} of {n} generator seeds on {_LS[ls]}" for ls, w, n in wins) + ")")
    return ["- **On the teeth missing at entry** (the applied set, scored against the synthetic answer key, which a "
            "real extract doesn't have) some candidates do beat the plan's best model beyond the interval: "
            + "; ".join(parts) + ". Every model, plan or candidate, is badly calibrated there (section 1)."]


def _short_verdict(v: dict) -> str:
    if len(v["held_better"]):
        return "some candidates are worth a closer look; adding one needs an analysis-plan amendment."
    if len(v["entry_better"]):
        return ("keep the plan's two models; at most, add the best candidate on the applied set as a sensitivity "
                "analysis, by an analysis-plan amendment.")
    return "keep the plan's two models; none of the others earns a place."


@traced
def read_built(out_dir=None, n_boot: int = tlm.DEFAULT.n_boot) -> dict:
    """The tables as written (CSV, 6 significant figures): the page is always drawn from these, so it can be redrawn
    from the committed files without refitting."""
    out_dir = out_dir or OUT_DIR
    return {name: pd.read_csv(out_dir / f"{name}.csv") for name in ALL_TABLES} | {"n_boot": n_boot}


@traced
def details_markdown(b: dict) -> str:
    rank, con, drv = b["tooth_loss_model_rank"], b["tooth_loss_model_contrast"], b["tooth_loss_driver"]
    st = b.get(STABILITY)
    v = _verdict(b)
    main = v["main"]
    ref = con[con.label_set_code.eq("completed") & con.feature_set_code.eq("shared")
              & con.eval_set_code.eq("held_out")].reference_model_code.iloc[0]
    n_boot = b.get("n_boot", tlm.DEFAULT.n_boot)
    seeds = st.generator_seed_num.nunique() if st is not None and len(st) else 1
    r0 = main.iloc[0]
    out = ["# Should the tooth-loss model use another kind of model?", "",
           "<!-- generated by python/scripts/78_tooth_loss_drivers.py; do not edit -->", "",
           "> **SYNTHETIC.** Every number is from the synthetic Open Dental extract made in this repo, scored against "
           "its synthetic answer key: agreement with it, not a finding about any practice or patient. The plan's two "
           "models (logistic regression and XGBoost) are the pre-specified ones "
           "([analysis plan](../specs/029-tooth-loss/analysis_plan.md), s. 8). **Every other model here is post hoc, "
           "outside the analysis plan**: tried after the plan's results were known, to answer \"should we look at "
           "other models for tooth loss?\" (spec 042 US4, #867). Generated by `python/scripts/78_tooth_loss_drivers.py`"
           "; tables in `data/datasets/model_drivers/tooth_loss_*.csv` and, on Databricks, "
           "`health_transformation_lab.gold_opendental_perio.tooth_loss_*` (every table and column commented) with one MLflow "
           "run per model in `/Shared/tooth-loss-model-comparison`, loaded by "
           "`python/scripts/79_load_tooth_loss_drivers.py`.", "",
           "## In plain words", "",
           f"The tooth-loss model ([tooth_loss.md](tooth_loss.md)) gives each missing tooth a probability that it was "
           f"lost to gum disease (periodontitis). We fitted {v['n_cand']} other kinds of model that suit a small table "
           f"of numbers, on exactly the same teeth, with the same predictors and the same held-out patients, and "
           f"tuned them the same way as XGBoost (5-fold cross-validation on the training teeth, folds by patient).",
           ""]
    if len(v["held_better"]):
        names = ", ".join(sorted(set(v["held_better"].model_code)))
        out.append(f"- **Some candidates do better than the plan's best model beyond the 95% interval** on the "
                   f"held-out teeth: {names} (see section 2).")
    else:
        out.append(f"- **No candidate beats the plan's models on the held-out extractions.** Across both label sets and "
                   f"both predictor sets ({v['n_cells']} comparisons), every candidate's AUC is within "
                   f"{v['best_gain']:+.3f} to {v['worst_gain']:+.3f} of the best pre-specified model's, and every 95% "
                   f"interval of the paired difference includes zero or lies below it.")
    out += [f"- **The main result** (completed extractions, shared predictors, {int(r0.tooth_count)} held-out teeth of "
            f"{int(r0.patient_count)} patients, {int(r0.perio_tooth_count)} periodontal): the plan's best is "
            f"`{ref}` with AUC {_ci_text(main.loc[ref], 'auc_ratio')}; the best candidate is "
            f"`{main[~main.is_prespecified].auc_ratio.idxmax()}` with "
            f"{_ci_text(main[~main.is_prespecified].sort_values('auc_ratio').iloc[-1], 'auc_ratio')}.",
            *_entry_bullet(v, st),
            f"- **The models lean on the same predictors**: {_top_drivers(drv)} lose the most AUC when shuffled, "
            f"averaged over the {drv.model_code.nunique()} models{_first_everywhere(drv)} (section 3).",
            f"- **Recommendation** (last section): {_short_verdict(v)}", "",
            "How it was done: the plan's two models are fitted exactly as `tooth_loss_model.run` fits them, so their "
            "scores are the pre-specified results. Intervals are 95% from "
            f"{n_boot:,} bootstrap resamples of patients (analysis plan s. 10); a difference against the best "
            "pre-specified model is computed on the same resamples, so it is paired. DeLong's p is given as well; it "
            "treats teeth as independent, so the patient bootstrap is the one to read. "
            "Calibration slope 1 is perfect; below 1, the probabilities are too extreme (too close to 0 and 1); above 1, too "
            "timid (too close to the average).", "",
            "## 1. The ranking", ""]
    for (ls, fs, ev), g in rank.groupby(["label_set_code", "feature_set_code", "eval_set_code"], sort=False):
        r = g.iloc[0]
        c = con[con.label_set_code.eq(ls) & con.feature_set_code.eq(fs) & con.eval_set_code.eq(ev)].set_index(
            "model_code")
        out += [f"### {_LS[ls].capitalize()}, {_FS[fs]}, {_EV[ev]}", "",
                f"{int(r.tooth_count):,} teeth of {int(r.patient_count):,} patients, {int(r.perio_tooth_count):,} "
                f"periodontal. Paired differences are against `{c.reference_model_code.iloc[0]}`.", "",
                "| # | Model | AUC (95% CI) | Brier (95% CI) | Calibration slope (95% CI) | AUC difference (95% CI) | "
                "DeLong p | Brier difference (95% CI) |", "|---:|---|---|---|---|---|---|---|"]
        for x in g.itertuples():
            d = c.loc[x.model_code]
            ref_row = d.auc_diff_ratio == 0 and d.reference_model_code == x.model_code
            diff = "reference" if ref_row else (
                f"{d.auc_diff_ratio:+.3f} ({d.auc_diff_lo_ratio:+.3f} to {d.auc_diff_hi_ratio:+.3f})")
            bd = "" if ref_row else (
                f"{d.brier_diff_ratio:+.4f} ({d.brier_diff_lo_ratio:+.4f} to {d.brier_diff_hi_ratio:+.4f})")
            p = "" if ref_row else ("< 0.001" if d.delong_p_ratio < 0.001 else f"{d.delong_p_ratio:.2f}")
            out.append(f"| {x.rank_position_count} | {_name(x.model_code)} | {_ci_text(x, 'auc_ratio')} | "
                       f"{_ci_text(x, 'brier_ratio', '.3f')} | {_ci_text(x, 'calibration_slope_coef')} | {diff} | "
                       f"{p} | {bd} |")
        out.append("")
    out += ["## 2. Does any candidate beat the plan's models beyond the interval?", "",
            "A candidate beats the best pre-specified model when the 95% interval of its paired AUC difference lies "
            "above zero (or its Brier difference below zero).", "",
            "| Set of teeth | Comparisons | AUC better beyond the interval | AUC worse beyond the interval | Brier "
            "better beyond the interval |", "|---|---:|---|---|---|"]
    for ev, g in v["cand"].groupby("eval_set_code", sort=False):
        def names(mask, g=g):
            sel = g[mask]
            return ", ".join(f"`{r.model_code}` ({_LS[r.label_set_code]}, {r.feature_set_code})"
                             for r in sel.itertuples()) or "none"
        out.append(f"| {_EV[ev]} | {len(g)} | {names(g.is_better_beyond_ci)} | {names(g.is_worse_beyond_ci)} | "
                   f"{names(g.is_brier_better_beyond_ci)} |")
    out += ["", "### Across generator seeds", "", *_seed_lines(st), "",
            "## 3. What drives the prediction", "",
            "Three measures, on the held-out teeth: **mean |SHAP|** (the average size of a predictor's push on the "
            "log-odds, exact, for the plan's two models); **permutation**: the AUC lost when that predictor is "
            f"shuffled ({N_PERMUTE} shuffles, every model); **refit**: the AUC lost when the model is fitted again "
            "without it (shared predictors only, where predictors that carry the same information can stand in "
            "for each other, so it is smaller).", ""]
    for ls in tlm.LABEL_SETS:
        for fs in tlm.FEATURE_SETS:
            g = drv[drv.label_set_code.eq(ls) & drv.feature_set_code.eq(fs)]
            if not len(g):
                continue
            models = list(dict.fromkeys(g.model_code))
            piv = g.pivot(index="feature_group_code", columns="model_code", values="permutation_auc_drop_ratio")
            order = piv.mean(axis=1).sort_values(ascending=False).index
            sh = g[g.model_code.isin(PRESPECIFIED)].pivot(index="feature_group_code", columns="model_code",
                                                          values="mean_abs_shap_coef")
            rf = g[g.model_code.eq(ref)].set_index("feature_group_code").refit_auc_drop_ratio
            out += [f"**{_LS[ls].capitalize()}, {_FS[fs]}**: AUC lost when shuffled, per model; then the plan's "
                    "SHAP and the refit drop for the reference model.", "",
                    "| Predictor | " + " | ".join(_name(m) for m in models) + " | mean \\|SHAP\\| logistic / "
                    f"XGBoost | refit drop (`{ref}`) |",
                    "|---|" + "---:|" * len(models) + "---|---:|"]
            for f in order:
                shap = " / ".join(f"{sh.loc[f, m]:.2f}" if m in sh.columns else "" for m in PRESPECIFIED)
                refit = f"{rf.loc[f]:.3f}" if f in rf.index and rf.loc[f] == rf.loc[f] else ""
                out.append(f"| {FEATURE_TEXT.get(f, f)} | " + " | ".join(f"{piv.loc[f, m]:.3f}" for m in models)
                           + f" | {shap} | {refit} |")
            out.append("")
    out += _recommendation(b, v, ref, seeds)
    return "\n".join(out) + "\n"


def _recommendation(b: dict, v: dict, ref: str, seeds: int) -> list[str]:
    main = v["main"]
    st = b.get(STABILITY)
    rank = b["tooth_loss_model_rank"]
    calib = main.calibration_slope_coef
    out = ["## Recommendation", ""]
    if len(v["held_better"]):
        names = ", ".join(sorted(set(v["held_better"].model_code)))
        out += [f"**Worth a closer look: {names}** beat the plan's best model beyond the 95% interval on the held-out "
                f"teeth in some comparisons (section 2). Read that with the seed spread and the calibration slopes "
                f"before acting.", ""]
    else:
        out += [f"**Keep the plan's two models; don't replace them.** None of the {v['n_cand']} post-hoc candidates "
                f"beats the plan's best model (`{ref}` in the main comparison) beyond the 95% interval on the held-out "
                f"extractions, the teeth with a recorded reason, in any of the {v['n_cells']} comparisons (both label "
                f"sets, both predictor sets); the largest gain is {v['best_gain']:+.3f} AUC. The plan's models are "
                f"also the easiest to read and check: logistic regression has one coefficient per predictor, and both "
                f"give exact SHAP. Because a phenotype input sums the probabilities (the expected count of teeth lost "
                f"to periodontitis), calibration matters as much as ranking: in the main comparison the plan's slopes "
                f"are " + " and ".join(f"{calib.loc[m]:.2f} (`{m}`)" for m in PRESPECIFIED if m in calib.index)
                + f", against {calib[~main.is_prespecified].min():.2f} to {calib[~main.is_prespecified].max():.2f} "
                  f"for the candidates.", ""]
    e = v["entry_better"]
    if len(e):
        best = e.sort_values("auc_diff_ratio").iloc[-1]
        er = rank[rank.eval_set_code.eq("missing_at_entry") & rank.label_set_code.eq(best.label_set_code)
                  & rank.feature_set_code.eq(best.feature_set_code)].set_index("model_code")
        wins = _seed_wins(st, best.model_code, best.label_set_code, "missing_at_entry")
        out += [f"**The one open question is the applied set.** On the teeth missing at entry `{best.model_code}` "
                f"beats `{best.reference_model_code}` by {best.auc_diff_ratio:+.3f} AUC "
                f"({best.auc_diff_lo_ratio:+.3f} to {best.auc_diff_hi_ratio:+.3f}; {_LS[best.label_set_code]}), "
                f"higher on {wins[0]} of {wins[1]} generator seeds, with a lower Brier score. That set is the one the "
                f"model is used on, so it matters; but it is scored against the synthetic answer key, which a real "
                f"extract doesn't have (analysis plan s. 9), the gain is small beside the gap between the two sets "
                f"(AUC {er.auc_ratio.max():.2f} at best there, against about "
                f"{main.auc_ratio.max():.2f} on the held-out extractions), and every model is badly calibrated there "
                f"(slopes {er.calibration_slope_coef.min():.2f} to {er.calibration_slope_coef.max():.2f}). If the study "
                f"lead wants it, the defensible step is to add `{best.model_code}` as a **sensitivity analysis** "
                f"beside the plan's models, not in place of them.", ""]
    out += ["**Where effort would pay more:** the gap between the held-out extractions and the teeth missing at entry "
            "is large for every kind of model, so it comes mostly from the predictors and the label (trained on "
            "extractions with a recorded reason, applied to teeth lost for unrecorded reasons), not from the model. "
            f"Section 3 shows where the signal is: {_top_drivers(b['tooth_loss_driver'])}.", "",
            "**Any change needs an analysis-plan amendment first.** The plan (s. 8) fixes logistic regression and "
            "XGBoost. Adding a model, even as a sensitivity analysis, is a dated row in the plan's change log with its "
            "reason, made before that model's results are used as anything but exploration. These post-hoc results "
            "are a reason to consider one, not a pre-specified result. Nothing in the plan or in "
            "`tooth_loss_model.py` is changed by this page.", ""]
    return out


# ---------- Unity Catalog comments

_C = {"label_set_code": "completed (completed extractions) or completed_planned (plus planned extractions whose "
                        "tooth went missing within 548 days); analysis plan s. 4",
      "feature_set_code": "shared (predictors every missing tooth has: the applied model) or own (plus the tooth's "
                          "own last measures); analysis plan s. 5",
      "eval_set_code": "held_out (completed extractions of the held-out patients, recorded label) or "
                       "missing_at_entry (teeth missing at the first exam, scored against the synthetic answer key)",
      "model_code": "logistic and xgboost (pre-specified), or a post-hoc candidate: elastic_net_logistic, "
                    "spline_logistic, random_forest, hist_gradient_boosting, ebm",
      "is_prespecified": "True for the analysis plan's two models (s. 8); False for the post-hoc candidates, outside "
                         "the plan",
      "generator_seed_num": "The synthetic extract's generator seed",
      "tooth_count": "Teeth scored", "patient_count": "Patients those teeth belong to",
      "perio_tooth_count": "Of them, lost to periodontitis (recorded diagnosis, or the answer key for missing_at_entry)",
      "auc_ratio": "Area under the ROC curve", "brier_ratio": "Brier score: mean squared difference between "
      "probability and outcome (lower is better)",
      "calibration_slope_coef": "Calibration slope: logistic regression of the outcome on logit(p); 1 is perfect"}
_CI = {f"{k}_{b}_{s}": f"{'Lower' if b == 'lo' else 'Upper'} 95% bound of {k}_{s} (bootstrap of patients)"
       for k, s in (("auc", "ratio"), ("brier", "ratio"), ("calibration_slope", "coef"),
                    ("calibration_intercept", "coef")) for b in ("lo", "hi")}
COMMENTS = {
    "tooth_loss_model_rank": (
        "Tooth loss (spec 029) in the multi-model format (spec 042 US4): one row per label set, predictor set, set of "
        "teeth and model, ranked by AUC on the same teeth, with patient-bootstrap 95% intervals. SYNTHETIC extract; "
        "models with is_prespecified false are post hoc, outside the analysis plan.",
        _C | _CI | {"rank_position_count": "Position by AUC within the label set, predictor set and set of teeth "
                                           "(1 = highest)",
                    "model_text": "The model in words", "model_family_code": "linear, additive, bagged_trees or "
                                                                            "boosted_trees",
                    "hyperparameter_text": "The settings used (JSON): the tuned grid point, or {} for the plan's "
                                           "fixed logistic regression",
                    "cv_auc_ratio": "Mean validation AUC of those settings over the 5 grouped folds of the "
                                    "training teeth; NULL for the plan's logistic regression (not tuned)",
                    "calibration_intercept_coef": "Calibration in the large: intercept with logit(p) as offset; 0 is "
                                                  "perfect"}),
    "tooth_loss_model_contrast": (
        "Tooth loss (spec 029, spec 042 US4): each model paired against the best pre-specified model on the same "
        "teeth and the same patient-bootstrap resamples: AUC and Brier differences with 95% intervals, and DeLong's "
        "p. SYNTHETIC extract.",
        _C | {"reference_model_code": "The pre-specified model with the higher AUC on these teeth",
              "auc_diff_ratio": "AUC of the model minus AUC of the reference",
              "auc_diff_lo_ratio": "Lower 95% bound of auc_diff_ratio (paired patient bootstrap)",
              "auc_diff_hi_ratio": "Upper 95% bound of auc_diff_ratio",
              "delong_p_ratio": "Two-sided p of DeLong's paired AUC test (treats teeth as independent)",
              "brier_diff_ratio": "Brier of the model minus Brier of the reference (negative is better)",
              "brier_diff_lo_ratio": "Lower 95% bound of brier_diff_ratio", "brier_diff_hi_ratio":
              "Upper 95% bound of brier_diff_ratio",
              "is_better_beyond_ci": "True when the whole AUC-difference interval is above zero",
              "is_worse_beyond_ci": "True when the whole AUC-difference interval is below zero",
              "is_brier_better_beyond_ci": "True when the whole Brier-difference interval is below zero"}),
    "tooth_loss_driver": (
        "Tooth loss (spec 029, spec 042 US4): what drives each model, per predictor, on the held-out teeth: mean "
        "|SHAP| (plan models), permutation AUC drop (every model), refit-without AUC drop (shared predictors). "
        "SYNTHETIC extract.",
        _C | {"feature_group_code": "The predictor (one-hot columns and missing indicators folded into it)",
              "feature_text": "The predictor in words",
              "mean_abs_shap_coef": "Mean absolute SHAP value on the log-odds scale (exact linear SHAP or TreeSHAP); "
                                    "NULL for models without exact SHAP",
              "permutation_auc_drop_ratio": "Held-out AUC lost when this predictor is shuffled (mean of 10 shuffles)",
              "refit_auc_without_ratio": "Held-out AUC of the model refitted without this predictor (same settings; "
                                         "shared predictors only)",
              "refit_auc_drop_ratio": "Full model's held-out AUC minus refit_auc_without_ratio",
              "driver_rank_count": "Rank of the predictor by permutation_auc_drop_ratio within the model (1 = "
                                   "largest)"}),
    STABILITY: (
        "Tooth loss (spec 029, spec 042 US4): each model's point scores on every generator seed (the main one and the "
        "stability seeds), shared predictors, refitted and retuned per seed: the spread across synthetic extracts.",
        _C),
}
