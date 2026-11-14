"""Build the two de-identification review projects for Label Studio (spec 008).

    python scripts/30_deid_review_tasks.py                                  # synthetic challenge notes
    python scripts/30_deid_review_tasks.py --engine presidio+regex_v2+guard --n-gold 50 --n-qa 100
    python scripts/30_deid_review_tasks.py --records other_labeled_set.jsonl  # any spec 007 format

Writes to data/raw/ (note text with fake PHI; never committed):
  deid_gold_tasks.json    import into a project set up with labelstudio/deid_gold.xml
                          (engine spans as predictions; a seeded share without, to measure anchoring)
  deid_qa_tasks.json      import into a project set up with labelstudio/deid_qa.xml
                          (de-identified notes: residual-scan hits first, then a seeded sample)
  deid_qa_key.json        true leaks per QA note: never give this to reviewers
  deid_review_notes.jsonl the notes behind both, for 31_deid_review_import.py
"""

import argparse
import json
import random

from health_transformation_lab_nlp import deid, deid_review
from health_transformation_lab_nlp.paths import RAW_DIR
from health_transformation_lab_nlp.phi_challenge import build_challenge, load_external
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("30_deid_review_tasks", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--engine", default="regex_v2+guard", help="pre-annotates the gold tasks and de-identifies the QA notes")
ap.add_argument("--records", default=None, help="labeled notes (JSONL/JSON); default: the synthetic challenge set")
ap.add_argument("--n-gold", type=int, default=60)
ap.add_argument("--n-qa", type=int, default=100)
ap.add_argument("--unaided-share", type=float, default=0.2)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

recs = load_external(a.records) if a.records else build_challenge(n_notes=a.n_gold + a.n_qa, seed=7)
random.Random(a.seed).shuffle(recs)                 # a file sorted by tier mustn't decide which set a note is in
if len(recs) <= a.n_gold:
    raise SystemExit(f"{len(recs)} notes: need more than --n-gold {a.n_gold} so the QA notes differ from the gold ones")
gold_recs, qa_recs = recs[:a.n_gold], recs[a.n_gold:]
detect = deid.get_engine(a.engine)
gold = deid_review.gold_tasks(gold_recs, detect, a.engine, unaided_share=a.unaided_share, seed=a.seed)
qa, key = deid_review.qa_tasks(qa_recs, detect, a.engine, n=a.n_qa, seed=a.seed)

RAW_DIR.mkdir(parents=True, exist_ok=True)
(RAW_DIR / "deid_gold_tasks.json").write_text(json.dumps(gold, indent=1))
(RAW_DIR / "deid_qa_tasks.json").write_text(json.dumps(qa, indent=1))
(RAW_DIR / "deid_qa_key.json").write_text(key.to_json(orient="records"))
(RAW_DIR / "deid_review_notes.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
print(f"gold: {len(gold)} tasks ({sum(not t['data']['aided'] for t in gold)} unaided); "
      f"qa: {len(qa)} tasks ({int(key['residual_flag'].sum())} flagged by the residual scan, "
      f"{int((key['n_true_leaks'] > 0).sum())} with a true leak); engine {a.engine}")
print(f"wrote {RAW_DIR} (fake PHI: never commit)")
