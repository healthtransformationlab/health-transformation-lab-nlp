"""Fine-tune an encoder to tag Age, Sex and Date in MACCROBAT case reports (spec 010).

    python scripts/33_maccrobat_phi_tagger.py                          # Longformer, default settings
    python scripts/33_maccrobat_phi_tagger.py --lr 5e-5 --epochs 6 --tag lr5e-5_e6
    python scripts/33_maccrobat_phi_tagger.py --conll-dir ../data/external/maccrobat/course --tag course_lr5e-5_e3 --lr 5e-5

Notes are split 80:20 (seeded) into train and test; 20 training notes are held out as a validation
set, so settings and regex sets are chosen on validation and the test set is read once at the end.
Writes:
  data/external/maccrobat/bio/{train,val,test}.txt   BIO files (public, CC BY 4.0: committed)
  python/runs/phi_tagger/<tag>/pred.json        word tags, gold and predicted, for val and test (git-ignored)
  data/deid/maccrobat_tagger_runs.csv           one row per run: settings, val and test F1 per type
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from health_transformation_lab_nlp import maccrobat, phi_tagger
from health_transformation_lab_nlp.paths import DEID_DIR, EXTERNAL_DIR, REPO_ROOT
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("33_maccrobat_phi_tagger", data_label="public")

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="allenai/longformer-base-4096")
ap.add_argument("--lr", type=float, default=3e-5)
ap.add_argument("--epochs", type=float, default=3)
ap.add_argument("--batch-size", type=int, default=4)
ap.add_argument("--weight-decay", type=float, default=0.0)
ap.add_argument("--warmup", type=float, default=0.0, help="warm-up share of the training steps")
ap.add_argument("--max-words", type=int, default=250, help="words per chunk (whole sentences packed)")
ap.add_argument("--max-length", type=int, default=1024, help="sub-tokens per chunk after tokenizing")
ap.add_argument("--seed", type=int, default=42, help="training seed")
ap.add_argument("--split-seed", type=int, default=42)
ap.add_argument("--n-val", type=int, default=20)
ap.add_argument("--zip", default=str(EXTERNAL_DIR / "maccrobat" / "MACCROBAT2020.zip"))
ap.add_argument("--conll-dir", default=None,
                help="use a course's own train.txt / test.txt (word POS tag) instead of rebuilding from brat; "
                     "n-val notes of its train file are held out for validation")
ap.add_argument("--tag", default=None)
a = ap.parse_args()
tag = a.tag or f"{a.model.split('/')[-1]}_lr{a.lr:g}_e{a.epochs:g}_bs{a.batch_size}_wd{a.weight_decay:g}_s{a.seed}"

import torch
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
    set_seed,
)

if a.conll_dir:
    course_train = phi_tagger.read_conll(Path(a.conll_dir) / "train.txt")
    course_test = phi_tagger.read_conll(Path(a.conll_dir) / "test.txt")
    docs = {d["note_id"]: d for d in course_train + course_test}
    ids = [d["note_id"] for d in course_train]
    val_ids = phi_tagger.split_docs(ids, a.n_val / len(ids), a.split_seed)[1]
    train_ids = [i for i in ids if i not in set(val_ids)]
    test_ids = [d["note_id"] for d in course_test]
else:
    docs = {d["note_id"]: d for d in phi_tagger.bio_docs(maccrobat.load_brat(a.zip))}
    train_ids, val_ids, test_ids = phi_tagger.three_way_split(list(docs), 0.2, a.n_val, a.split_seed)
    bio_dir = EXTERNAL_DIR / "maccrobat" / "bio"
    bio_dir.mkdir(parents=True, exist_ok=True)
    for name, ids in (("train", train_ids), ("val", val_ids), ("test", test_ids)):
        phi_tagger.write_conll([docs[i] for i in ids], bio_dir / f"{name}.txt")
print(f"notes: train {len(train_ids)}, val {len(val_ids)}, test {len(test_ids)}")

set_seed(a.seed)
label2id = {t: i for i, t in enumerate(phi_tagger.LABELS)}
tok = AutoTokenizer.from_pretrained(a.model, add_prefix_space=True)
model = AutoModelForTokenClassification.from_pretrained(
    a.model, num_labels=len(label2id), id2label=dict(enumerate(phi_tagger.LABELS)), label2id=label2id)


def encode(ids):
    out = []
    for i in ids:
        d = docs[i]
        for s, e in phi_tagger.chunks(d, a.max_words):
            enc = tok(d["words"][s:e], is_split_into_words=True, truncation=True, max_length=a.max_length)
            enc["labels"] = phi_tagger.align(enc.word_ids(), d["tags"][s:e], label2id)
            out.append(dict(enc))
    return out


train = encode(train_ids)
out_dir = REPO_ROOT / "python" / "runs" / "phi_tagger" / tag
args = TrainingArguments(output_dir=str(out_dir), learning_rate=a.lr, num_train_epochs=a.epochs,
                         per_device_train_batch_size=a.batch_size, weight_decay=a.weight_decay,
                         warmup_steps=a.warmup, seed=a.seed, save_strategy="no", logging_steps=20,
                         report_to=[], use_cpu=not torch.cuda.is_available())
t0 = time.time()
Trainer(model=model, args=args, train_dataset=train,
        data_collator=DataCollatorForTokenClassification(tok)).train()
minutes = (time.time() - t0) / 60


def predict(ids):
    model.eval()
    preds = {}
    for i in ids:
        d = docs[i]
        tags = []
        for s, e in phi_tagger.chunks(d, a.max_words):
            enc = tok(d["words"][s:e], is_split_into_words=True, truncation=True, max_length=a.max_length,
                      return_tensors="pt")
            with torch.no_grad():
                logits = model(**enc.to(model.device)).logits[0].float().cpu().numpy()
            tags += phi_tagger.word_tags(enc.word_ids(), np.argmax(logits, axis=-1), e - s)
        preds[i] = tags
    return preds


row = {"tag": tag, "data": "course" if a.conll_dir else "rebuilt", "model": a.model, "lr": a.lr, "epochs": a.epochs, "batch_size": a.batch_size,
       "weight_decay": a.weight_decay, "warmup": a.warmup, "max_words": a.max_words, "seed": a.seed,
       "split_seed": a.split_seed, "train_minutes": round(minutes, 1)}
saved = {}
for name, ids in (("val", val_ids), ("test", test_ids)):
    pred = predict(ids)
    saved[name] = {i: {"gold": docs[i]["tags"], "pred": pred[i]} for i in ids}
    s = phi_tagger.score([docs[i]["tags"] for i in ids], [pred[i] for i in ids]).set_index("type")
    for t in (*phi_tagger.TYPES, "weighted"):
        row[f"{name}_f1_{t}"] = round(float(s.loc[t, "f1"]), 4)
    print(name, s.round(3).to_string())
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "pred.json").write_text(json.dumps(saved))
runs = DEID_DIR / "maccrobat_tagger_runs.csv"
old = pd.read_csv(runs) if runs.exists() else pd.DataFrame()
old = old[old.tag != tag] if len(old) else old
pd.concat([old, pd.DataFrame([row])], ignore_index=True).to_csv(runs, index=False)
print(f"{tag}: val weighted F1 {row['val_f1_weighted']}, {minutes:.1f} min; wrote {runs}")
