"""Spec 042 US4 (#867): the tooth-loss model (spec 029) in the multi-model evaluation format.

Every model, the plan's two and the post-hoc candidates, is scored on the same held-out teeth with patient-bootstrap
intervals, paired against the best pre-specified model on the same bootstrap resamples, and explained by its drivers.
The candidates are outside the analysis plan (specs/029-tooth-loss/analysis_plan.md): is_prespecified is False for
them everywhere. Synthetic Open Dental extract only.
"""

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp import open_dental as od
from health_transformation_lab_nlp import tooth_loss_drivers as tld
from health_transformation_lab_nlp import tooth_loss_model as tm

pytest.importorskip("xgboost")

SUFFIXES = ("_id", "_code", "_text", "_count", "_ratio", "_pct", "_coef", "_num", "_seconds", "_sha")


@pytest.fixture(scope="module")
def extract():
    # the same small extract as test_tooth_loss_model.small_run: enough periodontal teeth for 5-fold tuning
    tables, truth, reads = od.build_with_readings(od.Params(n_patients=600), seed=5)
    return {**od.clean(tables), "radiograph_bone_level": reads}, truth


@pytest.fixture(scope="module")
def compared(extract):
    x, truth = extract
    return tld.compare(x, truth, tm.ModelParams(n_boot=20), models=("logistic", "xgboost", "elastic_net_logistic",
                                                                     "random_forest"), generator_seed=5)


# ---------- the model registry ----------

def test_prespecified_models_are_the_plans_two():
    assert {m for m, s in tld.MODEL_SPECS.items() if s["is_prespecified"]} == set(tm.MODELS)
    assert {"random_forest", "hist_gradient_boosting", "elastic_net_logistic", "spline_logistic"} <= set(
        tld.MODEL_SPECS)
    for name, spec in tld.MODEL_SPECS.items():
        assert spec["family_code"] and spec["model_text"], name


def test_every_candidate_fits_and_predicts_probabilities():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=300), "b": rng.normal(size=300),
                      "tooth_type_code=upper_molar": rng.integers(0, 2, 300).astype(float)})
    X.loc[::7, "b"] = np.nan                                    # missing values are part of the data (plan s. 7)
    y = (X["a"] + rng.normal(size=300) > 0).astype(int).to_numpy()
    for name in tld.available_models():
        p = tld.fit_model(name, X, y, seed=1, hyper=tld.default_hyper(name)).predict(X)
        assert p.shape == (300,) and np.all((p >= 0) & (p <= 1)), name
        assert tm.auc(y, p) > 0.7, name


def test_tuning_uses_the_plans_folds_and_returns_a_grid_point():
    rng = np.random.default_rng(1)
    X = pd.DataFrame({"a": rng.normal(size=400), "b": rng.normal(size=400)})
    y = (X["a"] + rng.normal(size=400) > 0).astype(int).to_numpy()
    groups = np.repeat(np.arange(200), 2)
    hyper, cv_auc = tld.tune("random_forest", X, y, groups, folds=5, seed=42)
    grid = tld.GRIDS["random_forest"]
    assert set(hyper) == set(grid) and all(hyper[k] in grid[k] for k in grid)
    assert 0.5 < cv_auc <= 1


# ---------- the paired comparison ----------

def test_delong_on_identical_scores_is_zero_and_detects_a_better_one():
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, 400)
    good = y + rng.normal(scale=0.6, size=400)
    bad = y + rng.normal(scale=3.0, size=400)
    d, p = tld.delong(y, good, good)
    assert d == 0 and p == 1.0
    d, p = tld.delong(y, good, bad)
    assert d == pytest.approx(tm.auc(y, good) - tm.auc(y, bad)) and p < 0.001


def test_paired_bootstrap_difference_is_on_the_same_patients():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 300).astype(float)
    pats = np.repeat(np.arange(100), 3)
    a = np.clip(y * 0.6 + rng.uniform(0, 0.4, 300), 0, 1)
    out = tld.paired_difference(y, a, a, pats, n_boot=50, seed=42)
    assert out["auc_diff_ratio"] == 0 and out["auc_diff_lo_ratio"] == 0 and out["auc_diff_hi_ratio"] == 0
    assert out["brier_diff_ratio"] == 0
    b = np.full(300, 0.5)
    out = tld.paired_difference(y, b, a, pats, n_boot=50, seed=42)        # b minus a: worse on both
    assert out["auc_diff_hi_ratio"] < 0 and out["brier_diff_lo_ratio"] > 0


