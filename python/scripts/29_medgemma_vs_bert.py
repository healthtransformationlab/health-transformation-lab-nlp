"""MedGemma note readers vs the fine-tuned BERT encoders, same review charts (spec 004 T018).

    python scripts/29_medgemma_vs_bert.py                       # real MedGemma runs (needs GPU output)
    python scripts/29_medgemma_vs_bert.py --bert modernbert-base
    python scripts/29_medgemma_vs_bert.py --simulated           # dry run against the simulated reader

Reads data/datasets/ai_predictions_<rung>.csv for every MedGemma run (zero-shot, +lora, +k<shots>,
+terse; from 11_ai_predict.py) and every BERT encoder run, plus note_rules. Each gets a '+rules4'
twin (the note rules decide stage IV). The reference is one encoder (--bert; default the most
accurate encoder alone), so diff_vs_ref is "MedGemma minus BERT" with a paired bootstrap CI.

Writes data/datasets/ladder/[simulated_]medgemma_vs_bert*.csv:
  medgemma_vs_bert.csv                 per method: accuracy (CI), diff vs the BERT reference (paired CI),
                                       stage IV recall, unsafe/S2 rates, calibration (encoders only),
                                       LLM gate pass and fallback rates, tokens, assumed corpus cost
  medgemma_vs_bert_by_difficulty.csv   accuracy by note difficulty level (L1 plain .. L3 hard)
  medgemma_vs_bert_preds.csv           the predictions scored (R recomputes the point estimates)

Scored as scripts/28_ladder_vs_truth.py scores (spec 032 US8, #448): at the five status groups, on the review
charts that count (study.scored_review: adults, visits from 2021-04-01); the predictions themselves are unchanged.

--simulated reads simulated_ai_predictions_medgemma-*.csv: the reader errs at placeholder rates,
so its rows say nothing about MedGemma. The truth is the generator's: synthetic-data results,
not clinical performance.
"""

import argparse
import glob
from pathlib import Path

import pandas as pd
import yaml

from health_transformation_lab_nlp import ladder_eval, study
from health_transformation_lab_nlp.labels import DEFAULT_GROUPING, LABELS
from health_transformation_lab_nlp.llm_reader import summarize_details
from health_transformation_lab_nlp.paths import COSTS_YAML, DATASETS_DIR
from health_transformation_lab_nlp.registry import load_registry

ap = argparse.ArgumentParser()
ap.add_argument("--bert", default=None, help="reference encoder rung (default: most accurate encoder alone)")
ap.add_argument("--simulated", action="store_true", help="use the simulated MedGemma reader (dry run)")
ap.add_argument("--n-boot", type=int, default=1000)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

reg = load_registry()
roles = {m["id"]: m["role"] for m in reg["models"]}
prefix = "simulated_" if a.simulated else ""


def runs(pattern_prefix: str, role: set) -> dict:
    """{rung (with tag): file} for prediction files whose base model has one of these roles."""
    out = {}
    for f in sorted(glob.glob(str(DATASETS_DIR / f"{pattern_prefix}ai_predictions_*.csv"))):
        rung = Path(f).stem.removeprefix(f"{pattern_prefix}ai_predictions_")
        if roles.get(rung.split("+")[0]) in role:
            out[rung] = f
    return out


llm_files = runs(prefix, {"llm"})
bert_files = runs("", {"classifier", "long_context"})
if not llm_files:
    raise SystemExit(f"no {prefix}ai_predictions_medgemma-*.csv. Run, e.g.:\n"
                     "  python scripts/11_ai_predict.py --rung medgemma-1.5-4b-it --backend hf   (GPU)\n"
                     "or a dry run: --backend simulated, then this script with --simulated")
if not bert_files:
    raise SystemExit("no encoder predictions; run scripts/11_ai_predict.py --rung bert-base (or another encoder)")

key = study.scored_review(pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv"),
                          pd.read_csv(DATASETS_DIR / "visits_structured.csv")).set_index("visit_id")
