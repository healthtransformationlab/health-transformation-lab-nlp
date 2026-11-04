"""Was a missing tooth lost to periodontitis? The tooth-level model on the synthetic Open Dental extract (spec 029 US3,
#371), following specs/029-tooth-loss/analysis_plan.md.

    python scripts/51_tooth_loss_model.py [--patients 6000] [--seed 42] [--stability-seeds 5] [--n-boot 1000]
                                          [--min-age N] [--third-molars]
                                          [--split-unit person|visit] [--test-share 0.2] [--cv-folds K]
                                          [--start-date 2018-01-01] [--planned-window-days 548|none]
                                          [--stage-recount]

For the main generator seed and each further stability seed (seed + 1, ...): builds the extract (open_dental), cleans
it as silver, fits logistic regression and XGBoost on both label sets (tooth_loss_model.run) and scores them on the
held-out extractions and, against the synthetic answer key, on the teeth missing at entry and the extractions without
a diagnosis. Bootstrap intervals are computed for the main seed only. Writes to data/results/ (paths.RESULTS_DIR):

    synthetic_tooth_loss_scores.csv         one row per seed, label set, feature set, model, set of teeth, metric
    synthetic_tooth_loss_calibration.csv    ten bins per seed, label set, feature set, model and set of teeth
    synthetic_tooth_loss_stage_recount.csv  (with --stage-recount) patients called stage III and IV under each rule
    synthetic_tooth_loss_patient_stage.csv  (with --stage-recount) one row per patient: teeth lost to periodontitis, the
                                            teeth and occluding pairs left, and stage IV under each rule
    synthetic_tooth_loss_predictions.csv    one row per tooth and model (the gold fact_tooth_loss_prediction rows)
    synthetic_tooth_loss_missing.csv        share missing per predictor, by label set and split
    synthetic_tooth_loss_eval_rows.csv      outcome and probability per scored tooth (read by r/tests/test_parity.R)

Every number is SYNTHETIC: agreement with a synthetic answer key, not a finding about any practice. Needs the `ml`
extra (xgboost). No age cut-off by default since 029 US10 (#529); --min-age 18 or 30 as sensitivity settings.

Defaults (spec 032 US8, #448; preset repo_v2): an 80/20 split by patient, 5-fold tuning of XGBoost, and teeth lost (or
first charted) from 2018-01-01. The defaults before it (preset repo_v1): --test-share 0.3 --cv-folds 0 --start-date ""
(those results are then written beside these, with their own prefix).

Tooth level only (029 US10, #529): the model gives one probability per missing tooth; summing them to the person is a
separate, later decision. The stage III vs IV recount (stage_recount, patient_stage, stage_probabilities) is written
only with --stage-recount (the parity inputs use it).

Planned extractions (029 US9, #507; US10): a planned periodontal extraction never done counts as a label only when the
tooth is recorded missing at a later visit within --planned-window-days of its most recent plan (548, 1.5 years); --planned-window-days none is the
rule before it (every planned extraction with a diagnosis counts, the tooth in the mouth or not), a sensitivity
setting whose files are written as synthetic_tooth_loss_planned<days|any>_<name>.csv beside the defaults.

Validation settings (spec 032 US5): --split-unit visit holds out random teeth instead of patients and reports how many
patients fall in both parts (a leak that flatters the score; never the default); --cv-folds K tunes XGBoost by K-fold
cross-validation (tooth_loss_model.XGB_GRID). With any of the three away from its default the files are written as
synthetic_tooth_loss_<split>_<share>_cv<K>_<name>.csv, beside the default results rather than over them, with a
..._validation.csv saying how; with the defaults the validation is printed only.
"""

import argparse

import pandas as pd

from health_transformation_lab_nlp import open_dental, telemetry, tooth_loss
from health_transformation_lab_nlp import tooth_loss_model as tlm
from health_transformation_lab_nlp.paths import RESULTS_DIR

