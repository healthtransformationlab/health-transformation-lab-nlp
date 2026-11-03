"""Which note set a committed result was made on (#467).

A model's predictions are only comparable with the answer key of the review notes it read. When the benchmark notes
are rebuilt (spec 032 US8, #467: adults from the start date; spec 033 US3: published risk shares), results made on
the old notes are kept, not deleted, and not scored against the new answer key: they show as "rerun pending on the
new notes" until the run is redone.

    fingerprint      SHA-256 of the review notes (visit_id and note text, in visit order): the note set's identity
    current          the fingerprint of a folder's answer key (answer_key/review_key.csv)
    stamp            record the note set a result file was made on, in prediction_note_sets.csv (idempotent)
    is_current       a file was made on the current note set: its recorded fingerprint, or, with none recorded,
                     derived from the visits it holds (every review visit, and no other)
    prediction_files the current ai_predictions files, and the pending ones with where they came from

Every number is SYNTHETIC.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd

from .telemetry import traced

REGISTER = "prediction_note_sets.csv"
COLUMNS = ["file", "note_set_sha256"]
PATTERN = re.compile(r"^(ai_predictions|llm_details)_(.+)\.csv$")
JUDGE_FILE = "judge/judgments.csv"           # the real LLM judge run (spec 012), relative to the datasets folder
PENDING_FILE = "ladder_pending.csv"          # written next to ladder_vs_truth.csv by scripts/28_ladder_vs_truth.py
PENDING_COLUMNS = ["method_name", "file_name", "source_name", "run_url", "note_set_sha256", "current_note_set_sha256"]
RERUN_PENDING = "rerun pending on the new notes"


@traced
def fingerprint(key: pd.DataFrame) -> str:
    """SHA-256 of the review notes: one line per visit, `visit_id<TAB>note_text`, in visit_id order."""
    rows = key[["visit_id", "note_text"]].sort_values("visit_id")
    text = "".join(f"{int(v)}\t{t}\n" for v, t in zip(rows["visit_id"], rows["note_text"].fillna("")))
    return hashlib.sha256(text.encode()).hexdigest()


def _key_path(folder: Path) -> Path:
    return Path(folder) / "answer_key" / "review_key.csv"


@traced
def current(folder: Path) -> str:
    """The fingerprint of the folder's review notes."""
    return fingerprint(pd.read_csv(_key_path(folder), usecols=["visit_id", "note_text"]))


@traced
def read_register(folder: Path) -> pd.DataFrame:
    path = Path(folder) / REGISTER
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, dtype=str).fillna("")


@traced
def stamp(folder: Path, files, note_set_sha256: str | None = None) -> None:
    """Record that `files` (paths relative to `folder`) were made on `note_set_sha256` (default: the folder's
    current review notes). Replaces each file's earlier row, so stamping twice changes nothing."""
    files = [str(f) for f in files]
    fp = note_set_sha256 or current(folder)
    reg = read_register(folder)
    reg = reg[~reg["file"].isin(files)]
    out = pd.concat([reg, pd.DataFrame({"file": files, "note_set_sha256": fp})], ignore_index=True)
    out.sort_values("file").to_csv(Path(folder) / REGISTER, index=False)


@traced
def recorded(folder: Path, file: str) -> str | None:
    """The note set recorded for `file`, or None."""
    reg = read_register(folder).set_index("file")["note_set_sha256"]
    return reg.get(str(file)) or None


@traced
def is_current(folder: Path, file: str) -> bool:
    """`file` was made on the folder's current review notes. With no note set recorded, it counts as current when it
    holds exactly the review visits (a result written by a script that doesn't stamp), else as made on another."""
    fp = recorded(folder, file)
    if fp is not None:
        return fp == current(folder)
    ids = set(pd.read_csv(Path(folder) / file, usecols=["visit_id"])["visit_id"])
    return ids == set(pd.read_csv(_key_path(folder), usecols=["visit_id"])["visit_id"])


@traced
def prediction_files(folder: Path) -> tuple[list[Path], pd.DataFrame]:
    """(the ai_predictions_<method>.csv files made on the current notes, one row per file made on other notes:
    PENDING_COLUMNS). simulated_* dry runs are neither."""
    folder = Path(folder)
    now = current(folder)
    manifest_path = folder / "results_manifest.csv"
    manifest = (pd.read_csv(manifest_path, dtype=str).fillna("").set_index("file") if manifest_path.exists()
                else pd.DataFrame(columns=["source", "run_url"]))
    ok, pending = [], []
    for path in sorted(folder.glob("ai_predictions_*.csv")):
        if is_current(folder, path.name):
            ok.append(path)
            continue
        src = manifest.loc[path.name] if path.name in manifest.index else None
        pending.append({"method_name": path.stem.removeprefix("ai_predictions_"), "file_name": path.name,
                        "source_name": src["source"] if src is not None else "repo",
                        "run_url": src["run_url"] if src is not None else "",
                        "note_set_sha256": recorded(folder, path.name) or "unrecorded",
                        "current_note_set_sha256": now})
    return ok, pd.DataFrame(pending, columns=PENDING_COLUMNS)