def test_feature_group_folds_one_hot_and_missing_indicators():
    assert tld.feature_group("tooth_type_code=upper_molar") == "tooth_type_code"
    assert tld.feature_group("last_bop_pct_missing") == "last_bop_pct"
    assert tld.feature_group("mouth_max_pd_mm") == "mouth_max_pd_mm"


# ---------- the comparison on the extract ----------

def test_prespecified_models_reproduce_the_plans_run(extract, compared):
    """The plan's logistic regression and tuned XGBoost score exactly what tooth_loss_model.run scores, on the same
    held-out teeth: the comparison starts from the pre-specified results, not a refit of its own."""
    x, truth = extract
    plan = tm.run(x, truth, tm.ModelParams(n_boot=0), generator_seed=5)["scores"]
    plan = plan[plan.metric.eq("auc") & plan.model.isin(tm.MODELS)].set_index(
        ["label_set", "feature_set", "model", "eval_set"])["value"]
    rank = compared["tooth_loss_model_rank"]
    for r in rank[rank.is_prespecified].itertuples():
        key = (r.label_set_code, r.feature_set_code, r.model_code, r.eval_set_code)
        assert r.auc_ratio == pytest.approx(plan.loc[key], abs=1e-12), key


def test_rank_table_covers_every_label_set_feature_set_and_model(compared):
    rank = compared["tooth_loss_model_rank"]
    held = rank[rank.eval_set_code.eq("held_out")]
    assert set(held.label_set_code) == set(tm.LABEL_SETS) and set(held.feature_set_code) == set(tm.FEATURE_SETS)
    assert len(held) == len(tm.LABEL_SETS) * len(tm.FEATURE_SETS) * 4
    assert set(rank.eval_set_code) == {"held_out", "missing_at_entry"}
    assert not rank[rank.eval_set_code.eq("missing_at_entry")].feature_set_code.eq("own").any()   # no own measures
    for _, g in held.groupby(["label_set_code", "feature_set_code"]):
        assert g.tooth_count.nunique() == 1                     # the same held-out teeth for every model
        assert sorted(g.rank_position_count) == list(range(1, len(g) + 1))
    assert (rank.auc_lo_ratio <= rank.auc_ratio).all() and (rank.auc_ratio <= rank.auc_hi_ratio).all()
    assert rank.set_index("model_code").is_prespecified.groupby(level=0).first().to_dict() == {
        "logistic": True, "xgboost": True, "elastic_net_logistic": False, "random_forest": False}


def test_paired_table_is_against_the_best_prespecified_model(compared):
    rank, paired = compared["tooth_loss_model_rank"], compared["tooth_loss_model_contrast"]
    keys = ["label_set_code", "feature_set_code", "eval_set_code"]
    for k, g in paired.groupby(keys):
        r = rank.set_index(keys).loc[k]
        pre = r[r.is_prespecified]
        best = pre.sort_values("auc_ratio", ascending=False).model_code.iloc[0]
        assert (g.reference_model_code == best).all()
        ref = g.set_index("model_code").loc[best]
        assert ref.auc_diff_ratio == 0 and ref.brier_diff_ratio == 0
        for row in g.itertuples():
            a = r.set_index("model_code").loc[row.model_code, "auc_ratio"] - r.set_index("model_code").loc[best,
                                                                                                         "auc_ratio"]
            assert row.auc_diff_ratio == pytest.approx(a)
            assert row.auc_diff_lo_ratio <= row.auc_diff_ratio <= row.auc_diff_hi_ratio
            assert row.is_better_beyond_ci == (row.auc_diff_lo_ratio > 0)
    assert "is_prespecified" in paired


