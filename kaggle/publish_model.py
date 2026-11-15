"""Build a Kaggle model folder from a fine-tuned encoder (the weights the encoder notebook keeps with SAVE_MODEL)
and, with --upload, publish it: the model created public the first time, its transformers instance the first time,
a new instance version after (spec 020 US3). Used by .github/workflows/kaggle-encoders.yml; Apache 2.0, the base
model's licence.

    python kaggle/publish_model.py --model-dir build/output/model \
        --predictions build/output/ai_predictions_modernbert-base+cw.csv --out build/kaggle-model \
        --username <kaggle user> --commit <sha the notebook trained> [--upload]

The card's scores come from --predictions, the review-set predictions of the same run that saved the weights.
build() refuses a partial or simulated prediction file and a folder that isn't this six-label classifier.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))

import pandas as pd
from health_transformation_lab_nlp import dataset_version as dv   # spec 039: the release note and the manifest
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.ladder_eval import by_difficulty, ladder_table
from health_transformation_lab_nlp.paths import DATASETS_DIR

MODEL = {"slug": "perio-bench-note-classifier", "title": "PerioBench Note Classifier",
         "subtitle": "Periodontal status from a dental chart note, fine-tuned on synthetic notes"}
INSTANCE = {"slug": "modernbert-base-cw", "base_url": "https://huggingface.co/answerdotai/ModernBERT-base"}
WEIGHTS = ("model.safetensors", "pytorch_model.bin")
REPO_URL = "https://github.com/healthtransformationlab/health-transformation-lab-nlp"
USAGE = """## Usage

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import kagglehub

