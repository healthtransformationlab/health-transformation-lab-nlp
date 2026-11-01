"""MedGemma accuracy per field: status, grade, extent (spec 004 US6, #132).

    python scripts/52_medgemma_field_accuracy.py               # every committed MedGemma run
    python scripts/52_medgemma_field_accuracy.py --simulated   # the simulated dry run (placeholder reader)

Reads data/datasets/[simulated_]llm_details_medgemma-*.csv (one per run, from 11_ai_predict.py) and the
reference answers (answer_key/reference_answers.csv, 51_reference_answers.py). Writes
data/datasets/ladder/[simulated_]medgemma_field_accuracy.csv: run, field, n, correct, accuracy, 95% Wilson CI.
Each run is logged to MLflow (tracking.track; a no-op without mlflow) as field_accuracy_<field> and
field_n_<field>, with the table as an artifact. r/R/17_spec004.R recomputes the table (parity test).

Runs that didn't read every review note (a --limit run) are skipped. Synthetic notes and generator truth: not
evidence about either model on real records. --simulated rows come from placeholder error rates and say nothing
about MedGemma (the simulated reader returns no grade or extent at all).
"""

import argparse
import glob
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.reference_answers import field_accuracy, field_metrics
from health_transformation_lab_nlp.tracking import track

ap = argparse.ArgumentParser()
ap.add_argument("--simulated", action="store_true", help="score the simulated MedGemma reader (dry run)")
a = ap.parse_args()
prefix = "simulated_" if a.simulated else ""

ref_file = DATASETS_DIR / "answer_key" / "reference_answers.csv"
if not ref_file.exists():
    raise SystemExit(f"no {ref_file}; run scripts/51_reference_answers.py first")
ref = pd.read_csv(ref_file, keep_default_na=False)

tables = []
for f in sorted(glob.glob(str(DATASETS_DIR / f"{prefix}llm_details_medgemma-*.csv"))):
    run = Path(f).stem.removeprefix(f"{prefix}llm_details_")
    try:
        t = field_accuracy(pd.read_csv(f), ref)
    except ValueError as e:
        print(f"skip {run}: {e}")
        continue
    tables.append(t.assign(run=run)[["run", *t.columns]])
if not tables:
    raise SystemExit(f"no complete {prefix}llm_details_medgemma-*.csv to score")

table = pd.concat(tables, ignore_index=True)
out = DATASETS_DIR / "ladder" / f"{prefix}medgemma_field_accuracy.csv"
out.parent.mkdir(parents=True, exist_ok=True)
table.to_csv(out, index=False)

for run, t in table.groupby("run", sort=False):
    with track("52_medgemma_field_accuracy", f"{'sim:' if a.simulated else ''}{run}", simulated=a.simulated,
               params={"run": run, "reference": "answer_key/reference_answers.csv"}) as r:
        r.log_metrics(field_metrics(t.drop(columns="run")))
        r.log_artifact(out)

print(table.round(3).to_string(index=False))
if a.simulated:
    print("*** SIMULATED READER: dry run, placeholder error rates; not a MedGemma result ***")
print("wrote", out, "(synthetic notes and generator truth; not evidence about real records)")
