"""Clinic-level periodontitis prevalence from the integrated phenotype (spec 005, US3).

    python scripts/19_prevalence.py

Person-level (latest visit with a known status), per clinic and overall, with
95% Wilson intervals, for: the study-design phenotype, the v0 phenotype, each
single source, and (synthetic only) the generator truth. Then the overall
estimate next to published US figures (NHANES 2009-2014) with the caveats in
prevalence.py. Writes data/datasets/prevalence/.

Since spec 032 US8 (#448) on the visits that count (adults, visits from 2021-04-01: study.visits_in_study), with the
diagnosis codes and rule phenotypes read with a plan that has no gum-disease code as healthy or gingivitis
(study.reread_absent_code), and prevalence_by_group.csv adds the share in each status group at the five groups and
the three. --all-visits --absent-code no_answer gives the files as before.
"""

import argparse

import pandas as pd

from health_transformation_lab_nlp import study
from health_transformation_lab_nlp.labels import ALSO_REPORTED_GROUPINGS, DEFAULT_GROUPING
from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.phenotype import ABSENT_CODE_RULES, DEFAULT_ABSENT_CODE
from health_transformation_lab_nlp.prevalence import (
    NHANES_2009_2014,
    prevalence_by,
    prevalence_by_group,
)

ap = argparse.ArgumentParser()
ap.add_argument("--all-visits", action="store_true", help="every visit (no age or date filter)")
ap.add_argument("--absent-code", default=DEFAULT_ABSENT_CODE, choices=ABSENT_CODE_RULES)
a = ap.parse_args()

v = study.reread_absent_code(pd.read_csv(DATASETS_DIR / "visits_structured.csv"), a.absent_code)
if not a.all_visits:
    v = study.visits_in_study(v)
truth = pd.read_csv(DATASETS_DIR / "answer_key" / "visits_truth.csv")[["visit_id", "truth_status"]]
v = v.merge(truth, on="visit_id")
out = DATASETS_DIR / "prevalence"
out.mkdir(exist_ok=True)

methods = ["algorithm_design", "algorithm_v0", "notes", "exam_form", "proc_dx_completed", "probing_chart",
           "truth_status"]
by_clinic = pd.concat([prevalence_by(v, m, by="clinic_id").assign(method=m) for m in methods])
overall = pd.concat([prevalence_by(v, m).assign(method=m) for m in methods])
by_clinic.to_csv(out / "prevalence_by_clinic.csv", index=False)
overall.to_csv(out / "prevalence_overall.csv", index=False)
if not a.all_visits:      # spec 032 US8: the share in each status group, at the default grouping and those reported
    pd.concat([prevalence_by_group(v, m, g, by="clinic_id").assign(method=m)
               for g in (DEFAULT_GROUPING, *ALSO_REPORTED_GROUPINGS) for m in methods]).to_csv(
        out / "prevalence_by_group.csv", index=False)

adults30 = v[v["age"] >= 30]
ov30 = pd.concat([prevalence_by(adults30, m).assign(method=m) for m in ("algorithm_design", "truth_status")])
nh = NHANES_2009_2014.iloc[0]
cmp = ov30.assign(published_total_pct=nh.total_pct, published_severe_pct=nh.severe_pct,
                  note="NHANES uses CDC/AAP definitions; 'severe' is not stage III-IV; clinic != national sample")
cmp.to_csv(out / "vs_published.csv", index=False)
NHANES_2009_2014.to_csv(out / "published_nhanes_2009_2014.csv", index=False)

pd.set_option("display.width", 160)
print("SYNTHETIC population: prevalence describes the generator, not any real clinic\n")
d = by_clinic[by_clinic.method.isin(["algorithm_design", "truth_status"])]
print(d.pivot(index="clinic_id", columns="method", values="periodontitis").round(3).to_string())
print("\nadults 30+, overall vs published (NHANES 2009-2014: 42.2% any, 7.8% severe):")
print(ov30[["method", "n_people", "periodontitis", "periodontitis_ci_low", "periodontitis_ci_high",
            "stage3_4"]].round(3).to_string(index=False))
