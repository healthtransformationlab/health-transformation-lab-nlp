"""Every model on the review charts against the synthetic truth, with bootstrap CIs (spec 002 T015).

    python scripts/28_ladder_vs_truth.py [--n-boot 1000] [--seed 0]
    python scripts/28_ladder_vs_truth.py --grouping six --all-visits --absent-code no_answer   # before spec 032 US8

Reads data/datasets/ai_predictions_<rung>.csv (not the simulated_* dry runs) and the answer key.
Adds '<rung>+rules4' for each learned rung: the note rules decide stage IV, the model the rest.
Scored under the spec 032 US8 defaults (#448; docs/presets.md, preset repo_v2): at the five status groups (healthy
and gingivitis merged), on the review charts that count (adults, visits from 2021-04-01: study.scored_review), with a
treatment plan that has no gum-disease code read as healthy or gingivitis. The benchmark note set and every committed
prediction are unchanged; only the scoring is.
Writes data/datasets/ladder/:
  ladder_vs_truth.csv   per method: accuracy (CI), difference from note_rules (paired CI),
                        stage IV recall, unsafe and S2 rates, calibration error
  ladder_preds.csv      the predictions scored, as status groups (R recomputes the point estimates from these)
  ladder_proba.csv      class probabilities added up within each group, long (method, visit_id, group columns)
  ladder_by_stageable.csv  per method: n and accuracy on charts that can and can't be staged (spec 030)
  ladder_by_age.csv, ladder_by_clinic.csv  the same by age band and by clinic (spec 030 US2)
The truth is the generator's: these are synthetic-data results, not clinical performance.
"""

import argparse
import glob
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import ladder_eval, study
from health_transformation_lab_nlp.labels import DEFAULT_GROUPING, GROUPINGS, LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.phenotype import ABSENT_CODE_RULES, DEFAULT_ABSENT_CODE

RULES = ("note_rules", "rules_baseline")
ap = argparse.ArgumentParser()
ap.add_argument("--n-boot", type=int, default=1000)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--grouping", default=DEFAULT_GROUPING, choices=list(GROUPINGS), help="status grouping scored")
ap.add_argument("--min-age", type=int, default=study.ANALYSIS_MIN_AGE, help="review charts of people this age or older")
ap.add_argument("--start-date", default=study.ANALYSIS_START_DATE, help="ISO date: review charts from it on")
ap.add_argument("--all-visits", action="store_true", help="every review chart (no age or date filter)")
ap.add_argument("--absent-code", default=DEFAULT_ABSENT_CODE, choices=ABSENT_CODE_RULES)
a = ap.parse_args()

key_all = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")
visits = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
min_age, start_date = (None, None) if a.all_visits else (a.min_age, a.start_date)
key = study.scored_review(key_all, visits, min_age, start_date, a.absent_code).set_index("visit_id")
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
truth = ladder_eval.grouped(truth, a.grouping)
preds = {m: ladder_eval.grouped(p, a.grouping) for m, p in preds.items()}
proba = {m: ladder_eval.grouped_proba(p, a.grouping) for m, p in proba.items()}

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
print(f"{len(truth)} of {len(key_all)} review charts scored (min age {min_age}, start date {start_date}), grouping "
      f"{a.grouping}, absent code {a.absent_code}")
print("wrote", out, "(synthetic truth; not clinical performance)")
