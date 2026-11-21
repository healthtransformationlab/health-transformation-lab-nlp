"""How each de-identification tool ranks, and what decides whether an identifier is removed (spec 042 US3, #866).

    pip install -e ".[deid]"                     # Presidio, spaCy en_core_web_lg, transformers, CPU torch (#875)
    python scripts/76_deid_drivers.py --rerun    # rerun the local tools on CPU (regex, regex_v2, Presidio, the two
                                                 # Hugging Face models; ~25 min on 4 CPUs) into
                                                 # data/deid/drivers/span_result.csv.gz, only if it reproduces
                                                 # data/deid/scores.csv exactly; then write the outputs below
    python scripts/76_deid_drivers.py            # write data/datasets/model_drivers/deid_*.csv and docs/deid_drivers.md
    python scripts/76_deid_drivers.py --check    # exit 1 if any of them is stale (--check does not need .[deid])

The format is the phenotyping models' (scripts/74_model_drivers.py): a ranked table with paired exact McNemar tests,
contrasts that add one ingredient, and which identifier facts and tool ingredients predict removal, by AUC. Method:
health_transformation_lab_nlp/deid_drivers.py. Fake PHI on synthetic notes. CPU only: never a GPU run.
"""

import argparse
import logging
import sys
import tempfile
import time
from pathlib import Path

from health_transformation_lab_nlp import deid_drivers as dd
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("76_deid_drivers", data_label="synthetic")
logging.getLogger("tldextract").setLevel(logging.CRITICAL)   # Presidio's URL recognizer tries the network

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
ap.add_argument("--rerun", action="store_true")
a = ap.parse_args()

if a.rerun:
    records = dd.challenge()
    raw = {}
    for engine in dd.LOCAL_ENGINES:
        t0 = time.perf_counter()
        raw |= dd.rerun_raw(records, [engine])
        print(f"{engine}: {len(records)} notes in {time.perf_counter() - t0:.0f} s (CPU)", flush=True)
    sr = dd.span_result(records, raw)
    rep = dd.reproduce(sr, dd.load_committed_scores())
    if not rep.is_match.all():
        print(rep[~rep.is_match].to_string(index=False))
        sys.exit("the rerun does not reproduce data/deid/scores.csv: nothing written")
    dd.SPAN_RESULT.parent.mkdir(parents=True, exist_ok=True)
    sr.to_csv(dd.SPAN_RESULT, index=False, compression={"method": "gzip", "mtime": 0})
    print(f"wrote {dd.SPAN_RESULT} ({len(sr):,} rows); reproduces scores.csv in {len(rep)} tool-tier cells")

built = dd.build(dd.load_span_result())
new = {dd.DETAILS_DOC: dd.details_markdown(built)}
with tempfile.TemporaryDirectory() as tmp:
    for name in dd.TABLES:
        p = Path(tmp) / f"{name}.csv"
        built[name].to_csv(p, index=False, float_format="%.6g")
        new[dd.OUT_DIR / f"{name}.csv"] = p.read_text()
stale = [p for p, t in new.items() if not p.exists() or p.read_text() != t]
if a.check:
    sys.exit(f"stale: {', '.join(p.name for p in stale)}; run python scripts/76_deid_drivers.py" if stale else 0)
dd.OUT_DIR.mkdir(parents=True, exist_ok=True)
for p in stale:
    p.write_text(new[p])
print("updated:", ", ".join(p.name for p in stale) or "nothing")
