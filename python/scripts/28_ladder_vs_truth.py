"""Every model on the review charts against the synthetic truth, with bootstrap CIs (spec 002 T015).

    python scripts/28_ladder_vs_truth.py [--n-boot 1000] [--seed 0]

Reads data/datasets/ai_predictions_<rung>.csv (not the simulated_* dry runs) and the answer key.
Adds '<rung>+rules4' for each learned rung: the note rules decide stage IV, the model the rest.
Writes data/datasets/ladder/:
  ladder_vs_truth.csv   per method: accuracy (CI), difference from note_rules (paired CI),
                        stage IV recall, unsafe and S2 rates, calibration error
  ladder_preds.csv      the predictions scored (R recomputes the point estimates from these)
  ladder_proba.csv      class probabilities, long (method, visit_id, p_<status>)
  ladder_by_stageable.csv  per method: n and accuracy on charts that can and can't be staged (spec 030)
  ladder_by_age.csv, ladder_by_clinic.csv  the same by age band and by clinic (spec 030 US2)
The truth is the generator's: these are synthetic-data results, not clinical performance.
"""

import argparse
import glob
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import ladder_eval
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR

RULES = ("note_rules", "rules_baseline")
ap = argparse.ArgumentParser()
ap.add_argument("--n-boot", type=int, default=1000)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv").set_index("visit_id")
truth = key["truth_status"]
preds, proba = {}, {}
for f in sorted(glob.glob(str(DATASETS_DIR / "ai_predictions_*.csv"))):
    rung = Path(f).stem.removeprefix("ai_predictions_")
    d = pd.read_csv(f).set_index("visit_id").reindex(truth.index)
    preds[rung] = d["pred"]
    pcols = [f"p_{lab}" for lab in LABELS]
    if all(c in d for c in pcols):
        proba[rung] = d[pcols].set_axis(LABELS, axis=1)
for rung in [r for r in list(preds) if r not in RULES and "note_rules" in preds]:
    preds[f"{rung}+rules4"] = ladder_eval.rules_override(preds[rung], preds["note_rules"])

table = ladder_eval.ladder_table(truth, preds, proba, n_boot=a.n_boot, seed=a.seed, reference="note_rules")
out = DATASETS_DIR / "ladder"
out.mkdir(parents=True, exist_ok=True)
table.sort_values("accuracy", ascending=False).to_csv(out / "ladder_vs_truth.csv", index=False)
pd.DataFrame(preds).assign(truth=truth).rename_axis("visit_id").reset_index().to_csv(out / "ladder_preds.csv", index=False)
pd.concat([p.assign(method=m) for m, p in proba.items()]).rename_axis("visit_id").reset_index().to_csv(
    out / "ladder_proba.csv", index=False)
# spec 030: the same scores on charts that can be staged (a probing chart or a radiograph) and on those that can't
split = ladder_eval.by_difficulty(truth, preds, ladder_eval.stageable(key)).rename(columns={"difficulty": "stageable_code"})
split.to_csv(out / "ladder_by_stageable.csv", index=False)
# spec 030 US2: the same scores by age band and by clinic
for name, level in (("age", ladder_eval.age_band(key["age"])), ("clinic", key["clinic_id"].astype(str))):
    ladder_eval.by_difficulty(truth, preds, level).rename(columns={"difficulty": f"{name}_code"}).to_csv(
        out / f"ladder_by_{name}.csv", index=False)
print(table.sort_values("accuracy", ascending=False).round(3).to_string(index=False))
print("wrote", out, "(synthetic truth; not clinical performance)")