truth = key["truth_status"]
preds, proba, kind = {}, {}, {}
for group, files in (("llm", llm_files), ("encoder", bert_files), ("rules", {"note_rules": str(
        DATASETS_DIR / "ai_predictions_note_rules.csv")})):
    for rung, f in files.items():
        d = pd.read_csv(f).set_index("visit_id").reindex(truth.index)
        if (miss := ladder_eval.missing_charts(d["pred"], truth)):
            print(f"skip {rung}: {miss} of {len(truth)} review charts unscored (a --limit run); rerun on all")
            continue
        name = f"sim:{rung}" if group == "llm" and a.simulated else rung
        preds[name], kind[name] = d["pred"], group
        pcols = [f"p_{lab}" for lab in LABELS]
        if all(c in d for c in pcols):
            proba[name] = d[pcols].set_axis(LABELS, axis=1)
if not any(k == "llm" for k in kind.values()):
    raise SystemExit("no complete MedGemma run to compare (every review chart must be scored)")
llm_files = {r: f for r, f in llm_files.items() if (f"sim:{r}" if a.simulated else r) in preds}
bert_files = {r: f for r, f in bert_files.items() if r in preds}
for m in [m for m in list(preds) if kind[m] != "rules"]:
    preds[f"{m}+rules4"], kind[f"{m}+rules4"] = ladder_eval.rules_override(preds[m], preds["note_rules"]), kind[m]
truth = ladder_eval.grouped(truth, DEFAULT_GROUPING)
preds = {m: ladder_eval.grouped(p, DEFAULT_GROUPING) for m, p in preds.items()}
proba = {m: ladder_eval.grouped_proba(p, DEFAULT_GROUPING) for m, p in proba.items()}

if a.bert is None:
    a.bert = max(bert_files, key=lambda r: (preds[r] == truth).mean())
if a.bert not in preds:
    raise SystemExit(f"--bert {a.bert}: no ai_predictions_{a.bert}.csv (have: {', '.join(bert_files)})")

table = ladder_eval.ladder_table(truth, preds, proba, n_boot=a.n_boot, seed=a.seed, reference=a.bert)
table.insert(1, "kind", table["method"].map(kind))
table.insert(2, "reference", a.bert)

# LLM reliability (gate, fallback to note_rules) and an assumed corpus cost, per base run
costs = yaml.safe_load(COSTS_YAML.read_text())
extra = []
for m in table["method"]:
    run = m.removeprefix("sim:").removesuffix("+rules4")
    row = {"method": m}
    det = DATASETS_DIR / f"{prefix}llm_details_{run}.csv"
    if kind[m] == "llm" and det.exists():
        row |= summarize_details(pd.read_csv(det))
    c = costs["methods"].get(run.split("+")[0], {})
    if c.get("notes_per_sec"):
        hours = costs["corpus_notes"] / c["notes_per_sec"] / 3600
        rate = costs["compute"][f"{c['hardware']}_node_usd_per_hour"]
        row |= {"notes_per_sec": c["notes_per_sec"], "throughput_source": c["throughput_source"],
                "corpus_usd_illustrative": hours * rate}
    extra.append(row)
table = table.merge(pd.DataFrame(extra), on="method", how="left").sort_values("accuracy", ascending=False)

out = DATASETS_DIR / "ladder"
out.mkdir(parents=True, exist_ok=True)
table.to_csv(out / f"{prefix}medgemma_vs_bert.csv", index=False)
ladder_eval.by_difficulty(truth, preds, key["difficulty"]).to_csv(
    out / f"{prefix}medgemma_vs_bert_by_difficulty.csv", index=False)
pd.DataFrame(preds).assign(truth=truth, difficulty=key["difficulty"]).rename_axis("visit_id").reset_index().to_csv(
    out / f"{prefix}medgemma_vs_bert_preds.csv", index=False)

show = ["method", "kind", "accuracy", "acc_lo", "acc_hi", "diff_vs_ref", "diff_lo", "diff_hi",
        "stage4_recall", "unsafe_rate", "fallback"]
print(f"reference: {a.bert} (diff_vs_ref = method minus {a.bert})")
print(table[[c for c in show if c in table]].round(3).to_string(index=False))
heads = [m for m in preds if kind[m] == "llm" and not m.endswith("+rules4")] + [a.bert]
lv = ladder_eval.by_difficulty(truth, {m: preds[m] for m in heads}, key["difficulty"])
print(lv.pivot(index="method", columns="difficulty", values="accuracy").round(3).to_string())
if a.simulated:
    print("*** SIMULATED READER: dry run, placeholder error rates; not a MedGemma result ***")
print("wrote", out, "(synthetic truth; not clinical performance)")
