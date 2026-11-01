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
# Spec 032 US1: the same predictions scored at the five and three status groupings, and person-level prevalence
# per status group by clinic, for the R twins (eval/score.R, r/R/06_validation.R). data/labels/ is not committed.
for grouping in ("five", "three"):
    score(test["label"], test["pred"], None, "rules_baseline", run_id="parity", grouping=grouping).to_csv(
        LABELS_DIR / f"python_rules_score_{grouping}.csv", index=False)

from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.prevalence import prevalence_by_group

visits = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
pd.concat([prevalence_by_group(visits, "algorithm_design", grouping=g, by="clinic_id")
           for g in ("six", "five", "three")]).to_csv(LABELS_DIR / "python_prevalence_by_group.csv", index=False)
# Spec 032 US8: the visits scripts/19_prevalence.py counts (adults from the start date, codes re-read under the default
# absent-code rule from the seeded raw codes, which R can't regenerate), so R recomputes the committed prevalence.
from health_transformation_lab_nlp import study

study.visits_in_study(study.reread_absent_code(visits)).to_csv(LABELS_DIR / "python_scored_visits.csv", index=False)

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

# Spec 032 US3: the diagnosis-code source under each absent-code rule, on every pairing of a code and a plan, for its
# R twin (r/R/18_spec032.R).
from health_transformation_lab_nlp.phenotype import ABSENT_CODE_RULES, read_dx_code

codes = ["", "Z01.20", "Z00.00", "K05.00", "K05.10", "K05.311", "K05.312", "K05.313", "K05.321", "K05.322",
         "K05.323", "K05.3", "K05.6", "K08.1"]
plans = ["", "(none)", "D0120 D1110", "D0180 D4341", "D0180 D4341 D7140"]
cases = pd.DataFrame([{"dx_raw": dx, "plan_raw": plan, "absent_code": rule, "status": read_dx_code(dx, plan, rule)}
                      for dx, plan, rule in itertools.product(codes, plans, ABSENT_CODE_RULES)])
cases.to_csv(LABELS_DIR / "absent_code_cases.csv", index=False)
print(f"wrote absent_code_cases.csv ({len(cases)} cases)")
