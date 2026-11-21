"""The tooth-loss model in the multi-model evaluation format, and whether other models do better (spec 042 US4, #867).

    python scripts/78_tooth_loss_drivers.py           # write data/datasets/model_drivers/tooth_loss_*.csv and
                                                      # docs/tooth_loss_drivers.md
    python scripts/78_tooth_loss_drivers.py --check   # exit 1 if any of them is stale (refits: about an hour)
    python scripts/78_tooth_loss_drivers.py --page-only [--check]   # the page alone, from the committed CSVs
    [--patients 6000] [--seed 42] [--stability-seeds 5] [--n-boot 1000]   # the defaults of scripts/51

Rebuilds the synthetic Open Dental extract as scripts/51_tooth_loss_model.py does, fits the analysis plan's two models
exactly as tooth_loss_model.run does and the post-hoc candidates (outside the plan; is_prespecified = False) on the
same split, and scores them on the same held-out teeth. CPU only, about an hour with the defaults. Method:
health_transformation_lab_nlp/tooth_loss_drivers.py. Every number is SYNTHETIC.
"""

import argparse
import sys
import tempfile
from pathlib import Path

from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp import tooth_loss_drivers as tld

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true", help="exit 1 if a committed output differs from a fresh build")
ap.add_argument("--patients", type=int, default=6000)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--stability-seeds", type=int, default=5, help="generator seeds in all, the main one included")
ap.add_argument("--n-boot", type=int, default=1000, help="bootstrap resamples of patients (main seed)")
ap.add_argument("--page-only", action="store_true", help="redraw docs/tooth_loss_drivers.md from the committed CSVs")
a = ap.parse_args()

telemetry.setup()
telemetry.start_script("78_tooth_loss_drivers", data_label="synthetic")

new = {}
if a.page_only:
    new[tld.DETAILS_DOC] = tld.details_markdown(tld.read_built(n_boot=a.n_boot))
else:
    built = tld.build(a.patients, a.seed, a.stability_seeds, a.n_boot)
    with tempfile.TemporaryDirectory() as tmp:
        for name in tld.ALL_TABLES:
            p = Path(tmp) / f"{name}.csv"
            built[name].to_csv(p, index=False, float_format="%.6g")
            new[tld.OUT_DIR / f"{name}.csv"] = p.read_text()
        # the page is drawn from the tables as written, so --page-only redraws it identically
        new[tld.DETAILS_DOC] = tld.details_markdown(tld.read_built(Path(tmp), a.n_boot))
stale = [p for p, t in new.items() if not p.exists() or p.read_text() != t]
if a.check:
    sys.exit(f"stale: {', '.join(p.name for p in stale)}; run python scripts/78_tooth_loss_drivers.py" if stale else 0)
tld.OUT_DIR.mkdir(parents=True, exist_ok=True)
for p in stale:
    p.write_text(new[p])
print("updated:", ", ".join(p.name for p in stale) or "nothing")
r = tld.read_built()["tooth_loss_model_rank"]
print("SYNTHETIC held-out AUC by model:")
print(r[r.eval_set_code.eq("held_out")].pivot_table(index="model_code", columns=["label_set_code", "feature_set_code"],
                                                     values="auc_ratio").round(3).to_string())
