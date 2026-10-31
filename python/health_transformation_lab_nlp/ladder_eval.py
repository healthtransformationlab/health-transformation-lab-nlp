"""The model ladder against the synthetic truth (spec 002 T015).

The review charts' true status is known (the generator wrote it), so each method's accuracy can be
measured directly, not only as agreement with reviewers. Per method:

  accuracy            share of charts labelled correctly, with a 95% bootstrap CI
  diff_vs_ref         accuracy minus the reference method's (note_rules), paired bootstrap CI:
                      the same resampled charts for both, so the CI reflects the difference itself
  stage4_recall       share of stage IV charts called stage IV
  unsafe_rate/s2_rate harm.py's severity matrix against the truth
  ece                 expected calibration error of the top-class probability (10 bins)

`by_difficulty` splits accuracy by the note's difficulty level (L1 plain, L2, L3 hard), where an
LLM reader and a fine-tuned encoder are most likely to differ (scripts/29_medgemma_vs_bert.py).

`rules_override` is the stage IV hybrid: where the note rules say stage IV, use that; otherwise the
model. Fine-tuned encoders saw 7 stage IV notes in training and miss nearly all of them.
R twin: r/R/10_ladder.R (point estimates; bootstrap CIs differ by RNG).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .harm import unsafe_rates
from .telemetry import traced

STAGE4 = "periodontitis_stage_4"


@traced
def rules_override(pred: pd.Series, rules_pred: pd.Series, labels=(STAGE4,)) -> pd.Series:
    return rules_pred.where(rules_pred.isin(labels), pred)


@traced
def expected_calibration_error(truth: pd.Series, proba: pd.DataFrame, n_bins: int = 10) -> float:
    conf = proba.max(axis=1).to_numpy()
    correct = (proba.idxmax(axis=1).to_numpy() == truth.to_numpy())
    bins = np.minimum((conf * n_bins).astype(int), n_bins - 1)
    return float(sum(abs(conf[bins == b].mean() - correct[bins == b].mean()) * (bins == b).mean()
                     for b in range(n_bins) if (bins == b).any()))


@traced
def ladder_table(truth: pd.Series, preds: dict, proba: dict | None = None, n_boot: int = 1000,
                 seed: int = 0, reference: str = "note_rules") -> pd.DataFrame:
    """One row per method. All series share truth's index (one row per chart)."""
    proba = proba or {}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(truth), size=(n_boot, len(truth)))   # same resamples for every method
    t = truth.to_numpy()
    correct = {m: (p.reindex(truth.index).to_numpy() == t) for m, p in preds.items()}
    ref = correct.get(reference)
    s4 = t == STAGE4
    rows = []
    for m, p in preds.items():
        c = correct[m]
        boot = c[idx].mean(axis=1)
        row = {"method": m, "n": len(t), "accuracy": c.mean(),
               "acc_lo": np.quantile(boot, 0.025), "acc_hi": np.quantile(boot, 0.975),
               "stage4_recall": c[s4].mean() if s4.any() else np.nan,
               **{k: v for k, v in unsafe_rates(truth, p.reindex(truth.index)).items() if k != "n"},
               "ece": expected_calibration_error(truth, proba[m].reindex(truth.index)) if m in proba else np.nan}
        if ref is not None:
            d = (c[idx].mean(axis=1) - ref[idx].mean(axis=1))
            row |= {"diff_vs_ref": c.mean() - ref.mean(), "diff_lo": np.quantile(d, 0.025),
                    "diff_hi": np.quantile(d, 0.975)}
        rows.append(row)
    return pd.DataFrame(rows)


@traced
def missing_charts(pred: pd.Series, truth: pd.Series) -> int:
    """Review charts a run did not score (e.g. a --limit smoke test); such a run isn't comparable."""
    return int(pred.reindex(truth.index).isna().sum())


@traced
def by_difficulty(truth: pd.Series, preds: dict, level: pd.Series) -> pd.DataFrame:
    """Accuracy per method and difficulty level (long: method, difficulty, n, accuracy)."""
    t, lv = truth.to_numpy(), level.reindex(truth.index).to_numpy()
    rows = []
    for m, p in preds.items():
        ok = p.reindex(truth.index).to_numpy() == t
        rows += [{"method": m, "difficulty": lev, "n": int((lv == lev).sum()), "accuracy": ok[lv == lev].mean()}
                 for lev in sorted(set(lv))]
    return pd.DataFrame(rows)


# ---------- spec 030 (#387): what a synthetic score means ----------
# Methods that turn measurements into a status with labels.py: the same 2017 rules that made the answer key, so on
# synthetic charts they start with an advantage real records won't give them.
ANSWER_KEY_RULES = ("note_rules", "rules_baseline", "algorithm_v0", "algorithm_design", "probing_chart",
                    "radiograph_ai")


@traced
def stageable(key: pd.DataFrame) -> pd.Series:
    """'stageable' when the chart has a probing chart or a radiograph (staging needs attachment or bone loss), else
    'not_stageable': there, a status can only come from what the note or codes say."""
    chart = key["probing_chart"].fillna("unknown").astype(str) != "unknown"
    xray = pd.to_numeric(key["rad_present"], errors="coerce").fillna(0) == 1
    return pd.Series(["stageable" if ok else "not_stageable" for ok in (chart | xray)], index=key.index)


@traced
def uses_answer_key_rules(method: str) -> bool:
    """True for a method that uses the answer key's own rules (ANSWER_KEY_RULES, or a '+rules4' hybrid)."""
    return method.endswith("+rules4") or method.split("+")[0] in ANSWER_KEY_RULES


# ---------- spec 030 US2 (#397): subgroups and stability ----------
@traced
def age_band(age: pd.Series) -> pd.Series:
    """'under_35', '35_64' or '65_plus', for the subgroup split."""
    return pd.Series(np.where(age < 35, "under_35", np.where(age < 65, "35_64", "65_plus")), index=age.index)


@traced
def seed_spread(long: pd.DataFrame) -> pd.DataFrame:
    """Each method's accuracy over seeds (long: method, seed, accuracy): seed count, mean, SD (n - 1), min, max."""
    g = long.groupby("method")["accuracy"]
    return pd.DataFrame({"seed_count": g.size(), "mean_accuracy": g.mean(), "sd_accuracy": g.std(ddof=1),
                         "min_accuracy": g.min(), "max_accuracy": g.max()}).reset_index()
