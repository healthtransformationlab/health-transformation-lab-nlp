"""Train an AI rung on the training set and predict the chart-review notes.

The AI model reads ONLY the de-identified note. Reviewers see every evidence type.

    python scripts/11_ai_predict.py --rung tfidf_logreg
    python scripts/11_ai_predict.py --rung distilbert-base --epochs 2 --max-len 256
    python scripts/11_ai_predict.py --rung bioclinical-modernbert-base --label stated_status
    python scripts/11_ai_predict.py --rung modernbert-base --class-weight sqrt --seed 1   # -> ..._modernbert-base+cw+s1.csv
    python scripts/11_ai_predict.py --rung gatortron-base --lr 2e-5                        # -> ..._gatortron-base+lr2e-05.csv
    python scripts/11_ai_predict.py --rung modernbert-base --class-weight sqrt --save-model runs/model   # + the weights

LLM note readers (MedGemma, spec 004):

    python scripts/11_ai_predict.py --rung medgemma-1.5-4b-it --backend hf          # local GPU/CPU
    python scripts/11_ai_predict.py --rung medgemma-1.5-4b-it --backend hf --adapter runs/medgemma-lora
    python scripts/11_ai_predict.py --rung medgemma-1.5-4b-it --backend hf --weights /kaggle/temp/medgemma-hf   # Kaggle
    READER_BASE_URL=... READER_API_KEY=... python scripts/11_ai_predict.py \
        --rung medgemma-27b-text-it --backend openai --endpoint <serving endpoint name>
    python scripts/11_ai_predict.py --rung medgemma-1.5-4b-it --backend simulated   # dry run, no model

LLM variants get their own files: +lora (adapter), +k<shots> (few-shot), +terse (prompt variant).
Compare with the BERT encoders: scripts/29_medgemma_vs_bert.py.

Writes data/datasets/ai_predictions_<rung>.csv (visit_id, pred, p_<status>...), plus
llm_details_<rung><tag>.csv for LLM rungs. The simulated backend writes simulated_* files,
which the reliability and judge scripts do not pick up.
"""

import argparse
import sys

import pandas as pd

from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.radiograph import FEATURES as RAD_FEATURES
from health_transformation_lab_nlp.registry import load_registry
from health_transformation_lab_nlp.rungs import make_rung, output_tag

ap = argparse.ArgumentParser()
ap.add_argument("--rung", required=True)
ap.add_argument("--label", default="label", help="train target: label (chart) or stated_status (clinician)")
ap.add_argument("--epochs", type=int, default=3)
ap.add_argument("--max-len", type=int, default=256)
ap.add_argument("--class-weight", choices=["sqrt"], default=None,
                help="encoders: weight the loss by inverse class frequency (square root); output tagged +cw")
ap.add_argument("--seed", type=int, default=42, help="encoders: training seed; a non-default seed tags the output +s<seed>")
ap.add_argument("--lr", type=float, default=5e-5, help="encoders: learning rate; a non-default rate tags the output +lr<rate>")
ap.add_argument("--grad-checkpoint", action="store_true",
                help="encoders: gradient checkpointing, for a GPU too small for the model (same results, slower)")
llm = ap.add_argument_group("LLM readers")
llm.add_argument("--backend", choices=["hf", "openai", "simulated"], default="hf")
llm.add_argument("--shots", type=int, default=0, help="few-shot examples per status from train.csv")
llm.add_argument("--variant", default="reader-v2", help="prompt variant (reader-v2, reader-v2-terse)")
llm.add_argument("--adapter", default=None, help="LoRA adapter dir from scripts/17_medgemma_lora.py")
llm.add_argument("--endpoint", default=None, help="openai backend: model / serving endpoint name")
llm.add_argument("--weights", default=None,
                 help="hf backend: local transformers folder to load instead of Hugging Face (kaggle/keras_to_hf.py)")
llm.add_argument("--limit", type=int, default=None, help="only the first N review notes (smoke test)")
ap.add_argument("--save-model", default=None, metavar="DIR",
                help="encoders: keep the fine-tuned model and tokenizer here, in transformers format (spec 020 US3)")
ap.add_argument("--register", default=None, metavar="CATALOG.SCHEMA.MODEL",
                help="log the fitted rung as an MLflow pyfunc and register a version (alias: challenger)")
a = ap.parse_args()
telemetry.setup()
telemetry.start_script("11_ai_predict", data_label="synthetic", rung=a.rung)

