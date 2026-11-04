"""Databricks ai_classify on the de-identified review notes (spec 017 US2).

    export DATABRICKS_HOST=... DATABRICKS_TOKEN=... DATABRICKS_WAREHOUSE_ID=<serverless warehouse id>
    python scripts/41_databricks_ai_methods.py --limit 10      # test on 10 notes
    python scripts/41_databricks_ai_methods.py                 # every review note -> data/datasets/ai_predictions_dbai-classify.csv
    python scripts/41_databricks_ai_methods.py --simulate      # dry run, no Databricks: simulated_* file only

The Llama 3.3 70B reader (US3) is the LLM reader on a Databricks endpoint:
    python scripts/11_ai_predict.py --rung llama-3.3-70b-instruct --backend openai
Settings are checked and the call count printed before anything is sent. Synthetic notes only.
"""

import argparse
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from health_transformation_lab_nlp import databricks_ai as dbai
from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--limit", type=int, default=None, help="only the first N review notes (a test)")
ap.add_argument("--batch-size", type=int, default=10)
ap.add_argument("--simulate", action="store_true", help="no Databricks: random answers, simulated_* output")
ap.add_argument("--seed", type=int, default=0, help="--simulate only")
ap.add_argument("--out", default=str(DATASETS_DIR))
a = ap.parse_args()

telemetry.setup()
telemetry.start_script("41_databricks_ai_methods", data_label="simulated" if a.simulate else "synthetic")
key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")
notes = key[["visit_id", "note_text"]].head(a.limit) if a.limit else key[["visit_id", "note_text"]]

if not a.simulate:
    try:
        dbai.check_settings()
    except RuntimeError as e:
        sys.exit(f"Not run: {e}")
e = dbai.estimate(notes, a.batch_size)
print(f"ai_classify: {e['notes']} notes in {e['statements']} statements, about {e['input_tokens']:,} input tokens"
      + (" (simulated: nothing is sent)" if a.simulate else ""))

if a.simulate:
    rng = random.Random(a.seed)
    res = pd.DataFrame({"visit_id": notes.visit_id, "pred": [rng.choice(LABELS) for _ in range(len(notes))], "error": ""})
else:
    res = dbai.run_classify(notes, batch_size=a.batch_size)

name = ("simulated_" if a.simulate else "") + "ai_predictions_dbai-classify.csv"
out = Path(a.out) / name
res[["visit_id", "pred"]].to_csv(out, index=False)              # overwrites: a rerun replaces the run
print(f"wrote {out}: {res.pred.notna().sum()} answered, {res.pred.isna().sum()} no answer")
if res.pred.isna().any():
    print(res.loc[res.pred.isna(), "error"].value_counts().head(5).to_string())
telemetry.end_script()
