"""Promote a registered model version to champion only if it passes the acceptance test (docs/mlops.md).

    python scripts/11_ai_predict.py --rung tfidf_logreg --register health_transformation_lab.gold_perio_bench.perio_note_classifier
    python scripts/13_reliability.py                       # writes agreement_vs_humans.csv
    python scripts/24_promote_model.py --model health_transformation_lab.gold_perio_bench.perio_note_classifier --version 3 \
        --rater ai:tfidf_logreg [--simulated]

Sets the alias 'champion' when the verdict is non-inferior; always writes the verdict
and the difference from the human bar as version tags. A dry run against simulated
reviewers is refused unless --allow-simulated (a simulated pass is not evidence).
"""

import argparse

import pandas as pd

from health_transformation_lab_nlp.model_registry import promote_if_accepted
from health_transformation_lab_nlp.paths import REVIEW_DIR
import sys
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("24_promote_model", data_label="simulated" if "--simulated" in sys.argv else "synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--version", required=True)
ap.add_argument("--rater", required=True, help="method name in agreement_vs_humans.csv, e.g. ai:tfidf_logreg")
ap.add_argument("--simulated", action="store_true", help="read the simulated reviewers' results")
ap.add_argument("--allow-simulated", action="store_true")
ap.add_argument("--five", action="store_true", help="use the five-category acceptance test")
a = ap.parse_args()
if a.simulated and not a.allow_simulated:
    raise SystemExit("refusing to promote on simulated reviewers; pass --allow-simulated for a dry run")
d = REVIEW_DIR / (("simulated_" if a.simulated else "") + ("reliability_5cat" if a.five else "reliability"))
vh = pd.read_csv(d / "agreement_vs_humans.csv")
ok = promote_if_accepted(a.model, a.version, a.rater, vh)
row = vh[vh.rater == a.rater]
print(row[["rater", "mean_kappa_vs_humans", "diff_vs_human_bar", "ci_low", "ci_high", "verdict"]].round(3).to_string(index=False))
print(f"{a.model} v{a.version}: {'promoted to champion' if ok else 'stays challenger'}")
