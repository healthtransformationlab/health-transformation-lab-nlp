"""Databricks LLM judges end to end: evaluate on the review set, then monitor live traffic (docs/mlops.md).

    # 1. Offline: one MLflow evaluation run per method on the reviewed charts, with
    #    the custom AAP judge, the built-in Guidelines judge, the PHI scan and
    #    agreement with reviewer consensus side by side.
    python scripts/25_judge_monitoring.py eval --judge-model databricks:/<endpoint> [--method ai:tfidf_logreg]
    python scripts/25_judge_monitoring.py eval --simulated          # dry run, no LLM

    # 2. Production: register the judges on the experiment and score a sample of
    #    live traces from the serving endpoint (Databricks tracking only).
    python scripts/25_judge_monitoring.py start --judge-model databricks:/<endpoint> \
        --experiment-id <id> --sample-rate 0.1
    python scripts/25_judge_monitoring.py stop --experiment-id <id>

With --simulated the AAP judge is simulated and the Guidelines judge is skipped
(it needs an LLM); the PHI scan and reviewer agreement are real. Runs are tagged
simulated. Synthetic data only: the review set has passed the de-identification gate.
"""

import argparse
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import mlflow_judge as mj
from health_transformation_lab_nlp import note_set
from health_transformation_lab_nlp.paths import DATASETS_DIR, REVIEW_DIR

ap = argparse.ArgumentParser()
ap.add_argument("action", choices=["eval", "start", "stop"])
ap.add_argument("--judge-model", default=None, help="e.g. databricks:/<serving endpoint>")
ap.add_argument("--simulated", action="store_true", help="simulated AAP judge; no LLM calls")
ap.add_argument("--simulated-review", action="store_true", help="use the simulated reviewers' consensus")
ap.add_argument("--method", default=None, help="one method, e.g. ai:tfidf_logreg (default: all)")
ap.add_argument("--limit", type=int, default=None, help="charts per method")
ap.add_argument("--experiment-id", default=None)
ap.add_argument("--sample-rate", type=float, default=0.1, help="share of live traces the LLM judges score")
a = ap.parse_args()

if a.action == "stop":
    print("stopped:", mj.stop_monitoring(a.experiment_id))
    raise SystemExit
if not a.simulated and not a.judge_model:
    raise SystemExit("--judge-model is required (or --simulated for a dry run)")
if a.action == "start":
    if a.simulated:
        raise SystemExit("monitoring needs a real judge model; there is nothing to simulate on live traffic")
    print("monitoring started:", mj.start_monitoring(a.judge_model, a.experiment_id, a.sample_rate))
    raise SystemExit

rel = REVIEW_DIR / ("simulated_reliability" if (a.simulated_review or a.simulated) else "reliability")
consensus = pd.read_csv(rel / "consensus.csv").set_index("visit_id")["consensus"]
notes = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv").set_index("visit_id")["note_text"]
results = []
for f in note_set.prediction_files(DATASETS_DIR)[0]:   # #467: only runs on the current review notes
    method = Path(f).stem.removeprefix("ai_predictions_")
    if a.method and method != a.method.removeprefix("ai:"):
        continue
    p = pd.read_csv(f)
    p = p[p["visit_id"].isin(consensus.index) & (consensus.reindex(p["visit_id"]).to_numpy() != "no_consensus")]
    if a.limit:
        p = p.head(a.limit)
    rows = pd.DataFrame({"visit_id": p["visit_id"], "note": notes.reindex(p["visit_id"]).to_numpy(),
                         "pred": p["pred"], "truth": consensus.reindex(p["visit_id"]).to_numpy()})
    judge = None if a.simulated else mj.make_perio_judge(a.judge_model)
    extra = [mj.no_phi_in_note] + ([] if a.simulated else [mj.make_guidelines_judge(a.judge_model)])
    res = mj.evaluate_predictions(rows, judge=judge, method=f"ai:{method}", simulated=a.simulated,
                                  extra_scorers=extra)
    results.append({"method": f"ai:{method}", "n": res["n"], "run_id": res["run_id"], **res["metrics"]})
    print(f"ai:{method}: n={res['n']} run={res['run_id']}")

out = REVIEW_DIR / ("simulated_judge_eval.csv" if a.simulated else "judge_eval.csv")
pd.DataFrame(results).to_csv(out, index=False)
print("wrote", out, "(SIMULATED judge)" if a.simulated else "")
