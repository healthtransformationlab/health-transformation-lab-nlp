"""Build a Kaggle dataset folder (the files, and dataset-metadata.json with the card) and, with --upload,
publish it: created public the first time, a new version after (spec 020). Used by
.github/workflows/kaggle-publish.yml; CC BY 4.0.

    python kaggle/publish.py --dataset notes|results --out build/notes --username <kaggle user> --commit <sha>
        [--upload --message "Update from the repository"]

Files are listed here, or globbed inside named folders, never from the whole tree: nothing from data/external/
(others' datasets) or data/raw/, and no simulated_* file (dry runs would read as results). check() also refuses
a prediction file that isn't a full run (11_ai_predict.py --limit writes the same name) and any sim:/calib: row.
Uploads go through Kaggle's Python API, not the CLI: the CLI prints a refused upload and still exits 0.
"""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))

from health_transformation_lab_nlp import note_set
from health_transformation_lab_nlp.paths import DATASETS_DIR as DATA

REPO = HERE.parent
DATASETS = {
    "notes": {"slug": "perio-bench-notes", "title": "Synthetic Dental Periodontal Notes and Charts",
              "subtitle": "Synthetic dental chart notes labelled with 2017 AAP/EFP periodontal status",
              "keywords": ["nlp", "health", "medicine"],
              "files": [("train.csv", "train.csv"), ("visits_structured.csv", "visits_structured.csv"),
                        ("answer_key/review_key.csv", "review_key.csv"),
                        ("answer_key/visits_truth.csv", "visits_truth.csv"),
                        ("answer_key/clinic_profiles.csv", "clinic_profiles.csv"),
                        ("review_tasks.json", "review_tasks.json")]},
    "results": {"slug": "perio-bench-results", "title": "Dental Perio Note Classifier Benchmark",
                "subtitle": "What rules, encoders and LLMs answered on 240 synthetic dental review notes",
                "keywords": ["nlp", "health", "medicine"],
                "globs": [("", "ai_predictions_*.csv"), ("", "llm_details_*.csv"), ("ladder", "*.csv"),
                          ("judge", "*.csv")]},
}


def files_of(name: str) -> dict:
    """{path in the dataset: source file}, in a stable order. A result made on another note set (#467:
    prediction_note_sets.csv) is left out until its run is redone; ladder/ladder_pending.csv lists it."""
    d = DATASETS[name]
    out = {dest: DATA / src for src, dest in d.get("files", [])}
    stale = {f for f in note_set.read_register(DATA)["file"] if not note_set.is_current(DATA, f)}
    for folder, pattern in d.get("globs", []):
        for src in sorted((DATA / folder).glob(pattern)):
            rel = f"{folder}/{src.name}" if folder else src.name
            if not src.name.startswith("simulated_") and rel not in stale:
                out[rel] = src
    return out


def _rows(src: Path) -> str:
    if src.suffix == ".json":
        return f"{len(json.loads(src.read_text()))} items"
    with open(src, newline="") as f:
        return f"{sum(1 for _ in csv.reader(f)) - 1:,} rows"


def check(name: str) -> None:
    """Refuse what must never be published: a partial prediction file, or a simulated or calibration row."""
    with open(DATA / "answer_key" / "review_key.csv", newline="") as f:
        full = sum(1 for _ in csv.reader(f)) - 1          # a full run reads every review note
    for dest, src in files_of(name).items():
        if src.suffix != ".csv":
            continue
        with open(src, newline="") as f:
            rows = list(csv.reader(f))[1:]
        if Path(dest).name.startswith(("ai_predictions_", "llm_details_")) and len(rows) != full:
            raise SystemExit(f"{dest}: {len(rows)} rows, not a full run of {full} review notes")
        if any(v.startswith(("sim:", "calib:")) for r in rows for v in r):
            raise SystemExit(f"{dest}: holds simulated (sim:) or calibration (calib:) rows")


def card(name: str, commit: str) -> str:
    table = "\n".join(f"| `{dest}` | {_rows(src)} |" for dest, src in files_of(name).items())
    return ((HERE / "cards" / f"{name}.md").read_text().rstrip() + "\n\n## Contents\n\n| File | Size |\n|---|---|\n"
            + table + f"\n\nPublished from commit `{commit}` of the repository.\n")


def build(name: str, out: Path, username: str, commit: str) -> dict:
    d = DATASETS[name]
    check(name)
    if out.exists():
        shutil.rmtree(out)
    for dest, src in files_of(name).items():
        (out / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out / dest)
    meta = {"title": d["title"], "subtitle": d["subtitle"], "id": f"{username}/{d['slug']}",
            "licenses": [{"name": "CC-BY-4.0"}], "keywords": d["keywords"], "description": card(name, commit)}
    (out / "dataset-metadata.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def upload(folder: Path, ref: str, message: str, api) -> str:
    """Create the dataset public, or add a version; fail unless Kaggle answers ok. Returns its URL."""
    try:
        api.dataset_status(ref)
        exists = True
    except Exception:  # noqa: BLE001 - a missing dataset is an HTTP error here; any other failure resurfaces at create
        exists = False
    if exists:
        result = api.dataset_create_version(str(folder), message, dir_mode="zip")
    else:
        result = api.dataset_create_new(str(folder), public=True, dir_mode="zip")
    if result is None or str(result.status).lower() != "ok":
        raise SystemExit(f"Kaggle refused {ref}: {getattr(result, 'error', None) or 'see the output above'}")
    if result.invalidTags:
        print(f"Kaggle dropped tags it doesn't know: {result.invalidTags}")
    print(f"{'versioned' if exists else 'created'} {ref}: {result.url}")
    return result.url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--username", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--upload", action="store_true", help="publish it (needs Kaggle credentials)")
    ap.add_argument("--message", default="Update from the repository")
    a = ap.parse_args()
    meta = build(a.dataset, a.out, a.username, a.commit)
    print(f"prepared {meta['id']}: {len(files_of(a.dataset))} files at {a.commit[:12]}")
    if a.upload:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        upload(a.out, meta["id"], f"{a.message} ({a.commit[:12]})", api)


if __name__ == "__main__":
    main()
