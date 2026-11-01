"""Do the scores hold on other test sets? Rebuild the synthetic study with five seeds and rescore (spec 030 US2, #397).

    python scripts/49_seed_stability.py [--seeds 42 1 2 3 4]

The 240 review charts are one draw (seed 42). For each seed, the study is rebuilt in a temporary folder (nothing in
data/ is changed), and every method that needs no GPU is scored on that seed's 240 review charts:
- the keyword rules;
- word counts, and word counts plus X-ray (trained on that seed's training notes);
- the two rule phenotypes;
- each part of the record alone.

Writes data/datasets/ladder/:
  seed_stability.csv          one row per method and seed: n, accuracy
  seed_stability_summary.csv  each method's seed count, mean, SD, min and max (ladder_eval.seed_spread)
SYNTHETIC: agreement with each seed's generator answer key, not clinical performance.
"""

import argparse
import tempfile
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import ladder_eval, rungs, telemetry
from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.radiograph import FEATURES as RAD_FEATURES
from health_transformation_lab_nlp.study import build_study

FROM_KEY = ("algorithm_v0", "algorithm_design", "probing_chart", "exam_form", "proc_dx_completed",
            "proc_dx_planned", "radiograph_ai")
TRAINED = {"note_rules": rungs.NoteRules, "tfidf_logreg": rungs.tfidf_logreg,
           "fusion_tfidf_rad": rungs.fusion_tfidf_rad}

ap = argparse.ArgumentParser()
ap.add_argument("--seeds", type=int, nargs="+", default=[42, 1, 2, 3, 4])
a = ap.parse_args()
telemetry.setup()
telemetry.start_script("49_seed_stability", data_label="synthetic")

rows = []
for seed in a.seeds:
    with tempfile.TemporaryDirectory() as tmp:
        build_study(Path(tmp) / "ds", Path(tmp) / "raw", seed=seed)
        key = pd.read_csv(Path(tmp) / "ds" / "answer_key" / "review_key.csv")
        train = pd.read_csv(Path(tmp) / "ds" / "train.csv")
    truth = key["truth_status"]
    preds = {m: key[m] for m in FROM_KEY}
    review = key[["visit_id", "note_text", *RAD_FEATURES]]
    for name, make in TRAINED.items():
        preds[name] = pd.Series(make().fit(train).predict(review)[0], index=key.index)
    rows += [{"method": m, "seed": seed, "n": len(truth), "accuracy": float((p == truth).mean())}
             for m, p in preds.items()]
    print(f"seed {seed}: done")

out = DATASETS_DIR / "ladder"
long = pd.DataFrame(rows)
long.to_csv(out / "seed_stability.csv", index=False)
summary = ladder_eval.seed_spread(long).sort_values("mean_accuracy", ascending=False)
summary.to_csv(out / "seed_stability_summary.csv", index=False)
print(summary.round(3).to_string(index=False))
print("SYNTHETIC: agreement with each seed's answer key, not clinical performance")
