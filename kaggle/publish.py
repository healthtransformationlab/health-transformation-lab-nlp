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
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))

from health_transformation_lab_nlp import note_set
from health_transformation_lab_nlp.paths import DATASETS_DIR as DATA

sys.path.insert(0, str(HERE))
import dataset_docs as docs  # kaggle/dataset_docs.py: file and column descriptions, cover, sources (spec 034)

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
                "subtitle": "What rules, encoders and LLMs answered on synthetic dental review notes",
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


def meta_dir(out: Path) -> Path:
    """The folder beside a build that holds only its metadata and cover, for Kaggle's metadata update: the cover
    is never in the data folder, so it is never uploaded as a data file (spec 034)."""
    return out.parent / f"{out.name}-metadata"


# Create and version take a licence's short name; the metadata update refuses it ("You've specified an invalid
# license") and takes the full name `kaggle datasets metadata` shows.
LICENCE_FULL_NAMES = {"CC-BY-4.0": "Attribution 4.0 International (CC BY 4.0)"}


def for_metadata_update(meta: dict) -> dict:
    """meta with each licence under the name Kaggle's metadata update accepts."""
    return {**meta, "licenses": [{**l, "name": LICENCE_FULL_NAMES.get(l["name"], l["name"])}
                                 for l in meta.get("licenses", [])]}


def write_metadata(out: Path, meta: dict, slug: str) -> None:
    """dataset-metadata.json in the build, and the same with the cover in meta_dir(out), for the metadata update."""
    (out / "dataset-metadata.json").write_text(json.dumps(meta, indent=1) + "\n")
    side = meta_dir(out)
    if side.exists():
        shutil.rmtree(side)
    side.mkdir(parents=True)
    (side / "dataset-metadata.json").write_text(json.dumps(for_metadata_update(meta), indent=1) + "\n")
    shutil.copyfile(docs.cover(slug), side / "dataset-cover-image.png")


def build(name: str, out: Path, username: str, commit: str) -> dict:
    d = DATASETS[name]
    check(name)
    gaps = docs.missing(d["slug"], files_of(name))
    if gaps:   # AGENTS.md: every published file and column is described (spec 034)
        raise SystemExit(f"{len(gaps)} undescribed in kaggle/dataset_docs.yaml, e.g. {gaps[0]}")
    if out.exists():
        shutil.rmtree(out)
    for dest, src in files_of(name).items():
        (out / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out / dest)
    meta = {"title": d["title"], "subtitle": d["subtitle"], "id": f"{username}/{d['slug']}",
            "licenses": [{"name": "CC-BY-4.0"}], "keywords": d["keywords"], "description": card(name, commit),
            **docs.dataset(d["slug"]), "resources": docs.resources(d["slug"], files_of(name))}
    write_metadata(out, meta, d["slug"])
    return meta


def update_metadata(folder: Path, ref: str, api) -> None:
    """Send the description, file and column descriptions, sources, update frequency and cover; no data."""
    api.dataset_metadata_update(ref, str(meta_dir(folder)))
    print(f"metadata updated for {ref}: files, columns, cover, sources and update frequency")


def live_files(api, ref: str) -> set[str]:
    """The files the live dataset holds, from Kaggle's listing (paged)."""
    names, token = set(), None
    while True:
        page = api.dataset_list_files(ref, page_token=token, page_size=200)
        names |= {f.name for f in (page.files or [])}
        token = getattr(page, "next_page_token", None)
        if not token:
            return names


def metadata_only(out: Path, meta: dict, api) -> dict:
    """Send the metadata for the files the live dataset holds: Kaggle refuses a description of a file it doesn't
    have, so a file added since the last version waits for the next one. Returns what was sent."""
    live = live_files(api, meta["id"])
    sent = {**meta, "resources": [r for r in meta["resources"] if r["path"] in live]}
    waiting = sorted({r["path"] for r in meta["resources"]} - live)
    if waiting:
        print(f"not on Kaggle yet, described in the next version: {', '.join(waiting)}")
    write_metadata(out, sent, meta["id"].split("/", 1)[1])
    update_metadata(out, meta["id"], api)
    return sent


def wait_for_files(api, ref: str, paths: set[str], tries: int = 40, wait: float = 15, sleep=time.sleep) -> set[str]:
    """Wait (up to tries x wait seconds) until the live dataset lists every path: Kaggle processes a new version
    for a minute or two and lists the old files meanwhile (#602). Returns the paths still missing."""
    missing = set(paths)
    for i in range(tries):
        missing = set(paths) - live_files(api, ref)
        if not missing:
            break
        if i < tries - 1:
            sleep(wait)
    return missing


def upload(folder: Path, ref: str, message: str, api, sleep=time.sleep) -> str:
    """Create the dataset public, or add a version, then send its metadata; fail unless Kaggle answers ok.
    Returns its URL."""
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
    built = folder / "dataset-metadata.json"
    if built.exists():   # a version doesn't carry the cover or column descriptions (spec 034); wait for its files
        meta = json.loads(built.read_text())
        wait_for_files(api, ref, {r["path"] for r in meta.get("resources", [])}, sleep=sleep)
        metadata_only(folder, meta, api)   # describes the live files, naming any still processing
    else:
        update_metadata(folder, ref, api)
    return result.url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--username", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--upload", action="store_true", help="publish it (needs Kaggle credentials)")
    ap.add_argument("--message", default="Update from the repository")
    ap.add_argument("--metadata-only", action="store_true",
                    help="with --upload: send only the metadata and cover, no new version (spec 034)")
    a = ap.parse_args()
    meta = build(a.dataset, a.out, a.username, a.commit)
    print(f"prepared {meta['id']}: {len(files_of(a.dataset))} files at {a.commit[:12]}")
    if a.upload:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        if a.metadata_only:
            metadata_only(a.out, meta, api)
        else:
            upload(a.out, meta["id"], f"{a.message} ({a.commit[:12]})", api)


if __name__ == "__main__":
    main()
