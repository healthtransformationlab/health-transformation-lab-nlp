"""Parse a Label Studio JSON export into reviewer_labels.csv and evidence_spans.csv.

    python scripts/12_import_review.py path/to/export.json
    python scripts/12_import_review.py reviewer1.json reviewer2.json reviewer3.json   # one project per reviewer
    python scripts/12_import_review.py --simulate 4     # dry run: 4 fake reviewers, files named simulated_*
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp.labelstudio import import_export, simulate_export
from health_transformation_lab_nlp.paths import DATASETS_DIR, REVIEW_DIR
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("12_import_review", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("exports", nargs="*")
ap.add_argument("--simulate", type=int, metavar="N_REVIEWERS")
a = ap.parse_args()

if a.simulate:
    tasks = json.loads((DATASETS_DIR / "review_tasks.json").read_text())
    key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path = REVIEW_DIR / "simulated_labelstudio_export.json"
    path.write_text(json.dumps(simulate_export(tasks, key, a.simulate)))
    labels, spans = import_export(path, REVIEW_DIR)
else:
    if not a.exports:
        ap.error("give one or more Label Studio JSON exports, or --simulate N")
    merged = []
    for f in a.exports:
        merged.extend(json.loads(Path(f).read_text()))
    sim = all("simulated" in Path(f).name for f in a.exports)  # never let a dry run look real
    path = REVIEW_DIR / ("simulated_labelstudio_export_merged.json" if sim else "labelstudio_export_merged.json")
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged))
    labels, spans = import_export(path, REVIEW_DIR)
dupes = labels.duplicated(["visit_id", "reviewer"]).sum()
if dupes:
    print(f"WARNING: {dupes} charts labelled twice by the same reviewer; first one kept by the reliability step")
print(f"{len(labels)} reviews from {labels['reviewer'].nunique()} reviewers over "
      f"{labels['visit_id'].nunique()} charts; {len(spans)} evidence spans")
