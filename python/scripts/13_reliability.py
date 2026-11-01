"""Quantitative validation: reviewers vs each other, and every method, the
rule-based algorithm and each AI model vs the reviewers.

    python scripts/13_reliability.py              # uses reviewer_labels.csv
    python scripts/13_reliability.py --simulated  # uses simulated_reviewer_labels.csv (dry run)
"""

import argparse
import glob
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp.paths import DATASETS_DIR, REVIEW_DIR
from health_transformation_lab_nlp.phenotype import collapse5
from health_transformation_lab_nlp.reliability import agreement_vs_humans, by_level, reliability_report

ap = argparse.ArgumentParser()
ap.add_argument("--simulated", action="store_true")
ap.add_argument("--n-boot", type=int, default=500)
ap.add_argument("--margin", type=float, default=0.05,
                help="non-inferiority margin in kappa, fixed before looking at results")
a = ap.parse_args()
prefix = "simulated_" if a.simulated else ""

labels = pd.read_csv(REVIEW_DIR / f"{prefix}reviewer_labels.csv")
key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv").set_index("visit_id")
compare = {m: key[m] for m in ["notes", "exam_form", "proc_codes_completed", "proc_codes_planned",
                               "proc_dx_completed", "proc_dx_planned", "probing_chart", "radiograph_ai",
                               "algorithm_v0", "algorithm_design"]}
# spec 024: the Patel et al. 2022 stepwise phenotype, from its own file (visits_structured and the key stay unchanged)
compare["algorithm_patel2022"] = pd.read_csv(DATASETS_DIR / "periodx_visits.csv").set_index("visit_id")[
    "algorithm_patel2022"].reindex(key.index)
for f in sorted(glob.glob(str(DATASETS_DIR / "ai_predictions_*.csv"))):
    p = pd.read_csv(f).set_index("visit_id")["pred"]
    compare["ai:" + Path(f).stem.removeprefix("ai_predictions_")] = p
rep = reliability_report(labels, key, compare)

out = REVIEW_DIR / f"{prefix}reliability"
out.mkdir(parents=True, exist_ok=True)
rep["pairwise"].to_csv(out / "reviewer_pairwise.csv", index=False)
rep["methods"].to_csv(out / "methods_vs_reviewers.csv", index=False)
rep["consensus"].to_csv(out / "consensus.csv")
lv = by_level(key, rep["consensus"], compare)
lv.to_csv(out / "by_level.csv", index=False)
if a.simulated:
    print("*** SIMULATED REVIEWERS: pipeline dry run, not a result ***")
print(f"charts={rep['n_visits']} reviewers={rep['n_reviewers']} "
      f"Fleiss kappa={rep['fleiss_kappa']:.3f} consensus reached={rep['consensus_reached']:.1%}")
cols = ["method", "coverage", "n", "pct_agree_consensus", "kappa_vs_consensus", "unsafe_rate", "s2_rate"]
print(rep["methods"][cols].round(3).to_string(index=False))
print("\nagreement by difficulty (L1 stated in 2017 terms, L2 translate, L3 infer/resolve):")
print(lv.pivot(index="method", columns="level", values="pct_agree_consensus").round(3).to_string())

wide = labels.pivot_table(index="visit_id", columns="reviewer", values="status", aggfunc="first")
vh = agreement_vs_humans(wide, compare, n_boot=a.n_boot, margin=a.margin)
vh.to_csv(out / "agreement_vs_humans.csv", index=False)
print(f"\nacceptance test: agree with reviewers at least as much as they agree with each other "
      f"(non-inferiority margin {a.margin} kappa, 95% bootstrap CI over charts):")
print(vh.drop(columns=["margin"]).round(3).to_string(index=False))

# Spec 005: the same report on five categories (healthy and gingivitis combined)
out5 = REVIEW_DIR / f"{prefix}reliability_5cat"
out5.mkdir(parents=True, exist_ok=True)
labels5 = labels.assign(status=collapse5(labels["status"]))
key5 = key.assign(truth_status=collapse5(key["truth_status"]))
compare5 = {k: collapse5(v) for k, v in compare.items()}
rep5 = reliability_report(labels5, key5, compare5)
rep5["methods"].to_csv(out5 / "methods_vs_reviewers.csv", index=False)
wide5 = labels5.pivot_table(index="visit_id", columns="reviewer", values="status", aggfunc="first")
vh5 = agreement_vs_humans(wide5, compare5, n_boot=a.n_boot, margin=a.margin)
vh5.to_csv(out5 / "agreement_vs_humans.csv", index=False)
print(f"\nfive categories: Fleiss kappa={rep5['fleiss_kappa']:.3f}")
print(vh5[vh5["kind"] != "human"].drop(columns=["margin"]).round(3).to_string(index=False))

# ---- MLflow (docs/mlops.md): headline numbers per method and the acceptance verdicts
from health_transformation_lab_nlp.tracking import track  # noqa: E402

with track("13_reliability", "reliability", simulated=a.simulated,
           params={"n_boot": a.n_boot, "margin": a.margin, "reviewers": rep["n_reviewers"], "charts": rep["n_visits"]}) as run:
    run.log_metrics({"fleiss_kappa": rep["fleiss_kappa"], "fleiss_kappa_5cat": rep5["fleiss_kappa"],
                     "consensus_reached": rep["consensus_reached"]})
    for r in vh[vh["kind"] == "method"].itertuples():
        key_ = r.rater.replace(":", "__")
        run.log_metrics({f"kappa_vs_humans__{key_}": r.mean_kappa_vs_humans, f"diff_vs_human_bar__{key_}": r.diff_vs_human_bar})
        run.set_tags({f"verdict__{key_}": r.verdict})
    for f in (out / "methods_vs_reviewers.csv", out / "agreement_vs_humans.csv", out5 / "agreement_vs_humans.csv"):
        run.log_artifact(f)
