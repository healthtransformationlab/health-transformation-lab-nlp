"""Compare de-identification engines on the labeled fake-PHI challenge set, and price them (spec 007).

    python scripts/26_deid_benchmark.py                       # every engine that can run here
    python scripts/26_deid_benchmark.py --engines regex,regex_v2+guard,presidio+regex_v2+guard
    AZURE_DEID_ENDPOINT=... python scripts/26_deid_benchmark.py --engines azure_deid+regex_v2+guard
    AWS_REGION=us-east-1 python scripts/26_deid_benchmark.py --engines aws_comprehend,aws_comprehend+regex_v2+guard

Writes:
  data/raw/deid_challenge.jsonl       the labeled notes (fake PHI; never committed)
  data/deid/scores.csv                per engine and tier: recall, precision, decoy damage, leaks
  data/deid/by_category.csv           recall per PHI category
  data/deid/not_run.csv               engines that couldn't run here, and why
  data/deid/cost_inputs.csv           what the cost model uses (R recomputes from this: parity)
  data/deid/cost_effectiveness.csv    cost per corpus, leaks per 1M notes, frontier, ICER

  --external path adds another labeled set as tier "external": JSONL/JSON, or ASQ-PHI's own
  synthetic_clinical_queries.txt as downloaded. Price it with --tiers all,unseen,external.
  --jsl48 path adds John Snow Labs' benchmark CSV as tier "jsl48"; token_precision/recall/f1 are
  scored by their word-level rule, comparable with their published PHI F1.

An engine that can't run here (package missing, no Azure endpoint) is listed as not run, with
the reason; nothing is estimated for it. Service prices in costs.yaml are ILLUSTRATIVE until
filled from the vendor's pricing page.
"""

import argparse
import functools
import json
import logging

import pandas as pd
import yaml

from health_transformation_lab_nlp import deid, deid_eval, telemetry
from health_transformation_lab_nlp.paths import COSTS_YAML, DEID_DIR, RAW_DIR
from health_transformation_lab_nlp.phi_challenge import build_challenge

telemetry.setup()
telemetry.start_script("26_deid_benchmark", data_label="synthetic")

logging.getLogger("tldextract").setLevel(logging.CRITICAL)   # Presidio's URL recognizer tries the network

DEFAULT = ["regex", "regex+guard", "regex_v2", "regex_v2+guard", "presidio", "presidio+guard",
           "presidio+regex_v2+guard", "hf_stanford", "hf_stanford+guard", "hf_stanford+regex_v2+guard",
           "hf_obi", "hf_obi+regex_v2+guard", "llm", "llm+regex_v2+guard", "ai_mask", "ai_mask+regex_v2+guard",
           "azure_deid", "azure_deid+regex_v2+guard", "azure_language", "azure_language+regex_v2+guard",
           "aws_comprehend", "aws_comprehend+regex_v2+guard",
           "hf_stanford+hf_obi+regex_v2+guard", "hf_stanford+presidio+regex_v2+guard", "routed+guard"]
ap = argparse.ArgumentParser()
ap.add_argument("--engines", default=",".join(DEFAULT))
ap.add_argument("--n-notes", type=int, default=400)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--external", default=None,
                help="another labeled PHI set (JSONL/JSON, e.g. ASQ-PHI) scored as tier 'external'")
ap.add_argument("--i2b2-2014", default=None, help="folder of the n2c2 2014 XML notes (data use agreement)")
ap.add_argument("--jsl48", default=None,
                help="John Snow Labs' 48-note benchmark CSV (likely i2b2 notes: keep it in data/raw/), tier 'jsl48'")
ap.add_argument("--route-engines", default="hf_stanford,hf_obi,presidio,regex_v2",
                help="engines 'routed+guard' may draw on; each keeps only the types it was precise on")
ap.add_argument("--route-min-precision", type=float, default=0.8)
ap.add_argument("--route-train-tiers", default="easy,hard",
                help="tiers the routes are chosen on; score them on the others (unseen, external)")
ap.add_argument("--tiers", default="all,unseen",
                help="tiers priced: all (the mix) and unseen (held out from regex_v2's design)")
a = ap.parse_args()

ch = build_challenge(a.n_notes, a.seed)
if a.i2b2_2014:
    from health_transformation_lab_nlp.phi_challenge import load_i2b2_2014
    ch += [r | {"tier": "external"} for r in load_i2b2_2014(a.i2b2_2014)]
if a.external:
    from health_transformation_lab_nlp.phi_challenge import load_external
    ch += load_external(a.external)
if a.jsl48:
    from health_transformation_lab_nlp.phi_challenge import load_external
    ch += load_external(a.jsl48, tier="jsl48")
RAW_DIR.mkdir(parents=True, exist_ok=True)
DEID_DIR.mkdir(parents=True, exist_ok=True)
with open(RAW_DIR / "deid_challenge.jsonl", "w") as f:
    f.writelines(json.dumps(r) + "\n" for r in ch)

