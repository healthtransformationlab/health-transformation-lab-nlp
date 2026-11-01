"""Write the Python rules predictions and their score for r/tests/test_parity.R."""

import sys

import pandas as pd

from health_transformation_lab_nlp.paths import LABELS_DIR, REPO_ROOT
from health_transformation_lab_nlp.rungs import rules_predict

sys.path.insert(0, str(REPO_ROOT / "eval"))
from score import score

notes = pd.read_parquet(LABELS_DIR / "labeled_notes.parquet")
notes["pred"] = [rules_predict(t) for t in notes["note_text"]]
notes[["note_id", "pred"]].to_csv(LABELS_DIR / "python_rules_predictions.csv", index=False)

test = notes.merge(pd.read_csv(LABELS_DIR / "split.csv"), on="person_id").query("split == 'test'")
score(test["label"], test["pred"], None, "rules_baseline", run_id="parity").to_csv(
    LABELS_DIR / "python_rules_score.csv", index=False)

# AAP worksheet edge cases (CAL missing, tooth loss, complexity) for the R twin of label_chart
import itertools

from health_transformation_lab_nlp.labels import PerioChart, label_chart

rows = []
for cal, rbl, pd_, lost, vd, fc, mob, rem in itertools.product(
        [None, 0.5, 2, 4, 6], [None, 0, 10, 25, 40], [3, 5, 6], [0, 2, 5], [0, 3], [0, 2], [0, 2], [None, 18]):
    if cal is None and rbl is None:
        continue
    lab = label_chart(PerioChart(pd_, 30, cal, rbl, lost, vertical_defect_mm=vd, furcation_class=fc,
                                 mobility_degree=mob, remaining_teeth=rem)).value
    rows.append({"pd": pd_, "cal": cal, "rbl": rbl, "lost": lost, "vd": vd, "fc": fc, "mob": mob,
                 "rem": rem, "label": lab})
pd.DataFrame(rows).to_csv(LABELS_DIR / "aap_rule_cases.csv", index=False)
print(f"wrote python_rules_predictions.csv, python_rules_score.csv, aap_rule_cases.csv ({len(rows)} cases)")

# Spec 024 US1: the PerioDx Diagnoser (Patel et al. 2022, Fig. 2) on seeded chart inputs, with gaps, for its R twin
# (r/R/14_spec024.R); and the repo's summary chart read as the figure's inputs.
from health_transformation_lab_nlp.periodx import write_parity_cases

print(write_parity_cases(LABELS_DIR))
