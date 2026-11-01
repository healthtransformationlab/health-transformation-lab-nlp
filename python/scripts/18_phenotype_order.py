"""Score every ordering of the four evidence groups for the integrated phenotype (spec 005).

    python scripts/18_phenotype_order.py --simulated     # against simulated reviewers (dry run)
    python scripts/18_phenotype_order.py                 # against real reviewer labels

The paper's order (Patel et al. 2022, algorithm_patel2022, spec 024) is scored as one extra row, never selected.

Groups: exam_form, dx_code (diagnosis codes on completed, then planned procedures),
notes (chart-note NLP), probing_chart (periodontal-chart algorithm). The study
design's starting order is exam_form > dx_code > notes > probing_chart; the
order is chosen on half of the review charts and reported on the other half,
in five categories, with the AI-vs-human acceptance test.

Writes data/review/[simulated_]reliability_5cat/phenotype_orders.csv.
"""

import argparse

import pandas as pd

from health_transformation_lab_nlp.paths import DATASETS_DIR, REVIEW_DIR
from health_transformation_lab_nlp.phenotype import PATEL2022_ROW, score_orders, split_halves

ap = argparse.ArgumentParser()
ap.add_argument("--simulated", action="store_true")
ap.add_argument("--n-boot", type=int, default=200)
ap.add_argument("--seed", type=int, default=11)
ap.add_argument("--six", action="store_true", help="score on six categories instead of five")
a = ap.parse_args()
prefix = "simulated_" if a.simulated else ""

labels = pd.read_csv(REVIEW_DIR / f"{prefix}reviewer_labels.csv")
key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv").set_index("visit_id")
wide = labels.pivot_table(index="visit_id", columns="reviewer", values="status", aggfunc="first")
# spec 024: the order of Patel et al. 2022 with its own readers (algorithm_patel2022), one extra row on the same halves
paper = pd.read_csv(DATASETS_DIR / "periodx_visits.csv").set_index("visit_id")["algorithm_patel2022"]
t = score_orders(key, wide, n_boot=a.n_boot, seed=a.seed, five=not a.six, extra={PATEL2022_ROW: paper})
out = REVIEW_DIR / f"{prefix}reliability_5cat"
out.mkdir(parents=True, exist_ok=True)
t.to_csv(out / "phenotype_orders.csv", index=False)
sel, hold = split_halves(sorted(set(key.index) & set(wide.index)), a.seed)   # same halves; for the R twin
pd.DataFrame({"visit_id": sorted(sel | hold), "half": ["select" if i in sel else "holdout" for i in sorted(sel | hold)]}) \
    .to_csv(out / "phenotype_orders_split.csv", index=False)

if a.simulated:
    print("*** SIMULATED REVIEWERS: pipeline dry run, not a result ***")
cols = ["order", "is_design_order", "select_kappa", "holdout_kappa", "holdout_coverage",
        "holdout_diff_vs_human_bar", "holdout_verdict", "selected"]
print(t[cols].round(3).to_string(index=False))
d, s = t[t.is_design_order].iloc[0], t[t.selected].iloc[0]
print(f"\ndesign order {d['order']}: held-out kappa {d['holdout_kappa']:.3f} ({d['holdout_verdict']})")
print(f"selected     {s['order']}: held-out kappa {s['holdout_kappa']:.3f} ({s['holdout_verdict']})")

from health_transformation_lab_nlp.tracking import track  # noqa: E402

with track("18_phenotype_order", "phenotype-orders", simulated=a.simulated) as run:
    run.log_metrics({"design_holdout_kappa": d["holdout_kappa"], "selected_holdout_kappa": s["holdout_kappa"]})
    run.set_tags({"selected_order": s["order"], "design_verdict": d["holdout_verdict"]})
    run.log_artifact(out / "phenotype_orders.csv")