ap = argparse.ArgumentParser()
ap.add_argument("--patients", type=int, default=6000, help="synthetic patients per extract (analysis plan s. 6)")
ap.add_argument("--seed", type=int, default=42, help="generator seed of the main run; the model seed is fixed")
ap.add_argument("--stability-seeds", type=int, default=5, help="generator seeds in all, the main one included")
ap.add_argument("--n-boot", type=int, default=1000, help="bootstrap resamples of patients (main seed only)")
ap.add_argument("--min-age", type=int, default=tlm.DEFAULT.min_age or 0,
                help="minimum age, a sensitivity setting (analysis plan s. 3); 0 (the default since 029 US10): none")
ap.add_argument("--third-molars", action="store_true", help="include third molars (a sensitivity analysis)")
ap.add_argument("--split-unit", default=tlm.DEFAULT.split_unit, choices=tlm.SPLIT_UNITS,
                help="hold out patients (default) or random teeth (reports the patients in both parts)")
ap.add_argument("--test-share", type=float, default=tlm.DEFAULT.test_share, help="held-out share")
ap.add_argument("--cv-folds", type=int, default=tlm.DEFAULT.cv_folds or 0,
                help="tune XGBoost by K-fold cross-validation; 0 for no tuning")
ap.add_argument("--start-date", default=tlm.DEFAULT.start_date,
                help='ISO date: leave out teeth lost (or first charted) before it; "" for every year')
ap.add_argument("--stage-recount", action="store_true",
                help="also write the stage III vs IV recount (029 US10: not in the default results)")
ap.add_argument("--planned-window-days", default=str(tlm.DEFAULT.planned_window_days),
                help="a planned extraction counts if the tooth is missing within this many days; none: any planned")
args = ap.parse_args()
window = None if args.planned_window_days.lower() == "none" else int(args.planned_window_days)
validation = {"split_unit": args.split_unit, "test_share": args.test_share, "cv_folds": args.cv_folds or None}
changed = any(getattr(tlm.DEFAULT, k) != v for k, v in validation.items())
prefix = (f"synthetic_tooth_loss_{args.split_unit}_{args.test_share:g}_cv{args.cv_folds}_" if changed
          else "synthetic_tooth_loss_")
if window != tlm.DEFAULT.planned_window_days:          # beside the default results, never over them
    prefix += f"planned{'any' if window is None else window}_"

telemetry.setup()
telemetry.start_script("51_tooth_loss_model", data_label="synthetic")
frames: dict[str, list[pd.DataFrame]] = {}
for k in range(max(1, args.stability_seeds)):
    gen_seed = args.seed + k
    tables, truth, readings = open_dental.build_with_readings(open_dental.Params(n_patients=args.patients), gen_seed)
    x = {**open_dental.clean(tables), "radiograph_bone_level": readings}   # the reading is SIMULATED (#385)
    params = tlm.ModelParams(n_boot=args.n_boot if k == 0 else 0, min_age=args.min_age or None,
                             include_third_molars=args.third_molars, start_date=args.start_date or None,
                             planned_window_days=window, **validation)
    out = tlm.run(x, truth, params, generator_seed=gen_seed)
    if k == 0:                     # who was left out, and why (a tooth with no recorded age, once a cut-off applies)
        teeth = tlm.with_first_exam_date(tooth_loss.tooth_table(x), x)
        print(f"generator seed {gen_seed}: teeth {tlm.exclusions(teeth, params)}")
        print(f"generator seed {gen_seed}: validation\n"
              f"{out['validation'].drop(columns=['data_label']).to_string(index=False)}")
    if not changed:                # the default results keep their files; the validation is printed above
        out = {n: df for n, df in out.items() if n != "validation"}
    out = tlm.outputs_to_write(out, args.stage_recount)       # tooth level only by default (029 US10)
    keep = out if k == 0 else {n: out[n] for n in ("scores", "stage_recount") if n in out}   # stability: the spread
    for name, df in keep.items():
        frames.setdefault(name, []).append(df)
    print(f"generator seed {gen_seed}: done")

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
for name, parts in frames.items():
    path = RESULTS_DIR / f"{prefix}{name}.csv"
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
if args.stage_recount:
    st = pd.concat(frames["stage_recount"], ignore_index=True)
    print("\nSYNTHETIC stage III vs IV, main seed:")
    print(st[st["generator_seed"] == args.seed].drop(columns=["generator_seed", "data_label"]).to_string(index=False))
