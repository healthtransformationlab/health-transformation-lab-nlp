"""Run every analysis part under a named preset and under the defaults (repo_v2), side by side (spec 032 US7, #446).

    python scripts/58_preset.py [--preset exploratory_1] [--people 1200] [--patients 6000] [--seed 42] [--n-boot 0]

Presets live in health_transformation_lab_nlp/analysis_presets.yaml (docs/presets.md): `repo_v2` is the code's defaults
(spec 032 US8, #448), `repo_v1` the defaults before it, `exploratory_1` common choices of published record studies turned
on together (repo_v2 with a split by visit). For the preset and for repo_v2 this
generates the synthetic visit-level study set (`--people`) and the synthetic Open Dental extract (`--patients`, one
generator seed), runs every part (presets.run_preset) and writes, one file per part, to data/datasets/presets/:

    synthetic_preset_<name>_settings.csv                 every setting: the default (repo_v2), the preset's, changed or not
    synthetic_preset_<name>_visits_left_out.csv          visits left out of the study set, by reason
    synthetic_preset_<name>_visits_agreement.csv         each source's agreement with the synthetic truth (score())
    synthetic_preset_<name>_prevalence.csv               share in each status group by clinic, at each grouping
    synthetic_preset_<name>_tooth_loss_left_out.csv      teeth left out of the tooth-loss model, by reason
    synthetic_preset_<name>_tooth_loss_scores.csv        AUC, Brier and calibration slope of the two models
    synthetic_preset_<name>_tooth_loss_validation.csv    how the model was validated (patients in both parts)
    synthetic_preset_<name>_tooth_loss_stage_recount.csv stage III vs IV under the preset's rules
    synthetic_preset_<name>_classifier.csv               the visit-level status classifier, 5level and 3level
    synthetic_preset_<name>_consistency.csv              chart consistency by group
    synthetic_preset_<name>_icc.csv                      the CAL reliability ICC (when the preset turns it on)

To keep the run to minutes it uses one generator seed and no bootstrap intervals (--n-boot 0), where
scripts/51_tooth_loss_model.py uses five seeds and 1000 resamples (both use 6000 patients). Every number is SYNTHETIC:
agreement with a synthetic answer key, not a finding about any practice or patient. Needs the `ml` extra (xgboost). The other
committed results don't change: a preset run writes only these files.
"""

import argparse

import pandas as pd

from health_transformation_lab_nlp import presets, telemetry
from health_transformation_lab_nlp.paths import DATASETS_DIR

ap = argparse.ArgumentParser()
ap.add_argument("--preset", default="exploratory_1", help="a preset in analysis_presets.yaml")
ap.add_argument("--people", type=int, default=1200, help="synthetic people in the visit-level study set")
ap.add_argument("--patients", type=int, default=6000,
                help="synthetic patients in the Open Dental extract (as script 51)")
ap.add_argument("--seed", type=int, default=42, help="generator seed (one, for both data sets)")
ap.add_argument("--n-boot", type=int, default=0, help="bootstrap resamples for the tooth-loss intervals")
args = ap.parse_args()
names = [args.preset] if args.preset == presets.BASE_PRESET else [args.preset, presets.BASE_PRESET]
for name in names:
    presets.load_preset(name)                 # fail at once, naming it, before any work

telemetry.setup()
telemetry.start_script("58_preset", data_label="synthetic")
out_dir = DATASETS_DIR / "presets"
out_dir.mkdir(parents=True, exist_ok=True)
runs = {}
for name in names:
    runs[name] = presets.run_preset(name, n_people=args.people, n_patients=args.patients, seed=args.seed,
                                    n_boot=args.n_boot)
    for part, df in runs[name].items():
        path = out_dir / f"synthetic_preset_{name}_{part}.csv"
        df.round(10).to_csv(path, index=False)
        print(f"wrote {path}")


def side_by_side(part: str, keys: list[str], value: str) -> pd.DataFrame:
    frames = [runs[n][part].set_index(keys)[value].rename(n) for n in names if part in runs[n]]
    return pd.concat(frames, axis=1)


print(f"\nSYNTHETIC: {args.people} people (visits), {args.patients} patients (tooth loss), generator seed {args.seed}, "
      f"{args.n_boot} bootstrap resamples")
s = runs[args.preset]["settings"]
print(f"\nSettings ({presets.BASE_PRESET} -> preset):")
print(s.assign(is_changed=s["is_changed"].map({True: "yes", False: "no"}))
      .drop(columns=["preset_name", "data_label"]).to_string(index=False))

print("\nVisits left out of the study set:")
print(side_by_side("visits_left_out", ["reason_name"], "visit_count").to_string())

for name in names:
    a = runs[name]["visits_agreement"]
    a = a[a["status_group"].isna() | (a["status_group"] == "")]
    print(f"\nSYNTHETIC agreement with the synthetic truth, {name} (absent_code "
          f"{presets.load_preset(name)['absent_code']}):")
    print(a.pivot_table(index="method_name", columns=["grouping", "metric"], values="value")
          .loc[:, (slice(None), ["macro_f1", "sensitivity", "specificity"])].round(3).to_string())

sc = side_by_side("tooth_loss_scores", ["label_set", "feature_set", "model", "eval_set", "metric"], "value")
both = side_by_side("tooth_loss_validation", ["label_set", "feature_set"], "people_in_both_count")
print("\nSYNTHETIC tooth-loss model, headline scores (held-out teeth):")
print(sc.xs("held_out", level="eval_set").round(3).to_string())
print("patients in both the training and the test part:")
print(both.to_string())

cl = pd.concat([runs[n]["classifier"].assign(preset=n) for n in names], ignore_index=True)
print("\nSYNTHETIC visit-level status classifier:")
print(cl[["preset", "scheme", "split_unit", "test_share", "cv_folds", "accuracy", "macro_f1",
          "people_in_both_count"]].round(3).to_string(index=False))
if (cl["people_in_both_count"] > 0).any() or (both > 0).any().any():
    print(f"WARNING: {presets.VISIT_SPLIT_WARNING}.")

print("\nSYNTHETIC stage III vs IV (all patients, model-free rules):")
st = side_by_side("tooth_loss_stage_recount", ["label_set", "model", "rule"], "stage4_count")
print(st.xs("all", level="label_set").to_string())

if "icc" in runs[args.preset]:
    print("\nSYNTHETIC CAL reliability (placeholder variance components):")
    print(runs[args.preset]["icc"].set_index("metric_name")["value"].round(3).to_string())
