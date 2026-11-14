"""Run rungs from models.yaml and score them with eval/score.py.

    python scripts/03_run_ladder.py --rungs rules_baseline,structured_baseline,tfidf_logreg
    python scripts/03_run_ladder.py --rungs distilbert-base --epochs 2 --max-len 192
    python scripts/03_run_ladder.py --ladder classification     # every rung, in order

Encoder rungs need `pip install -e ".[models]"`.
"""

import argparse
import sys

import pandas as pd

from health_transformation_lab_nlp.paths import LABELS_DIR, REPO_ROOT, RESULTS_DIR
from health_transformation_lab_nlp.registry import load_registry
from health_transformation_lab_nlp.rungs import make_rung

sys.path.insert(0, str(REPO_ROOT / "eval"))
from score import score, write
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("03_run_ladder", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--rungs", help="comma-separated rung ids")
ap.add_argument("--ladder", help="run a whole ladder from models.yaml")
ap.add_argument("--epochs", type=int, default=3)
ap.add_argument("--max-len", type=int, default=None)
ap.add_argument("--batch-size", type=int, default=16)
a = ap.parse_args()

reg = load_registry()
rungs = a.rungs.split(",") if a.rungs else reg["ladders"][a.ladder]
notes = pd.read_parquet(LABELS_DIR / "labeled_notes.parquet")
split = pd.read_csv(LABELS_DIR / "split.csv")
df = notes.merge(split, on="person_id")
train, test = df[df["split"] == "train"], df[df["split"] == "test"]
print(f"train={len(train)} test={len(test)}")

hf_kwargs = dict(epochs=a.epochs, batch_size=a.batch_size)
if a.max_len:
    hf_kwargs["max_len"] = a.max_len

summary = []
for rung in rungs:
    if rung == "llm_challenger":
        print("skip llm_challenger (Databricks Model Serving; see databricks/notebooks)")
        continue
    model = make_rung(rung, reg, **hf_kwargs).fit(train)
    pred, proba = model.predict(test)
    res = score(test["label"], pred, proba, model_id=rung)
    print(f"{rung}: wrote {write(res, RESULTS_DIR)}")
    summary.append(res[res["class"] == ""].set_index("metric")["value"].rename(rung))

print()
print(pd.DataFrame(summary).round(3).to_string())
