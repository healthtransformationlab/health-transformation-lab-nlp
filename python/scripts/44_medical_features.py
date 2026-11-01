"""Status classifier on dental-only, dental+medical and medical-only features (spec 023 US2), SYNTHETIC.

    python scripts/44_medical_features.py [--seed 0] [--outcome algorithm_design|truth_status]

After Patel et al. 2026 (JDR Clin Trans Res; experiments 1 and 5): one row per person (latest charted visit), the
4 classes healthy (with gingivitis), I, II, III+IV, a 70/30 split stratified by class and kept by person, XGBoost
tuned by grouped 5-fold cross-validation, the same split for every feature set. The medical record is the seeded
synthetic one (medical_record.py, data/datasets/medical_record.csv): the comparison shows the pipeline works and
how the generator's built-in links come through; it says nothing about real patients. Needs the `ml` extra.

Writes data/datasets/classify_status/synthetic_medical_feature_sets{,_predictions,_shap}.csv.
"""

import argparse

import pandas as pd

from health_transformation_lab_nlp import classify_status as cs
from health_transformation_lab_nlp.paths import DATASETS_DIR

ap = argparse.ArgumentParser()
ap.add_argument("--outcome", default="algorithm_design", choices=["algorithm_design", "truth_status"])
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

v = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
if a.outcome == "truth_status":
    v = v.merge(pd.read_csv(DATASETS_DIR / "answer_key" / "visits_truth.csv")[["visit_id", "truth_status"]],
                on="visit_id")
record = pd.read_csv(DATASETS_DIR / "medical_record.csv")
people = cs.person_features(v, record, a.outcome, "four")
res = cs.compare_feature_sets(people, seed=a.seed)

out = DATASETS_DIR / "classify_status"
out.mkdir(exist_ok=True)
stem = "synthetic_medical_feature_sets"
res["metrics"].assign(outcome=a.outcome).to_csv(out / f"{stem}.csv", index=False, float_format="%.10g")
res["predictions"].to_csv(out / f"{stem}_predictions.csv", index=False, float_format="%.10g")
res["shap_importance"].to_csv(out / f"{stem}_shap.csv", index=False, float_format="%.6g")

m = res["metrics"]
print(f"SYNTHETIC: 4-class status, outcome {a.outcome}, {len(people)} people "
      f"({int(m['n_train'].iloc[0])} train), seed {a.seed}")
print(m.drop(columns=["features", "seed", "is_synthetic", "n_train"]).round(3).to_string(index=False))
print(m.groupby("feature_set", sort=False)[["sensitivity", "specificity", "auc"]].mean().round(3).to_string())
