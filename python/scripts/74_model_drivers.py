"""How each note-reading model ranks, and what drives its score (spec 042 US1, #863), from committed results only.

    python scripts/74_model_drivers.py           # write data/datasets/model_drivers/*.csv, docs/model_drivers.md and
                                                 # the block in docs/edr/README.md
    python scripts/74_model_drivers.py --check   # exit 1 if any of them is stale

The format is the agent competition's (a ranked table with paired exact McNemar tests, contrasts that change one model
feature, and which chart facts and model features predict a correct reading, by AUC). Method:
health_transformation_lab_nlp/model_drivers.py. Synthetic charts; agreement with the answer key, not accuracy.
"""

import argparse
import sys
import tempfile
from pathlib import Path

from health_transformation_lab_nlp import model_drivers as md
from health_transformation_lab_nlp import readme_results as rr
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("74_model_drivers", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
a = ap.parse_args()

built = md.build(rr.load_inputs())
new = {md.DETAILS_DOC: md.details_markdown(built),
       md.README: md.update_readme(md.README.read_text(), md.readme_block(built))}
with tempfile.TemporaryDirectory() as tmp:
    for name in md.TABLES:
        p = Path(tmp) / f"{name}.csv"
        built[name].to_csv(p, index=False, float_format="%.6g")
        new[md.OUT_DIR / f"{name}.csv"] = p.read_text()
stale = [p for p, t in new.items() if not p.exists() or p.read_text() != t]
if a.check:
    sys.exit(f"stale: {', '.join(p.name for p in stale)}; run python scripts/74_model_drivers.py" if stale else 0)
md.OUT_DIR.mkdir(parents=True, exist_ok=True)
for p in stale:
    p.write_text(new[p])
print("updated:", ", ".join(p.name for p in stale) or "nothing")
