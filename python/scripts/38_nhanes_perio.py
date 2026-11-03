"""NHANES 2009-2014 periodontal prevalence under CDC/AAP 2012 and ACES, from the public files (spec 013 G4).

    python scripts/38_nhanes_perio.py --data-dir /path/to/nhanes [--download] [--out DIR]

Real, public-domain charts (CDC/NCHS). Adults 30+ with a complete periodontal exam, plus the
edentulous; survey-weighted (six-year weights) with linearized 95% CIs. Compared with the published
figures (Eke 2018; Tay 2025): close agreement checks this repo's case definitions and survey code,
it is not a new finding. cdc.gov is not reachable from every environment: the Databricks job
`nhanes_perio` runs this with --download. Writes nhanes_prevalence.csv and, since spec 033 US4 (#500),
nhanes_edentulous_by_age.csv: complete tooth loss by age band, which sets the synthetic Open Dental extract's
edentulous share below 65 (aggregates only).
"""

import argparse
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.nhanes import (
    CYCLES,
    classify_people,
    download,
    edentulous_by_age,
    nhanes_cdc_aap_published,
    read_xpt,
    weighted_prevalence,
)
from health_transformation_lab_nlp.paths import DATASETS_DIR

ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", type=Path, required=True)
ap.add_argument("--download", action="store_true")
ap.add_argument("--out", type=Path, default=DATASETS_DIR / "nhanes")
args = ap.parse_args()
telemetry.setup()
telemetry.start_script("38_nhanes_perio", data_label="public")
if args.download:
    download(args.data_dir)
args.out.mkdir(parents=True, exist_ok=True)

people = []
for suffix in CYCLES:
    per, labels = read_xpt(args.data_dir / f"OHXPER_{suffix}.xpt")
    den, _ = read_xpt(args.data_dir / f"OHXDEN_{suffix}.xpt")
    demo, _ = read_xpt(args.data_dir / f"DEMO_{suffix}.xpt")
    people.append(classify_people(per, den, demo, labels).assign(cycle=suffix))
people = pd.concat(people, ignore_index=True)

people["w"] = people["WTMEC2YR"] / 3
people = people.rename(columns={"SDMVSTRA": "strata", "SDMVPSU": "psu"}).dropna(subset=["w"])
people = people[people["w"] > 0]
adults = people["RIDAGEYR"] >= 30
rows = []
for label, dom in {"adults30_all": adults & (people["perio_complete"] | people["edentulous"]),
                   "adults30_dentate": adults & people["perio_complete"] & ~people["edentulous"]}.items():
    for c in ("cdc_aap", "aces", "aces_no_complexity"):
        p = weighted_prevalence(people.assign(domain=dom), c)
        rows.append(p.assign(population=label, classification=c, n_domain=int(dom.sum())))
res = pd.concat(rows, ignore_index=True)
res.to_csv(args.out / "nhanes_prevalence.csv", index=False)
by_age = edentulous_by_age(people)
by_age.to_csv(args.out / "nhanes_edentulous_by_age.csv", index=False)
nhanes_cdc_aap_published().to_csv(args.out / "nhanes_published.csv", index=False)
print("NHANES 2009-2014, adults 30+ (REAL public data; weighted %, 95% CI):")
print(res.round(1).to_string(index=False))
print("\ncomplete tooth loss by age band, adults 30+ (REAL public data; weighted %, 95% CI):")
print(by_age.round(1).to_string(index=False))
print("\npublished, for comparison:")
print(nhanes_cdc_aap_published().to_string(index=False))
