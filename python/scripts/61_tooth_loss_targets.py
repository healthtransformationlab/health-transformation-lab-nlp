"""Published tooth-loss targets for the synthetic Open Dental extract (spec 037), from real public data.

    python scripts/61_tooth_loss_targets.py --data-dir /path/to/nhanes [--download] [--out DIR]

Writes two files of aggregates (no person-level data):

    nhanes/nhanes_missing_teeth_by_age.csv   NHANES 2009-2014: natural teeth lost (third molars aside) by age band,
                                             survey-weighted (six-year weight), mean and shares with none and with
                                             six or more lost, with linearized 95% CIs
    brfss/brfss_teeth_lost_by_state.csv      BRFSS 2022 via CDC's U.S. Chronic Disease Indicators (data.cdc.gov
                                             dataset hksd-2xuw): ORH01 no teeth lost at 18-64, ORH02 six or more lost
                                             at 65+, ORH03 all lost at 65+; crude %, each state and the US

The extract's partial and complete tooth loss by age is checked against the first, its state scaling against the
second. cdc.gov must be reachable (as for 38_nhanes_perio.py).
"""
import argparse
import json
import urllib.request
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.nhanes import CYCLES, download, missing_teeth_by_age, read_xpt
from health_transformation_lab_nlp.paths import DATASETS_DIR

CDI = ("https://data.cdc.gov/resource/hksd-2xuw.json?questionid={q}&yearstart=2022&stratificationid1=OVR"
       "&datavaluetypeid=CRDPREV&$limit=100")
QUESTIONS = {"ORH01": "no_teeth_lost_18_64_pct", "ORH02": "six_or_more_lost_65_pct", "ORH03": "all_lost_65_pct"}

ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", type=Path, required=True)
ap.add_argument("--download", action="store_true")
ap.add_argument("--out", type=Path, default=DATASETS_DIR)
args = ap.parse_args()
telemetry.setup()
telemetry.start_script("61_tooth_loss_targets", data_label="public")
if args.download:
    download(args.data_dir)

den = pd.concat([read_xpt(args.data_dir / f"OHXDEN_{s}.xpt")[0] for s in CYCLES], ignore_index=True)
demo = pd.concat([read_xpt(args.data_dir / f"DEMO_{s}.xpt")[0] for s in CYCLES], ignore_index=True)
demo["WTMEC2YR"] = demo["WTMEC2YR"] / len(CYCLES)          # pooled cycles: six-year weight
by_age = missing_teeth_by_age(den, demo)
(args.out / "nhanes").mkdir(parents=True, exist_ok=True)
by_age.to_csv(args.out / "nhanes" / "nhanes_missing_teeth_by_age.csv", index=False)
print("NHANES 2009-2014, natural teeth lost by age band (REAL public data; weighted):")
print(by_age.round(1).to_string(index=False))

states = None
for q, col in QUESTIONS.items():
    with urllib.request.urlopen(CDI.format(q=q), timeout=60) as r:
        rows = json.load(r)
    d = pd.DataFrame([{"state_code": x["locationabbr"], col: float(x["datavalue"])} for x in rows
                      if x.get("datavalue") not in (None, "")])
    states = d if states is None else states.merge(d, on="state_code", how="outer")
states = states.sort_values("state_code")
(args.out / "brfss").mkdir(parents=True, exist_ok=True)
states.to_csv(args.out / "brfss" / "brfss_teeth_lost_by_state.csv", index=False)
print("\nBRFSS 2022, teeth lost by state (REAL public aggregates, crude %):")
print(states[states["state_code"] == "US"].to_string(index=False), f"\n{len(states)} rows")