path = kagglehub.model_download("{ref}/transformers/{instance}")
tok = AutoTokenizer.from_pretrained(path)
model = AutoModelForSequenceClassification.from_pretrained(path)
inputs = tok(note_text, truncation=True, max_length=256, return_tensors="pt")
status = model.config.id2label[model(**inputs).logits.argmax(-1).item()]
```

Input: one chart note, truncated to 256 tokens as in training. Output: one of the six labels
({labels}). Notes should be de-identified before they reach any model.
"""


def check_model(model_dir: Path) -> None:
    """A transformers sequence classifier with the six status labels, in order."""
    cfg = model_dir / "config.json"
    if not cfg.exists() or not any((model_dir / w).exists() for w in WEIGHTS):
        raise SystemExit(f"{model_dir}: not a transformers model folder (config.json and weights)")
    labels = json.loads(cfg.read_text()).get("id2label", {})
    if [labels.get(str(i), labels.get(i)) for i in range(len(labels))] != list(LABELS):
        raise SystemExit(f"{model_dir}: labels {list(labels.values())} are not the six statuses {list(LABELS)}")


def load_predictions(path: Path) -> pd.Series:
    """The run's review-set predictions, refused unless a full, real run."""
    if path.name.startswith("simulated_"):
        raise SystemExit(f"{path.name}: simulated predictions are never published as a model's scores")
    pred = pd.read_csv(path)
    key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv", usecols=["visit_id"])
    if len(pred) != len(key) or set(pred.visit_id) != set(key.visit_id):
        raise SystemExit(f"{path.name}: {len(pred)} rows, not a full run of {len(key)} review notes")
    if pred["pred"].astype(str).str.startswith(("sim:", "calib:")).any():
        raise SystemExit(f"{path.name}: holds simulated (sim:) or calibration (calib:) rows")
    return pred.set_index("visit_id")["pred"]


def scores(pred: pd.Series, name: str) -> str:
    """The card's results section, from the same scoring as the repo's leaderboard (ladder_eval)."""
    key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv").set_index("visit_id")
    n = len(key)
    row = ladder_table(key["truth_status"], {name: pred}, reference=name).iloc[0]
    diff = by_difficulty(key["truth_status"], {name: pred}, key["difficulty"]).set_index("difficulty")
    plain = {"L1": "states the 2017 diagnosis", "L2": "states it in older terms", "L3": "leaves it to the findings"}
    lines = [f"| {lev}: the note {plain.get(lev, lev)} | {int(r.n)} | {100 * r.accuracy:.1f} |"
             for lev, r in diff.iterrows()]
    return (f"## Results on the review set (synthetic, not clinical performance)\n\n"
            f"{n} synthetic review notes, scored against the generator's truth, from `{name}` of the same run.\n\n"
            f"- **Correct:** {100 * row.accuracy:.1f} per 100 (95% bootstrap CI {100 * row.acc_lo:.1f}-"
            f"{100 * row.acc_hi:.1f})\n"
            f"- **Unsafe errors** (could harm a patient if acted on, e.g. a missed stage 3-4): "
            f"{100 * row.unsafe_rate:.1f} per 100\n"
            f"- **Stage IV called stage IV:** {100 * row.stage4_recall:.0f}%. The model saw few stage IV notes in "
            f"training; the repo's leaderboard pairs it with a keyword rule for stage IV (`+rules4`).\n\n"
            "| Difficulty | Notes | Correct per 100 |\n|---|---:|---:|\n" + "\n".join(lines) + "\n")


def build(model_dir: Path, predictions: Path, out: Path, username: str, commit: str) -> tuple[dict, dict]:
    """The folder `publish` uploads: the model files, model-metadata.json and model-instance-metadata.json."""
    check_model(model_dir)
    pred = load_predictions(predictions)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in sorted(model_dir.iterdir()):
        if f.is_file():
            shutil.copyfile(f, out / f.name)
    card = (HERE / "cards" / "model.md").read_text().rstrip() + "\n\n" + scores(pred, predictions.name)
    card += f"\nTrained from commit `{commit}` of [the repository]({REPO_URL}).\n"
    meta = {"ownerSlug": username, "title": MODEL["title"], "slug": MODEL["slug"], "subtitle": MODEL["subtitle"],
            "isPrivate": False, "description": card, "publishTime": "", "provenanceSources": ""}
    inst = {"ownerSlug": username, "modelSlug": MODEL["slug"], "instanceSlug": INSTANCE["slug"],
            "framework": "transformers", "overview": card,
            "usage": USAGE.format(ref=f"{username}/{MODEL['slug']}", instance=INSTANCE["slug"],
                                  labels=", ".join(f"`{lab}`" for lab in LABELS)),
            "licenseName": "Apache 2.0", "fineTunable": True, "trainingData": [],
            "modelInstanceType": "ExternalVariant", "externalBaseModelUrl": INSTANCE["base_url"]}
    (out / "model-metadata.json").write_text(json.dumps(meta, indent=1) + "\n")
    (out / "model-instance-metadata.json").write_text(json.dumps(inst, indent=1) + "\n")
    dv.write_manifest(out, MODEL["slug"], commit)   # spec 039 (#730): the model files' provenance, inside the folder
    return meta, inst


def _ok(resp, what: str):
    if resp is None or getattr(resp, "error", None):
        raise SystemExit(f"Kaggle refused {what}: {getattr(resp, 'error', None) or 'no answer'}")
    return resp


def upload(folder: Path, model_ref: str, instance_slug: str, notes: str, api) -> str:
    """Create the model (public) and its transformers instance, or add an instance version. Returns the URL."""
    try:
        api.model_get(model_ref)
        model_exists = True
    except Exception:  # noqa: BLE001 - a missing model is an HTTP error here; another failure resurfaces below
        model_exists = False
    if model_exists:            # a version sends files only: the card (scores, commit) is updated separately
        _ok(api.model_update(str(folder)), model_ref)
    else:
        _ok(api.model_create_new(str(folder)), model_ref)
        print(f"created {model_ref}")
    ref = f"{model_ref}/transformers/{instance_slug}"
    try:
        api.model_instance_get(ref)
        exists = True
    except Exception:  # noqa: BLE001
        exists = False
    if exists:
        _ok(api.model_instance_update(str(folder)), ref)
        resp = _ok(api.model_instance_version_create(ref, str(folder), notes, dir_mode="zip"), ref)
    else:
        resp = _ok(api.model_instance_create(str(folder), dir_mode="zip"), ref)
    print(f"{'versioned' if exists else 'created'} {ref}: {resp.url}")
    return resp.url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True, type=Path)
    ap.add_argument("--predictions", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--username", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--upload", action="store_true", help="publish it (needs Kaggle credentials)")
    a = ap.parse_args()
    meta, inst = build(a.model_dir, a.predictions, a.out, a.username, a.commit)
    print(f"prepared {a.username}/{meta['slug']}/transformers/{inst['instanceSlug']} at {a.commit[:12]}")
    if a.upload:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        note = dv.release_message(MODEL["slug"], a.commit)   # spec 039 (#730): the version note from the changelog
        print(f"release: {note}")
        upload(a.out, f"{a.username}/{meta['slug']}", inst["instanceSlug"], note, api)


if __name__ == "__main__":
    main()
