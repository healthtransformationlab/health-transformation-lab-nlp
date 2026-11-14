"""Run each method over a corpus sample, measure throughput, cost it at full-corpus scale.

    python scripts/14_benchmark_cost.py                          # 1,500-person corpus sample
    python scripts/14_benchmark_cost.py --simulate-missing       # + simulated predictions for methods
                                                                 #   not yet runnable here (BERT, LLM),
                                                                 #   named sim:<method>, for dry runs only

Writes data/corpus/corpus_sample.parquet, preds_<method>.parquet, cost_benchmark.csv.
Prices come from costs.yaml and are ILLUSTRATIVE until you replace them.
"""

import argparse
import json
import random
import time

import pandas as pd
import yaml

from health_transformation_lab_nlp.cost_effectiveness import method_cost
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import CORPUS_DIR, COSTS_YAML, DATASETS_DIR
from health_transformation_lab_nlp.registry import load_registry
from health_transformation_lab_nlp.rungs import make_rung
from health_transformation_lab_nlp.study import build_corpus_sample
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("14_benchmark_cost", data_label="synthetic")

SIM_ACCURACY = {"distilbert-base": 0.86, "bioclinical-modernbert-base": 0.90, "llm_challenger": 0.88,
                "medgemma-1.5-4b-it": 0.87, "medgemma-27b-text-it": 0.90}   # placeholders for dry runs only

ap = argparse.ArgumentParser()
ap.add_argument("--n-people", type=int, default=1500)
ap.add_argument("--seed", type=int, default=2027)
ap.add_argument("--simulate-missing", action="store_true")
a = ap.parse_args()

costs = yaml.safe_load(COSTS_YAML.read_text())
CORPUS_DIR.mkdir(parents=True, exist_ok=True)
corpus = build_corpus_sample(a.n_people, a.seed)
corpus.to_parquet(CORPUS_DIR / "corpus_sample.parquet")
avg_tokens = costs["avg_note_tokens"] or float(corpus["note_text"].str.len().mean() / 4)
N = costs["corpus_notes"]
print(f"corpus sample: {len(corpus)} notes, ~{avg_tokens:.0f} tokens/note; costing at {N:,} notes")

train = pd.read_csv(DATASETS_DIR / "train.csv")
reg = load_registry()
rows = []
for method, cfg in costs["methods"].items():
    tput, preds, name = None, None, method
    if cfg["kind"] == "local" and cfg.get("throughput_source") == "measured":
        model = make_rung(method, reg).fit(train)
        t0 = time.perf_counter()
        preds, _ = model.predict(corpus)
        tput = len(corpus) / (time.perf_counter() - t0)
    elif a.simulate_missing and method in SIM_ACCURACY:
        rng = random.Random(hash(method) % 10_000)
        acc = SIM_ACCURACY[method]
        preds = [t if rng.random() < acc else rng.choice([x for x in LABELS if x != t])
                 for t in corpus["truth_status"]]
        name = f"sim:{method}"
    c = method_cost(cfg, N, avg_tokens, costs["compute"], tput)
    rows.append({"method": name, **c, "has_predictions": preds is not None})
    if preds is not None:
        corpus[["visit_id"]].assign(pred=preds).to_parquet(CORPUS_DIR / f"preds_{name.replace(':', '__')}.parquet")

bench = pd.DataFrame(rows)
bench.to_csv(CORPUS_DIR / "cost_benchmark.csv", index=False)
(CORPUS_DIR / "corpus_meta.json").write_text(json.dumps({"n_sample": len(corpus), "avg_note_tokens": avg_tokens,
                                                          "corpus_notes": N}))
print("\nILLUSTRATIVE PRICES (costs.yaml) - replace before reporting")
print(bench.round(2).to_string(index=False))
