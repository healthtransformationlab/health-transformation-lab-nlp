"""LoRA fine-tune of a MedGemma note reader on the synthetic training set (spec 004, "extend").

The training records use exactly the reader's prompt and JSON answer format
(llm_reader.sft_records), so the saved adapter plugs straight back in:

    pip install -e ".[lora]"         # GPU strongly advised; 4B in bf16 needs ~10 GB+
    huggingface-cli login            # account that has accepted the HAI-DEF terms
    python scripts/17_medgemma_lora.py --rung medgemma-1.5-4b-it --epochs 1 --out runs/medgemma-lora
    python scripts/11_ai_predict.py --rung medgemma-1.5-4b-it --backend hf --adapter runs/medgemma-lora

    python scripts/17_medgemma_lora.py --dry-run     # write the SFT records only, no training

Labels are generator truth on synthetic notes. Not yet run on real weights in
this repo (no GPU / Hugging Face access in the authoring environment).
"""

import argparse
import json

import pandas as pd

from health_transformation_lab_nlp.llm_reader import dtype_kwarg, sft_records
from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.registry import load_registry, model

ap = argparse.ArgumentParser()
ap.add_argument("--rung", default="medgemma-1.5-4b-it")
ap.add_argument("--epochs", type=float, default=1.0)
ap.add_argument("--lr", type=float, default=2e-4)
ap.add_argument("--rank", type=int, default=16)
ap.add_argument("--batch-size", type=int, default=2)
ap.add_argument("--grad-accum", type=int, default=8)
ap.add_argument("--max-train", type=int, default=None, help="cap training notes (Free Edition GPU quota)")
ap.add_argument("--out", default="runs/medgemma-lora")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

train = pd.read_csv(DATASETS_DIR / "train.csv")
if a.max_train:
    train = train.sample(n=min(a.max_train, len(train)), random_state=7)
recs = sft_records(train)
sft_path = DATASETS_DIR / "sft_reader_records.jsonl"
sft_path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
print(f"wrote {sft_path} ({len(recs)} records)")
if a.dry_run:
    raise SystemExit(0)

import torch
from datasets import Dataset
from peft import LoraConfig
from transformers import (
    AutoModelForCausalLM,
    AutoModelForImageTextToText,
    AutoProcessor,
    AutoTokenizer,
)
from trl import SFTConfig, SFTTrainer

m = model(load_registry(), a.rung)
kw = {**dtype_kwarg(torch.bfloat16), "device_map": "auto"}
if m.get("modality") == "multimodal":
    proc = AutoProcessor.from_pretrained(m["hf"])
    base = AutoModelForImageTextToText.from_pretrained(m["hf"], **kw)
    tok = proc.tokenizer
else:
    tok = proc = AutoTokenizer.from_pretrained(m["hf"])
    base = AutoModelForCausalLM.from_pretrained(m["hf"], **kw)

lora = LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05, bias="none",
                  target_modules="all-linear", task_type="CAUSAL_LM")
cfg = SFTConfig(output_dir=a.out, num_train_epochs=a.epochs, learning_rate=a.lr,
                per_device_train_batch_size=a.batch_size, gradient_accumulation_steps=a.grad_accum,
                bf16=True, logging_steps=10, save_strategy="no", report_to=[], seed=42,
                assistant_only_loss=False)
trainer = SFTTrainer(model=base, args=cfg, train_dataset=Dataset.from_list(recs),
                     processing_class=tok, peft_config=lora)
trainer.train()
trainer.model.save_pretrained(a.out)
print(f"saved LoRA adapter to {a.out}")