cfg = yaml.safe_load(COSTS_YAML.read_text())
dcfg, compute, n_corpus = cfg["deid"], cfg["compute"], cfg["corpus_notes"]

# Each engine runs once per note: unions and routes reuse the cached spans (throughput below is
# measured on the uncached engines).
RAW_ENGINES = dict(deid.ENGINES)
for _name, _fn in RAW_ENGINES.items():
    deid.ENGINES[_name] = functools.lru_cache(maxsize=None)(lambda t, _fn=_fn: tuple(_fn(t)))


def _routed():
    names = a.route_engines.split(",")
    train = [r for r in ch if r["tier"] in a.route_train_tiers.split(",")]
    routes, table = deid_eval.choose_routes(train, {n: lambda t, n=n: list(deid.ENGINES[n](t)) for n in names},
                                            min_precision=a.route_min_precision)
    table.to_csv(DEID_DIR / "routes.csv", index=False)
    print("routes:", {e: sorted(t) for e, t in routes.items()})
    return deid.routed_engine(routes, {n: lambda t, n=n: list(deid.ENGINES[n](t)) for n in names}), names


scores, cats, not_run, speed, members_of = [], [], [], {}, {}
for spec in a.engines.split(","):
    members = [p for p in spec.split("+") if p != "guard"]
    try:
        if spec == "routed+guard":
            detect, members = _routed()
        else:
            detect = deid.get_engine(spec)
        detect(ch[0]["text"])
    except Exception as e:  # noqa: BLE001 - missing package, model or endpoint: record and skip
        not_run.append({"method": spec, "reason": f"{type(e).__name__}: {str(e)[:160]}"})
        print(f"{spec}: not run ({type(e).__name__})")
        continue
    members_of[spec] = members
    for member in members:
        if member not in speed and member not in deid.CLOUD_ENGINES:
            speed[member] = deid_eval.measure_throughput(ch[:100], RAW_ENGINES[member])
    r = deid_eval.score_records(ch, detect)
    scores.append(r["summary"].assign(method=spec))
    cats.append(r["by_category"].assign(method=spec))
    s = r["summary"].set_index("tier").loc["all"]
    print(f"{spec}: entity recall {s.entity_recall:.3f}, decoy damage {s.decoy_damage:.3f}")

scores = pd.concat(scores)[["method", "tier", "n_notes", "n_phi", "entity_recall", "char_recall",
                            "char_precision", "decoy_damage", "n_hard_negatives", "hard_negative_damage",
                            "token_precision", "token_recall", "token_f1", "leaked_per_1k_notes", "avg_chars"]]
scores.to_csv(DEID_DIR / "scores.csv", index=False)
pd.concat(cats)[["method", "tier", "category", "n", "n_leaked", "recall"]].to_csv(DEID_DIR / "by_category.csv",
                                                                               index=False)
pd.DataFrame(not_run, columns=["method", "reason"]).to_csv(DEID_DIR / "not_run.csv", index=False)

# ---- cost inputs: one row per (method, member engine); R recomputes the frontier from this file
rows = []
for (tier, spec), g in scores[scores.tier.isin(a.tiers.split(","))].groupby(["tier", "method"], sort=False):
    s = g.iloc[0]
    for member in members_of[spec]:
        e = dict(dcfg["engines"][member])
        if e["kind"] == "local":
            e["notes_per_sec"] = speed[member]
        rows.append({"tier": tier, "method": spec, "engine": member, "kind": e["kind"], "hardware": e.get("hardware", ""),
                     "notes_per_sec": e.get("notes_per_sec", float("nan")), "unit": e.get("unit", ""),
                     "usd_per_unit": e.get("usd_per_unit", float("nan")), "free_units": e.get("free_units", 0),
                     "tiers": deid_eval.format_tiers(e.get("tiers")),
                     **{k: e.get(k, 0.0) for k in deid_eval._LLM_KEYS + deid_eval._LICENSE_KEYS},
                     "n_notes": n_corpus, "avg_chars": s.avg_chars,
                     "leaked_per_1m_notes": s.leaked_per_1k_notes * 1000, "decoy_damage": s.decoy_damage,
                     "cpu_node_usd_per_hour": compute["cpu_node_usd_per_hour"],
                     "gpu_node_usd_per_hour": compute["gpu_node_usd_per_hour"],
                     "qa_sample_share": dcfg["review"]["qa_sample_share"],
                     "minutes_per_note": dcfg["review"]["minutes_per_note"],
                     "review_usd_per_hour": dcfg["review"]["usd_per_hour"]})
ci = pd.DataFrame(rows)
ci.to_csv(DEID_DIR / "cost_inputs.csv", index=False)
ce = deid_eval.cost_table(ci)
ce.to_csv(DEID_DIR / "cost_effectiveness.csv", index=False)
print(ce.round(4).to_string(index=False))
print("wrote", DEID_DIR, "(service prices ILLUSTRATIVE; local throughput measured on this machine)")
