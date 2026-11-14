"""Judge status, grade and extent as separate verdicts (spec 002 T011; GlobalDentBench's key points).

    python scripts/27_component_judge.py --simulated          # simulated judge and reviewers (dry run)
    JUDGE_MODEL=... JUDGE_BASE_URL=... JUDGE_API_KEY=... python scripts/27_component_judge.py

A prediction can get the stage right and the grade wrong; one overall verdict hides that. Here the
note-rules reader's status, grade and extent on each reviewed chart are compared with reviewer
consensus per component, and the judge gives one verdict per component. Outputs:

  data/review/[simulated_]reliability/components_vs_reviewers.csv   agreement per component
  data/corpus/[simulated_]component_gold.csv                        one row per chart x component
  data/corpus/[simulated_]component_calibration.csv                 judge sensitivity/specificity per component
"""

import argparse
import sys

import pandas as pd

from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.cost_effectiveness import calibrate_components
from health_transformation_lab_nlp.judge import (
    COMPONENTS,
    OpenAIJudge,
    SimulatedComponentJudge,
    judge_components_openai,
)
from health_transformation_lab_nlp.note_reader import read_extent, read_grade
from health_transformation_lab_nlp.paths import CORPUS_DIR, DATASETS_DIR, REVIEW_DIR
from health_transformation_lab_nlp.reliability import consensus

telemetry.setup()
telemetry.start_script("27_component_judge", data_label="simulated" if "--simulated" in sys.argv else "synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--simulated", action="store_true", help="simulated reviewers and simulated judge")
a = ap.parse_args()
prefix = "simulated_" if a.simulated else ""

labels = pd.read_csv(REVIEW_DIR / f"{prefix}reviewer_labels.csv")
key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv").set_index("visit_id")
rules = pd.read_csv(DATASETS_DIR / "ai_predictions_note_rules.csv").set_index("visit_id")["pred"]

cons = {c: consensus(labels.pivot_table(index="visit_id", columns="reviewer", values=c, aggfunc="first"))
        for c in COMPONENTS}
rows = []
for vid in sorted(set(key.index) & set(cons["status"].index)):
    note = key.loc[vid, "note_text"]
    pred = {"status": rules.get(vid, "unknown"), "grade": read_grade(note), "extent": read_extent(note)}
    truth = {c: cons[c].get(vid) for c in COMPONENTS}
    for c in COMPONENTS:
        p, t = pred[c], truth[c]
        perio = str(pred["status"]).startswith("periodontitis") and str(truth["status"]).startswith("periodontitis")
        if c != "status" and not perio:
            continue        # grade/extent compared only where both say periodontitis
        if p in ("unknown", "NA", None) or not isinstance(t, str) or t in ("no_consensus", "cannot_determine"):
            continue
        rows.append({"visit_id": vid, "component": c, "pred": p, "truth": t, "truly_correct": p == t,
                     "note": note, "pred_status": pred["status"], "pred_grade": pred["grade"],
                     "pred_extent": pred["extent"]})
gold = pd.DataFrame(rows)

agree = (gold.groupby("component", sort=False)
         .agg(n=("truly_correct", "size"), pct_agree_consensus=("truly_correct", "mean")).reset_index())
out_r = REVIEW_DIR / f"{prefix}reliability"
out_r.mkdir(parents=True, exist_ok=True)
agree.assign(method="note_rules").to_csv(out_r / "components_vs_reviewers.csv", index=False)

if a.simulated:
    truth = {vid: {c: g.loc[g.component == c, "truth"].iloc[0] if (g.component == c).any() else None
                   for c in COMPONENTS} for vid, g in gold.groupby("visit_id")}
    judge = SimulatedComponentJudge(truth)
    verdicts = {vid: judge(g.note.iloc[0], {"status": g.pred_status.iloc[0], "grade": g.pred_grade.iloc[0],
                                            "extent": g.pred_extent.iloc[0]}, visit_id=vid)
                for vid, g in gold.groupby("visit_id")}
else:  # pragma: no cover - needs an LLM endpoint
    j = OpenAIJudge()
    verdicts = {vid: judge_components_openai(j, g.note.iloc[0], {"status": g.pred_status.iloc[0],
                                                                 "grade": g.pred_grade.iloc[0],
                                                                 "extent": g.pred_extent.iloc[0]})
                for vid, g in gold.groupby("visit_id")}
gold["verdict"] = [verdicts[r.visit_id][r.component].verdict for r in gold.itertuples()]
gold["gate_ok"] = [verdicts[r.visit_id][r.component].quote_ok for r in gold.itertuples()]
CORPUS_DIR.mkdir(parents=True, exist_ok=True)
gold.drop(columns=["note"]).to_csv(CORPUS_DIR / f"{prefix}component_gold.csv", index=False)
cal = calibrate_components(gold)
cal.to_csv(CORPUS_DIR / f"{prefix}component_calibration.csv", index=False)

if a.simulated:
    print("*** SIMULATED reviewers and judge: pipeline dry run, not a result ***")
print("note rules vs reviewer consensus, per component:")
print(agree.round(3).to_string(index=False))
print("\njudge calibration per component:")
print(cal.round(3).to_string(index=False))
