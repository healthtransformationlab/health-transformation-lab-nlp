"""The model ladder. Each rung: fit(train_df) -> predict(test_df) -> (labels, proba|None).

note_rules           rules for clinical notes (note_reader.py): stated dx, else findings.
rules_baseline       regex for the short templated notes + the staging rules in labels.py.
                     On synthetic notes this is a strong baseline because the numbers
                     are usually in the text; that is a property of synthetic data and
                     the reason real notes are the real test.
structured_baseline  logistic regression on the chart numerics (not the text). Upper
                     bound for "what the chart knows".
tfidf_logreg         TF-IDF + logistic regression on the text. Cheapest text model.
<hf id>              any `classifier` / `long_context` model in models.yaml, fine-tuned
                     with a sequence-classification head via transformers.Trainer.
<llm id>             any `role: llm` model (MedGemma): zero-/few-shot note reader,
                     llm_reader.py (spec 004).
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from .labels import LABELS, PerioChart, label_chart
from .telemetry import traced

CHART_COLS = ["max_probing_depth_mm", "bop_pct", "max_cal_mm", "rbl_pct", "teeth_lost_perio"]


# ---------------------------------------------------------------- rules
_NUM = r"(\d+(?:\.\d+)?)"
_PATTERNS = {
    "pd": [rf"PD max {_NUM}", rf"probing depths up to {_NUM}", rf"deepest pocket {_NUM}"],
    "bop": [rf"BOP {_NUM}%", rf"bleeding at {_NUM}%"],
    "cal": [rf"CAL {_NUM}", rf"attachment loss {_NUM}"],
    "rbl": [rf"RBL ~?{_NUM}%", rf"{_NUM}% horizontal bone loss"],
    "lost": [rf"{_NUM} teeth previously lost"],
}
_NEG_BOP = re.compile(r"no BOP|BOP neg|no bleeding on probing", re.IGNORECASE)


def _find(text: str, key: str) -> float | None:
    for p in _PATTERNS[key]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


@traced
def rules_predict(text: str) -> str:
    bop = 0.0 if _NEG_BOP.search(text) else (_find(text, "bop") or 0.0)
    cal, rbl = _find(text, "cal"), _find(text, "rbl")
    if cal is None and rbl is None:
        rbl = 0.0
    chart = PerioChart(max_probing_depth_mm=_find(text, "pd") or 0.0, bop_pct=min(bop, 100),
                       max_cal_mm=cal, rbl_pct=None if rbl is None else min(rbl, 100),
                       teeth_lost_perio=int(_find(text, "lost") or 0))
    return label_chart(chart).value


class NoteRules:
    """Rules for clinical notes: stated diagnosis in any scheme, else findings (note_reader.py)."""

    @traced
    def fit(self, train: pd.DataFrame):
        return self

    @traced
    def predict(self, test: pd.DataFrame):
        from .note_reader import read_note
        return [read_note(t) for t in test["note_text"]], None


class RulesBaseline:
    @traced
    def fit(self, train: pd.DataFrame):
        return self

    @traced
    def predict(self, test: pd.DataFrame):
        return [rules_predict(t) for t in test["note_text"]], None


# ---------------------------------------------------------------- sklearn
class _SkWrap:
    def __init__(self, est, cols: str | list[str]):
        self.est, self.cols = est, cols

    @traced
    def fit(self, train):
        self.est.fit(train[self.cols], train["label"])
        return self

    @traced
    def predict(self, test):
        proba = self.est.predict_proba(test[self.cols])
        cls = list(self.est.classes_)
        full = np.zeros((len(test), len(LABELS)))  # align to LABEL order; absent classes stay 0
        for j, lab in enumerate(cls):
            full[:, LABELS.index(lab)] = proba[:, j]
        return [LABELS[i] for i in full.argmax(axis=1)], full


@traced
def structured_baseline():
    return _SkWrap(LogisticRegression(max_iter=2000), CHART_COLS)


@traced
def fusion_tfidf_rad():
    """Note text + structured radiograph features (spec 003). Visits without a
    radiograph get zeros plus rad_present = 0, so the model falls back to text."""
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import StandardScaler

    from .radiograph import FEATURES
    pre = ColumnTransformer([("text", TfidfVectorizer(ngram_range=(1, 2), min_df=2), "note_text"),
                             ("rad", StandardScaler(), FEATURES)])
    return _SkWrap(make_pipeline(pre, LogisticRegression(max_iter=3000)), ["note_text", *FEATURES])


@traced
def tfidf_logreg():
    return _SkWrap(make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=2),
                                 LogisticRegression(max_iter=2000)), "note_text")


# ---------------------------------------------------------------- transformers
def _last_checkpoint(out_dir) -> str | None:
    """Highest-step complete checkpoint-N folder in out_dir (has trainer_state.json), or None."""
    from pathlib import Path
    d = Path(out_dir)
    steps = [int(c.name.split("-")[1]) for c in d.glob("checkpoint-*")
             if c.name.split("-")[1].isdigit() and (c / "trainer_state.json").exists()] if d.is_dir() else []
    return str(d / f"checkpoint-{max(steps)}") if steps else None


def _clear_checkpoints(out_dir) -> None:
    """Drop checkpoints once a run finishes, so only an interrupted run is ever resumed."""
    import shutil
    from pathlib import Path
    for c in Path(out_dir).glob("checkpoint-*"):
        shutil.rmtree(c, ignore_errors=True)


@traced
def class_weights(labels, classes, power: float = 0.5) -> list[float]:
    """Inverse-frequency loss weights raised to `power` (0.5 = square root, gentler than fully
    balanced), scaled so the average weight over the training notes is 1. Absent classes get 0."""
    from collections import Counter
    n, counts = len(labels), Counter(labels)
    raw = [(n / counts[c]) ** power if counts[c] else 0.0 for c in classes]
    mean = sum(raw[classes.index(y)] for y in labels) / n
    return [w / mean for w in raw]


class HFEncoder:
    """Fine-tune a Hugging Face encoder. CPU works for the small models on a few
    hundred notes; set epochs/max_len down on Databricks Free Edition. grad_checkpoint recomputes
    activations in the backward pass instead of storing them: same training, less GPU memory, slower
    (the large encoders on Kaggle's 15 GB T4, #172)."""

    def __init__(self, hf_id: str, max_len: int = 256, epochs: int = 3, batch_size: int = 16,
                 lr: float = 5e-5, out_dir: str = "runs", class_weight: str | None = None, seed: int = 42,
                 grad_checkpoint: bool = False):
        self.hf_id, self.max_len, self.epochs = hf_id, max_len, epochs
        self.grad_checkpoint = grad_checkpoint
        self.batch_size, self.lr, self.out_dir = batch_size, lr, out_dir
        self.class_weight, self.seed = class_weight, seed       # class_weight: None or "sqrt"
        tag = (f"__cw-{class_weight}" if class_weight else "") + (f"__seed{seed}" if seed != 42 else "")
        self.run_dir = f"{out_dir}/{hf_id.replace('/', '__')}{tag}"

    def _ds(self, df):
        from datasets import Dataset
        d = Dataset.from_pandas(df[["note_text"]].assign(
            labels=[LABELS.index(x) for x in df["label"]] if "label" in df else 0))
        return d.map(lambda b: self.tok(b["note_text"], truncation=True, max_length=self.max_len,
                                        padding="max_length"), batched=True)

    @traced
    def training_kwargs(self) -> dict:
        return {"output_dir": self.run_dir, "num_train_epochs": self.epochs,
                "per_device_train_batch_size": self.batch_size, "learning_rate": self.lr, "logging_steps": 20,
                "save_strategy": "steps", "save_steps": 50, "save_total_limit": 1, "report_to": [],
                "seed": self.seed, "gradient_checkpointing": self.grad_checkpoint}

    @traced
    def fit(self, train):
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
        self.tok = AutoTokenizer.from_pretrained(self.hf_id)
        # float32 whatever the checkpoint stores (#226): transformers 5 loads a checkpoint in its own dtype, and
        # GatorTron's is float16; AdamW on float16 weights (no float32 copy) went NaN after one step.
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.hf_id, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)),
            label2id={l: i for i, l in enumerate(LABELS)}, ignore_mismatched_sizes=True).float()
        args = TrainingArguments(**self.training_kwargs())
        trainer_cls = Trainer
        if self.class_weight == "sqrt":
            import torch
            w = torch.tensor(class_weights(list(train["label"]), LABELS), dtype=torch.float)

            class _WeightedTrainer(Trainer):
                def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
                    labels = inputs.pop("labels")
                    out = model(**inputs)
                    loss = torch.nn.functional.cross_entropy(out.logits, labels, weight=w.to(out.logits.device))
                    return (loss, out) if return_outputs else loss
            trainer_cls = _WeightedTrainer
        elif self.class_weight:
            raise ValueError(f"unknown class_weight {self.class_weight!r}")
        self.trainer = trainer_cls(model=self.model, args=args, train_dataset=self._ds(train))
        self.trainer.train(resume_from_checkpoint=_last_checkpoint(args.output_dir))   # resume after a restart
        _clear_checkpoints(args.output_dir)
        return self

    @traced
    def predict(self, test):
        import torch
        logits = self.trainer.predict(self._ds(test)).predictions
        proba = torch.softmax(torch.tensor(logits), dim=-1).numpy()
        return [LABELS[i] for i in proba.argmax(axis=1)], proba

    @traced
    def save(self, path) -> None:
        """The fine-tuned model and its tokenizer in transformers format (config with the six labels, weights,
        tokenizer files), loadable with AutoModelForSequenceClassification.from_pretrained(path)."""
        self.model.save_pretrained(str(path))
        self.tok.save_pretrained(str(path))


