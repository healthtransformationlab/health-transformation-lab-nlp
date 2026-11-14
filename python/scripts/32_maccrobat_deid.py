"""De-identification test pass on MACCROBAT, real published case reports with hand-made labels (spec 009).

    python scripts/32_maccrobat_deid.py                     # the committed copy in data/external/maccrobat/
    python scripts/32_maccrobat_deid.py --download          # re-fetch the original release from figshare (MD5 checked)
    python scripts/32_maccrobat_deid.py --source bio --download   # or the BIO mirror on Hugging Face
    python scripts/32_maccrobat_deid.py --engines regex,regex_v2+guard,hf_stanford+regex_v2+guard

The original brat files are the default: exact text and offsets, and overlapping entities that BIO
labels can't hold (about twice as many clinical entities as the BIO mirror).

Scores, per engine (deid_eval.score_records on the records from maccrobat.load_brat / load_bio):
  entity_recall   share of derived PHI (dates with a month or day, ages >= 90) fully removed
  decoy_damage    share of clinical entities (symptoms, drugs, procedures ...) with any character removed
  char_precision  share of removed characters that were derived PHI

Data: data/external/maccrobat/ (public, CC BY 4.0; committed with its README).
Writes:
  data/deid/maccrobat_scores.csv    one row per engine
  data/deid/maccrobat_by_type.csv   per engine, role and entity type: share touched, share of characters removed
  data/deid/maccrobat_not_run.csv   engines that couldn't run here, and why

routed+guard uses the routes chosen on the challenge set (data/deid/routes.csv, written by
26_deid_benchmark.py), not routes chosen on MACCROBAT.
"""

import argparse
import functools
import hashlib
import urllib.request
from pathlib import Path

import pandas as pd

from health_transformation_lab_nlp import deid, deid_eval, maccrobat
from health_transformation_lab_nlp.paths import DEID_DIR, EXTERNAL_DIR, RAW_DIR
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("32_maccrobat_deid", data_label="public")

DEFAULT = ["regex", "regex+guard", "regex_v2", "regex_v2+guard", "presidio", "presidio+guard",
           "presidio+regex_v2+guard", "hf_stanford", "hf_stanford+guard", "hf_stanford+regex_v2+guard",
           "hf_obi", "hf_obi+regex_v2+guard", "hf_stanford+presidio+regex_v2+guard",
           "hf_stanford+hf_obi+regex_v2+guard", "routed+guard",
           "ai_mask", "ai_mask+regex_v2+guard"]   # every method scored by 26_deid_benchmark.py; ai_mask needs
                                                  # DATABRICKS_HOST, _TOKEN and _WAREHOUSE_ID, else it's listed as not run
ap = argparse.ArgumentParser()
ap.add_argument("--source", choices=["brat", "bio"], default="brat")
ap.add_argument("--path", default=None, help="the zip or folder (brat), or the JSONL (bio)")
ap.add_argument("--download", action="store_true", help=f"fetch {maccrobat.FIGSHARE_URL} or {maccrobat.HF_URL}")
ap.add_argument("--engines", default=",".join(DEFAULT))
a = ap.parse_args()

default = EXTERNAL_DIR / "maccrobat" / "MACCROBAT2020.zip" if a.source == "brat" else RAW_DIR / "maccrobat" / "maccrobat_bio.jsonl"
a.path = a.path or str(default)
if a.download:
    Path(a.path).parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(maccrobat.FIGSHARE_URL if a.source == "brat" else maccrobat.HF_URL, a.path)
    if a.source == "brat" and hashlib.md5(Path(a.path).read_bytes()).hexdigest() != maccrobat.FIGSHARE_MD5:
        raise SystemExit(f"{a.path}: MD5 differs from figshare's {maccrobat.FIGSHARE_MD5}")
recs = (maccrobat.load_brat if a.source == "brat" else maccrobat.load_bio)(a.path)
n_ent = pd.Series([e["role"] for r in recs for e in r["entities"]]).value_counts()
print(f"{len(recs)} documents; entities by role: {n_ent.to_dict()}")

# Each base engine runs once per document; the unions reuse its spans.
for _name, _fn in dict(deid.ENGINES).items():
    deid.ENGINES[_name] = functools.lru_cache(maxsize=None)(lambda t, _fn=_fn: tuple(_fn(t)))


def _engine(spec: str):
    if spec != "routed+guard":
        return deid.get_engine(spec)
    routes = deid_eval.routes_from_table(pd.read_csv(DEID_DIR / "routes.csv"))
    return deid.routed_engine(routes, {n: lambda t, n=n: list(deid.ENGINES[n](t)) for n in routes})


scores, by_type, not_run = [], [], []
for spec in a.engines.split(","):
    try:
        detect = _engine(spec)
        detect(recs[0]["text"])
    except Exception as e:  # noqa: BLE001 - missing package or model: record and skip
        not_run.append({"method": spec, "reason": f"{type(e).__name__}: {str(e)[:160]}"})
        print(f"{spec}: not run ({type(e).__name__})")
        continue
    detect_once = functools.lru_cache(maxsize=None)(lambda t, d=detect: tuple(d(t)))  # both scorers reuse the spans
    s = deid_eval.score_records(recs, detect_once)["summary"].set_index("tier").loc["maccrobat"]
    scores.append({"method": spec, **s.to_dict()})
    by_type.append(deid_eval.damage_by_type(recs, detect_once).assign(method=spec))
    print(f"{spec}: PHI recall {s.entity_recall:.3f} (n={int(s.n_phi)}), clinical damage {s.decoy_damage:.3f}")

if not scores:
    raise SystemExit("no engine ran: see the reasons above")
DEID_DIR.mkdir(parents=True, exist_ok=True)
cols = ["method", "n_notes", "n_phi", "entity_recall", "char_recall", "char_precision", "decoy_damage",
        "leaked_per_1k_notes", "avg_chars"]
pd.DataFrame(scores)[cols].round(4).to_csv(DEID_DIR / "maccrobat_scores.csv", index=False)
pd.concat(by_type)[["method", "role", "type", "n", "n_touched", "touched", "chars_removed"]].round(4).to_csv(
    DEID_DIR / "maccrobat_by_type.csv", index=False)
pd.DataFrame(not_run, columns=["method", "reason"]).to_csv(DEID_DIR / "maccrobat_not_run.csv", index=False)
print("wrote", DEID_DIR)
