"""Cost-effectiveness table and chart.

    python scripts/16_cost_effectiveness.py              # real judgments
    python scripts/16_cost_effectiveness.py --simulated  # dry run

Writes data/corpus/[simulated_]cost_effectiveness.csv, judge_calibration.json and
a frontier chart PNG.
"""

import argparse
import json

import matplotlib
import sys
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("16_cost_effectiveness", data_label="simulated" if "--simulated" in sys.argv else "synthetic")

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

from health_transformation_lab_nlp.cost_effectiveness import (
    calibrate_judge,
    corrected_accuracy,
    frontier,
    judge_cost,
)
from health_transformation_lab_nlp.paths import CORPUS_DIR, COSTS_YAML

ap = argparse.ArgumentParser()
ap.add_argument("--simulated", action="store_true")
a = ap.parse_args()
prefix = "simulated_" if a.simulated else ""

costs = yaml.safe_load(COSTS_YAML.read_text())
meta = json.loads((CORPUS_DIR / "corpus_meta.json").read_text())
N = costs["corpus_notes"]
gold = pd.read_csv(CORPUS_DIR / f"{prefix}judgments_gold.csv")
corp = pd.read_csv(CORPUS_DIR / f"{prefix}judgments_corpus.csv")
bench = pd.read_csv(CORPUS_DIR / "cost_benchmark.csv").set_index("method")

cal = calibrate_judge(gold)
judged_total = len(gold) + len(corp)
cal["judge_cost_usd_this_run"] = judge_cost(judged_total, meta["avg_note_tokens"], costs["judge"])
(CORPUS_DIR / f"{prefix}judge_calibration.json").write_text(json.dumps(cal, indent=1))

rows = []
for m, s in corp.groupby("method"):
    acc = corrected_accuracy(s, gold)
    rows.append({"method": m, **acc, "cost_usd": float(bench.loc[m, "cost_usd"]),
                 "throughput_source": bench.loc[m, "throughput_source"]})
t = frontier(pd.DataFrame(rows), N)
t.to_csv(CORPUS_DIR / f"{prefix}cost_effectiveness.csv", index=False)

fig, ax = plt.subplots(figsize=(9, 5.5))
for _, r in t.iterrows():
    color = "#9ca3af" if r["dominated"] else "#2563eb"
    ax.errorbar(max(r["cost_usd"], 0.01), r["accuracy_est"],
                yerr=[[r["accuracy_est"] - r["ci_low"]], [r["ci_high"] - r["accuracy_est"]]],
                fmt="o", color=color, capsize=3)
    ax.annotate(r["method"], (max(r["cost_usd"], 0.01), r["accuracy_est"]), textcoords="offset points",
                xytext=(6, 6), fontsize=10)
fr = t[~t["dominated"]].sort_values("cost_usd")
ax.plot(fr["cost_usd"].clip(lower=0.01), fr["accuracy_est"], color="#2563eb", lw=1, alpha=0.6)
ax.set_xscale("log")
ax.set_xlabel(f"Cost to classify {N:,} notes (USD, log scale; ILLUSTRATIVE prices)", fontsize=11)
ax.set_ylabel("Accuracy, judge-estimated and corrected (95% CI)", fontsize=11)
ttl = "Cost-effectiveness frontier" + (" (SIMULATED dry run)" if a.simulated else "")
ax.set_title(ttl, fontsize=13)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(CORPUS_DIR / f"{prefix}cost_effectiveness.png", dpi=150)

if a.simulated:
    print("*** SIMULATED: dry run, not a result ***")
print(f"judge: sensitivity {cal['sensitivity']:.3f}, specificity {cal['specificity']:.3f} "
      f"(n={cal['n_pos']}+{cal['n_neg']}), not-determinable {cal['nd_rate']:.1%}; "
      f"judging this run ~${cal['judge_cost_usd_this_run']:.2f} (illustrative)")
cols = ["method", "accuracy_est", "ci_low", "ci_high", "cost_usd", "usd_per_1k_correct", "dominated",
        "icer_usd_per_extra_correct_note", "compared_to"]
with pd.option_context("display.float_format", "{:.4g}".format):
    print(t[cols].to_string(index=False))

from health_transformation_lab_nlp.tracking import track  # noqa: E402

with track("16_cost_effectiveness", "cost-effectiveness", simulated=bool(prefix),
           params={"corpus_notes": costs["corpus_notes"], "prices": "ILLUSTRATIVE"}) as run:
    for r in t.itertuples():
        k = str(r.method).replace(":", "__")
        run.log_metrics({f"accuracy_est__{k}": r.accuracy_est, f"cost_usd__{k}": r.cost_usd})
    run.log_artifact(CORPUS_DIR / f"{prefix}cost_effectiveness.csv")
