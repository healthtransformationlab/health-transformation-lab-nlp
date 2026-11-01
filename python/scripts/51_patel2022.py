"""Score the Patel et al. 2022 phenotype (spec 024 US3) beside the paper's own tables.

    python scripts/51_patel2022.py

Reads data/datasets/periodx_visits.csv (written by 10_build_study.py) and writes:

  data_quality/completeness_patel2022.csv  completeness per section (M1 diagnosis codes, M2 the PerioDx Extractor on
                                           the note, M3 the PerioDx Diagnoser on the chart) before merging, and of the
                                           merged result, on all visits and on the 240 review charts (paper: Fig. 1)
  periodx/confusion_scores.csv             TP, FP, FN, TN, precision, recall and F1 per status, one-vs-rest and
                                           pooled, for the Diagnoser, the Extractor and the stepwise phenotype, against
                                           the synthetic generator's truth on the 240 review charts (paper: Table 1)

Synthetic data scored against the generator's truth: not clinical performance, and not a replication of the paper,
whose figures come from real records at one dental school (docs/periodx.md).
"""

import pandas as pd

from health_transformation_lab_nlp.completeness import section_completeness
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.phenotype import PATEL2022_SECTIONS
from health_transformation_lab_nlp.reliability import confusion_scores

v = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
p = pd.read_csv(DATASETS_DIR / "periodx_visits.csv")
key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")
v = v.merge(p, on="visit_id", validate="one_to_one")

parts = []
for scale, rows in (("all_visits", v), ("reference_set", v[v["in_review"].astype(bool)])):
    t = section_completeness(rows, PATEL2022_SECTIONS, "algorithm_patel2022", "algorithm_patel2022_decided_by")
    parts.append(t.assign(scale=scale))
comp = pd.concat(parts, ignore_index=True)[["scale", "section", "n_visits", "n_with_value", "pct_with_value",
                                            "n_decided", "pct_decided"]]
(DATASETS_DIR / "data_quality").mkdir(exist_ok=True)
comp.to_csv(DATASETS_DIR / "data_quality" / "completeness_patel2022.csv", index=False)

r = key[["visit_id", "truth_status"]].merge(p, on="visit_id", validate="one_to_one").sort_values("visit_id")
conf = pd.concat([confusion_scores(r["truth_status"], r[col], LABELS).assign(component=name)
                  for name, col in (("diagnoser", "periodx_chart_label"), ("extractor", "periodx_note_label"),
                                    ("algorithm_patel2022", "algorithm_patel2022"))], ignore_index=True)
conf = conf[["component", "class", "tp", "fp", "fn", "tn", "precision", "recall", "f1"]]
(DATASETS_DIR / "periodx").mkdir(exist_ok=True)
conf.to_csv(DATASETS_DIR / "periodx" / "confusion_scores.csv", index=False)

print("Synthetic charts, scored against the generator's truth (not the paper's real records):")
print(comp.round(1).to_string(index=False))
print(conf[conf["class"] == "pooled"].round(3).to_string(index=False))
