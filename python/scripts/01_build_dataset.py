"""Synthea CSV (or generated stand-in) -> OMOP parquet + labeled notes.

    python scripts/01_build_dataset.py                  # uses synthea/output/csv if present
    python scripts/01_build_dataset.py --n-people 200   # stand-in population size
    python scripts/01_build_dataset.py --no-leak        # Assessment line never states status
"""

import argparse

from health_transformation_lab_nlp.build import build
from health_transformation_lab_nlp.paths import LABELS_DIR, OMOP_DIR, SYNTHEA_CSV
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("01_build_dataset", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--n-people", type=int, default=300)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--no-leak", action="store_true")
a = ap.parse_args()
build(OMOP_DIR, LABELS_DIR, SYNTHEA_CSV, n_people=a.n_people, seed=a.seed,
      leak_assessment=not a.no_leak)
