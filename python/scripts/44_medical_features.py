"""Status classifier on dental-only, dental+medical and medical-only features (spec 023 US2-US3), SYNTHETIC.

    python scripts/44_medical_features.py [--seed 0] [--outcome algorithm_design|truth_status]
    python scripts/44_medical_features.py --metrics-only     # R parity inputs only; no xgboost needed

After Patel et al. 2026 (JDR Clin Trans Res; experiments 1 and 5): one row per person (latest charted visit), the
4 classes healthy (with gingivitis), I, II, III+IV, a 70/30 split stratified by class and kept by person, XGBoost
tuned by grouped 5-fold cross-validation, the same split for every feature set; per class, one-vs-rest,
sensitivity, specificity, AUC and Brier score, and their class means (classify_status.class_metrics). The medical
record is the seeded synthetic one (medical_record.py, data/datasets/medical_record.csv): the comparison shows the
pipeline works and how the generator's built-in links come through; it says nothing about real patients. The full
run needs the `ml` extra.

Writes data/datasets/classify_status/synthetic_medical_feature_sets{,_predictions,_shap}.csv. Both modes then
write the parity inputs r/tests/test_parity.R reads: class_metrics on the committed held-out predictions and on a
seeded table of hand-made cases with ties and a missing class (synthetic_class_metrics_{cases,parity}.csv).
"""

import argparse

import numpy as np
import pandas as pd

from health_transformation_lab_nlp import classify_status as cs
from health_transformation_lab_nlp.paths import DATASETS_DIR

ap = argparse.ArgumentParser()
ap.add_argument("--outcome", default="algorithm_design", choices=["algorithm_design", "truth_status"])
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--metrics-only", action="store_true", help="only the R parity inputs, from committed predictions")
a = ap.parse_args()

out = DATASETS_DIR / "classify_status"
out.mkdir(exist_ok=True)
stem = "synthetic_medical_feature_sets"
names = cs.CLASS_NAMES["four"]
pcols = [f"p_{c}" for c in names]

if not a.metrics_only:
    v = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
    if a.outcome == "truth_status":
        v = v.merge(pd.read_csv(DATASETS_DIR / "answer_key" / "visits_truth.csv")[["visit_id", "truth_status"]],
                    on="visit_id")
    record = pd.read_csv(DATASETS_DIR / "medical_record.csv")
    people = cs.person_features(v, record, a.outcome, "four")
    res = cs.compare_feature_sets(people, seed=a.seed)
    res["metrics"].assign(outcome=a.outcome).to_csv(out / f"{stem}.csv", index=False, float_format="%.10g")
    res["predictions"].to_csv(out / f"{stem}_predictions.csv", index=False, float_format="%.10g")
    res["shap_importance"].to_csv(out / f"{stem}_shap.csv", index=False, float_format="%.6g")
    m = res["metrics"]
    print(f"SYNTHETIC: 4-class status, outcome {a.outcome}, {len(people)} people "
          f"({int(m['n_train'].iloc[0])} train), seed {a.seed}")
    print(m.drop(columns=["features", "seed", "is_synthetic", "n_train"]).round(3).to_string(index=False))

# ---- R parity inputs (spec 023 FR-006): the same metrics from the same CSVs, in Python here and in base R there.
# Hand-made cases: 10 votes split among the classes give probabilities that sum to exactly 1 with many ties;
# class III_IV never occurs, so its AUC and sensitivity are missing and the means cover 3 classes.
rng = np.random.default_rng(23)
n = 120
votes = rng.multinomial(10, [0.4, 0.25, 0.2, 0.15], size=n)
cases = pd.DataFrame(votes / 10, columns=pcols).assign(feature_set="cases", visit_id=np.arange(1, n + 1),
                                                       y=rng.choice(3, size=n, p=[0.5, 0.3, 0.2]))
cases = cases[["feature_set", "visit_id", "y", *pcols]]
cases.to_csv(out / "synthetic_class_metrics_cases.csv", index=False)
preds = pd.read_csv(out / f"{stem}_predictions.csv")
parity = pd.concat([cs.class_metrics(g["y"].to_numpy(), g[pcols].to_numpy(), names).assign(feature_set=k)
                    for k, g in pd.concat([preds, cases]).groupby("feature_set", sort=False)], ignore_index=True)
parity = parity[["feature_set", "class", "n_test", "sensitivity", "specificity", "auc", "brier", "classes_averaged"]]
parity.to_csv(out / "synthetic_class_metrics_parity.csv", index=False, float_format="%.17g")
print(parity[parity["class"] == "mean"].drop(columns="n_test").round(3).to_string(index=False))
