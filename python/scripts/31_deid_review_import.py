"""Import the de-identification review projects' exports and score them (spec 008).

    python scripts/31_deid_review_import.py --gold ann1.json ann2.json --qa qa1.json qa2.json
    python scripts/31_deid_review_import.py --simulate 3       # dry run: simulated annotators, simulated_* files

Needs data/raw/ from 30_deid_review_tasks.py. Only simulated_* outputs are committed (.gitignore): a real
run's files name the annotators. Spans are written as "start-end;start-end". Writes data/deid/review/[simulated_]*.csv (no note text):
  gold_spans.csv             every marked span: note, annotator, aided, start, end, category (no text)
  gold_consensus.csv         the consensus spans (characters half or more of a note's annotators marked)
  generator_spans.csv        the generator's PHI spans for the same notes (synthetic only; offsets, no text)
  gold_agreement.csv         pairwise entity F1 between annotators (exact span; with category)
  gold_annotator_recall.csv  each annotator against the generator's spans, aided vs unaided (synthetic only)
  gold_engine_scores.csv     each engine scored against the human consensus and against the generator
  qa_labels.csv              one row per (note, reviewer): leak yes/no, over-redaction, leak spans marked
  qa_key.csv                 true leaks per QA note, in de-identified-text offsets (synthetic only)
  qa_summary.csv             leak-note rate (Wilson 95% CI) pooled and per reviewer; sensitivity and
                             specificity against the answer key (synthetic only)
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import deid, deid_eval, deid_review
from health_transformation_lab_nlp.paths import DEID_DIR, RAW_DIR
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("31_deid_review_import", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--gold", nargs="*", default=[], help="Label Studio JSON exports of the gold project")
ap.add_argument("--qa", nargs="*", default=[], help="Label Studio JSON exports of the QA project")
ap.add_argument("--simulate", type=int, default=0, help="N simulated annotators and QA reviewers (dry run)")
ap.add_argument("--engines", default="regex,regex_v2,regex_v2+guard", help="engines scored against the consensus")
ap.add_argument("--seed", type=int, default=11)
a = ap.parse_args()

recs = [json.loads(x) for x in (RAW_DIR / "deid_review_notes.jsonl").read_text().splitlines() if x]
gold_tasks = json.loads((RAW_DIR / "deid_gold_tasks.json").read_text())
qa_tasks = json.loads((RAW_DIR / "deid_qa_tasks.json").read_text())
key = pd.DataFrame(json.loads((RAW_DIR / "deid_qa_key.json").read_text()))
if a.simulate:
    gold_exp = deid_review.simulate_gold_export(gold_tasks, recs, n_annotators=a.simulate, seed=a.seed)
    qa_exp = deid_review.simulate_qa_export(qa_tasks, key, n_reviewers=a.simulate, seed=a.seed + 2)
else:
    gold_exp = [t for f in a.gold for t in json.loads(Path(f).read_text())]
    qa_exp = [t for f in a.qa for t in json.loads(Path(f).read_text())]
prefix = "simulated_" if a.simulate else ""
out = DEID_DIR / "review"
out.mkdir(parents=True, exist_ok=True)

if gold_exp:
    spans = deid_review.parse_gold_export(gold_exp)
    spans.drop(columns="text").to_csv(out / f"{prefix}gold_spans.csv", index=False)
    pd.DataFrame([{"note_id": n, **g} for n, gs in deid_review.consensus(spans).items() for g in gs],
                 columns=["note_id", "start", "end", "type"]).to_csv(out / f"{prefix}gold_consensus.csv", index=False)
    done = set(spans["note_id"])
    pd.DataFrame([{"note_id": r["note_id"], "start": p["start"], "end": p["end"], "type": p["type"]}
                  for r in recs if r["note_id"] in done for p in r["phi"]],
                 columns=["note_id", "start", "end", "type"]).to_csv(out / f"{prefix}generator_spans.csv", index=False)
    ag = deid_review.agreement(spans)
    ag.to_csv(out / f"{prefix}gold_agreement.csv", index=False)
    rec = deid_review.annotator_recall(spans, recs)
    rec.to_csv(out / f"{prefix}gold_annotator_recall.csv", index=False)
    human = deid_review.gold_records(spans, recs)
    synth = [r for r in recs if r["note_id"] in {h["note_id"] for h in human}]
    rows = []
    for e in a.engines.split(","):
        for against, rr in (("human_consensus", human), ("generator", synth)):
            s = deid_eval.score_records(rr, deid.get_engine(e))["summary"]
            rows.append(s[s.tier == "all"].assign(engine=e, against=against))
    eng = pd.concat(rows)
    eng.to_csv(out / f"{prefix}gold_engine_scores.csv", index=False)
    print("annotator agreement (entity F1):\n", ag.round(3).to_string(index=False))
    print("annotator recall vs generator:\n", rec.round(3).to_string(index=False))
    print(eng[["engine", "against", "entity_recall", "char_precision"]].round(3).to_string(index=False))
if qa_exp:
    lab = deid_review.parse_qa_export(qa_exp)
    lab.assign(leak_spans=lab["leak_spans"].map(deid_review.format_spans)).to_csv(
        out / f"{prefix}qa_labels.csv", index=False)
    key.assign(leak_spans=key["leak_spans"].map(lambda x: deid_review.format_spans((s["start"], s["end"]) for s in x)))[
        ["note_id", "n_true_leaks", "leak_spans"]].to_csv(out / f"{prefix}qa_key.csv", index=False)
    summ = deid_review.qa_summary(lab, key)
    summ.to_csv(out / f"{prefix}qa_summary.csv", index=False)
    print("QA:\n", summ.round(3).to_string(index=False))
if not (gold_exp or qa_exp):
    raise SystemExit("nothing to import: pass --gold/--qa exports or --simulate N")
if a.simulate:
    print("*** SIMULATED ANNOTATORS: dry run of the plumbing, not a result ***")
print("wrote", out)
