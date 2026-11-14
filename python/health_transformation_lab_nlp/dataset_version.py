"""One declared semantic version and changelog per published dataset (spec 039 US1, #707).

Each dataset in ``kaggle/dataset_docs.yaml`` declares, beside its files and columns:

- ``version``: ``MAJOR.MINOR.PATCH``;
- ``changelog``: one line per version, newest first, ``"X.Y.Z — what changed"``;
- ``schema_sha256``: the SHA-256 of its published file and column set, from ``kaggle/dataset_docs.py``'s
  ``schema_sha256``.

The semver rule:

- **MAJOR**: a breaking schema change: a column removed, renamed or retyped, or a file removed.
- **MINOR**: a new file or column.
- **PATCH**: values, rows or a fix, with no schema change.

``python/tests/test_kaggle_dataset_docs.py`` hashes what each dataset publishes and fails when the hash isn't the
declared ``schema_sha256``. So a file or column can't change without a new version, a changelog line and the new
hash, all in the same diff.

Every build also writes ``manifest.json`` into the dataset (spec 039 US2, #708), from the files it holds: the slug,
the version, the git commit, when it was built (UTC), and each file's SHA-256, size and, for CSV and JSONL, its row
count. Kaggle and Hugging Face get the same one, so a download can be checked against the commit that made it.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import yaml

from .paths import REPO_ROOT
from .telemetry import traced

DOCS = REPO_ROOT / "kaggle" / "dataset_docs.yaml"
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
LINE = re.compile(r"(\S+) — (\S.*)")
RULE = (
    "MAJOR for a removed, renamed or retyped column or a removed file; MINOR for a new file or column; "
    "PATCH for values, rows or a fix with no schema change"
)
MANIFEST = "manifest.json"
NOT_DATA = {MANIFEST, "dataset-metadata.json"}   # the manifest itself, and Kaggle's metadata for the upload
COMMIT = re.compile(r"[0-9a-f]{7,40}")
# The line every dataset card ends with, after the commit it was published from (#708).
MANIFEST_NOTE = (
    "`manifest.json` lists every file with its SHA-256, size and row count, with the dataset's version and this "
    "commit: check a download against it."
)


@cache
def _shipped() -> dict:
    return yaml.safe_load(DOCS.read_text())["datasets"]


def _entry(slug: str, docs: Path | None) -> dict:
    datasets = _shipped() if docs is None else (yaml.safe_load(Path(docs).read_text()) or {}).get("datasets") or {}
    if slug not in datasets:
        raise KeyError(f"{slug}: not in {Path(docs or DOCS).name}")
    return datasets[slug] or {}


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@traced
def version(slug: str, *, docs: Path | None = None) -> str:
    """The dataset's declared semantic version."""
    declared = _entry(slug, docs).get("version")
    if not declared:
        raise ValueError(f"{slug}: no version declared")
    return str(declared)


@traced
def changelog(slug: str, *, docs: Path | None = None) -> list[str]:
    """The dataset's changelog, one line per version, newest first."""
    return [" ".join(str(line).split()) for line in _entry(slug, docs).get("changelog") or []]


@traced
def latest_change(slug: str, *, docs: Path | None = None) -> str:
    """The newest changelog line: what the current version changed."""
    lines = changelog(slug, docs=docs)
    if not lines:
        raise ValueError(f"{slug}: no changelog")
    return lines[0]


@traced
def problems(slug: str, *, schema_sha256: str | None = None, docs: Path | None = None) -> list[str]:
    """What's wrong with the dataset's version declaration; empty when nothing is. Given ``schema_sha256``, the hash
    of what the dataset publishes now, it also reports a published set that changed without a new version."""
    try:
        entry = _entry(slug, docs)
    except KeyError as exc:
        return [str(exc.args[0])]
    found = []
    declared = str(entry.get("version") or "")
    if not declared:
        found.append(f'{slug}: no version; declare version: "1.0.0" and its changelog line')
    elif not SEMVER.fullmatch(declared):
        found.append(f"{slug}: version {declared!r} is not MAJOR.MINOR.PATCH")
    lines = changelog(slug, docs=docs)
    if not lines:
        found.append(f'{slug}: no changelog; add one line per version, newest first: "X.Y.Z — what changed"')
    versions = []
    for line in lines:
        match = LINE.fullmatch(line)
        if match and SEMVER.fullmatch(match.group(1)):
            versions.append(match.group(1))
        else:
            found.append(f'{slug}: changelog line {line!r} is not "X.Y.Z — what changed"')
    if versions and SEMVER.fullmatch(declared) and versions[0] != declared:
        found.append(
            f"{slug}: version is {declared} but the top changelog line is for {versions[0]}; "
            "a new version needs its own changelog line, at the top"
        )
    if any(_key(newer) <= _key(older) for newer, older in zip(versions, versions[1:])):
        found.append(f"{slug}: changelog versions must go newest first, each higher than the one below it")
    stored = str(entry.get("schema_sha256") or "")
    if schema_sha256 is not None and schema_sha256 != stored:
        found.append(
            f"{slug}: its published files or columns changed (schema_sha256 {stored or 'missing'}, now "
            f"{schema_sha256}). Bump version ({RULE}), add its changelog line at the top, and set schema_sha256 "
            f"to {schema_sha256}."
        )
    return found



def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_count(path: Path) -> int | None:
    """Rows in a CSV (records, header excluded) or a JSONL file (non-blank lines); None for any other file."""
    if path.suffix == ".csv":
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            return max(sum(1 for _ in csv.reader(f)) - 1, 0)
    if path.suffix == ".jsonl":
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for line in f if line.strip())
    return None


@traced
def build_manifest(folder: Path, slug: str, commit: str) -> dict:
    """The provenance of the files in ``folder``, as published: ``{slug, version, git_commit_sha, built_ts, files}``,
    with ``files`` mapping each path to ``{sha256, bytes}`` and, for CSV and JSONL, ``row_count``. The manifest
    itself and Kaggle's ``dataset-metadata.json`` aren't listed. ``commit`` must be a git SHA (7 to 40 hex
    characters): the workflow passes the commit it built."""
    if not COMMIT.fullmatch(commit or ""):
        raise ValueError(f"{commit!r} is not a git commit SHA (7 to 40 lowercase hex characters)")
    folder = Path(folder)
    files = {}
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        if rel in NOT_DATA:
            continue
        entry = {"sha256": _sha256(path), "bytes": path.stat().st_size}
        rows = _row_count(path)
        if rows is not None:
            entry["row_count"] = rows
        files[rel] = entry
    return {"slug": slug, "version": version(slug), "git_commit_sha": commit,
            "built_ts": datetime.now(UTC).isoformat(timespec="seconds"), "files": files}


@traced
def write_manifest(folder: Path, slug: str, commit: str) -> Path:
    """Write ``folder/manifest.json`` (``build_manifest``), replacing any earlier one, and return its path."""
    path = Path(folder) / MANIFEST
    path.write_text(json.dumps(build_manifest(folder, slug, commit), indent=1) + "\n")
    return path
