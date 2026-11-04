"""LLM judge: calibrate on the human-reviewed charts, then judge a sample of each
method's predictions on the corpus.

    # real judges (any OpenAI-compatible endpoint, e.g. Databricks Model Serving).
    # Several candidates are calibrated on the reviewed charts (bake-off, spec 002);
    # the best by kappa that is not the same family as an evaluated LLM judges the corpus.
    export JUDGE_BASE_URL=https://<workspace>/serving-endpoints JUDGE_API_KEY=...
    python scripts/15_judge.py --backend openai \
        --judges endpoint-a=familyA,endpoint-b=familyB --classifier-families familyC

    # dry run, no LLM (verdicts simulated from the generator truth; output marked simulated)
    python scripts/15_judge.py --backend simulated --simulated-review

Only de-identified notes are sent. Writes data/corpus/judgments_gold.csv and
judgments_corpus.csv (prefixed simulated_ for the simulated backend).
"""

import argparse
import glob
from pathlib import Path

import pandas as pd
import yaml

from health_transformation_lab_nlp import note_set
from health_transformation_lab_nlp.cost_effectiveness import bakeoff
from health_transformation_lab_nlp.judge import PROMPT_VERSION, OpenAIJudge, SimulatedJudge
from health_transformation_lab_nlp.paths import CORPUS_DIR, COSTS_YAML, DATASETS_DIR, REVIEW_DIR

ap = argparse.ArgumentParser()
ap.add_argument("--backend", choices=["openai", "mlflow", "simulated"], required=True,
                help="openai: OpenAI-compatible endpoint; mlflow: MLflow GenAI make_judge, judges given as "
                     "model URIs (databricks:/<endpoint>, openai:/<model>); simulated: dry run")
ap.add_argument("--simulated-review", action="store_true",
                help="calibrate against simulated reviewer consensus (dry run)")
ap.add_argument("--per-method", type=int, default=None, help="corpus notes judged per method")
ap.add_argument("--seed", type=int, default=5)
ap.add_argument("--judges", default=None,
                help="candidate judges as name=family,... (openai: endpoint names). "
                     "Simulated default: three judges with different error profiles")
ap.add_argument("--classifier-families", default="",
                help="model families of LLMs being evaluated; a judge of the same family is not selected")
a = ap.parse_args()

cfg = yaml.safe_load(COSTS_YAML.read_text())["judge"]
n_per = a.per_method or cfg["sample_per_method"]
sim = a.backend == "simulated"
prefix = "simulated_" if (sim or a.simulated_review) else ""

# ---- calibration set: each method's prediction on each reviewed chart vs reviewer consensus
rel_dir = REVIEW_DIR / ("simulated_reliability" if a.simulated_review else "reliability")
consensus = pd.read_csv(rel_dir / "consensus.csv").set_index("visit_id")["consensus"]
key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv").set_index("visit_id")
gold_rows = []
for f in note_set.prediction_files(DATASETS_DIR)[0]:   # #467: only runs on the current review notes
    m = Path(f).stem.removeprefix("ai_predictions_")
    p = pd.read_csv(f).set_index("visit_id")["pred"]
    for vid, pred in p.items():
        c = consensus.get(vid)
        if c in (None, "no_consensus") or pd.isna(c):
            continue
        gold_rows.append({"method": m, "visit_id": vid, "pred": pred, "truth": c, "note": key.loc[vid, "note_text"]})
# Calibration needs plenty of WRONG predictions to pin down specificity; good models
# rarely give them. The single-evidence-type readers (exam form, codes) are wrong often,
# so their readings on the same charts are added as calibration-only pairs.
for m in ["exam_form", "proc_codes_completed", "proc_dx_completed"]:
    for vid, pred in key[m].items():
        c = consensus.get(vid)
        if pred == "unknown" or c in (None, "no_consensus") or pd.isna(c):
            continue
        gold_rows.append({"method": f"calib:{m}", "visit_id": vid, "pred": pred, "truth": c,
                          "note": key.loc[vid, "note_text"]})
gold = pd.DataFrame(gold_rows)

# ---- corpus sample: n per method, stratified by predicted class
corpus = pd.read_parquet(CORPUS_DIR / "corpus_sample.parquet").set_index("visit_id")
corp_rows = []
for f in sorted(glob.glob(str(CORPUS_DIR / "preds_*.parquet"))):
    m = Path(f).stem.removeprefix("preds_").replace("__", ":")
    p = pd.read_parquet(f)
    frac = min(1.0, n_per / len(p))
    s = p.groupby("pred").sample(frac=frac, random_state=a.seed)   # stratified by predicted class
    for r in s.itertuples():
        corp_rows.append({"method": m, "visit_id": r.visit_id, "pred": r.pred,
                          "truth": corpus.loc[r.visit_id, "truth_status"], "note": corpus.loc[r.visit_id, "note_text"]})
corp = pd.DataFrame(corp_rows)


# Simulated candidates: (sensitivity, specificity). One strong, one lenient (says
# "correct" too easily), one weak. The lenient one shares a family with the
# simulated LLM classifier, so it can't be selected even if it scored well.
SIM_JUDGES = {"sim-judge-a": (0.95, 0.91, "fam-a"), "sim-judge-b": (0.99, 0.62, "fam-llm"),
              "sim-judge-c": (0.86, 0.84, "fam-c")}