train = pd.read_csv(DATASETS_DIR / "train.csv").rename(columns={a.label: "target"})
train = train.drop(columns=[c for c in ("label",) if c in train]).rename(columns={"target": "label"})
key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")
review = key[["visit_id", "note_text", *RAD_FEATURES]]
if a.limit:
    review = review.head(a.limit)

reg = load_registry()
entry = next((m for m in reg["models"] if m["id"] == a.rung), {})
is_llm = entry.get("role") == "llm"
prefix = ""
if is_llm:
    kw = {"shots": a.shots, "variant": a.variant}
    if a.backend == "simulated":
        from health_transformation_lab_nlp.llm_reader import SimulatedReader
        kw["backend"] = SimulatedReader(dict(zip(key.visit_id, key.truth_status)),
                                        dict(zip(key.visit_id, key.difficulty)), seed=4)
        prefix = "simulated_"
    else:
        kw.update(backend_kind=a.backend, adapter=a.adapter, endpoint=a.endpoint, weights=a.weights)
elif a.rung in ("rules_baseline", "note_rules", "tfidf_logreg", "fusion_tfidf_rad"):
    kw = {}
else:
    kw = {"epochs": a.epochs, "max_len": a.max_len, "class_weight": a.class_weight, "seed": a.seed, "lr": a.lr,
          "grad_checkpoint": a.grad_checkpoint}

model = make_rung(a.rung, reg, **kw).fit(train)
if a.save_model:
    if not hasattr(model, "save"):
        sys.exit(f"--save-model: {a.rung} is not a fine-tuned encoder; only encoders are saved")
    model.save(a.save_model)
    print(f"saved the fine-tuned model to {a.save_model}")
pred, proba = model.predict(review)
out = review[["visit_id"]].assign(pred=pred)
if proba is not None:
    for i, lab in enumerate(LABELS):
        out[f"p_{lab}"] = proba[:, i]
tag = (output_tag(adapter=a.adapter, shots=a.shots, variant=a.variant) if is_llm
       else output_tag(class_weight=a.class_weight, seed=a.seed, lr=a.lr))
path = DATASETS_DIR / f"{prefix}ai_predictions_{a.rung}{tag}.csv"
out.to_csv(path, index=False)
print(f"wrote {path} ({len(out)} visits)")
if is_llm:
    d = model.details
    d.to_csv(DATASETS_DIR / f"{prefix}llm_details_{a.rung}{tag}.csv", index=False)
    print(f"gate pass {d['gate_ok'].mean():.1%}, fallback {d['fallback'].mean():.1%}, "
          f"tokens in/out {d['input_tokens'].mean():.0f}/{d['output_tokens'].mean():.0f} per note")
    if prefix:
        truth = key.set_index("visit_id")["truth_status"].reindex(out["visit_id"]).to_numpy()
        acc = (out["pred"].to_numpy() == truth).mean()
        print(f"*** SIMULATED READER: dry run, not a MedGemma result (agreement with truth {acc:.1%}) ***")

# ---- MLflow (docs/mlops.md): params, prediction file, optional Unity Catalog registration
from health_transformation_lab_nlp.tracking import track

with track("11_ai_predict", a.rung, simulated=bool(prefix),
           params={"rung": a.rung, "label": a.label, "n_train": len(train), "n_review": len(review), **{
               k: v for k, v in kw.items() if k in ("epochs", "max_len", "shots", "variant", "backend_kind")}}) as run:
    run.log_artifact(path)
    if is_llm:
        d = model.details
        run.log_metrics({"gate_pass": d["gate_ok"].mean(), "fallback": d["fallback"].mean(),
                         "input_tokens_mean": d["input_tokens"].mean(), "output_tokens_mean": d["output_tokens"].mean()})
        ref_file = DATASETS_DIR / "answer_key" / "reference_answers.csv"   # spec 004 US6: accuracy per field
        if ref_file.exists():
            from health_transformation_lab_nlp.reference_answers import (
                field_accuracy,
                field_metrics,
            )
            try:
                run.log_metrics(field_metrics(field_accuracy(d, pd.read_csv(ref_file, keep_default_na=False))))
            except ValueError as e:                                          # a --limit run: not every note read
                print(f"per-field accuracy not logged: {e}")
    if a.register:
        from health_transformation_lab_nlp.model_registry import log_and_register
        v = log_and_register(model, a.rung, a.register, train.head(3), simulated=bool(prefix))
        print(f"registered {a.register} version {v} (alias: challenger)")
