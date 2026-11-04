"""What every file and column of our Kaggle datasets holds, from kaggle/dataset_docs.yaml (spec 034 US1, #533).

    dataset(slug)          the dataset's metadata fields: userSpecifiedSources, expectedUpdateFrequency
    cover(slug)            its cover image, kaggle/covers/<slug>.png (drawn by kaggle/make_covers.py)
    resources(slug, files) Kaggle's `resources`: each file's path and description, and a schema with each
                           column's description for CSV and JSONL files ({path in dataset: source file})
    missing(slug, files)   what has no description; python/tests/test_kaggle_dataset_docs.py wants it empty

Columns are read from a CSV's header or a JSONL file's first row. Kaggle shows these on the dataset's Data tab and
counts them in its usability score.
"""

from __future__ import annotations

import csv
import fnmatch
import json
from functools import lru_cache
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DOCS = HERE / "dataset_docs.yaml"
COVERS = HERE / "covers"
# Kaggle's accepted values (kaggle datasets metadata), "not specified" being what it scores as missing.
UPDATE_FREQUENCIES = ("not specified", "never", "annually", "quarterly", "monthly", "weekly", "daily", "hourly")


@lru_cache(maxsize=1)
def _docs() -> dict:
    return yaml.safe_load(DOCS.read_text())


def _entry(slug: str) -> dict:
    try:
        return _docs()["datasets"][slug]
    except KeyError:
        raise SystemExit(f"{slug}: not in {DOCS.name}; add its sources, update frequency and file descriptions")


def dataset(slug: str) -> dict:
    e = _entry(slug)
    freq = e["update_frequency"]
    if freq not in UPDATE_FREQUENCIES:
        raise SystemExit(f"{slug}: update_frequency {freq!r} is not one of {', '.join(UPDATE_FREQUENCIES)}")
    return {"userSpecifiedSources": " ".join(e["sources"].split()), "expectedUpdateFrequency": freq}


def cover(slug: str) -> Path:
    return COVERS / f"{slug}.png"


def file_description(slug: str, dest: str) -> str | None:
    files = _entry(slug)["files"]
    if dest in files:
        return " ".join(files[dest].split())
    hit = next((d for pat, d in files.items() if fnmatch.fnmatchcase(dest, pat)), None)
    return " ".join(hit.split()) if hit else None


def columns_of(src: Path) -> list[str]:
    if src.suffix == ".csv":
        with open(src, newline="") as f:
            return next(csv.reader(f), [])
    if src.suffix == ".jsonl":
        with open(src) as f:
            first = next((line for line in f if line.strip()), "")
        return list(json.loads(first)) if first else []
    return []


def column_description(slug: str, dest: str, column: str) -> str | None:
    """A file's own description of the column first (file_columns, where a shared name means something else in
    that file), then the shared one, then the file's other_columns."""
    for pattern, cols in (_entry(slug).get("file_columns") or {}).items():
        if fnmatch.fnmatchcase(dest, pattern) and column in (cols or {}):
            return " ".join(str(cols[column]).split())
    shared = _docs()["columns"].get(column)
    if shared:
        return " ".join(str(shared).split())
    other = (_entry(slug).get("other_columns") or {}).get(dest)
    return " ".join(other.split()) if other else None


def resources(slug: str, files: dict) -> list[dict]:
    out = []
    for dest, src in files.items():
        r = {"path": dest, "description": file_description(slug, dest) or ""}
        cols = columns_of(Path(src))
        if cols:
            r["schema"] = {"fields": [{"name": c, "description": column_description(slug, dest, c) or ""}
                                      for c in cols]}
        out.append(r)
    return out


def missing(slug: str, files: dict) -> list[str]:
    gaps = []
    for dest, src in files.items():
        if not file_description(slug, dest):
            gaps.append(f"{dest}: no file description")
        gaps += [f"{dest}: column {c} has no description" for c in columns_of(Path(src))
                 if not column_description(slug, dest, c)]
    return gaps