if a.judges:
    judges = dict(x.split("=") for x in a.judges.split(","))
elif sim:
    judges = {k: v[2] for k, v in SIM_JUDGES.items()}
else:
    import os
    judges = {os.environ["JUDGE_MODEL"]: ""}
classifier_families = set(filter(None, a.classifier_families.split(","))) or ({"fam-llm"} if sim else set())
# Families of evaluated LLM rungs (e.g. MedGemma -> gemma) come from models.yaml automatically (spec 004).
from health_transformation_lab_nlp.registry import families_of, load_registry

classifier_families |= families_of(load_registry(), {r["method"] for r in gold_rows})
if classifier_families:
    print(f"judges of these families are not eligible: {sorted(classifier_families)}")


def run(df: pd.DataFrame, judge_truth_col: str, judge_name: str) -> pd.DataFrame:
    if sim:
        se, sp, _ = SIM_JUDGES[judge_name]
        judge = SimulatedJudge({i: t for i, t in enumerate(df[judge_truth_col])}, sensitivity=se,
                               specificity=sp, seed=hash(judge_name) % 1000)
        verdicts = [judge(n, p, visit_id=i) for i, (n, p) in enumerate(zip(df["note"], df["pred"]))]
        model_name = judge_name
    elif a.backend == "mlflow":
        from health_transformation_lab_nlp.mlflow_judge import MLflowJudgeAdapter
        judge = MLflowJudgeAdapter(judge_name)
        verdicts = [judge(n, p) for n, p in zip(df["note"], df["pred"])]
        model_name = judge_name
    else:
        judge = OpenAIJudge(model=judge_name)
        verdicts = [judge(n, p) for n, p in zip(df["note"], df["pred"])]
        model_name = judge.model
    out = df.drop(columns=["note"]).copy()
    out["verdict"] = [v.verdict for v in verdicts]
    out["supported_status"] = [v.supported_status for v in verdicts]
    out["quote"] = [v.quote for v in verdicts]
    out["gate_ok"] = [v.quote_ok for v in verdicts]
    out["error"] = [v.error for v in verdicts]
    out["input_tokens"] = [v.input_tokens for v in verdicts]
    out["output_tokens"] = [v.output_tokens for v in verdicts]
    out["prompt_version"], out["judge_model"] = PROMPT_VERSION, model_name
    return out


CORPUS_DIR.mkdir(parents=True, exist_ok=True)
# ---- bake-off: every candidate judges the calibration set
g_all = pd.concat([run(gold, "truth", j) for j in judges])
g_all["truly_correct"] = g_all["pred"] == g_all["truth"]
g_all.to_csv(CORPUS_DIR / f"{prefix}judgments_gold_all_candidates.csv", index=False)
bo = bakeoff(g_all, classifier_families, judges)
bo.to_csv(CORPUS_DIR / f"{prefix}judge_bakeoff.csv", index=False)
if not bo["selected"].any():
    raise SystemExit("no eligible judge: every candidate shares a family with an evaluated LLM")
chosen = bo.loc[bo["selected"], "judge_model"].iloc[0]
print("judge bake-off (kappa vs reviewer consensus):")
print(bo[["judge_model", "family", "sensitivity", "specificity", "kappa", "kappa_ci_low", "kappa_ci_high",
          "same_family_as_classifier", "selected"]].round(3).to_string(index=False))
g = g_all[g_all["judge_model"] == chosen]
g.to_csv(CORPUS_DIR / f"{prefix}judgments_gold.csv", index=False)
c = run(corp, "truth", chosen).drop(columns=["truth"])   # corpus truth is never stored with judgments
c.to_csv(CORPUS_DIR / f"{prefix}judgments_corpus.csv", index=False)
if prefix:
    print("*** SIMULATED: dry run, not a result ***")
print(f"selected judge: {chosen}")
print(f"calibration: {len(g)} judged pairs over {g['method'].nunique()} methods on reviewed charts")
print(f"corpus: {len(c)} judged predictions over {c['method'].nunique()} methods")
print(f"gate failures: gold {(~g['gate_ok']).mean():.1%}, corpus {(~c['gate_ok']).mean():.1%}")

# ---- MLflow: one run for the bake-off and corpus judging (docs/mlops.md)
from health_transformation_lab_nlp.tracking import track

with track("15_judge", f"judge-bakeoff:{chosen}", simulated=bool(prefix),
           params={"backend": a.backend, "prompt_version": PROMPT_VERSION, "candidates": ",".join(judges),
                   "chosen": chosen, "per_method": n_per}) as run:
    for r in bo.itertuples():
        run.log_metrics({f"kappa__{r.judge_model}": r.kappa, f"sensitivity__{r.judge_model}": r.sensitivity,
                         f"specificity__{r.judge_model}": r.specificity})
    for f in ("judge_bakeoff.csv", "judgments_gold.csv", "judgments_corpus.csv"):
        run.log_artifact(CORPUS_DIR / f"{prefix}{f}")
