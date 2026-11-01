"""Was a missing tooth lost to periodontitis? The tooth-level model on the synthetic Open Dental extract (spec 029 US3,
#371), following specs/029-tooth-loss/analysis_plan.md.

    python scripts/51_tooth_loss_model.py [--patients 6000] [--seed 42] [--stability-seeds 5] [--n-boot 1000]
                                          [--min-age N] [--third-molars]

For the main generator seed and each further stability seed (seed + 1, ...): builds the extract (open_dental), cleans
it as silver, fits logistic regression and XGBoost on both label sets (tooth_loss_model.run) and scores them on the
held-out extractions and, against the synthetic answer key, on the teeth missing at entry and the extractions without
a diagnosis. Bootstrap intervals are computed for the main seed only. Writes to data/results/ (paths.RESULTS_DIR):

    synthetic_tooth_loss_scores.csv         one row per seed, label set, feature set, model, set of teeth, metric
    synthetic_tooth_loss_calibration.csv    ten bins per seed, label set, feature set, model and set of teeth
    synthetic_tooth_loss_stage_recount.csv  patients called stage III and IV under each counting rule
    synthetic_tooth_loss_patient_stage.csv  one row per patient: teeth lost to periodontitis counted four ways
    synthetic_tooth_loss_predictions.csv    one row per tooth and model (the gold fact_tooth_loss_prediction rows)
    synthetic_tooth_loss_missing.csv        share missing per predictor, by label set and split
    synthetic_tooth_loss_eval_rows.csv      outcome and probability per scored tooth (read by r/tests/test_parity.R)

Every number is SYNTHETIC: agreement with a synthetic answer key, not a finding about any practice. Needs the `ml`
extra (xgboost). The minimum age is an open decision (analysis plan s. 3): none unless --min-age is given.
"""

import argparse

import pandas as pd

from health_transformation_lab_nlp import open_dental, telemetry
from health_transformation_lab_nlp import tooth_loss_model as tlm
from health_transformation_lab_nlp.paths import RESULTS_DIR

ap = argparse.ArgumentParser()
ap.add_argument("--patients", type=int, default=6000, help="synthetic patients per extract (analysis plan s. 6)")
ap.add_argument("--seed", type=int, default=42, help="generator seed of the main run; the model seed is fixed")
ap.add_argument("--stability-seeds", type=int, default=5, help="generator seeds in all, the main one included")
ap.add_argument("--n-boot", type=int, default=1000, help="bootstrap resamples of patients (main seed only)")
ap.add_argument("--min-age", type=int, default=None, help="open decision: no cut-off by default")
ap.add_argument("--third-molars", action="store_true", help="include third molars (a sensitivity analysis)")
args = ap.parse_args()

telemetry.setup()
telemetry.start_script("51_tooth_loss_model", data_label="synthetic")
frames: dict[str, list[pd.DataFrame]] = {}
for k in range(max(1, args.stability_seeds)):
    gen_seed = args.seed + k
    tables, truth, readings = open_dental.build_with_readings(open_dental.Params(n_patients=args.patients), gen_seed)
    x = {**open_dental.clean(tables), "radiograph_bone_level": readings}   # the reading is SIMULATED (#385)
    params = tlm.ModelParams(n_boot=args.n_boot if k == 0 else 0, min_age=args.min_age,
                             include_third_molars=args.third_molars)
    out = tlm.run(x, truth, params, generator_seed=gen_seed)
    keep = out if k == 0 else {n: out[n] for n in ("scores", "stage_recount")}   # stability: the spread only
    for name, df in keep.items():
        frames.setdefault(name, []).append(df)
    print(f"generator seed {gen_seed}: done")

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
for name, parts in frames.items():
    path = RESULTS_DIR / f"synthetic_tooth_loss_{name}.csv"
    pd.concat(parts, ignore_index=True).to_csv(path, index=False)
    print(f"wrote {path}")

s = pd.concat(frames["scores"], ignore_index=True)
main = s[(s["generator_seed"] == args.seed) & s["metric"].isin(["auc", "brier", "calibration_slope"])
         & s["model"].isin(tlm.MODELS)]
print(f"\nSYNTHETIC: {args.patients} patients per extract, generator seed {args.seed}")
print(main.pivot_table(index=["label_set", "feature_set", "model", "eval_set"], columns="metric", values="value")
      .round(3).to_string())
spread = s[s["metric"].eq("auc") & s["model"].isin(tlm.MODELS)].groupby(
    ["label_set", "feature_set", "model", "eval_set"])["value"].agg(["min", "max", "std"]).round(3)
print(f"\nSYNTHETIC AUC across {args.stability_seeds} generator seeds:\n{spread.to_string()}")
st = pd.concat(frames["stage_recount"], ignore_index=True)
print("\nSYNTHETIC stage III vs IV, main seed:")
print(st[st["generator_seed"] == args.seed].drop(columns=["generator_seed", "data_label"]).to_string(index=False))