@traced
def output_tag(class_weight: str | None = None, seed: int = 42, adapter: str | None = None,
               shots: int = 0, variant: str = "reader-v2", lr: float = 5e-5) -> str:
    """Suffix for a run's prediction file, so variants of one rung don't overwrite each other:
    +cw (class-weighted), +s<seed> (non-default seed), +lr<rate> (non-default learning rate),
    +lora (LoRA adapter), +k<shots> (few-shot), +<variant> (non-default prompt, minus 'reader-v2-')."""
    tag = ("+cw" if class_weight else "") + (f"+s{seed}" if seed != 42 else "") + (f"+lr{lr:g}" if lr != 5e-5 else "")
    tag += ("+lora" if adapter else "") + (f"+k{shots}" if shots else "")
    if variant != "reader-v2":
        tag += "+" + variant.removeprefix("reader-v2-")
    return tag


@traced
def make_rung(rung_id: str, registry: dict, **hf_kwargs):
    if rung_id == "rules_baseline":
        return RulesBaseline()
    if rung_id == "note_rules":
        return NoteRules()
    if rung_id == "structured_baseline":
        return structured_baseline()
    if rung_id == "tfidf_logreg":
        return tfidf_logreg()
    if rung_id == "fusion_tfidf_rad":
        return fusion_tfidf_rad()
    if rung_id == "llm_challenger":
        raise NotImplementedError("LLM rung runs on Databricks Model Serving; see databricks/notebooks")
    m = next((m for m in registry["models"] if m["id"] == rung_id), None)
    if m is None:
        raise KeyError(f"unknown rung {rung_id!r}")
    if m["role"] == "llm":
        from .llm_reader import LLMReader
        allowed = {"backend", "backend_kind", "shots", "variant", "seed", "adapter", "endpoint", "weights"}
        return LLMReader(rung_id, entry=m, **{k: v for k, v in hf_kwargs.items() if k in allowed})
    if m["role"] not in ("classifier", "long_context"):
        raise ValueError(f"{rung_id} has role {m['role']!r}; it is not a classifier rung")
    hf_kwargs.setdefault("max_len", min(m["max_len"], 256))
    return HFEncoder(m["hf"], **hf_kwargs)