def test_drivers_rank_feature_groups_per_model(compared):
    drv = compared["tooth_loss_driver"]
    shared = drv[drv.feature_set_code.eq("shared")]
    for _, g in shared.groupby(["label_set_code", "model_code"]):
        assert set(g.feature_group_code) == set(tm.FEATURE_SETS["shared"])
    pre = shared[shared.model_code.isin(tm.MODELS)]
    assert pre.mean_abs_shap_coef.notna().all()                 # SHAP for the plan's models
    assert shared[~shared.model_code.isin(tm.MODELS)].mean_abs_shap_coef.isna().all()
    assert drv.permutation_auc_drop_ratio.notna().all()        # permutation importance for every model
    assert shared.refit_auc_drop_ratio.notna().all()            # leave-one-group-out refit on the applied set


def test_every_column_is_typed_and_commented(compared):
    for name in tld.TABLES:
        df = compared[name]
        table_comment, cols = tld.COMMENTS[name]
        assert table_comment
        for c in df.columns:
            assert c.startswith("is_") or c.endswith(SUFFIXES), (name, c)
            assert cols.get(c), (name, c)


def test_page_says_post_hoc_and_ends_with_a_recommendation(compared):
    page = tld.details_markdown(compared | {tld.STABILITY: pd.DataFrame()})
    assert "post hoc" in page and "analysis plan" in page and "amendment" in page
    assert page.rstrip().split("\n## ")[-1].startswith("Recommendation")
    assert "SYNTHETIC" in page


def test_committed_outputs_exist():
    for name in tld.ALL_TABLES:
        assert (tld.OUT_DIR / f"{name}.csv").exists(), name
    assert tld.DETAILS_DOC.exists()


# ---------- the Databricks load (fake client) ----------

class FakeClient:
    def __init__(self, done=()):
        self.statements, self.runs, self.done = [], [], set(done)

    def sql(self, statement):
        self.statements.append(statement)

    def existing_run_models(self, commit):
        return self.done

    def log_run(self, run):
        self.runs.append(run)


def test_load_creates_commented_tables_and_one_run_per_model(compared):
    from health_transformation_lab_nlp import tooth_loss_drivers_load as tdl
    tables = {n: compared[n] for n in tld.TABLES} | {tld.STABILITY: compared["tooth_loss_model_rank"][
        ["generator_seed_num", "label_set_code", "feature_set_code", "eval_set_code", "model_code", "is_prespecified",
         "tooth_count", "perio_tooth_count", "auc_ratio", "brier_ratio", "calibration_slope_coef"]]}
    batch = {"run_id": "r1", "run_ts": "2026-11-17T00:00:00+00:00", "git_commit_sha": "abc"}
    client = FakeClient(done={"logistic"})
    out = tdl.load(tables, client, batch)
    creates = [s for s in client.statements if s.startswith("CREATE OR REPLACE TABLE")]
    assert len(creates) == len(tld.ALL_TABLES)
    assert all(s.startswith("CREATE OR REPLACE TABLE health_transformation_lab.gold_opendental_perio.tooth_loss_")
               for s in creates)
    for s in creates:
        assert "COMMENT ''" not in s and "git_commit_sha STRING COMMENT" in s and "is_prespecified BOOLEAN" in s
    assert out["row_count"] == sum(len(d) for d in tables.values())
    names = [r["run_name"] for r in client.runs]
    assert sorted(names) == ["elastic_net_logistic", "random_forest", "xgboost"]     # logistic already logged
    xgb = next(r for r in client.runs if r["run_name"] == "xgboost")
    assert xgb["params"]["is_prespecified"] == "true" and "completed.shared.max_depth" in xgb["params"]
    assert {"completed.shared.held_out.auc_ratio", "completed.shared.held_out.auc_lo_ratio",
            "completed.shared.held_out.calibration_slope_coef"} <= set(xgb["metrics"])
    rf = next(r for r in client.runs if r["run_name"] == "random_forest")
    assert rf["tags"]["is_prespecified"] == "false" and rf["tags"]["git_commit_sha"] == "abc"


def test_a_column_without_a_comment_is_refused():
    from health_transformation_lab_nlp import tooth_loss_drivers_load as tdl
    with pytest.raises(ValueError, match="no comment"):
        tdl.table_sql("tooth_loss_driver", pd.DataFrame({"mystery_count": [1]}), {"run_id": "r"})
