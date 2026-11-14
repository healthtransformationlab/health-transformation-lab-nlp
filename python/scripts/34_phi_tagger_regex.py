"""Regex date post-processing on a fine-tuned PHI tagger's predictions, and its errors (spec 010).

    python scripts/34_phi_tagger_regex.py --tag base_lr3e-5_e3

Reads python/runs/phi_tagger/<tag>/pred.json (written by 33_maccrobat_phi_tagger.py). Candidates are
the named date patterns (phi_tagger.DATE_PATTERNS: tag words the model left O) and the boundary rule
`trim_function_words` (phi_tagger.fix_dates). Each is scored alone, then a set is grown greedily on the validation
notes (add the pattern that raises validation weighted F1 most, stop when none does); the test notes
are scored for every row but never used to choose.
Writes (aggregates only):
  data/deid/maccrobat_tagger_regex.csv    per pattern set: val and test F1 (Date, weighted)
  data/deid/maccrobat_tagger_errors.csv   test error kinds per type, model alone and with the chosen set
  data/external/maccrobat/errors/<tag>_{val,test}.txt  each error of the model alone (no post-processing),
                                           with its words and context (public text). Analyse val; test
                                           is listed for the final report only
"""

import argparse
import json

import pandas as pd

from health_transformation_lab_nlp import maccrobat, phi_tagger
from health_transformation_lab_nlp.paths import DEID_DIR, EXTERNAL_DIR, REPO_ROOT
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("34_phi_tagger_regex", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--tag", required=True)
ap.add_argument("--zip", default=str(EXTERNAL_DIR / "maccrobat" / "MACCROBAT2020.zip"))
ap.add_argument("--conll-dir", default=None, help="the run used a course's own train.txt / test.txt")
a = ap.parse_args()

pred = json.loads((REPO_ROOT / "python" / "runs" / "phi_tagger" / a.tag / "pred.json").read_text())
if a.conll_dir:
    from pathlib import Path
    docs = {d["note_id"]: d for f in ("train", "test") for d in phi_tagger.read_conll(Path(a.conll_dir) / f"{f}.txt")}
else:
    docs = {d["note_id"]: d for d in phi_tagger.bio_docs(maccrobat.load_brat(a.zip))}


CANDIDATES = [*phi_tagger.DATE_PATTERNS, "trim_function_words"]


def run(split: str, patterns: list[str]) -> tuple[list, list]:
    gold, out = [], []
    for i, p in pred[split].items():
        gold.append(p["gold"])
        tags = phi_tagger.regex_dates(docs[i]["text"], docs[i]["spans"], p["pred"],
                                      [n for n in patterns if n in phi_tagger.DATE_PATTERNS])
        out.append(phi_tagger.fix_dates(docs[i]["words"], tags, patterns))
    return gold, out


def row(patterns: list[str], label: str) -> dict:
    r = {"tag": a.tag, "patterns": label}
    for split in ("val", "test"):
        s = phi_tagger.score(*run(split, patterns)).set_index("type")
        r[f"{split}_f1_Date"] = round(float(s.loc["Date", "f1"]), 4)
        r[f"{split}_p_Date"] = round(float(s.loc["Date", "precision"]), 4)
        r[f"{split}_r_Date"] = round(float(s.loc["Date", "recall"]), 4)
        r[f"{split}_f1_weighted"] = round(float(s.loc["weighted", "f1"]), 4)
        r[f"{split}_overlap_f1_weighted"] = round(float(
            phi_tagger.score(*run(split, patterns), overlap=True).set_index("type").loc["weighted", "f1"]), 4)
    return r


rows = [row([], "none (model alone)")] + [row([n], n) for n in CANDIDATES]
chosen, best = [], rows[0]["val_f1_weighted"]
while True:
    trials = [(row([*chosen, n], ""), n) for n in CANDIDATES if n not in chosen]
    if not trials:
        break
    r, n = max(trials, key=lambda t: t[0]["val_f1_weighted"])
    if r["val_f1_weighted"] <= best:
        break
    chosen.append(n)
    best = r["val_f1_weighted"]
    rows.append(r | {"patterns": "greedy: " + "+".join(chosen)})
rows.append(row(CANDIDATES, "all"))
table = pd.DataFrame(rows)
print(table.to_string(index=False))

DEID_DIR.mkdir(parents=True, exist_ok=True)
path = DEID_DIR / "maccrobat_tagger_regex.csv"
old = pd.read_csv(path) if path.exists() else pd.DataFrame()
old = old[old.tag != a.tag] if len(old) else old
pd.concat([old, table], ignore_index=True).to_csv(path, index=False)

errs = []
for label, patterns in (("model", []), ("model+regex", chosen)):
    for (t, kind), n in sorted(phi_tagger.error_kinds(*run("test", patterns)).items()):
        errs.append({"tag": a.tag, "system": label, "patterns": "+".join(patterns), "type": t, "kind": kind, "n": n})
(EXTERNAL_DIR / "maccrobat" / "errors").mkdir(parents=True, exist_ok=True)
for split in ("val", "test"):
    listing = []
    for i, p in pred[split].items():
        w, g, q = docs[i]["words"], phi_tagger.entities(p["gold"]), phi_tagger.entities(p["pred"])
        for side, mine, other in (("gold", g, q), ("pred", q, g)):
            for e in mine:
                if e not in other:
                    listing.append(f"{i}\t{side} {e[0]}\t{' '.join(w[e[1]:e[2]])}\t| {' '.join(w[max(0, e[1] - 6):e[2] + 6])}")
    (EXTERNAL_DIR / "maccrobat" / "errors" / f"{a.tag}_{split}.txt").write_text("\n".join(listing) + "\n")
path = DEID_DIR / "maccrobat_tagger_errors.csv"
old = pd.read_csv(path) if path.exists() else pd.DataFrame()
old = old[old.tag != a.tag] if len(old) else old
pd.concat([old, pd.DataFrame(errs)], ignore_index=True).to_csv(path, index=False)
print("chosen:", chosen or "none", "| wrote", DEID_DIR)
